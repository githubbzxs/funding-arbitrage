from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.models.schemas import (
    ClosePositionRequest,
    EmergencyCloseRequest,
    ExecutionActionResponse,
    ExecutionPreviewRequest,
    ExecutionPreviewResponse,
    HedgeRequest,
    OpenPositionRequest,
)
from app.services.container import execution_service


router = APIRouter(prefix="/api/execution", tags=["execution"])


@router.post("/preview", response_model=ExecutionPreviewResponse)
async def preview_execution(request: ExecutionPreviewRequest) -> ExecutionPreviewResponse:
    """开仓收益预估。"""

    return await execution_service.preview(request)


@router.post("/open", response_model=ExecutionActionResponse)
async def open_position(
    request: OpenPositionRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ExecutionActionResponse:
    """开仓执行。"""

    return await execution_service.open_position(session, request)


@router.post("/close", response_model=ExecutionActionResponse)
async def close_position(
    request: ClosePositionRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ExecutionActionResponse:
    """平仓执行。"""

    try:
        return await execution_service.close_position(session, request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/hedge", response_model=ExecutionActionResponse)
async def hedge_position(
    request: HedgeRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ExecutionActionResponse:
    """对冲执行。"""

    return await execution_service.hedge(session, request)


@router.post("/emergency-close", response_model=ExecutionActionResponse)
async def emergency_close(
    request: EmergencyCloseRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ExecutionActionResponse:
    """紧急全平。"""

    return await execution_service.emergency_close(session, request)

