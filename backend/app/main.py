import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.config import router as config_router
from app.api.credentials import router as credentials_router
from app.api.execution import router as execution_router
from app.api.market import router as market_router
from app.api.opportunities import router as opportunities_router
from app.api.records import router as records_router
from app.core.config import get_settings
from app.core.database import init_db
from app.core.time import utc_now
from app.services.container import market_data_service


settings = get_settings()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="资金费率套利系统后端服务",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market_router)
app.include_router(opportunities_router)
app.include_router(config_router)
app.include_router(credentials_router)
app.include_router(execution_router)
app.include_router(records_router)


@app.on_event("startup")
async def on_startup() -> None:
    """应用启动时初始化数据库。"""

    await init_db()
    asyncio.create_task(_warm_market_cache())


async def _warm_market_cache() -> None:
    """后台预热行情缓存，降低首个请求等待时间。"""

    try:
        await market_data_service.fetch_snapshots()
    except Exception as exc:  # pragma: no cover
        logger.warning("预热行情缓存失败: %s", exc)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "ts": utc_now().isoformat()}
