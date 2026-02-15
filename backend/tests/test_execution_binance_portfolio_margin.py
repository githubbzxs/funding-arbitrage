import sys
import types

import pytest

from app.models.schemas import ExchangeCredential
from app.services.execution import CcxtExecutionGateway


class _FakeClient:
    def __init__(self, create_order_errors: list[str | None]) -> None:
        self._create_order_errors = list(create_order_errors)
        self.create_order_params: list[dict] = []
        self.set_leverage_params: list[dict | None] = []

    def set_sandbox_mode(self, _enabled: bool) -> None:
        return None

    async def set_leverage(self, _leverage: float, _symbol: str, params: dict | None = None) -> None:
        self.set_leverage_params.append(params)

    async def create_order(self, *, symbol: str, type: str, side: str, amount: float, params: dict):
        _ = symbol, type, side, amount
        self.create_order_params.append(dict(params))
        if self._create_order_errors:
            error = self._create_order_errors.pop(0)
            if error:
                raise Exception(error)
        return {
            "id": "test-order-id",
            "filled": amount,
            "average": 100_000.0,
        }

    async def close(self) -> None:
        return None


class _FakeExchangeFactory:
    def __init__(self, create_order_errors: list[str | None]) -> None:
        self._create_order_errors = create_order_errors
        self.client: _FakeClient | None = None

    def __call__(self, _config: dict) -> _FakeClient:
        self.client = _FakeClient(self._create_order_errors)
        return self.client


def _install_fake_ccxt(
    monkeypatch: pytest.MonkeyPatch,
    exchange_map: dict[str, _FakeExchangeFactory],
) -> None:
    ccxt_module = types.ModuleType("ccxt")
    ccxt_async_support_module = types.ModuleType("ccxt.async_support")
    for exchange_id, factory in exchange_map.items():
        setattr(ccxt_async_support_module, exchange_id, factory)
    setattr(ccxt_module, "async_support", ccxt_async_support_module)
    monkeypatch.setitem(sys.modules, "ccxt", ccxt_module)
    monkeypatch.setitem(sys.modules, "ccxt.async_support", ccxt_async_support_module)


@pytest.mark.asyncio
async def test_binance_order_uses_portfolio_margin_and_position_side(monkeypatch: pytest.MonkeyPatch) -> None:
    factory = _FakeExchangeFactory(create_order_errors=[None])
    _install_fake_ccxt(monkeypatch, {"binanceusdm": factory})

    gateway = CcxtExecutionGateway()
    result = await gateway.place_market_order(
        exchange="binance",
        symbol="BTCUSDT",
        side="sell",
        quantity=0.001,
        credential=ExchangeCredential(api_key="k", api_secret="s", testnet=False),
        leverage=3,
        reduce_only=True,
        position_side="LONG",
    )

    assert result.success is True
    assert factory.client is not None
    assert len(factory.client.create_order_params) == 1
    assert factory.client.create_order_params[0]["portfolioMargin"] is True
    assert factory.client.create_order_params[0]["positionSide"] == "LONG"
    assert "reduceOnly" not in factory.client.create_order_params[0]
    assert {"portfolioMargin": True} in factory.client.set_leverage_params


@pytest.mark.asyncio
async def test_binance_position_side_mismatch_retries_with_both(monkeypatch: pytest.MonkeyPatch) -> None:
    factory = _FakeExchangeFactory(
        create_order_errors=[
            'binanceusdm {"code":-4061,"msg":"Order\'s position side does not match user\'s setting."}',
            None,
        ]
    )
    _install_fake_ccxt(monkeypatch, {"binanceusdm": factory})

    gateway = CcxtExecutionGateway()
    result = await gateway.place_market_order(
        exchange="binance",
        symbol="BTCUSDT",
        side="sell",
        quantity=0.001,
        credential=ExchangeCredential(api_key="k", api_secret="s", testnet=False),
        reduce_only=True,
        position_side="LONG",
    )

    assert result.success is True
    assert factory.client is not None
    assert len(factory.client.create_order_params) == 2
    assert factory.client.create_order_params[0]["positionSide"] == "LONG"
    assert "reduceOnly" not in factory.client.create_order_params[0]
    assert factory.client.create_order_params[1]["positionSide"] == "BOTH"
    assert factory.client.create_order_params[1]["reduceOnly"] is True


@pytest.mark.asyncio
async def test_non_binance_order_does_not_attach_portfolio_margin(monkeypatch: pytest.MonkeyPatch) -> None:
    factory = _FakeExchangeFactory(
        create_order_errors=[
            'okx {"code":-2015,"msg":"Invalid API-key, IP, or permissions for action"}',
        ]
    )
    _install_fake_ccxt(monkeypatch, {"okx": factory})

    gateway = CcxtExecutionGateway()
    result = await gateway.place_market_order(
        exchange="okx",
        symbol="BTCUSDT",
        side="buy",
        quantity=0.001,
        credential=ExchangeCredential(api_key="k", api_secret="s", testnet=False),
    )

    assert result.success is False
    assert factory.client is not None
    assert len(factory.client.create_order_params) == 1
    assert "portfolioMargin" not in factory.client.create_order_params[0]


@pytest.mark.asyncio
async def test_okx_order_uses_pos_side_for_hedge_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    factory = _FakeExchangeFactory(create_order_errors=[None])
    _install_fake_ccxt(monkeypatch, {"okx": factory})

    gateway = CcxtExecutionGateway()
    result = await gateway.place_market_order(
        exchange="okx",
        symbol="ETHUSDT",
        side="sell",
        quantity=0.05,
        credential=ExchangeCredential(api_key="k", api_secret="s", testnet=False),
        reduce_only=True,
        position_side="LONG",
    )

    assert result.success is True
    assert factory.client is not None
    assert len(factory.client.create_order_params) == 1
    assert factory.client.create_order_params[0]["posSide"] == "long"
    assert "reduceOnly" not in factory.client.create_order_params[0]


@pytest.mark.asyncio
async def test_okx_pos_side_error_retries_with_net_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    factory = _FakeExchangeFactory(
        create_order_errors=[
            'okx {"code":"1","data":[{"sCode":"51000","sMsg":"Parameter posSide error "}]}',
            None,
        ]
    )
    _install_fake_ccxt(monkeypatch, {"okx": factory})

    gateway = CcxtExecutionGateway()
    result = await gateway.place_market_order(
        exchange="okx",
        symbol="ETHUSDT",
        side="sell",
        quantity=0.05,
        credential=ExchangeCredential(api_key="k", api_secret="s", testnet=False),
        reduce_only=True,
        position_side="LONG",
    )

    assert result.success is True
    assert factory.client is not None
    assert len(factory.client.create_order_params) == 2
    assert factory.client.create_order_params[0]["posSide"] == "long"
    assert "reduceOnly" not in factory.client.create_order_params[0]
    assert factory.client.create_order_params[1]["posSide"] == "net"
    assert factory.client.create_order_params[1]["reduceOnly"] is True
