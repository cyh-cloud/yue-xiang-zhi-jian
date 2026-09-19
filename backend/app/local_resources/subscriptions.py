from datetime import datetime
from zoneinfo import ZoneInfo

from app.db import get_db
from app.local_resources.constants import (
    POLICY_LABELS,
    RECOMMENDATION_TAGS,
)
from app.local_resources.errors import LocalResourceValidationError
from app.profiles.service import get_profile_preferences


PLATFORM_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _now():
    return datetime.now(PLATFORM_TIMEZONE).isoformat(timespec="seconds")


def _validate_category(category_code):
    if category_code not in POLICY_LABELS:
        raise LocalResourceValidationError(
            "政策类别不正确",
            details={"category_code": "不属于政策类别"},
        )
    return category_code


def recommend_policy_categories(user_id):
    preferences = get_profile_preferences(user_id)
    ordered = []
    for name in preferences["interest_tag_names"]:
        for category in RECOMMENDATION_TAGS.get(name, ()):
            if category not in ordered:
                ordered.append(category)
    return ordered


def list_policy_subscriptions(user_id):
    rows = get_db().execute(
        """
        SELECT category_code, is_active
        FROM local_resource_policy_subscriptions
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchall()
    active = {
        str(row["category_code"])
        for row in rows
        if bool(row["is_active"])
    }
    recommended = recommend_policy_categories(user_id)
    return {
        "categories": [
            {
                "code": code,
                "label": POLICY_LABELS[code],
                "subscribed": code in active,
                "recommended": code in recommended,
            }
            for code in POLICY_LABELS
        ],
        "recommended_category_codes": recommended,
    }


def set_policy_subscription(user_id, category_code, subscribed):
    category = _validate_category(category_code)
    now = _now()
    with get_db():
        get_db().execute(
            """
            INSERT INTO local_resource_policy_subscriptions (
                user_id, category_code, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, category_code) DO UPDATE SET
                is_active = excluded.is_active,
                updated_at = excluded.updated_at
            """,
            (user_id, category, int(bool(subscribed)), now, now),
        )
    return {
        "code": category,
        "label": POLICY_LABELS[category],
        "subscribed": bool(subscribed),
    }
