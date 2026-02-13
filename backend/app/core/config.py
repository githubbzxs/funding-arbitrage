from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。"""

    app_name: str = "Funding Arbitrage Backend"
    app_env: str = "dev"
    database_url: str = "sqlite+aiosqlite:///./funding_arbitrage.db"
    request_timeout_seconds: float = 10.0
    max_concurrency_per_exchange: int = 20
    leverage_cache_ttl_seconds: int = 3600

    model_config = SettingsConfigDict(
        env_prefix="FA_",
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

