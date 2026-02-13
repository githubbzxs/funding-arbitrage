from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.crypto import build_fernet, decrypt_text, encrypt_text
from app.models.orm import ExchangeCredentialStore
from app.models.schemas import (
    CredentialStatus,
    ExchangeCredential,
    SupportedExchange,
)


SUPPORTED_EXCHANGES: list[SupportedExchange] = ["binance", "okx", "bybit", "bitget", "gateio"]


def mask_api_key(api_key: str) -> str:
    value = (api_key or "").strip()
    if not value:
        return "-"
    if len(value) <= 8:
        return f"{value[:2]}***"
    return f"{value[:4]}...{value[-4:]}"


class CredentialService:
    """API 凭据托管服务：对称加密存储，不对外返回明文。"""

    def __init__(self) -> None:
        self._settings = get_settings()

    def _fernet(self):
        key = self._settings.credential_encryption_key
        return build_fernet(key or "")

    async def list_status(self, session: AsyncSession) -> list[CredentialStatus]:
        rows = list((await session.scalars(select(ExchangeCredentialStore))).all())
        by_exchange = {row.exchange: row for row in rows}

        fernet = None
        try:
            fernet = self._fernet()
        except ValueError:
            # 未配置加密密钥时仍允许查看“是否已配置”，但不展示 api_key_masked
            fernet = None

        items: list[CredentialStatus] = []
        for exchange in SUPPORTED_EXCHANGES:
            row = by_exchange.get(exchange)
            if row is None:
                items.append(CredentialStatus(exchange=exchange, configured=False))
                continue

            api_key_masked = None
            if fernet is not None:
                try:
                    api_key_masked = mask_api_key(decrypt_text(fernet, row.api_key_enc))
                except ValueError:
                    api_key_masked = None
            items.append(
                CredentialStatus(
                    exchange=exchange,
                    configured=True,
                    api_key_masked=api_key_masked,
                    has_passphrase=row.passphrase_enc is not None,
                    testnet=row.testnet,
                    updated_at=row.updated_at,
                )
            )

        return items

    async def get_credential(self, session: AsyncSession, exchange: SupportedExchange) -> ExchangeCredential | None:
        row = await session.get(ExchangeCredentialStore, exchange)
        if row is None:
            return None

        fernet = self._fernet()
        return ExchangeCredential(
            api_key=decrypt_text(fernet, row.api_key_enc),
            api_secret=decrypt_text(fernet, row.api_secret_enc),
            passphrase=decrypt_text(fernet, row.passphrase_enc) if row.passphrase_enc else None,
            testnet=row.testnet,
        )

    async def upsert_credential(
        self,
        session: AsyncSession,
        exchange: SupportedExchange,
        credential: ExchangeCredential,
    ) -> CredentialStatus:
        fernet = self._fernet()

        row = await session.get(ExchangeCredentialStore, exchange)
        if row is None:
            row = ExchangeCredentialStore(
                exchange=exchange,
                api_key_enc="",
                api_secret_enc="",
                passphrase_enc=None,
                testnet=credential.testnet,
            )
            session.add(row)

        row.api_key_enc = encrypt_text(fernet, credential.api_key)
        row.api_secret_enc = encrypt_text(fernet, credential.api_secret)
        row.passphrase_enc = encrypt_text(fernet, credential.passphrase) if credential.passphrase else None
        row.testnet = credential.testnet
        await session.flush()

        return CredentialStatus(
            exchange=exchange,
            configured=True,
            api_key_masked=mask_api_key(credential.api_key),
            has_passphrase=bool(credential.passphrase),
            testnet=credential.testnet,
            updated_at=row.updated_at,
        )

    async def delete_credential(self, session: AsyncSession, exchange: SupportedExchange) -> bool:
        row = await session.get(ExchangeCredentialStore, exchange)
        if row is None:
            return False
        await session.delete(row)
        await session.flush()
        return True
