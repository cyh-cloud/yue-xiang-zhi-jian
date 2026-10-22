# -*- coding: utf-8 -*-
"""复核有效期：内容事实超过半年后需要重新人工确认。"""

from datetime import datetime, timedelta

REVIEW_STALE_DAYS = 183


def is_review_current(verified_at, now=None):
    """判断一次复核是否仍在 183 天有效期内。

    空复核时间表示从未复核，按过期处理。时间格式沿用 SQLite
    datetime('now', 'localtime') 的 YYYY-MM-DD HH:MM:SS。
    """
    raw = str(verified_at or '').strip()
    if not raw:
        return False
    try:
        reviewed = datetime.strptime(raw[:19], '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return False
    current = now or datetime.now()
    return current - reviewed <= timedelta(days=REVIEW_STALE_DAYS)


__all__ = ['REVIEW_STALE_DAYS', 'is_review_current']
