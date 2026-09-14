from __future__ import annotations

import sqlite3

from app.db import get_db


class InvalidInterestTagError(ValueError):
    def __init__(self, message: str = "兴趣标签不存在或已停用") -> None:
        super().__init__(message)
        self.errors = {"tag_ids": message}


def list_interest_tags() -> list[dict]:
    rows = get_db().execute(
        """
        SELECT id, group_key, name
        FROM interest_tags
        WHERE is_active = 1
        ORDER BY
            CASE group_key
                WHEN 'crop' THEN 1
                WHEN 'skill' THEN 2
                WHEN 'job' THEN 3
            END,
            sort_order,
            id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def replace_student_tags(user_id: int, tag_ids: list[int]) -> None:
    unique_ids = set(tag_ids)
    db = get_db()

    with db:
        if unique_ids:
            placeholders = ",".join("?" for _ in unique_ids)
            active_rows = db.execute(
                f"""
                SELECT id
                FROM interest_tags
                WHERE is_active = 1
                  AND id IN ({placeholders})
                """,
                tuple(unique_ids),
            ).fetchall()
            active_ids = {int(row["id"]) for row in active_rows}
            if active_ids != unique_ids:
                raise InvalidInterestTagError

        db.execute(
            "DELETE FROM student_interest_tags WHERE user_id = ?",
            (user_id,),
        )
        if unique_ids:
            db.executemany(
                """
                INSERT INTO student_interest_tags (user_id, tag_id)
                VALUES (?, ?)
                """,
                ((user_id, tag_id) for tag_id in unique_ids),
            )
