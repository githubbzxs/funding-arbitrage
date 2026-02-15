from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.orm import RiskEvent
from app.models.schemas import RiskEventRead, RiskEventsResponse


router = APIRouter(prefix="/api", tags=["risk-events"])


@router.get("/risk-events", response_model=RiskEventsResponse)
async def list_risk_events(
    limit: int = Query(default=200, ge=1, le=2000),
    resolved: bool | None = Query(default=None),
    severity: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> RiskEventsResponse:
    """查询风险事件列表。"""

    stmt = select(RiskEvent).order_by(RiskEvent.created_at.desc()).limit(limit)
    if resolved is not None:
        stmt = stmt.where(RiskEvent.resolved == resolved)
    if severity:
        stmt = stmt.where(RiskEvent.severity == severity)

    rows = list((await session.scalars(stmt)).all())
    return RiskEventsResponse(total=len(rows), items=[RiskEventRead.model_validate(row) for row in rows])


@router.post("/risk-events/{event_id}/resolve", response_model=RiskEventRead)
async def resolve_risk_event(
    event_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> RiskEventRead:
    """标记风险事件已处理。"""

    row = await session.get(RiskEvent, event_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"风险事件不存在: {event_id}")
    row.resolved = True
    await session.commit()
    await session.refresh(row)
    return RiskEventRead.model_validate(row)
