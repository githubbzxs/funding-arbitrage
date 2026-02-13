import pytest

from app.exchanges.providers.ccxt_market import CcxtMarketProvider
from app.models.schemas import MarketSnapshot


@pytest.mark.asyncio
@pytest.mark.parametrize("exchange", ["gateio", "binance"])
async def test_provider_uses_legacy_fallback_when_ccxt_empty(
    monkeypatch: pytest.MonkeyPatch,
    exchange: str,
) -> None:
    provider = CcxtMarketProvider(exchange)
    fallback_snapshot = MarketSnapshot(
        exchange=exchange,  # type: ignore[arg-type]
        symbol="BTCUSDT",
        funding_rate_raw=0.0001,
        funding_interval_hours=8,
    )

    async def fake_fetch_ccxt_snapshots() -> list[MarketSnapshot]:
        return []

    async def fake_fetch_rest_fallback() -> list[MarketSnapshot]:
        return [fallback_snapshot]

    monkeypatch.setattr(provider, "_fetch_ccxt_snapshots", fake_fetch_ccxt_snapshots)
    monkeypatch.setattr(provider, "_fetch_rest_fallback", fake_fetch_rest_fallback)

    snapshots, source = await provider.fetch_snapshots_with_source()
    assert source == "legacy_rest"
    assert len(snapshots) == 1
    assert snapshots[0].exchange == exchange


@pytest.mark.asyncio
async def test_provider_uses_ws_fallback_when_rest_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = CcxtMarketProvider("gateio")
    ws_snapshot = MarketSnapshot(
        exchange="gateio",
        symbol="ETHUSDT",
        funding_rate_raw=0.0002,
        funding_interval_hours=8,
    )

    async def fake_fetch_ccxt_snapshots() -> list[MarketSnapshot]:
        return []

    async def fake_fetch_rest_fallback() -> list[MarketSnapshot]:
        raise RuntimeError("rest failed")

    async def fake_fetch_ws_fallback() -> list[MarketSnapshot]:
        return [ws_snapshot]

    monkeypatch.setattr(provider, "_fetch_ccxt_snapshots", fake_fetch_ccxt_snapshots)
    monkeypatch.setattr(provider, "_fetch_rest_fallback", fake_fetch_rest_fallback)
    monkeypatch.setattr(provider, "_fetch_ws_fallback", fake_fetch_ws_fallback)

    snapshots, source = await provider.fetch_snapshots_with_source()
    assert source == "ws_fallback"
    assert len(snapshots) == 1
    assert snapshots[0].exchange == "gateio"
