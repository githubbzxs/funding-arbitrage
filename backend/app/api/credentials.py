from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.schemas import CredentialStatus, CredentialsResponse, ExchangeCredential, SupportedExchange
from app.services.credentials import CredentialService


router = APIRouter(prefix="/api/credentials", tags=["credentials"])
credential_service = CredentialService()


@router.get("", response_model=CredentialsResponse)
@router.get("/", response_model=CredentialsResponse)
async def list_credentials(session: AsyncSession = Depends(get_db_session)) -> CredentialsResponse:
    """获取后端托管的 API 凭据配置状态（不返回明文）。"""

    try:
        items = await credential_service.list_status(session)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return CredentialsResponse(items=items)


@router.put("/{exchange}", response_model=CredentialStatus)
async def upsert_credential(
    exchange: SupportedExchange,
    request: ExchangeCredential,
    session: AsyncSession = Depends(get_db_session),
) -> CredentialStatus:
    """写入/更新单个交易所托管凭据（加密存储）。"""

    api_key = (request.api_key or "").strip()
    api_secret = (request.api_secret or "").strip()
    passphrase = (request.passphrase or "").strip() or None

    if not api_key or not api_secret:
        raise HTTPException(status_code=422, detail="api_key/api_secret 不能为空")

    payload = ExchangeCredential(
        api_key=api_key,
        api_secret=api_secret,
        passphrase=passphrase,
        testnet=bool(request.testnet),
    )

    try:
        status = await credential_service.upsert_credential(session, exchange, payload)
        await session.commit()
        return status
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete("/{exchange}")
async def delete_credential(
    exchange: SupportedExchange,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, object]:
    """删除单个交易所托管凭据。"""

    try:
        deleted = await credential_service.delete_credential(session, exchange)
        await session.commit()
        return {"exchange": exchange, "deleted": deleted}
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

