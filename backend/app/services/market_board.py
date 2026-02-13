from collections.abc import Iterable
from typing import Any, Literal

from app.models.schemas import MarketBoardResponse, MarketSnapshot, OpportunityBoardLeg, OpportunityBoardRow, SupportedExchange
from app.services.arbitrage import scan_opportunities
from app.services.market_data import MarketDataService


def _build_snapshot_index(snapshots: list[MarketSnapshot]) -> dict[tuple[str, SupportedExchange], MarketSnapshot]:
    """基于 symbol + exchange 建立快照索引，便于机会结果回查双腿详情。"""

    index: dict[tuple[str, SupportedExchange], MarketSnapshot] = {}
    for snapshot in snapshots:
        index[(snapshot.symbol, snapshot.exchange)] = snapshot
    return index


def _format_interval(hours: float | None) -> str:
    if hours is None or hours <= 0:
        return "-"
    if float(hours).is_integer():
        return f"{int(hours)}h"
    return f"{hours}h"


def _to_board_leg(snapshot: MarketSnapshot) -> OpportunityBoardLeg:
    return OpportunityBoardLeg(
        exchange=snapshot.exchange,
        funding_rate_raw=snapshot.funding_rate_raw,
        rate_1h=snapshot.rate_1h,
        rate_8h=snapshot.rate_8h,
        rate_1y=snapshot.rate_1y,
        next_funding_time=snapshot.next_funding_time,
        max_leverage=snapshot.max_leverage,
        leveraged_nominal_rate_1y=snapshot.leveraged_nominal_rate_1y,
        open_interest_usd=snapshot.oi_usd,
        volume24h_usd=snapshot.vol24h_usd,
        settlement_interval=_format_interval(snapshot.funding_interval_hours),
        settlement_interval_hours=snapshot.funding_interval_hours,
    )


def _calc_spread(short_rate: float | None, long_rate: float | None) -> float | None:
    if short_rate is None or long_rate is None:
        return None
    return short_rate - long_rate


def _matches_exchange_filter(
    long_exchange: SupportedExchange,
    short_exchange: SupportedExchange,
    exchange_filter: set[SupportedExchange] | None,
) -> bool:
    """交易所筛选策略：单选按包含，多选按双腿都在选中集合。"""

    if not exchange_filter:
        return True
    if len(exchange_filter) == 1:
        return long_exchange in exchange_filter or short_exchange in exchange_filter
    return long_exchange in exchange_filter and short_exchange in exchange_filter


def _resolve_interval_relation(
    long_interval_hours: float | None,
    short_interval_hours: float | None,
) -> tuple[bool, Literal["long", "short"] | None]:
    """返回是否间隔不一致，以及短间隔侧。"""

    if long_interval_hours is None or short_interval_hours is None:
        return False, None
    if long_interval_hours <= 0 or short_interval_hours <= 0:
        return False, None

    diff = long_interval_hours - short_interval_hours
    if abs(diff) < 1e-9:
        return False, None
    if diff < 0:
        return True, "long"
    return True, "short"


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
    symbol: str | None = None,
) -> list[OpportunityBoardRow]:
    """将市场快照转换成前端可直接渲染的 board 行。"""

    if limit <= 0:
        return []

    symbol_filter = symbol.upper().strip() if symbol else ""
    snapshot_index = _build_snapshot_index(snapshots)
    exchange_filter = set(exchanges) if exchanges else None
    opportunities = scan_opportunities(
        snapshots=snapshots,
        min_spread_rate_1y_nominal=min_spread_rate_1y_nominal,
    )

    rows: list[OpportunityBoardRow] = []
    for item in opportunities:
        if symbol_filter and item.symbol != symbol_filter:
            continue
        if not _matches_exchange_filter(item.long_exchange, item.short_exchange, exchange_filter):
            continue

        long_snapshot = snapshot_index.get((item.symbol, item.long_exchange))
        short_snapshot = snapshot_index.get((item.symbol, item.short_exchange))
        if long_snapshot is None or short_snapshot is None:
            continue

        interval_mismatch, shorter_interval_side = _resolve_interval_relation(
            long_snapshot.funding_interval_hours,
            short_snapshot.funding_interval_hours,
        )

        rows.append(
            OpportunityBoardRow(
                id=f"{item.symbol}-{item.long_exchange}-{item.short_exchange}",
                symbol=item.symbol,
                long_exchange=item.long_exchange,
                short_exchange=item.short_exchange,
                long_leg=_to_board_leg(long_snapshot),
                short_leg=_to_board_leg(short_snapshot),
                interval_mismatch=interval_mismatch,
                shorter_interval_side=shorter_interval_side,
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
    symbol: str | None = None,
) -> MarketBoardResponse:
    """生成 /api/market/board 聚合响应。"""

    snapshots_response = await market_data_service.fetch_snapshots(force_refresh=force_refresh)
    exchange_filter = set(exchanges) if exchanges else None
    rows = build_board_rows_from_snapshots(
        snapshots=snapshots_response.snapshots,
        limit=limit,
        min_spread_rate_1y_nominal=min_spread_rate_1y_nominal,
        exchanges=exchange_filter,
        symbol=symbol,
    )

    meta: dict[str, Any] = dict(snapshots_response.meta or {})
    meta["board_sort"] = "leveraged_spread_rate_1y_nominal_desc_then_spread_rate_1y_nominal_desc"
    meta["board_limit"] = limit
    meta["board_min_spread_rate_1y_nominal"] = min_spread_rate_1y_nominal
    if exchange_filter:
        meta["board_exchanges_filter"] = sorted(exchange_filter)
        meta["board_exchanges_filter_mode"] = "single_include_or_multi_both"
    if symbol and symbol.strip():
        meta["board_symbol_filter"] = symbol.upper().strip()

    return MarketBoardResponse(
        as_of=snapshots_response.as_of,
        total=len(rows),
        rows=rows,
        errors=snapshots_response.errors,
        meta=meta,
    )
