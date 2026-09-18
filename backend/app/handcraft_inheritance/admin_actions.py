from __future__ import annotations

# Task 14 must overwrite actor/reviewer/admin role and identity fields from the
# active 01 session before calling these services. Raw client payload values
# must never be treated as trusted authorization data.

from app.agri_skills.errors import AgriNotFoundError, AgriValidationError
from app.handcraft_inheritance.fulfillment import (
    cancel_pending_fulfillment,
    deliver_fulfillment_outbox,
    issue_fulfillment,
    manual_verify_fulfillment,
)
from app.handcraft_inheritance.outbox import (
    deliver_after_commit,
    enqueue_handcraft_notification,
)
from app.handcraft_inheritance.providers import (
    get_fulfillment_action_provider,
    get_video_review_action_provider,
)


ADMIN_ROLES = {"admin", "super_admin"}


def _get_db():
    from app.db import get_db

    return get_db()


def _utc_now_iso() -> str:
    from app.session_manager import utc_now_iso

    return utc_now_iso()


def emit_review_result(**payload):
    from app.messaging.events import emit_review_result as emit

    return emit(**payload)


def emit_fulfillment_issued(**payload):
    from app.messaging.events import emit_fulfillment_issued as emit

    return emit(**payload)


def emit_fulfillment_cancelled(**payload):
    from app.messaging.events import emit_fulfillment_cancelled as emit

    return emit(**payload)


def _require_action(action: dict) -> dict:
    if not isinstance(action, dict):
        raise AgriValidationError("管理动作格式不正确")
    return dict(action)


def _require_admin_role(action: dict, *keys: str) -> str:
    role = next(
        (
            action.get(key)
            for key in (*keys, "actor_role")
            if action.get(key) is not None
        ),
        None,
    )
    if role not in ADMIN_ROLES:
        raise AgriValidationError("无管理权限")
    return str(role)


def _require_teacher_owner(action: dict) -> int:
    if action.get("actor_role") != "teacher":
        raise AgriValidationError("仅教师可编辑视频")
    actor_id = _require_positive_int(
        action.get("actor_id"),
        "教师身份不能为空",
    )
    submitter_id = _require_positive_int(
        action.get("submitter_id"),
        "视频提交者不能为空",
    )
    if actor_id != submitter_id:
        raise AgriValidationError("只能编辑本人提交的视频")
    return submitter_id


def _require_positive_int(value: object, message: str) -> int:
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value <= 0
    ):
        raise AgriValidationError(message)
    return value


class DatabaseTeachingVideoReviewActionProvider:
    def apply(self, action: dict) -> dict:
        action = _require_action(action)
        video_id = str(action.get("video_id", "")).strip()
        if not video_id:
            raise AgriValidationError("视频标识不能为空")
        version = _require_positive_int(
            action.get("version"),
            "版本号必须是正整数",
        )
        requested_version = version
        operation = action.get("action")
        if operation not in {"approve", "reject", "edit"}:
            raise AgriValidationError("不支持的视频审核动作")
        if operation in {"approve", "reject"}:
            _require_admin_role(action, "reviewer_role")
        else:
            _require_teacher_owner(action)

        with _get_db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                """
                SELECT *
                FROM heritage_videos
                WHERE video_id = ?
                """,
                (video_id,),
            ).fetchone()
            if row is None:
                raise AgriNotFoundError("视频不存在")
            if int(row["version"]) != version:
                raise AgriValidationError("审核版本已变化")

            current_status = str(row["review_status"])
            now = _utc_now_iso()
            notification = None
            outbox_id = None
            if operation == "approve":
                if current_status != "pending":
                    raise AgriValidationError("当前视频状态不可审核通过")
                submitter_id = _require_positive_int(
                    action.get("submitter_id"),
                    "提交者标识不能为空",
                )
                cursor = db.execute(
                    """
                    UPDATE heritage_videos
                    SET review_status = 'approved',
                        rejection_opinion = NULL,
                        published_at = ?,
                        updated_at = ?,
                        version = ?
                    WHERE video_id = ?
                      AND version = ?
                      AND review_status = 'pending'
                    """,
                    (now, now, version + 1, video_id, version),
                )
                if cursor.rowcount != 1:
                    raise AgriValidationError("审核版本已变化")
                version += 1
                result_status = "approved"
                notification = {
                    "event_id": (
                        "handcraft-video-review:"
                        f"{video_id}:v{requested_version}:approve"
                    ),
                    "submitter_id": submitter_id,
                    "content_type": "handcraft_teaching_video",
                    "content_id": video_id,
                    "approved": True,
                    "opinion": None,
                }
                outbox_id = enqueue_handcraft_notification(
                    db,
                    event_type="review_approved",
                    payload=notification,
                )
            elif operation == "reject":
                if current_status != "pending":
                    raise AgriValidationError("当前视频状态不可驳回")
                opinion = str(action.get("opinion", "")).strip()
                if not opinion:
                    raise AgriValidationError("驳回意见不能为空")
                submitter_id = _require_positive_int(
                    action.get("submitter_id"),
                    "提交者标识不能为空",
                )
                cursor = db.execute(
                    """
                    UPDATE heritage_videos
                    SET review_status = 'rejected',
                        rejection_opinion = ?,
                        published_at = NULL,
                        updated_at = ?,
                        version = ?
                    WHERE video_id = ?
                      AND version = ?
                      AND review_status = 'pending'
                    """,
                    (opinion, now, version + 1, video_id, version),
                )
                if cursor.rowcount != 1:
                    raise AgriValidationError("审核版本已变化")
                version += 1
                result_status = "rejected"
                notification = {
                    "event_id": (
                        "handcraft-video-review:"
                        f"{video_id}:v{requested_version}:reject"
                    ),
                    "submitter_id": submitter_id,
                    "content_type": "handcraft_teaching_video",
                    "content_id": video_id,
                    "approved": False,
                    "opinion": opinion,
                }
                outbox_id = enqueue_handcraft_notification(
                    db,
                    event_type="review_rejected",
                    payload=notification,
                )
            else:
                if current_status not in {"pending", "approved"}:
                    raise AgriValidationError("当前视频状态不可编辑")
                title = str(action.get("title", row["title"])).strip()
                media_url = str(
                    action.get("media_url", row["media_url"])
                ).strip()
                if not title or not media_url:
                    raise AgriValidationError("视频标题和播放地址不能为空")
                if (
                    title == str(row["title"])
                    and media_url == str(row["media_url"])
                ):
                    result_status = current_status
                    notification = None
                    return {
                        "video_id": video_id,
                        "status": result_status,
                        "version": version,
                        "notification": notification,
                        "outbox_id": outbox_id,
                    }
                next_version = version + 1
                cursor = db.execute(
                    """
                    UPDATE heritage_videos
                    SET title = ?,
                        media_url = ?,
                        review_status = 'pending',
                        rejection_opinion = NULL,
                        published_at = NULL,
                        version = ?,
                        updated_at = ?
                    WHERE video_id = ?
                      AND version = ?
                      AND review_status IN ('pending', 'approved')
                    """,
                    (
                        title,
                        media_url,
                        next_version,
                        now,
                        video_id,
                        version,
                    ),
                )
                if cursor.rowcount != 1:
                    raise AgriValidationError("审核版本已变化")
                result_status = "pending"
                version = next_version

        return {
            "video_id": video_id,
            "status": result_status,
            "version": version,
            "notification": notification,
            "outbox_id": outbox_id,
        }


class DatabaseFulfillmentAdminActionProvider:
    def apply(self, action: dict) -> dict:
        action = _require_action(action)
        admin_role = _require_admin_role(action, "admin_role")
        fulfillment_id = _require_positive_int(
            action.get("fulfillment_id"),
            "履约单标识必须是正整数",
        )
        operation = action.get("action")
        if operation not in {"issue", "cancel_pending", "manual_verify"}:
            raise AgriValidationError("不支持的履约管理动作")

        if operation == "issue":
            status = _get_db().execute(
                """
                SELECT status, issued_at
                FROM fulfillments
                WHERE id = ?
                """,
                (fulfillment_id,),
            ).fetchone()
            if status is None:
                raise AgriNotFoundError("履约单不存在")
            if (
                status["status"] != "pending"
                and not (
                    status["status"] == "issued"
                    and status["issued_at"] is not None
                )
            ):
                raise AgriValidationError("当前履约状态不可发放")
            return issue_fulfillment(
                fulfillment_id,
                role=admin_role,
                emit_notification=False,
            )
        if operation == "cancel_pending":
            return cancel_pending_fulfillment(
                fulfillment_id,
                role=admin_role,
                emit_notification=False,
            )
        return manual_verify_fulfillment(
            fulfillment_id,
            role=admin_role,
        )


def apply_video_review(action: dict) -> dict:
    result = get_video_review_action_provider().apply(action)
    outbox_id = result.get("outbox_id")
    if outbox_id is not None:
        deliver_after_commit(int(outbox_id))
    return {
        key: value
        for key, value in result.items()
        if key not in {"notification", "outbox_id"}
    }


def apply_fulfillment_admin_action(action: dict) -> dict:
    result = get_fulfillment_action_provider().apply(action)
    notification = result.get("notification")
    outbox_id = result.get("outbox_id")
    if outbox_id is not None and notification is not None:
        if result.get("notification_type") == "cancelled":
            deliver_fulfillment_outbox(
                outbox_id,
                emit_callback=lambda payload: emit_fulfillment_cancelled(
                    **payload
                ),
            )
        else:
            deliver_fulfillment_outbox(
                outbox_id,
                emit_callback=lambda payload: emit_fulfillment_issued(
                    **payload
                ),
            )
    elif notification is not None:
        if notification.get("restored_points") is not None:
            emit_fulfillment_cancelled(**notification)
        else:
            emit_fulfillment_issued(**notification)
    return {
        key: value
        for key, value in result.items()
        if key not in {"notification", "outbox_id", "notification_type"}
    }
