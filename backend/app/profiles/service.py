from __future__ import annotations

from datetime import datetime, timezone

from app.db import get_db
from app.tags.service import InvalidInterestTagError, replace_student_tags


LEARNING_DIRECTIONS = {
    "agriculture",
    "ecommerce",
    "handcraft",
    "comprehensive",
}


class InvalidStudentProfileError(ValueError):
    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("Invalid student profile")
        self.errors = errors


def _selected_tags(user_id: int) -> list[dict]:
    rows = get_db().execute(
        """
        SELECT t.id, t.name
        FROM student_interest_tags sit
        JOIN interest_tags t ON t.id = sit.tag_id
        WHERE sit.user_id = ?
        ORDER BY
            CASE t.group_key
                WHEN 'crop' THEN 1
                WHEN 'skill' THEN 2
                WHEN 'job' THEN 3
            END,
            t.sort_order,
            t.id
        """,
        (user_id,),
    ).fetchall()
    return [
        {"id": int(row["id"]), "name": str(row["name"])}
        for row in rows
    ]


def get_student_profile(user_id: int) -> dict:
    row = get_db().execute(
        """
        SELECT
            u.name,
            sp.contact,
            sp.learning_direction
        FROM users u
        JOIN student_profiles sp ON sp.user_id = u.id
        WHERE u.id = ?
        """,
        (user_id,),
    ).fetchone()
    if row is None:
        raise LookupError("Student profile not found")

    tags = _selected_tags(user_id)
    return {
        "name": row["name"],
        "contact": row["contact"],
        "learning_direction": row["learning_direction"],
        "tag_ids": [tag["id"] for tag in tags],
    }


def update_student_profile(user_id: int, payload: dict) -> dict:
    name = str(payload.get("name", "")).strip()
    contact = str(payload.get("contact", "")).strip()
    learning_direction = str(
        payload.get("learning_direction", "comprehensive")
    ).strip()
    tag_ids = payload.get("tag_ids", [])

    errors: dict[str, str] = {}
    if not name:
        errors["name"] = "姓名不能为空"
    if learning_direction not in LEARNING_DIRECTIONS:
        errors["learning_direction"] = "学习方向不正确"
    if not isinstance(tag_ids, list) or any(
        not isinstance(tag_id, int) or isinstance(tag_id, bool)
        for tag_id in tag_ids
    ):
        errors["tag_ids"] = "兴趣标签格式不正确"
    if errors:
        raise InvalidStudentProfileError(errors)

    now = datetime.now(timezone.utc).isoformat()
    db = get_db()
    try:
        db.execute(
            "UPDATE users SET name = ?, updated_at = ? WHERE id = ?",
            (name, now, user_id),
        )
        db.execute(
            """
            UPDATE student_profiles
            SET contact = ?, learning_direction = ?, updated_at = ?
            WHERE user_id = ?
            """,
            (contact, learning_direction, now, user_id),
        )
        replace_student_tags(user_id, tag_ids)
    except InvalidInterestTagError as error:
        db.rollback()
        raise InvalidStudentProfileError(error.errors) from error
    except Exception:
        db.rollback()
        raise

    return get_student_profile(user_id)


def get_profile_preferences(user_id: int) -> dict:
    profile = get_student_profile(user_id)
    tags = _selected_tags(user_id)
    return {
        "user_id": user_id,
        "learning_direction": profile["learning_direction"],
        "interest_tag_ids": [tag["id"] for tag in tags],
        "interest_tag_names": [tag["name"] for tag in tags],
    }
