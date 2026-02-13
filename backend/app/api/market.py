from fastapi import APIRouter, Query

from app.models.schemas import MarketBoardResponse, MarketSnapshotsResponse, SupportedExchange
from app.services.container import market_data_service
from app.services.market_board import build_market_board_response


router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/snapshots", response_model=MarketSnapshotsResponse)
async def get_market_snapshots(
    force_refresh: bool = Query(default=False, description="是否跳过缓存强制刷新"),
) -> MarketSnapshotsResponse:
    """获取 5 所统一市场快照。"""

    return await market_data_service.fetch_snapshots(force_refresh=force_refresh)


@router.get("/board", response_model=MarketBoardResponse)
async def get_market_board(
    limit: int = Query(default=500, ge=1, le=5000),
    min_spread_rate_1y_nominal: float = Query(default=0.0),
    force_refresh: bool = Query(default=False, description="是否跳过缓存强制刷新"),
    exchanges: list[SupportedExchange] | None = Query(default=None, description="交易所过滤，可多选"),
    symbol: str | None = Query(default=None, description="币对过滤，例如 BTCUSDT"),
) -> MarketBoardResponse:
    """获取前端可直接渲染的套利看板数据。"""

    return await build_market_board_response(
        market_data_service=market_data_service,
        limit=limit,
        min_spread_rate_1y_nominal=min_spread_rate_1y_nominal,
        force_refresh=force_refresh,
        exchanges=exchanges,
        symbol=symbol,
    )
