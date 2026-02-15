import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.orm import Position
from app.models.schemas import (
    ClosePositionRequest,
    ExchangeCredential,
    ExecutionMode,
    HedgeRequest,
    MarketSnapshot,
    MarketSnapshotsResponse,
    OpenPositionRequest,
    QuantityConvertRequest,
)
from app.services.execution import ExecutionService, GatewayResult


class _FakeMarketDataService:
    async def fetch_snapshots(self, force_refresh: bool = False) -> MarketSnapshotsResponse:
        _ = force_refresh
        return MarketSnapshotsResponse(
            snapshots=[
                MarketSnapshot(
                    exchange="binance",
                    symbol="BTCUSDT",
                    funding_rate_raw=0.0001,
                    funding_interval_hours=8,
                    mark_price=100_000,
                ),
                MarketSnapshot(
                    exchange="okx",
                    symbol="BTCUSDT",
                    funding_rate_raw=0.0001,
                    funding_interval_hours=8,
                    mark_price=100_000,
                ),
            ]
        )


class _FakeCredentialService:
    async def get_credential(self, session: AsyncSession, exchange: str) -> ExchangeCredential | None:
        _ = session, exchange
        return ExchangeCredential(api_key="k", api_secret="s", testnet=False)


class _FakeGateway:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def place_market_order(
        self,
        *,
        exchange: str,
        symbol: str,
        side: str,
        quantity: float,
        credential: ExchangeCredential,
        leverage: float | None = None,
        reduce_only: bool = False,
    ) -> GatewayResult:
        self.calls.append(
            {
                "exchange": exchange,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "leverage": leverage,
                "reduce_only": reduce_only,
                "api_key": credential.api_key,
            }
        )
        return GatewayResult(
            success=True,
            order_id=f"order-{len(self.calls)}",
            filled_qty=quantity,
            avg_price=100_000,
            message="ok",
            raw={},
        )


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as db:
        yield db

    await engine.dispose()


@pytest.mark.asyncio
async def test_execution_uses_quantity_and_auto_mode(session: AsyncSession) -> None:
    service = ExecutionService(
        market_data_service=_FakeMarketDataService(),
        credential_service=_FakeCredentialService(),
    )
    gateway = _FakeGateway()
    service.gateway = gateway  # type: ignore[assignment]

    open_result = await service.open_position(
        session,
        OpenPositionRequest(
            symbol="BTCUSDT",
            long_exchange="binance",
            short_exchange="okx",
            quantity=0.01,
            leverage=5,
            credentials={},
        ),
    )

    assert open_result.success is True
    assert open_result.mode == ExecutionMode.auto
    assert len(gateway.calls) == 2
    assert gateway.calls[0]["quantity"] == pytest.approx(0.01)
    assert gateway.calls[1]["quantity"] == pytest.approx(0.01)

    assert open_result.position_id is not None
    position = await session.get(Position, open_result.position_id)
    assert position is not None
    assert position.mode == ExecutionMode.auto.value
    assert position.long_qty == pytest.approx(0.01)
    assert position.short_qty == pytest.approx(0.01)

    close_result = await service.close_position(
        session,
        ClosePositionRequest(
            symbol="BTCUSDT",
            long_exchange="binance",
            short_exchange="okx",
            quantity=0.02,
            leverage=5,
            credentials={},
        ),
    )
    assert close_result.success is True
    assert close_result.mode == ExecutionMode.auto
    assert len(gateway.calls) == 4
    assert gateway.calls[2]["quantity"] == pytest.approx(0.02)
    assert gateway.calls[3]["quantity"] == pytest.approx(0.02)

    hedge_result = await service.hedge(
        session,
        HedgeRequest(
            symbol="BTCUSDT",
            exchange="binance",
            side="sell",
            quantity=0.005,
            leverage=3,
            credentials={},
            reason="unit-test",
        ),
    )
    assert hedge_result.success is True
    assert hedge_result.mode == ExecutionMode.auto
    assert len(gateway.calls) == 5
    assert gateway.calls[4]["quantity"] == pytest.approx(0.005)


@pytest.mark.asyncio
async def test_convert_notional_to_quantity_uses_binance_mark_price(session: AsyncSession) -> None:
    service = ExecutionService(
        market_data_service=_FakeMarketDataService(),
        credential_service=_FakeCredentialService(),
    )

    result = await service.convert_notional_to_quantity(
        QuantityConvertRequest(
            symbol="BTCUSDT",
            notional_usd=1500,
        )
    )

    assert result.exchange == "binance"
    assert result.symbol == "BTCUSDT"
    assert result.mark_price == pytest.approx(100_000)
    assert result.quantity == pytest.approx(0.015)
