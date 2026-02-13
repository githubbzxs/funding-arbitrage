import pytest

from app.models.schemas import MarketSnapshot, SupportedExchange
from app.services.market_board import build_board_rows_from_snapshots


def _snapshot(
    *,
    exchange: SupportedExchange,
    symbol: str,
    nominal_rate_1y: float,
    funding_interval_hours: float = 8,
    rate_1h: float | None = None,
    rate_8h: float | None = None,
    max_leverage: float | None = None,
) -> MarketSnapshot:
    leveraged_nominal_rate_1y = None
    if max_leverage is not None:
        leveraged_nominal_rate_1y = nominal_rate_1y * max_leverage

    return MarketSnapshot(
        exchange=exchange,
        symbol=symbol,
        funding_rate_raw=rate_1h,
        funding_interval_hours=funding_interval_hours,
        nominal_rate_1y=nominal_rate_1y,
        leveraged_nominal_rate_1y=leveraged_nominal_rate_1y,
        rate_1h=rate_1h,
        rate_8h=rate_8h,
        max_leverage=max_leverage,
        oi_usd=1_000_000,
        vol24h_usd=2_000_000,
    )


def test_board_rows_sorted_by_leveraged_spread_first() -> None:
    snapshots = [
        _snapshot(exchange="binance", symbol="BTCUSDT", nominal_rate_1y=-0.10, rate_1h=-0.0001, rate_8h=-0.0008, max_leverage=20),
        _snapshot(exchange="okx", symbol="BTCUSDT", nominal_rate_1y=0.20, rate_1h=0.0002, rate_8h=0.0016, max_leverage=10),
        _snapshot(exchange="gateio", symbol="ETHUSDT", nominal_rate_1y=0.10, rate_1h=0.0001, rate_8h=0.0008),
        _snapshot(exchange="bybit", symbol="ETHUSDT", nominal_rate_1y=0.60, rate_1h=0.0006, rate_8h=0.0048),
    ]

    rows = build_board_rows_from_snapshots(snapshots=snapshots, limit=10)

    assert [row.symbol for row in rows] == ["BTCUSDT", "ETHUSDT"]
    assert rows[0].leveraged_spread_rate_1y_nominal == pytest.approx(3.0)
    assert rows[0].spread_rate_1h == pytest.approx(0.0003)
    assert rows[0].spread_rate_8h == pytest.approx(0.0024)
    assert rows[0].interval_mismatch is False
    assert rows[0].shorter_interval_side is None
    assert rows[1].leveraged_spread_rate_1y_nominal is None
    assert rows[1].spread_rate_1y_nominal == pytest.approx(0.50)
    assert rows[1].interval_mismatch is False
    assert rows[1].shorter_interval_side is None


def test_board_rows_supports_exchange_filter() -> None:
    snapshots = [
        _snapshot(exchange="binance", symbol="BTCUSDT", nominal_rate_1y=-0.10, max_leverage=20),
        _snapshot(exchange="okx", symbol="BTCUSDT", nominal_rate_1y=0.20, max_leverage=10),
        _snapshot(exchange="gateio", symbol="ETHUSDT", nominal_rate_1y=0.10),
        _snapshot(exchange="bybit", symbol="ETHUSDT", nominal_rate_1y=0.60),
    ]

    rows = build_board_rows_from_snapshots(snapshots=snapshots, exchanges={"okx"}, limit=10)
    pair_rows = build_board_rows_from_snapshots(snapshots=snapshots, exchanges={"okx", "binance"}, limit=10)
    empty_rows = build_board_rows_from_snapshots(snapshots=snapshots, exchanges={"okx", "bybit"}, limit=10)
    empty_rows_single = build_board_rows_from_snapshots(snapshots=snapshots, exchanges={"bitget"}, limit=10)

    assert len(rows) == 1
    assert rows[0].symbol == "BTCUSDT"
    assert "okx" in {rows[0].long_exchange, rows[0].short_exchange}
    assert len(pair_rows) == 1
    assert pair_rows[0].symbol == "BTCUSDT"
    assert empty_rows == []
    assert empty_rows_single == []


def test_board_rows_limit_works() -> None:
    snapshots = [
        _snapshot(exchange="binance", symbol="BTCUSDT", nominal_rate_1y=-0.10, max_leverage=20),
        _snapshot(exchange="okx", symbol="BTCUSDT", nominal_rate_1y=0.20, max_leverage=10),
        _snapshot(exchange="bybit", symbol="SOLUSDT", nominal_rate_1y=-0.05, max_leverage=20),
        _snapshot(exchange="gateio", symbol="SOLUSDT", nominal_rate_1y=0.05, max_leverage=20),
        _snapshot(exchange="gateio", symbol="ETHUSDT", nominal_rate_1y=0.10),
        _snapshot(exchange="bybit", symbol="ETHUSDT", nominal_rate_1y=0.60),
    ]

    rows = build_board_rows_from_snapshots(snapshots=snapshots, limit=2)

    assert len(rows) == 2
    assert [row.symbol for row in rows] == ["BTCUSDT", "SOLUSDT"]


def test_board_rows_supports_symbol_filter() -> None:
    snapshots = [
        _snapshot(exchange="binance", symbol="BTCUSDT", nominal_rate_1y=-0.10, max_leverage=20),
        _snapshot(exchange="okx", symbol="BTCUSDT", nominal_rate_1y=0.20, max_leverage=10),
        _snapshot(exchange="gateio", symbol="ETHUSDT", nominal_rate_1y=0.10),
        _snapshot(exchange="bybit", symbol="ETHUSDT", nominal_rate_1y=0.60),
    ]

    btc_rows = build_board_rows_from_snapshots(snapshots=snapshots, symbol="BTCUSDT", limit=10)
    empty_rows = build_board_rows_from_snapshots(snapshots=snapshots, symbol="SOLUSDT", limit=10)

    assert len(btc_rows) == 1
    assert btc_rows[0].symbol == "BTCUSDT"
    assert empty_rows == []


def test_board_rows_marks_interval_mismatch_and_shorter_side() -> None:
    snapshots = [
        _snapshot(exchange="binance", symbol="BTCUSDT", nominal_rate_1y=-0.05, funding_interval_hours=4),
        _snapshot(exchange="okx", symbol="BTCUSDT", nominal_rate_1y=0.20, funding_interval_hours=8),
    ]

    rows = build_board_rows_from_snapshots(snapshots=snapshots, limit=10)

    assert len(rows) == 1
    assert rows[0].interval_mismatch is True
    assert rows[0].shorter_interval_side == "long"
