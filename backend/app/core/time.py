from datetime import datetime, timezone
from typing import Optional


def utc_now() -> datetime:
    """返回带时区的 UTC 时间。"""

    return datetime.now(timezone.utc)


def ms_to_utc(value: object) -> Optional[datetime]:
    """毫秒时间戳转 UTC。"""

    if value in (None, ""):
        return None
    try:
        millis = int(float(value))
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(millis / 1000, tz=timezone.utc)


def sec_to_utc(value: object) -> Optional[datetime]:
    """秒级时间戳转 UTC。"""

    if value in (None, ""):
        return None
    try:
        seconds = int(float(value))
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(seconds, tz=timezone.utc)

