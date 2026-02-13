from collections.abc import Iterable
from typing import Any

from app.models.schemas import (
    MarketBoardResponse,
    MarketSnapshot,
    OpportunityBoardLeg,
    OpportunityBoardRow,
    SupportedExchange,
)
from app.services.arbitrage import scan_opportunities
from app.services.market_data import MarketDataService


def _build_snapshot_index(
    snapshots: list[MarketSnapshot],
) -> dict[tuple[str, SupportedExchange], MarketSnapshot]:
    """基于 symbol + exchange 建立快照索引，便于机会结果回查双腿详情。"""

    index: dict[tuple[str, SupportedExchange], MarketSnapshot] = {}
    for snapshot in snapshots:
        index[(snapshot.symbol, snapshot.exchange)] = snapshot
    return index


def _to_board_leg(snapshot: MarketSnapshot) -> OpportunityBoardLeg:
    return OpportunityBoardLeg(
        funding_rate_raw=snapshot.funding_rate_raw,
        rate_1h=snapshot.rate_1h,
        rate_8h=snapshot.rate_8h,
        rate_1y=snapshot.rate_1y,
        next_funding_time=snapshot.next_funding_time,
        max_leverage=snapshot.max_leverage,
        leveraged_nominal_rate_1y=snapshot.leveraged_nominal_rate_1y,
        open_interest_usd=snapshot.oi_usd,
        volume24h_usd=snapshot.vol24h_usd,
        settlement_interval=snapshot.funding_interval_hours,
    )


def _calc_spread(short_rate: float | None, long_rate: float | None) -> float | None:
    if short_rate is None or long_rate is None:
        return None
    return short_rate - long_rate


def _board_sort_key(row: OpportunityBoardRow) -> tuple[int, float, float]:
    leveraged_spread = row.leveraged_spread_rate_1y_nominal
    if leveraged_spread is not None:
        return (1, leveraged_spread, row.spread_rate_1y_nominal)
    return (0, row.spread_rate_1y_nominal, row.spread_rate_1y_nominal)


def build_board_rows_from_snapshots(
    snapshots: list[MarketSnapshot],
    *,
    limit: int = 500,
    min_spread_rate_1y_nominal: float = 0.0,
    exchanges: Iterable[SupportedExchange] | None = None,
) -> list[OpportunityBoardRow]:
    """将市场快照转换成前端可直渲染的 board 行。"""

    if limit <= 0:
        return []

    snapshot_index = _build_snapshot_index(snapshots)
    exchange_filter = set(exchanges) if exchanges else None
    opportunities = scan_opportunities(
        snapshots=snapshots,
        min_spread_rate_1y_nominal=min_spread_rate_1y_nominal,
    )

    rows: list[OpportunityBoardRow] = []
    for item in opportunities:
        if exchange_filter and item.long_exchange not in exchange_filter and item.short_exchange not in exchange_filter:
            continue

        long_snapshot = snapshot_index.get((item.symbol, item.long_exchange))
        short_snapshot = snapshot_index.get((item.symbol, item.short_exchange))
        if long_snapshot is None or short_snapshot is None:
            continue

        rows.append(
            OpportunityBoardRow(
                symbol=item.symbol,
                long_exchange=item.long_exchange,
                short_exchange=item.short_exchange,
                long_leg=_to_board_leg(long_snapshot),
                short_leg=_to_board_leg(short_snapshot),
                spread_rate_1h=_calc_spread(short_snapshot.rate_1h, long_snapshot.rate_1h),
                spread_rate_8h=_calc_spread(short_snapshot.rate_8h, long_snapshot.rate_8h),
                spread_rate_1y_nominal=item.spread_rate_1y_nominal,
                leveraged_spread_rate_1y_nominal=item.leveraged_spread_rate_1y_nominal,
                max_usable_leverage=item.max_usable_leverage,
            )
        )

    rows.sort(key=_board_sort_key, reverse=True)
    return rows[:limit]


async def build_market_board_response(
    market_data_service: MarketDataService,
    *,
    limit: int = 500,
    min_spread_rate_1y_nominal: float = 0.0,
    force_refresh: bool = False,
    exchanges: Iterable[SupportedExchange] | None = None,
) -> MarketBoardResponse:
    """生成 /api/market/board 聚合响应。"""

    snapshots_response = await market_data_service.fetch_snapshots(force_refresh=force_refresh)
    exchange_filter = set(exchanges) if exchanges else None
    rows = build_board_rows_from_snapshots(
        snapshots=snapshots_response.snapshots,
        limit=limit,
        min_spread_rate_1y_nominal=min_spread_rate_1y_nominal,
        exchanges=exchange_filter,
    )

    meta: dict[str, Any] = dict(snapshots_response.meta or {})
    meta["board_sort"] = "leveraged_spread_rate_1y_nominal_desc_then_spread_rate_1y_nominal_desc"
    meta["board_limit"] = limit
    meta["board_min_spread_rate_1y_nominal"] = min_spread_rate_1y_nominal
    if exchange_filter:
        meta["board_exchanges_filter"] = sorted(exchange_filter)

    return MarketBoardResponse(
        as_of=snapshots_response.as_of,
        total=len(rows),
        rows=rows,
        errors=snapshots_response.errors,
        meta=meta,
    )
