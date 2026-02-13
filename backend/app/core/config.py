from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置。"""

    app_name: str = "Funding Arbitrage Backend"
    app_env: str = "dev"
    database_url: str = "sqlite+aiosqlite:///./funding_arbitrage.db"
    redis_url: str | None = None
    request_timeout_seconds: float = 10.0
    # 单交易所抓取的总体时间预算（避免单所拖垮整次快照请求）
    exchange_fetch_timeout_seconds: float = 25.0
    max_concurrency_per_exchange: int = 20
    # 市场快照缓存 TTL（秒）：降低外部接口压力与 504 风险
    market_cache_ttl_seconds: int = 20
    leverage_cache_ttl_seconds: int = 3600
    # OKX funding-rate 逐合约抓取的时间预算（秒），超出则降级返回部分结果
    okx_funding_fetch_budget_seconds: float = 12.0
    # ccxt 按 symbol 退化抓取 funding-rate 时的总体预算（秒）
    ccxt_funding_fetch_budget_seconds: float = 10.0
    enable_ccxt_market_leverage: bool = False
    # API 凭据加密密钥：用于后端托管 API Key/Secret（不配置则禁用托管能力）
    credential_encryption_key: str | None = None
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
