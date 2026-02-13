import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.core.time import utc_now
from app.exchanges.utils import canonical_from_base_quote, normalize_usdt_symbol, safe_float
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
_BINANCE_PUBLIC_BRACKETS_URL = "https://www.binance.com/bapi/futures/v1/friendly/future/common/brackets"


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

        if exchange == "binance":
            data = await _load_binance_public_leverage_map()
            if not data:
                data = await _load_from_ccxt(exchange)
        else:
            data = await _load_from_ccxt(exchange)
        _cache[exchange] = CacheEntry(
            expires_at_ts=now_ts + settings.leverage_cache_ttl_seconds,
            data=data,
        )
        return data


def _parse_binance_public_brackets(payload: object) -> dict[str, float]:
    leverage_map: dict[str, float] = {}
    if not isinstance(payload, dict):
        return leverage_map

    data = payload.get("data")
    if not isinstance(data, dict):
        return leverage_map

    brackets = data.get("brackets")
    if not isinstance(brackets, list):
        return leverage_map

    for row in brackets:
        if not isinstance(row, dict):
            continue
        symbol = normalize_usdt_symbol(str(row.get("symbol", "")))
        if not symbol:
            continue

        leverage_max = safe_float(row.get("maxLeverage"))
        risk_rows = row.get("riskBrackets")
        if isinstance(risk_rows, list):
            for tier in risk_rows:
                if not isinstance(tier, dict):
                    continue
                parsed = safe_float(tier.get("maxOpenPosLeverage"))
                if parsed is None or parsed <= 0:
                    continue
                if leverage_max is None or parsed > leverage_max:
                    leverage_max = parsed

        if leverage_max is not None and leverage_max > 0:
            leverage_map[symbol] = leverage_max

    return leverage_map


async def _load_binance_public_leverage_map() -> dict[str, float]:
    try:
        timeout = httpx.Timeout(12.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(_BINANCE_PUBLIC_BRACKETS_URL)
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:  # pragma: no cover
        logger.warning("Binance 公共杠杆抓取失败: %s", exc)
        return {}

    leverage_map = _parse_binance_public_brackets(payload)
    if not leverage_map:
        logger.warning("Binance 公共杠杆抓取返回空结果")
    return leverage_map


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
        if exchange == "bybit":
            await client.load_markets(params={"type": "swap"})
        else:
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
