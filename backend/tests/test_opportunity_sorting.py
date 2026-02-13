from app.models.schemas import MarketSnapshot
from app.services.arbitrage import scan_opportunities


def test_scan_opportunities_sorted_by_nominal_spread() -> None:
    snapshots = [
        MarketSnapshot(exchange="binance", symbol="BTCUSDT", funding_rate_raw=0.0001, funding_interval_hours=8, nominal_rate_1y=0.10),
        MarketSnapshot(exchange="okx", symbol="BTCUSDT", funding_rate_raw=0.0002, funding_interval_hours=8, nominal_rate_1y=0.25),
        MarketSnapshot(exchange="bybit", symbol="BTCUSDT", funding_rate_raw=-0.0001, funding_interval_hours=8, nominal_rate_1y=-0.05),
    ]

    opportunities = scan_opportunities(snapshots)

    assert len(opportunities) == 3
    assert opportunities[0].spread_rate_1y_nominal >= opportunities[1].spread_rate_1y_nominal
    assert opportunities[1].spread_rate_1y_nominal >= opportunities[2].spread_rate_1y_nominal
    assert opportunities[0].long_exchange == "bybit"
    assert opportunities[0].short_exchange == "okx"
    assert opportunities[0].spread_rate_1y_nominal == 0.30


def test_scan_opportunities_leveraged_spread() -> None:
    snapshots = [
        MarketSnapshot(
            exchange="binance",
            symbol="BTCUSDT",
            funding_rate_raw=0.0001,
            funding_interval_hours=8,
            nominal_rate_1y=0.10,
            max_leverage=50,
        ),
        MarketSnapshot(
            exchange="okx",
            symbol="BTCUSDT",
            funding_rate_raw=0.0002,
            funding_interval_hours=8,
            nominal_rate_1y=0.25,
            max_leverage=20,
        ),
    ]

    opportunities = scan_opportunities(snapshots)

    assert len(opportunities) == 1
    assert opportunities[0].max_usable_leverage == 20
    assert opportunities[0].leveraged_spread_rate_1y_nominal == 0.15 * 20
