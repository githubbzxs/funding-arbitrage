import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.risk_events import list_risk_events, resolve_risk_event
from app.models.base import Base
from app.models.orm import RiskEvent


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
async def test_list_and_resolve_risk_events(session: AsyncSession) -> None:
    event_critical = RiskEvent(
        event_type="open_second_leg_failed",
        severity="critical",
        message="测试高危事件",
        context={"position_id": "p1"},
        resolved=False,
    )
    event_high = RiskEvent(
        event_type="hedge_failed",
        severity="high",
        message="测试高风险事件",
        context={"position_id": "p2"},
        resolved=False,
    )
    session.add(event_critical)
    session.add(event_high)
    await session.commit()

    critical_events = await list_risk_events(limit=100, resolved=False, severity="critical", session=session)
    assert critical_events.total == 1
    assert critical_events.items[0].event_type == "open_second_leg_failed"

    resolved = await resolve_risk_event(event_critical.id, session=session)
    assert resolved.id == event_critical.id
    assert resolved.resolved is True

    unresolved = await list_risk_events(limit=100, resolved=False, severity=None, session=session)
    assert unresolved.total == 1
    assert unresolved.items[0].id == event_high.id
