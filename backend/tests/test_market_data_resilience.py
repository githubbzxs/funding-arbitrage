import pytest

from app.models.schemas import MarketSnapshot
from app.services.market_data import MarketDataService


class _EmptyFetcher:
    exchange = "gateio"

    async def fetch_snapshots_with_source(self) -> tuple[list[MarketSnapshot], str]:
        return [], "ccxt"


class _ToggleFetcher:
    exchange = "gateio"

    def __init__(self, snapshot: MarketSnapshot) -> None:
        self._snapshot = snapshot
        self._calls = 0

    async def fetch_snapshots_with_source(self) -> tuple[list[MarketSnapshot], str]:
        self._calls += 1
        if self._calls == 1:
            return [self._snapshot], "ccxt"
        return [], "ccxt"


@pytest.mark.asyncio
async def test_fetch_single_treats_empty_as_error() -> None:
    service = MarketDataService()
    exchange, snapshots, error, source = await service._fetch_single(_EmptyFetcher())
    assert exchange == "gateio"
    assert source == "ccxt"
    assert snapshots == []
    assert error is not None
    assert error.message == "抓取结果为空"


@pytest.mark.asyncio
async def test_market_data_uses_stale_snapshots_on_exchange_failure() -> None:
    service = MarketDataService()
    service._settings.market_cache_ttl_seconds = 0

    snapshot = MarketSnapshot(
        exchange="gateio",
        symbol="BTCUSDT",
        funding_rate_raw=0.0001,
        funding_interval_hours=8,
    )
    fetcher = _ToggleFetcher(snapshot)
    service._fetchers = [fetcher]

    first = await service.fetch_snapshots()
    assert len(first.snapshots) == 1
    assert first.errors == []

    service._local_cache_expires_at_ts = 0
    second = await service.fetch_snapshots()
    assert len(second.snapshots) == 1
    assert len(second.errors) == 1
    assert second.errors[0].exchange == "gateio"
    assert second.meta is not None
    assert second.meta.get("exchange_sources", {}).get("gateio") == "stale"
