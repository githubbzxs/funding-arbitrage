import re
from datetime import datetime
from typing import Optional

from app.core.time import ms_to_utc, sec_to_utc, utc_now
from app.models.schemas import MarketSnapshot, SupportedExchange
from app.services.rates import convert_funding_rate


def safe_float(value: object) -> Optional[float]:
    """安全转换浮点数。"""

    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_usdt_symbol(raw_symbol: str | None) -> str | None:
    """将交易所符号标准化为 `BASEUSDT`。"""

    if not raw_symbol:
        return None

    symbol = raw_symbol.upper().replace(" ", "")
    if "/USDT" in symbol:
        base = symbol.split("/USDT", maxsplit=1)[0]
    elif "-USDT" in symbol:
        base = symbol.split("-USDT", maxsplit=1)[0]
    elif "_USDT" in symbol:
        base = symbol.split("_USDT", maxsplit=1)[0]
    elif symbol.endswith("USDT"):
        base = symbol[: -len("USDT")]
    else:
        return None

    base = re.sub(r"[^A-Z0-9]", "", base)
    if not base:
        return None

    return f"{base}USDT"


def canonical_from_base_quote(base: str | None, quote: str | None) -> str | None:
    """由 base/quote 生成标准符号。"""

    if not base or not quote:
        return None
    if quote.upper() != "USDT":
        return None
    return f"{base.upper()}USDT"


def parse_exchange_timestamp(value: object, unit: str = "ms") -> datetime | None:
    """解析交易所时间戳。"""

    if unit == "s":
        return sec_to_utc(value)
    return ms_to_utc(value)


def build_snapshot(
    *,
    exchange: SupportedExchange,
    symbol: str,
    funding_rate_raw: float | None,
    funding_interval_hours: float | None,
    next_funding_time: datetime | None,
    oi_usd: float | None,
    vol24h_usd: float | None,
    max_leverage: float | None,
    mark_price: float | None = None,
) -> MarketSnapshot | None:
    """构造统一快照模型。"""

    normalized_symbol = normalize_usdt_symbol(symbol)
    if not normalized_symbol:
        return None

    rate_1h, rate_8h, rate_1y, nominal_rate_1y = convert_funding_rate(
        funding_rate_raw=funding_rate_raw,
        funding_interval_hours=funding_interval_hours,
    )
    return MarketSnapshot(
        exchange=exchange,
        symbol=normalized_symbol,
        oi_usd=oi_usd,
        vol24h_usd=vol24h_usd,
        funding_rate_raw=funding_rate_raw,
        funding_interval_hours=funding_interval_hours,
        next_funding_time=next_funding_time,
        max_leverage=max_leverage,
        rate_1h=rate_1h,
        rate_8h=rate_8h,
        rate_1y=rate_1y,
        nominal_rate_1y=nominal_rate_1y,
        mark_price=mark_price,
        updated_at=utc_now(),
    )

