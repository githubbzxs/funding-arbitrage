import os

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.models.base import Base
from app.models.orm import ExchangeCredentialStore
from app.models.schemas import ExchangeCredential
from app.services.credentials import CredentialService


@pytest.mark.asyncio
async def test_credential_service_roundtrip() -> None:
    os.environ["FA_CREDENTIAL_ENCRYPTION_KEY"] = "unit-test-key"
    get_settings.cache_clear()

    service = CredentialService()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False, future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    SessionFactory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionFactory() as session:
        status = await service.upsert_credential(
            session,
            "binance",
            ExchangeCredential(
                api_key="abcdefgh12345678",
                api_secret="secret-value",
                passphrase="pass",
                testnet=True,
            ),
        )
        await session.commit()

        assert status.exchange == "binance"
        assert status.configured is True
        assert status.api_key_masked is not None
        assert status.api_key_masked != "abcdefgh12345678"

        row = await session.get(ExchangeCredentialStore, "binance")
        assert row is not None
        assert row.api_key_enc != "abcdefgh12345678"
        assert row.api_secret_enc != "secret-value"

        loaded = await service.get_credential(session, "binance")
        assert loaded is not None
        assert loaded.api_key == "abcdefgh12345678"
        assert loaded.api_secret == "secret-value"
        assert loaded.passphrase == "pass"
        assert loaded.testnet is True

        deleted = await service.delete_credential(session, "binance")
        await session.commit()
        assert deleted is True

        loaded_after = await service.get_credential(session, "binance")
        assert loaded_after is None

