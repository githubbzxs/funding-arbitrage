from fastapi import FastAPI

from app.api.execution import router as execution_router
from app.api.market import router as market_router
from app.api.opportunities import router as opportunities_router
from app.api.records import router as records_router
from app.core.config import get_settings
from app.core.database import init_db
from app.core.time import utc_now


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="资金费率套利系统后端服务",
)

app.include_router(market_router)
app.include_router(opportunities_router)
app.include_router(execution_router)
app.include_router(records_router)


@app.on_event("startup")
async def on_startup() -> None:
    """应用启动时初始化数据库。"""

    await init_db()


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "ts": utc_now().isoformat()}

