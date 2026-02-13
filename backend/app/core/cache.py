import json
from typing import Any

from app.core.config import get_settings


settings = get_settings()
_redis_client = None


async def get_cache_client():
    """懒加载 Redis 客户端。未配置时返回 None。"""

    global _redis_client
    if settings.redis_url is None:
        return None
    if _redis_client is not None:
        return _redis_client

    try:
        import redis.asyncio as redis  # type: ignore
    except Exception:
        return None

    _redis_client = redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    return _redis_client


async def cache_get_json(key: str) -> Any | None:
    client = await get_cache_client()
    if client is None:
        return None
    try:
        raw = await client.get(key)
    except Exception:
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def cache_set_json(key: str, value: Any, ttl_seconds: int) -> None:
    client = await get_cache_client()
    if client is None:
        return
    try:
        payload = json.dumps(value, ensure_ascii=False)
        await client.set(key, payload, ex=ttl_seconds)
    except Exception:
        return
