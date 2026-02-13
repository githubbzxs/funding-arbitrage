from datetime import datetime, timedelta

import pytest

from app.core.time import utc_now
from app.models.schemas import MarketSnapshot, SupportedExchange
from app.services.market_board import build_board_rows_from_snapshots


def _snapshot(
    *,
    exchange: SupportedExchange,
    symbol: str,
    nominal_rate_1y: float,
    funding_rate_raw: float | None,
    next_funding_time: datetime | None,
    funding_interval_hours: float | None,
    max_leverage: float | None = None,
    rate_1h: float | None = None,
    rate_8h: float | None = None,
) -> MarketSnapshot:
    leveraged_nominal_rate_1y = None
    if max_leverage is not None:
        leveraged_nominal_rate_1y = nominal_rate_1y * max_leverage

    return MarketSnapshot(
        exchange=exchange,
        symbol=symbol,
        nominal_rate_1y=nominal_rate_1y,
        leveraged_nominal_rate_1y=leveraged_nominal_rate_1y,
        funding_rate_raw=funding_rate_raw,
        next_funding_time=next_funding_time,
        funding_interval_hours=funding_interval_hours,
        max_leverage=max_leverage,
        rate_1h=funding_rate_raw if rate_1h is None else rate_1h,
        rate_8h=rate_8h,
        oi_usd=1_000_000,
        vol24h_usd=2_000_000,
    )


def _rows_by_symbol(rows):
    return {row.symbol: row for row in rows}


def test_next_cycle_same_interval_only_both_events() -> None:
    base = utc_now()
    snapshots = [
        _snapshot(
            exchange="binance",
            symbol="BTCUSDT",
            nominal_rate_1y=-0.10,
            funding_rate_raw=-0.0001,
            next_funding_time=base + timedelta(hours=1),
            funding_interval_hours=8,
            max_leverage=10,
        ),
        _snapshot(
            exchange="okx",
            symbol="BTCUSDT",
            nominal_rate_1y=0.20,
            funding_rate_raw=0.0002,
            next_funding_time=base + timedelta(hours=1),
            funding_interval_hours=8,
            max_leverage=20,
        ),
    ]

    rows = build_board_rows_from_snapshots(snapshots=snapshots, limit=10)

    assert len(rows) == 1
    row = rows[0]
    assert row.calc_status == "ok"
    assert row.next_cycle_score_unlevered == pytest.approx(0.0003)
    assert row.next_cycle_score == pytest.approx(0.003)
    assert row.single_side_event_count == 0
    assert row.single_side_total_rate == pytest.approx(0.0)
    assert row.next_sync_settlement_time is not None
    assert row.window_hours_to_sync is not None
    assert 0.0 <= row.window_hours_to_sync <= 1.05
    assert len(row.settlement_events_preview) == 1
    assert row.settlement_events_preview[0].kind == "both"
    assert row.settlement_events_preview[0].rate == pytest.approx(0.0003)
    assert row.settlement_events_preview[0].leveraged_rate == pytest.approx(0.003)


def test_next_cycle_interval_mismatch_includes_single_side_events() -> None:
    base = utc_now()
    snapshots = [
        _snapshot(
            exchange="binance",
            symbol="BTCUSDT",
            nominal_rate_1y=-0.10,
            funding_rate_raw=-0.0001,
            next_funding_time=base + timedelta(hours=1),
            funding_interval_hours=4,
            max_leverage=5,
        ),
        _snapshot(
            exchange="okx",
            symbol="BTCUSDT",
            nominal_rate_1y=0.20,
            funding_rate_raw=0.0002,
            next_funding_time=base + timedelta(hours=5),
            funding_interval_hours=8,
            max_leverage=8,
        ),
    ]

    rows = build_board_rows_from_snapshots(snapshots=snapshots, limit=10)

    assert len(rows) == 1
    row = rows[0]
    assert row.calc_status == "ok"
    assert [event.kind for event in row.settlement_events_preview] == ["long_only", "both"]
    assert row.single_side_event_count == 1
    assert row.single_side_total_rate == pytest.approx(0.0001)
    assert row.next_cycle_score_unlevered == pytest.approx(0.0004)
    assert row.next_cycle_score == pytest.approx(0.002)


def test_board_rows_sorted_by_next_cycle_score_first() -> None:
    base = utc_now()
    snapshots = [
        _snapshot(
            exchange="binance",
            symbol="BTCUSDT",
            nominal_rate_1y=-0.50,
            funding_rate_raw=-0.00005,
            next_funding_time=base + timedelta(hours=1),
            funding_interval_hours=8,
            max_leverage=5,
        ),
        _snapshot(
            exchange="okx",
            symbol="BTCUSDT",
            nominal_rate_1y=0.80,
            funding_rate_raw=0.00005,
            next_funding_time=base + timedelta(hours=1),
            funding_interval_hours=8,
            max_leverage=5,
        ),
        _snapshot(
            exchange="gateio",
            symbol="ETHUSDT",
            nominal_rate_1y=0.00,
            funding_rate_raw=-0.0002,
            next_funding_time=base + timedelta(hours=1),
            funding_interval_hours=8,
            max_leverage=3,
        ),
        _snapshot(
            exchange="bybit",
            symbol="ETHUSDT",
            nominal_rate_1y=0.20,
            funding_rate_raw=0.0002,
            next_funding_time=base + timedelta(hours=1),
            funding_interval_hours=8,
            max_leverage=3,
        ),
    ]

    rows = build_board_rows_from_snapshots(snapshots=snapshots, limit=10)

    assert len(rows) == 2
    assert [row.symbol for row in rows] == ["ETHUSDT", "BTCUSDT"]
    assert rows[0].next_cycle_score == pytest.approx(0.0012)
    assert rows[1].next_cycle_score == pytest.approx(0.0005)
    assert rows[0].spread_rate_1y_nominal < rows[1].spread_rate_1y_nominal


def test_min_next_cycle_score_filters_numeric_rows_and_excludes_none_when_positive() -> None:
    base = utc_now()
    snapshots = [
        _snapshot(
            exchange="binance",
            symbol="BTCUSDT",
            nominal_rate_1y=-0.10,
            funding_rate_raw=-0.0001,
            next_funding_time=base + timedelta(hours=1),
            funding_interval_hours=8,
            max_leverage=5,
        ),
        _snapshot(
            exchange="okx",
            symbol="BTCUSDT",
            nominal_rate_1y=0.30,
            funding_rate_raw=0.0003,
            next_funding_time=base + timedelta(hours=1),
            funding_interval_hours=8,
            max_leverage=10,
        ),
        _snapshot(
            exchange="gateio",
            symbol="ETHUSDT",
            nominal_rate_1y=-0.10,
            funding_rate_raw=-0.00005,
            next_funding_time=base + timedelta(hours=1),
            funding_interval_hours=8,
            max_leverage=5,
        ),
        _snapshot(
            exchange="bybit",
            symbol="ETHUSDT",
            nominal_rate_1y=0.10,
            funding_rate_raw=0.00005,
            next_funding_time=base + timedelta(hours=1),
            funding_interval_hours=8,
            max_leverage=5,
        ),
        _snapshot(
            exchange="bitget",
            symbol="SOLUSDT",
            nominal_rate_1y=-0.10,
            funding_rate_raw=-0.0001,
            next_funding_time=None,
            funding_interval_hours=8,
            max_leverage=5,
        ),
        _snapshot(
            exchange="okx",
            symbol="SOLUSDT",
            nominal_rate_1y=0.20,
            funding_rate_raw=0.0002,
            next_funding_time=base + timedelta(hours=1),
            funding_interval_hours=8,
            max_leverage=5,
        ),
    ]

    rows_without_filter = build_board_rows_from_snapshots(snapshots=snapshots, limit=10, min_next_cycle_score=0.0)
    rows_with_filter = build_board_rows_from_snapshots(snapshots=snapshots, limit=10, min_next_cycle_score=0.001)

    assert len(rows_without_filter) == 3
    by_symbol = _rows_by_symbol(rows_without_filter)
    assert by_symbol["SOLUSDT"].next_cycle_score is None

    assert len(rows_with_filter) == 1
    assert rows_with_filter[0].symbol == "BTCUSDT"
    assert rows_with_filter[0].next_cycle_score == pytest.approx(0.002)


def test_missing_next_funding_time_or_interval_marks_calc_status_missing_data() -> None:
    base = utc_now()
    snapshots = [
        _snapshot(
            exchange="binance",
            symbol="BTCUSDT",
            nominal_rate_1y=-0.10,
            funding_rate_raw=-0.0001,
            next_funding_time=None,
            funding_interval_hours=8,
            max_leverage=5,
        ),
        _snapshot(
            exchange="okx",
            symbol="BTCUSDT",
            nominal_rate_1y=0.20,
            funding_rate_raw=0.0002,
            next_funding_time=base + timedelta(hours=1),
            funding_interval_hours=8,
            max_leverage=5,
        ),
        _snapshot(
            exchange="gateio",
            symbol="ETHUSDT",
            nominal_rate_1y=-0.10,
            funding_rate_raw=-0.0001,
            next_funding_time=base + timedelta(hours=1),
            funding_interval_hours=8,
            max_leverage=5,
        ),
        _snapshot(
            exchange="bybit",
            symbol="ETHUSDT",
            nominal_rate_1y=0.20,
            funding_rate_raw=0.0002,
            next_funding_time=base + timedelta(hours=1),
            funding_interval_hours=None,
            max_leverage=5,
        ),
    ]

    rows = build_board_rows_from_snapshots(snapshots=snapshots, limit=10)
    by_symbol = _rows_by_symbol(rows)

    assert len(rows) == 2
    assert by_symbol["BTCUSDT"].calc_status == "missing_data"
    assert by_symbol["BTCUSDT"].next_cycle_score is None
    assert by_symbol["BTCUSDT"].settlement_events_preview == []

    assert by_symbol["ETHUSDT"].calc_status == "missing_data"
    assert by_symbol["ETHUSDT"].next_cycle_score is None
    assert by_symbol["ETHUSDT"].settlement_events_preview == []


def test_no_sync_found_when_schedules_do_not_align() -> None:
    base = utc_now()
    snapshots = [
        _snapshot(
            exchange="binance",
            symbol="XRPUSDT",
            nominal_rate_1y=-0.10,
            funding_rate_raw=-0.0001,
            next_funding_time=base + timedelta(hours=1),
            funding_interval_hours=4,
            max_leverage=5,
        ),
        _snapshot(
            exchange="okx",
            symbol="XRPUSDT",
            nominal_rate_1y=0.20,
            funding_rate_raw=0.0002,
            next_funding_time=base + timedelta(hours=3),
            funding_interval_hours=8,
            max_leverage=5,
        ),
    ]

    rows = build_board_rows_from_snapshots(snapshots=snapshots, limit=10)

    assert len(rows) == 1
    assert rows[0].calc_status == "no_sync_found"
    assert rows[0].next_cycle_score is None
    assert rows[0].settlement_events_preview == []
