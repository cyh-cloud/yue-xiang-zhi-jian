from __future__ import annotations

# Task 14 must overwrite actor/reviewer/admin role and identity fields from the
# active 01 session before calling these services. Raw client payload values
# must never be treated as trusted authorization data.

from app.agri_skills.errors import AgriNotFoundError, AgriValidationError
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
        operation = action.get("action")
        if operation not in {"approve", "reject", "edit"}:
            raise AgriValidationError("不支持的视频审核动作")
        if operation in {"approve", "reject"}:
            _require_admin_role(action, "reviewer_role")
        else:
            _require_teacher_owner(action)

        with _get_db() as db:
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
                        updated_at = ?
                    WHERE video_id = ? AND review_status = 'pending'
                    """,
                    (now, now, video_id),
                )
                if cursor.rowcount != 1:
                    raise AgriValidationError("当前视频状态不可审核通过")
                result_status = "approved"
                notification = {
                    "event_id": (
                        f"handcraft-video-review:{video_id}:v{version}:approve"
                    ),
                    "submitter_id": submitter_id,
                    "content_type": "handcraft_teaching_video",
                    "content_id": video_id,
                    "approved": True,
                    "opinion": None,
                }
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
                        updated_at = ?
                    WHERE video_id = ? AND review_status = 'pending'
                    """,
                    (opinion, now, video_id),
                )
                if cursor.rowcount != 1:
                    raise AgriValidationError("当前视频状态不可驳回")
                result_status = "rejected"
                notification = {
                    "event_id": (
                        f"handcraft-video-review:{video_id}:v{version}:reject"
                    ),
                    "submitter_id": submitter_id,
                    "content_type": "handcraft_teaching_video",
                    "content_id": video_id,
                    "approved": False,
                    "opinion": opinion,
                }
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
                    }
                next_version = version + 1
                db.execute(
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
                    """,
                    (
                        title,
                        media_url,
                        next_version,
                        now,
                        video_id,
                    ),
                )
                result_status = "pending"
                version = next_version

        return {
            "video_id": video_id,
            "status": result_status,
            "version": version,
            "notification": notification,
        }


class DatabaseFulfillmentAdminActionProvider:
    def apply(self, action: dict) -> dict:
        action = _require_action(action)
        _require_admin_role(action, "admin_role")
        fulfillment_id = _require_positive_int(
            action.get("fulfillment_id"),
            "履约单标识必须是正整数",
        )
        operation = action.get("action")
        if operation not in {"issue", "cancel_pending", "manual_verify"}:
            raise AgriValidationError("不支持的履约管理动作")

        with _get_db() as db:
            row = db.execute(
                """
                SELECT
                    f.id,
                    f.user_id,
                    f.status,
                    r.reward_name,
                    r.points_cost
                FROM fulfillments f
                JOIN redemptions r ON r.id = f.redemption_id
                WHERE f.id = ?
                """,
                (fulfillment_id,),
            ).fetchone()
            if row is None:
                raise AgriNotFoundError("履约单不存在")

            current_status = str(row["status"])
            now = _utc_now_iso()
            notification = None
            if operation == "issue":
                if current_status != "pending":
                    raise AgriValidationError("当前履约状态不可发放")
                cursor = db.execute(
                    """
                    UPDATE fulfillments
                    SET status = 'issued',
                        issued_at = ?,
                        updated_at = ?
                    WHERE id = ? AND status = 'pending'
                    """,
                    (now, now, fulfillment_id),
                )
                if cursor.rowcount != 1:
                    raise AgriValidationError("当前履约状态不可发放")
                db.execute(
                    """
                    UPDATE redemptions
                    SET status = 'issued', updated_at = ?
                    WHERE id = (
                        SELECT redemption_id
                        FROM fulfillments
                        WHERE id = ?
                    )
                    """,
                    (now, fulfillment_id),
                )
                result_status = "issued"
                notification = {
                    "event_id": (
                        f"handcraft-fulfillment:{fulfillment_id}:issue"
                    ),
                    "student_id": int(row["user_id"]),
                    "fulfillment_id": str(fulfillment_id),
                    "prize_name": str(row["reward_name"]),
                }
            elif operation == "cancel_pending":
                if current_status != "pending":
                    raise AgriValidationError("当前履约状态不可取消")
                cursor = db.execute(
                    """
                    UPDATE fulfillments
                    SET status = 'canceled',
                        canceled_at = ?,
                        updated_at = ?
                    WHERE id = ? AND status = 'pending'
                    """,
                    (now, now, fulfillment_id),
                )
                if cursor.rowcount != 1:
                    raise AgriValidationError("当前履约状态不可取消")
                db.execute(
                    """
                    UPDATE redemptions
                    SET status = 'canceled',
                        canceled_at = ?,
                        updated_at = ?
                    WHERE id = (
                        SELECT redemption_id
                        FROM fulfillments
                        WHERE id = ?
                    )
                    """,
                    (now, now, fulfillment_id),
                )
                result_status = "canceled"
                notification = {
                    "event_id": (
                        f"handcraft-fulfillment:{fulfillment_id}:cancel_pending"
                    ),
                    "student_id": int(row["user_id"]),
                    "fulfillment_id": str(fulfillment_id),
                    "prize_name": str(row["reward_name"]),
                    "restored_points": int(row["points_cost"]),
                }
            else:
                if current_status != "issued":
                    raise AgriValidationError("当前履约状态不可手工核销")
                cursor = db.execute(
                    """
                    UPDATE fulfillments
                    SET status = 'verified',
                        verified_at = ?,
                        updated_at = ?
                    WHERE id = ? AND status = 'issued'
                    """,
                    (now, now, fulfillment_id),
                )
                if cursor.rowcount != 1:
                    raise AgriValidationError("当前履约状态不可手工核销")
                db.execute(
                    """
                    UPDATE redemptions
                    SET status = 'verified', updated_at = ?
                    WHERE id = (
                        SELECT redemption_id
                        FROM fulfillments
                        WHERE id = ?
                    )
                    """,
                    (now, fulfillment_id),
                )
                result_status = "verified"

        return {
            "fulfillment_id": fulfillment_id,
            "status": result_status,
            "notification": notification,
        }


def apply_video_review(action: dict) -> dict:
    result = get_video_review_action_provider().apply(action)
    notification = result.get("notification")
    if notification is not None:
        emit_review_result(**notification)
    return {
        key: value
        for key, value in result.items()
        if key != "notification"
    }


def apply_fulfillment_admin_action(action: dict) -> dict:
    result = get_fulfillment_action_provider().apply(action)
    notification = result.get("notification")
    if notification is not None:
        if notification.get("restored_points") is not None:
            emit_fulfillment_cancelled(**notification)
        else:
            emit_fulfillment_issued(**notification)
    return {
        key: value
        for key, value in result.items()
        if key != "notification"
    }
