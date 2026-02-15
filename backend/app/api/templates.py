from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.orm import StrategyTemplate
from app.models.schemas import StrategyTemplateCreate, StrategyTemplateRead, StrategyTemplatesResponse, StrategyTemplateUpdate


router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("", response_model=StrategyTemplatesResponse)
@router.get("/", response_model=StrategyTemplatesResponse)
async def list_templates(
    limit: int = Query(default=200, ge=1, le=2000),
    session: AsyncSession = Depends(get_db_session),
) -> StrategyTemplatesResponse:
    """查询策略模板列表。"""

    stmt = select(StrategyTemplate).order_by(StrategyTemplate.updated_at.desc()).limit(limit)
    rows = list((await session.scalars(stmt)).all())
    return StrategyTemplatesResponse(total=len(rows), items=[StrategyTemplateRead.model_validate(row) for row in rows])


@router.post("", response_model=StrategyTemplateRead)
@router.post("/", response_model=StrategyTemplateRead)
async def create_template(
    request: StrategyTemplateCreate,
    session: AsyncSession = Depends(get_db_session),
) -> StrategyTemplateRead:
    """创建策略模板。"""

    existing = await session.scalar(select(StrategyTemplate).where(StrategyTemplate.name == request.name))
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"模板名称已存在: {request.name}")

    row = StrategyTemplate(
        name=request.name,
        symbol=request.symbol,
        long_exchange=request.long_exchange,
        short_exchange=request.short_exchange,
        mode=request.mode.value,
        quantity=request.quantity,
        notional_usd=request.notional_usd,
        leverage=request.leverage,
        hold_hours=request.hold_hours,
        note=request.note,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return StrategyTemplateRead.model_validate(row)


@router.put("/{template_id}", response_model=StrategyTemplateRead)
async def update_template(
    template_id: str,
    request: StrategyTemplateUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> StrategyTemplateRead:
    """更新策略模板。"""

    row = await session.get(StrategyTemplate, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"模板不存在: {template_id}")

    payload = request.model_dump(exclude_unset=True)
    if "mode" in payload and payload["mode"] is not None:
        payload["mode"] = payload["mode"].value

    if "name" in payload:
        existing = await session.scalar(
            select(StrategyTemplate).where(StrategyTemplate.name == payload["name"], StrategyTemplate.id != template_id)
        )
        if existing is not None:
            raise HTTPException(status_code=409, detail=f"模板名称已存在: {payload['name']}")

    for key, value in payload.items():
        setattr(row, key, value)

    await session.commit()
    await session.refresh(row)
    return StrategyTemplateRead.model_validate(row)


@router.delete("/{template_id}")
async def delete_template(
    template_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, bool]:
    """删除策略模板。"""

    row = await session.get(StrategyTemplate, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"模板不存在: {template_id}")
    await session.delete(row)
    await session.commit()
    return {"success": True}
