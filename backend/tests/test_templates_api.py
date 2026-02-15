import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.templates import create_template, delete_template, list_templates, update_template
from app.models.base import Base
from app.models.schemas import StrategyTemplateCreate, StrategyTemplateUpdate


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
async def test_template_crud(session: AsyncSession) -> None:
    created = await create_template(
        StrategyTemplateCreate(
            name="BTC-OKX-BINANCE",
            symbol="btcusdt",
            long_exchange="okx",
            short_exchange="binance",
            leverage=6,
            notional_usd=1500,
            hold_hours=8,
            note="测试模板",
        ),
        session,
    )
    assert created.symbol == "BTCUSDT"
    assert created.name == "BTC-OKX-BINANCE"

    listed = await list_templates(limit=200, session=session)
    assert listed.total == 1
    assert listed.items[0].id == created.id

    updated = await update_template(
        created.id,
        StrategyTemplateUpdate(
            name="BTC-OKX-BINANCE-V2",
            notional_usd=2000,
        ),
        session,
    )
    assert updated.name == "BTC-OKX-BINANCE-V2"
    assert updated.notional_usd == pytest.approx(2000)

    deleted = await delete_template(created.id, session)
    assert deleted["success"] is True

    listed_after_delete = await list_templates(limit=200, session=session)
    assert listed_after_delete.total == 0
