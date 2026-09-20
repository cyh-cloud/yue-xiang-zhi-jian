from __future__ import annotations

from app.messaging.notification_service import (
    NotificationValidationError,
    emit_notification,
    emit_notifications,
)

REVIEW_APPROVED = "review_approved"
REVIEW_REJECTED = "review_rejected"
APPLICATION_SUBMITTED = "application_submitted"
APPLICATION_STATUS = "application_status"
POSITION_CLOSED = "position_closed"
REDEMPTION_SUCCEEDED = "redemption_succeeded"
FULFILLMENT_ISSUED = "fulfillment_issued"
FULFILLMENT_CANCELLED = "fulfillment_cancelled"
POINTS_EXPIRED = "points_expired"
PASSWORD_RESET = "password_reset"
SYSTEM_ANNOUNCEMENT = "system_announcement"


def _event_key(event_type: str, event_id: str) -> str:
    return f"{event_type}:{event_id}"


def emit_review_result(
    *,
    event_id: str,
    submitter_id: int,
    content_type: str,
    content_id: str,
    approved: bool,
    opinion: str | None = None,
) -> dict:
    if approved:
        event_type = REVIEW_APPROVED
        title = "审核通过"
        body = f"{content_type}已通过并上架"
    else:
        normalized_opinion = str(opinion or "").strip()
        if not normalized_opinion:
            raise NotificationValidationError({"opinion": "不能为空"})
        event_type = REVIEW_REJECTED
        title = "审核未通过"
        body = f"审核意见：{normalized_opinion}"

    return emit_notification(
        recipient_id=submitter_id,
        event_key=_event_key(event_type, event_id),
        event_type=event_type,
        title=title,
        body=body,
        source_type=content_type,
        source_id=content_id,
    )


def emit_application_submitted(
    *,
    event_id: str,
    enterprise_id: int,
    student_id: int,
    application_id: str,
    student_name: str,
    job_title: str,
) -> dict:
    return emit_notification(
        recipient_id=enterprise_id,
        event_key=_event_key(APPLICATION_SUBMITTED, event_id),
        event_type=APPLICATION_SUBMITTED,
        title="收到新的岗位申请",
        body=f"{student_name}申请了{job_title}，请及时查看并开展意向沟通",
        source_type="application",
        source_id=application_id,
    )


def emit_application_status_changed(
    *,
    event_id: str,
    student_id: int,
    application_id: str,
    status: str,
) -> dict:
    return emit_notification(
        recipient_id=student_id,
        event_key=_event_key(APPLICATION_STATUS, event_id),
        event_type=APPLICATION_STATUS,
        title="申请状态已更新",
        body=f"您的申请状态已更新为：{status}",
        source_type="application",
        source_id=application_id,
    )


def emit_position_closed(
    *,
    event_id: str,
    student_ids: list[int],
    position_id: str,
    job_title: str,
) -> dict:
    return emit_notifications(
        recipient_ids=student_ids,
        event_key=_event_key(POSITION_CLOSED, event_id),
        event_type=POSITION_CLOSED,
        title="岗位已关闭",
        body=f"您申请的岗位“{job_title}”已关闭",
        source_type="job_position",
        source_id=position_id,
    )


def emit_redemption_succeeded(
    *,
    event_id: str,
    student_id: int,
    redemption_id: str,
    points_spent: int,
    prize_name: str,
) -> dict:
    return emit_notification(
        recipient_id=student_id,
        event_key=_event_key(REDEMPTION_SUCCEEDED, event_id),
        event_type=REDEMPTION_SUCCEEDED,
        title="奖品兑换成功",
        body=f"您已兑换{prize_name}，消耗{points_spent}积分",
        source_type="redemption",
        source_id=redemption_id,
    )


def emit_fulfillment_issued(
    *,
    event_id: str,
    student_id: int,
    fulfillment_id: str,
    prize_name: str,
) -> dict:
    return emit_notification(
        recipient_id=student_id,
        event_key=_event_key(FULFILLMENT_ISSUED, event_id),
        event_type=FULFILLMENT_ISSUED,
        title="奖品已发放",
        body=f"您的奖品“{prize_name}”已发放",
        source_type="fulfillment",
        source_id=fulfillment_id,
    )


def emit_fulfillment_cancelled(
    *,
    event_id: str,
    student_id: int,
    fulfillment_id: str,
    prize_name: str,
    restored_points: int,
) -> dict:
    return emit_notification(
        recipient_id=student_id,
        event_key=_event_key(FULFILLMENT_CANCELLED, event_id),
        event_type=FULFILLMENT_CANCELLED,
        title="履约已取消",
        body=f"您的奖品“{prize_name}”已取消，{restored_points}积分已回退",
        source_type="fulfillment",
        source_id=fulfillment_id,
    )


def emit_points_expired(
    *,
    event_id: str,
    student_id: int,
    points_cleared: int,
) -> dict:
    return emit_notification(
        recipient_id=student_id,
        event_key=_event_key(POINTS_EXPIRED, event_id),
        event_type=POINTS_EXPIRED,
        title="积分已过期",
        body=f"您的{points_cleared}积分清零",
    )


def emit_password_reset(*, event_id: str, user_id: int) -> dict:
    return emit_notification(
        recipient_id=user_id,
        event_key=_event_key(PASSWORD_RESET, event_id),
        event_type=PASSWORD_RESET,
        title="密码已重置",
        body="请联系管理员获取初始密码",
    )


def emit_system_announcement(
    *,
    event_id: str,
    recipient_ids: list[int],
    announcement_id: str,
    title: str,
    body: str,
) -> dict:
    return emit_notifications(
        recipient_ids=recipient_ids,
        event_key=_event_key(SYSTEM_ANNOUNCEMENT, event_id),
        event_type=SYSTEM_ANNOUNCEMENT,
        title=title,
        body=body,
        source_type="system_announcement",
        source_id=announcement_id,
    )
