from app.models.schemas import FetchError, MarketSnapshot, MarketSnapshotsResponse


def test_market_snapshots_response_supports_meta() -> None:
    response = MarketSnapshotsResponse(
        snapshots=[
            MarketSnapshot(
                exchange="binance",
                symbol="BTCUSDT",
                funding_rate_raw=0.0001,
                funding_interval_hours=8,
            )
        ],
        errors=[FetchError(exchange="okx", message="timeout")],
        meta={
            "fetch_ms": 1200,
            "cache_hit": False,
            "exchanges_ok": ["binance"],
            "exchanges_failed": ["okx"],
        },
    )
    assert response.meta is not None
    assert response.meta["fetch_ms"] == 1200
    assert response.meta["exchanges_failed"] == ["okx"]
