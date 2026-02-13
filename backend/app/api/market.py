from fastapi import APIRouter

from app.models.schemas import MarketSnapshotsResponse
from app.services.container import market_data_service


router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/snapshots", response_model=MarketSnapshotsResponse)
async def get_market_snapshots() -> MarketSnapshotsResponse:
    """获取 5 所统一市场快照。"""

    return await market_data_service.fetch_snapshots()

