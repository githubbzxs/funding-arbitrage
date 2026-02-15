import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.config import router as config_router
from app.api.credentials import router as credentials_router
from app.api.execution import router as execution_router
from app.api.records import router as records_router
from app.api.risk_events import router as risk_events_router
from app.api.templates import router as templates_router
from app.core.config import get_settings
from app.core.database import init_db
from app.core.time import utc_now


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

app.include_router(config_router)
app.include_router(credentials_router)
app.include_router(execution_router)
app.include_router(records_router)
app.include_router(risk_events_router)
app.include_router(templates_router)


@app.on_event("startup")
async def on_startup() -> None:
    """应用启动时初始化数据库。"""

    await init_db()


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "ts": utc_now().isoformat()}
