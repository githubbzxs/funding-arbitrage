from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。"""

    app_name: str = "Funding Arbitrage Backend"
    app_env: str = "dev"
    database_url: str = "sqlite+aiosqlite:///./funding_arbitrage.db"
    redis_url: str | None = None
    request_timeout_seconds: float = 10.0
    max_concurrency_per_exchange: int = 20
    market_cache_ttl_seconds: int = 3
    leverage_cache_ttl_seconds: int = 3600
    enable_ccxt_market_leverage: bool = False
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    model_config = SettingsConfigDict(
        env_prefix="FA_",
        env_file=".env",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
