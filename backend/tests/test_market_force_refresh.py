import pytest

from app.models.schemas import MarketSnapshot
from app.services import market_data as market_data_module
from app.services.market_data import MarketDataService


class _CountingFetcher:
    exchange = "binance"

    def __init__(self) -> None:
        self.calls = 0

    async def fetch_snapshots_with_source(self) -> tuple[list[MarketSnapshot], str]:
        self.calls += 1
        snapshot = MarketSnapshot(
            exchange="binance",
            symbol=f"BTCUSDT_{self.calls}",
            funding_rate_raw=0.0001,
            funding_interval_hours=8,
        )
        return [snapshot], "ccxt"


@pytest.mark.asyncio
async def test_force_refresh_bypasses_local_and_remote_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    service = MarketDataService()
    service._settings.market_cache_ttl_seconds = 60
    service._fetchers = [_CountingFetcher()]

    async def fake_cache_get_json(_key: str):
        return None

    async def fake_cache_set_json(_key: str, _value, _ttl: int) -> None:
        return None

    monkeypatch.setattr(market_data_module, "cache_get_json", fake_cache_get_json)
    monkeypatch.setattr(market_data_module, "cache_set_json", fake_cache_set_json)

    first = await service.fetch_snapshots()
    second = await service.fetch_snapshots()
    third = await service.fetch_snapshots(force_refresh=True)

    assert len(first.snapshots) == 1
    assert len(second.snapshots) == 1
    assert len(third.snapshots) == 1
    assert first.snapshots[0].symbol == "BTCUSDT_1"
    assert second.snapshots[0].symbol == "BTCUSDT_1"
    assert third.snapshots[0].symbol == "BTCUSDT_2"
