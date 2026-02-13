import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass

from app.core.config import get_settings
from app.core.time import utc_now
from app.exchanges.utils import canonical_from_base_quote, safe_float
from app.models.schemas import SupportedExchange


logger = logging.getLogger(__name__)

CCXT_EXCHANGE_MAP: dict[SupportedExchange, str] = {
    "binance": "binanceusdm",
    "okx": "okx",
    "bybit": "bybit",
    "bitget": "bitget",
    "gateio": "gateio",
}


@dataclass
class CacheEntry:
    expires_at_ts: float
    data: dict[str, float]


_cache: dict[SupportedExchange, CacheEntry] = {}
_locks: dict[SupportedExchange, asyncio.Lock] = defaultdict(asyncio.Lock)


async def get_leverage_map(exchange: SupportedExchange) -> dict[str, float]:
    """读取并缓存各交易所 USDT 永续最大杠杆。"""

    settings = get_settings()
    if not settings.enable_ccxt_market_leverage:
        return {}

    now_ts = utc_now().timestamp()
    cached = _cache.get(exchange)
    if cached and cached.expires_at_ts > now_ts:
        return cached.data

    lock = _locks[exchange]
    async with lock:
        now_ts = utc_now().timestamp()
        cached = _cache.get(exchange)
        if cached and cached.expires_at_ts > now_ts:
            return cached.data

        data = await _load_from_ccxt(exchange)
        _cache[exchange] = CacheEntry(
            expires_at_ts=now_ts + settings.leverage_cache_ttl_seconds,
            data=data,
        )
        return data


async def _load_from_ccxt(exchange: SupportedExchange) -> dict[str, float]:
    leverage_map: dict[str, float] = {}
    exchange_id = CCXT_EXCHANGE_MAP[exchange]

    try:
        import ccxt.async_support as ccxt_async  # type: ignore
    except Exception as exc:  # pragma: no cover
        logger.warning("ccxt 导入失败，无法加载杠杆信息: %s", exc)
        return leverage_map

    exchange_cls = getattr(ccxt_async, exchange_id, None)
    if exchange_cls is None:
        return leverage_map

    client = exchange_cls(
        {
            "enableRateLimit": True,
            "options": {"defaultType": "swap"},
        }
    )
    try:
        await client.load_markets()
        for market in client.markets.values():
            if not market.get("swap"):
                continue
            if str(market.get("quote", "")).upper() != "USDT":
                continue

            symbol = canonical_from_base_quote(
                str(market.get("base", "")).upper(),
                str(market.get("quote", "")).upper(),
            )
            if not symbol:
                continue

            limits = market.get("limits", {})
            leverage_max = safe_float(limits.get("leverage", {}).get("max"))
            info = market.get("info", {})
            if leverage_max is None:
                for key in ("maxLeverage", "maxLever", "lever", "leverage_max", "leverageMax"):
                    leverage_max = safe_float(info.get(key))
                    if leverage_max is not None:
                        break

            if leverage_max is not None:
                leverage_map[symbol] = leverage_max
    except Exception as exc:  # pragma: no cover
        logger.warning("通过 ccxt 加载 %s 杠杆信息失败: %s", exchange, exc)
    finally:
        try:
            await client.close()
        except Exception:
            pass

    return leverage_map
