from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def now_shanghai_iso() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def parse_provider_time(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("时间字段必须包含时区")
    return parsed.astimezone(ZoneInfo("Asia/Shanghai"))
