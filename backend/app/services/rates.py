import math
from typing import Optional


def convert_funding_rate(
    funding_rate_raw: float | None,
    funding_interval_hours: float | None,
) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """
    资金费率换算：
    - rate_1h：按小时折算
    - rate_8h：按 8 小时折算
    - rate_1y：按小时复利折算年化
    - nominal_rate_1y：按线性名义年化
    """

    if funding_rate_raw is None or funding_interval_hours in (None, 0):
        return None, None, None, None

    rate_1h = funding_rate_raw / funding_interval_hours
    rate_8h = rate_1h * 8
    nominal_rate_1y = rate_1h * 24 * 365

    try:
        rate_1y = math.pow(1 + rate_1h, 24 * 365) - 1
    except (OverflowError, ValueError):
        rate_1y = None

    return rate_1h, rate_8h, rate_1y, nominal_rate_1y

