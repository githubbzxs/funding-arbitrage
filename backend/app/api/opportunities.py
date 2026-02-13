from fastapi import APIRouter, Query

from app.models.schemas import OpportunitiesResponse
from app.services.arbitrage import scan_opportunities
from app.services.container import market_data_service


router = APIRouter(prefix="/api", tags=["opportunities"])


@router.get("/opportunities", response_model=OpportunitiesResponse)
async def get_opportunities(
    limit: int = Query(default=100, ge=1, le=5000),
    min_spread_rate_1y_nominal: float = Query(default=0.0),
) -> OpportunitiesResponse:
    """扫描同币种跨交易所套利机会。"""

    snapshots = await market_data_service.fetch_snapshots()
    opportunities = scan_opportunities(
        snapshots=snapshots.snapshots,
        min_spread_rate_1y_nominal=min_spread_rate_1y_nominal,
    )
    selected = opportunities[:limit]
    return OpportunitiesResponse(
        total=len(selected),
        opportunities=selected,
        errors=snapshots.errors,
    )

