from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.orm import Order, Position
from app.models.schemas import OrderRead, OrdersResponse, PositionRead, PositionsResponse


router = APIRouter(prefix="/api", tags=["records"])


@router.get("/positions", response_model=PositionsResponse)
async def list_positions(
    limit: int = Query(default=200, ge=1, le=2000),
    status: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> PositionsResponse:
    """查询仓位列表。"""

    stmt = select(Position).order_by(Position.created_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(Position.status == status)
    rows = list((await session.scalars(stmt)).all())
    return PositionsResponse(total=len(rows), items=[PositionRead.model_validate(row) for row in rows])


@router.get("/orders", response_model=OrdersResponse)
async def list_orders(
    limit: int = Query(default=500, ge=1, le=5000),
    action: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> OrdersResponse:
    """查询订单列表。"""

    stmt = select(Order).order_by(Order.created_at.desc()).limit(limit)
    if action:
        stmt = stmt.where(Order.action == action)
    rows = list((await session.scalars(stmt)).all())
    return OrdersResponse(total=len(rows), items=[OrderRead.model_validate(row) for row in rows])

