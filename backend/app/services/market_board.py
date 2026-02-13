from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal

from app.core.time import utc_now
from app.models.schemas import (
    MarketBoardResponse,
    MarketSnapshot,
    OpportunityBoardLeg,
    OpportunityBoardRow,
    SettlementEvent,
    SupportedExchange,
)
from app.services.arbitrage import scan_opportunities
from app.services.market_data import MarketDataService

_SETTLEMENT_TIME_TOLERANCE_SECONDS = 1.0
_MAX_SYNC_SEARCH_STEPS = 2000


@dataclass(slots=True)
class _NextCycleMetrics:
    calc_status: Literal["ok", "missing_data", "no_sync_found"]
    next_sync_settlement_time: datetime | None
    window_hours_to_sync: float | None
    next_cycle_score: float | None
    next_cycle_score_unlevered: float | None
    settlement_events_preview: list[SettlementEvent]
    single_side_event_count: int
    single_side_total_rate: float | None


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


def _legacy_board_sort_key(row: OpportunityBoardRow) -> tuple[int, float, float]:
    leveraged_spread = row.leveraged_spread_rate_1y_nominal
    if leveraged_spread is not None:
        return (1, leveraged_spread, row.spread_rate_1y_nominal)
    return (0, row.spread_rate_1y_nominal, row.spread_rate_1y_nominal)


def _next_cycle_sort_key(row: OpportunityBoardRow) -> tuple[int, float, int, float, float]:
    score = row.next_cycle_score
    legacy = _legacy_board_sort_key(row)
    if score is None:
        return (0, float("-inf"), legacy[0], legacy[1], legacy[2])
    return (1, score, legacy[0], legacy[1], legacy[2])


def _is_same_settlement_time(left: datetime, right: datetime) -> bool:
    return abs((left - right).total_seconds()) <= _SETTLEMENT_TIME_TOLERANCE_SECONDS


def _resolve_leverage(max_usable_leverage: float | None) -> float:
    if max_usable_leverage is None or max_usable_leverage <= 0:
        return 1.0
    return max_usable_leverage


def _normalize_next_settlement_time(
    next_funding_time: datetime,
    interval_hours: float,
    now: datetime,
) -> datetime:
    interval_delta = timedelta(hours=interval_hours)
    candidate = next_funding_time
    if candidate > now or _is_same_settlement_time(candidate, now):
        return candidate

    interval_seconds = interval_delta.total_seconds()
    elapsed_seconds = (now - candidate).total_seconds()
    if elapsed_seconds > interval_seconds:
        skipped = int(elapsed_seconds // interval_seconds)
        candidate = candidate + interval_delta * skipped

    while candidate < now and not _is_same_settlement_time(candidate, now):
        candidate += interval_delta
    return candidate


def _find_next_sync_settlement_time(
    long_first: datetime,
    short_first: datetime,
    long_interval: timedelta,
    short_interval: timedelta,
) -> datetime | None:
    long_cursor = long_first
    short_cursor = short_first
    for _ in range(_MAX_SYNC_SEARCH_STEPS):
        if _is_same_settlement_time(long_cursor, short_cursor):
            return long_cursor if long_cursor >= short_cursor else short_cursor
        if long_cursor < short_cursor:
            long_cursor += long_interval
        else:
            short_cursor += short_interval
    return None


def _build_settlement_events_preview(
    *,
    long_first: datetime,
    short_first: datetime,
    long_interval: timedelta,
    short_interval: timedelta,
    sync_time: datetime,
    long_rate_raw: float,
    short_rate_raw: float,
    leverage: float,
) -> list[SettlementEvent]:
    events: list[SettlementEvent] = []
    long_cursor = long_first
    short_cursor = short_first

    for _ in range(_MAX_SYNC_SEARCH_STEPS):
        if _is_same_settlement_time(long_cursor, short_cursor):
            event_time = long_cursor if long_cursor >= short_cursor else short_cursor
            if event_time > sync_time and not _is_same_settlement_time(event_time, sync_time):
                break
            rate = short_rate_raw - long_rate_raw
            events.append(
                SettlementEvent(
                    time=event_time,
                    kind="both",
                    rate=rate,
                    leveraged_rate=rate * leverage,
                    long_rate_raw=long_rate_raw,
                    short_rate_raw=short_rate_raw,
                )
            )
            long_cursor += long_interval
            short_cursor += short_interval
            if _is_same_settlement_time(event_time, sync_time):
                break
            continue

        if long_cursor < short_cursor:
            event_time = long_cursor
            if event_time > sync_time and not _is_same_settlement_time(event_time, sync_time):
                break
            rate = -long_rate_raw
            events.append(
                SettlementEvent(
                    time=event_time,
                    kind="long_only",
                    rate=rate,
                    leveraged_rate=rate * leverage,
                    long_rate_raw=long_rate_raw,
                    short_rate_raw=None,
                )
            )
            long_cursor += long_interval
            continue

        event_time = short_cursor
        if event_time > sync_time and not _is_same_settlement_time(event_time, sync_time):
            break
        rate = short_rate_raw
        events.append(
            SettlementEvent(
                time=event_time,
                kind="short_only",
                rate=rate,
                leveraged_rate=rate * leverage,
                long_rate_raw=None,
                short_rate_raw=short_rate_raw,
            )
        )
        short_cursor += short_interval

    return events


def _build_missing_data_metrics() -> _NextCycleMetrics:
    return _NextCycleMetrics(
        calc_status="missing_data",
        next_sync_settlement_time=None,
        window_hours_to_sync=None,
        next_cycle_score=None,
        next_cycle_score_unlevered=None,
        settlement_events_preview=[],
        single_side_event_count=0,
        single_side_total_rate=None,
    )


def _build_no_sync_metrics() -> _NextCycleMetrics:
    return _NextCycleMetrics(
        calc_status="no_sync_found",
        next_sync_settlement_time=None,
        window_hours_to_sync=None,
        next_cycle_score=None,
        next_cycle_score_unlevered=None,
        settlement_events_preview=[],
        single_side_event_count=0,
        single_side_total_rate=None,
    )


def _calculate_next_cycle_metrics(
    *,
    long_snapshot: MarketSnapshot,
    short_snapshot: MarketSnapshot,
    max_usable_leverage: float | None,
    now: datetime,
) -> _NextCycleMetrics:
    long_next = long_snapshot.next_funding_time
    short_next = short_snapshot.next_funding_time
    long_interval_hours = long_snapshot.funding_interval_hours
    short_interval_hours = short_snapshot.funding_interval_hours
    long_rate_raw = long_snapshot.funding_rate_raw
    short_rate_raw = short_snapshot.funding_rate_raw

    if (
        long_next is None
        or short_next is None
        or long_interval_hours is None
        or short_interval_hours is None
        or long_interval_hours <= 0
        or short_interval_hours <= 0
        or long_rate_raw is None
        or short_rate_raw is None
    ):
        return _build_missing_data_metrics()

    long_first = _normalize_next_settlement_time(long_next, long_interval_hours, now)
    short_first = _normalize_next_settlement_time(short_next, short_interval_hours, now)
    long_interval = timedelta(hours=long_interval_hours)
    short_interval = timedelta(hours=short_interval_hours)
    sync_time = _find_next_sync_settlement_time(long_first, short_first, long_interval, short_interval)
    if sync_time is None:
        return _build_no_sync_metrics()

    leverage = _resolve_leverage(max_usable_leverage)
    events = _build_settlement_events_preview(
        long_first=long_first,
        short_first=short_first,
        long_interval=long_interval,
        short_interval=short_interval,
        sync_time=sync_time,
        long_rate_raw=long_rate_raw,
        short_rate_raw=short_rate_raw,
        leverage=leverage,
    )

    next_cycle_score_unlevered = sum(event.rate for event in events)
    next_cycle_score = next_cycle_score_unlevered * leverage
    single_side_events = [event for event in events if event.kind != "both"]
    single_side_total_rate = sum(event.rate for event in single_side_events)
    window_hours_to_sync = max(0.0, (sync_time - now).total_seconds() / 3600)

    return _NextCycleMetrics(
        calc_status="ok",
        next_sync_settlement_time=sync_time,
        window_hours_to_sync=window_hours_to_sync,
        next_cycle_score=next_cycle_score,
        next_cycle_score_unlevered=next_cycle_score_unlevered,
        settlement_events_preview=events,
        single_side_event_count=len(single_side_events),
        single_side_total_rate=single_side_total_rate,
    )


def _apply_board_sort(rows: list[OpportunityBoardRow]) -> str:
    if any(row.next_cycle_score is not None for row in rows):
        rows.sort(key=_next_cycle_sort_key, reverse=True)
        return "next_cycle_score_desc_nulls_last"

    rows.sort(key=_legacy_board_sort_key, reverse=True)
    return "next_cycle_score_desc_nulls_last_fallback_to_leveraged_spread_rate_1y_nominal_desc_then_spread_rate_1y_nominal_desc"


def build_board_rows_from_snapshots(
    snapshots: list[MarketSnapshot],
    *,
    limit: int = 500,
    min_spread_rate_1y_nominal: float = 0.0,
    min_next_cycle_score: float = 0.0,
    exchanges: Iterable[SupportedExchange] | None = None,
    symbol: str | None = None,
) -> list[OpportunityBoardRow]:
    """将市场快照转换成前端可直接渲染的 board 行。"""

    if limit <= 0:
        return []

    symbol_filter = symbol.upper().strip() if symbol else ""
    now = utc_now()
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
        next_cycle_metrics = _calculate_next_cycle_metrics(
            long_snapshot=long_snapshot,
            short_snapshot=short_snapshot,
            max_usable_leverage=item.max_usable_leverage,
            now=now,
        )
        row = OpportunityBoardRow(
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
            next_sync_settlement_time=next_cycle_metrics.next_sync_settlement_time,
            window_hours_to_sync=next_cycle_metrics.window_hours_to_sync,
            next_cycle_score=next_cycle_metrics.next_cycle_score,
            next_cycle_score_unlevered=next_cycle_metrics.next_cycle_score_unlevered,
            settlement_events_preview=next_cycle_metrics.settlement_events_preview,
            single_side_event_count=next_cycle_metrics.single_side_event_count,
            single_side_total_rate=next_cycle_metrics.single_side_total_rate,
            calc_status=next_cycle_metrics.calc_status,
        )

        if min_next_cycle_score > 0:
            if row.next_cycle_score is None or row.next_cycle_score < min_next_cycle_score:
                continue

        rows.append(row)

    _apply_board_sort(rows)
    return rows[:limit]


async def build_market_board_response(
    market_data_service: MarketDataService,
    *,
    limit: int = 500,
    min_spread_rate_1y_nominal: float = 0.0,
    min_next_cycle_score: float = 0.0,
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
        min_next_cycle_score=min_next_cycle_score,
        exchanges=exchange_filter,
        symbol=symbol,
    )

    meta: dict[str, Any] = dict(snapshots_response.meta or {})
    if any(row.next_cycle_score is not None for row in rows):
        meta["board_sort"] = "next_cycle_score_desc_nulls_last"
    else:
        meta["board_sort"] = (
            "next_cycle_score_desc_nulls_last_fallback_to_"
            "leveraged_spread_rate_1y_nominal_desc_then_spread_rate_1y_nominal_desc"
        )
    meta["board_limit"] = limit
    meta["board_min_spread_rate_1y_nominal"] = min_spread_rate_1y_nominal
    meta["board_min_next_cycle_score"] = min_next_cycle_score
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
