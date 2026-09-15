from __future__ import annotations

from app.db import get_db
from app.messaging.notification_service import emit_notifications
from app.messaging.source_provider import get_messaging_source_provider

SYSTEM_ANNOUNCEMENT = "system_announcement"
TEACHING_ANNOUNCEMENT = "teaching_announcement"
POLICY_PUBLISHED = "policy_published"
AGRICULTURE_REMINDER = "agriculture_reminder"


def _event_key(event_type: str, event_id: str) -> str:
    return f"{event_type}:{event_id}"


def emit_system_announcement(
    *,
    event_id: str,
    announcement_id: str,
    title: str,
    body: str,
) -> dict:
    all_user_ids = [
        int(row["id"])
        for row in get_db().execute("SELECT id FROM users ORDER BY id").fetchall()
    ]
    return emit_notifications(
        recipient_ids=all_user_ids,
        event_key=_event_key(SYSTEM_ANNOUNCEMENT, event_id),
        event_type=SYSTEM_ANNOUNCEMENT,
        title=title,
        body=body,
        source_type="announcement",
        source_id=announcement_id,
    )


def emit_teaching_announcement(
    *,
    event_id: str,
    teacher_id: int,
    announcement_id: str,
    title: str,
    body: str,
) -> dict:
    student_ids = [
        int(row["id"])
        for row in get_db()
        .execute("SELECT id FROM users WHERE role = 'student' ORDER BY id")
        .fetchall()
    ]
    return emit_notifications(
        recipient_ids=student_ids,
        event_key=_event_key(TEACHING_ANNOUNCEMENT, event_id),
        event_type=TEACHING_ANNOUNCEMENT,
        title=title,
        body=body,
        source_type="announcement",
        source_id=announcement_id,
    )


def emit_policy_published(
    *,
    event_id: str,
    policy_id: str,
    title: str,
    category: str,
) -> dict:
    provider = get_messaging_source_provider()
    policy_subscriber_ids = provider.list_policy_subscriber_ids(category)
    return emit_notifications(
        recipient_ids=policy_subscriber_ids,
        event_key=_event_key(POLICY_PUBLISHED, event_id),
        event_type=POLICY_PUBLISHED,
        title=title,
        body=f"政策类别：{category}",
        source_type="policy",
        source_id=policy_id,
    )


def emit_monthly_agriculture_reminder(
    *,
    event_id: str,
    product_key: str,
    month: str,
    body: str,
) -> dict:
    provider = get_messaging_source_provider()
    product_subscriber_ids = provider.list_product_subscriber_ids(product_key)
    return emit_notifications(
        recipient_ids=product_subscriber_ids,
        event_key=_event_key(AGRICULTURE_REMINDER, event_id),
        event_type=AGRICULTURE_REMINDER,
        title="月度农事提醒",
        body=f"农产品：{product_key}；月份：{month}。{body}",
        source_type="agricultural_product",
        source_id=product_key,
    )
