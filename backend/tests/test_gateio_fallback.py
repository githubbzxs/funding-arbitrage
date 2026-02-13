import pytest

from app.exchanges.providers.ccxt_market import CcxtMarketProvider
from app.models.schemas import MarketSnapshot


@pytest.mark.asyncio
async def test_gateio_provider_uses_legacy_fallback_when_ccxt_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = CcxtMarketProvider("gateio")
    fallback_snapshot = MarketSnapshot(
        exchange="gateio",
        symbol="BTCUSDT",
        funding_rate_raw=0.0001,
        funding_interval_hours=8,
    )

    async def fake_fetch_ccxt_snapshots() -> list[MarketSnapshot]:
        return []

    async def fake_fetch_gateio_fallback() -> list[MarketSnapshot]:
        return [fallback_snapshot]

    monkeypatch.setattr(provider, "_fetch_ccxt_snapshots", fake_fetch_ccxt_snapshots)
    monkeypatch.setattr(provider, "_fetch_gateio_fallback", fake_fetch_gateio_fallback)

    snapshots, source = await provider.fetch_snapshots_with_source()
    assert source == "legacy_rest"
    assert len(snapshots) == 1
    assert snapshots[0].exchange == "gateio"
