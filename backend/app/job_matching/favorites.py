from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.db import get_db
from app.job_matching.errors import JobUnavailableError
from app.job_matching.jobs import (
    get_published_job,
    list_published_jobs,
)


def _now_iso() -> str:
    return datetime.now(
        ZoneInfo("Asia/Shanghai")
    ).isoformat(timespec="seconds")


def list_favorites(student_id: int) -> list[dict]:
    published = {
        job["job_id"]: job
        for job in list_published_jobs(student_id)["jobs"]
    }
    rows = get_db().execute(
        """
        SELECT *
        FROM job_favorites
        WHERE user_id = ?
        ORDER BY favorited_at DESC, job_id ASC
        """,
        (student_id,),
    ).fetchall()
    result = []
    for row in rows:
        current = published.get(str(row["job_id"]))
        if current is not None:
            _persist_favorite_snapshot(student_id, current)
        base = (
            {
                **current,
                "title_snapshot": str(current["title"]),
                "enterprise_name_snapshot": str(
                    current["enterprise_name"]
                ),
            }
            if current
            else {
                "job_id": str(row["job_id"]),
                "title": str(row["title_snapshot"]),
                "enterprise_name": str(
                    row["enterprise_name_snapshot"]
                ),
                "salary": str(row["salary_snapshot"]),
                "location": str(row["location_snapshot"]),
                "description": str(row["description_snapshot"]),
                "title_snapshot": str(row["title_snapshot"]),
                "enterprise_name_snapshot": str(
                    row["enterprise_name_snapshot"]
                ),
            }
        )
        result.append(
            {
                **base,
                "favorited_at": str(row["favorited_at"]),
                "closed": current is None,
            }
        )
    return result


def _persist_favorite_snapshot(student_id: int, job: dict) -> None:
    with get_db() as db:
        db.execute(
            """
            UPDATE job_favorites
            SET title_snapshot = ?,
                enterprise_name_snapshot = ?,
                salary_snapshot = ?,
                location_snapshot = ?,
                description_snapshot = ?,
                updated_at = ?
            WHERE user_id = ? AND job_id = ?
            """,
            (
                job["title"],
                job["enterprise_name"],
                job["salary"],
                job["location"],
                job["description"],
                _now_iso(),
                student_id,
                job["job_id"],
            ),
        )


def add_favorite(student_id: int, job_id: str) -> dict:
    job = get_published_job(student_id, job_id)
    if job is None:
        raise JobUnavailableError("岗位已关闭或暂不可收藏")
    now = _now_iso()
    with get_db() as db:
        db.execute(
            """
            INSERT INTO job_favorites (
                user_id, job_id, title_snapshot,
                enterprise_name_snapshot, salary_snapshot,
                location_snapshot, description_snapshot,
                favorited_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, job_id) DO UPDATE SET
                title_snapshot = excluded.title_snapshot,
                enterprise_name_snapshot =
                    excluded.enterprise_name_snapshot,
                salary_snapshot = excluded.salary_snapshot,
                location_snapshot = excluded.location_snapshot,
                description_snapshot = excluded.description_snapshot,
                updated_at = excluded.updated_at
            """,
            (
                student_id,
                job_id,
                job["title"],
                job["enterprise_name"],
                job["salary"],
                job["location"],
                job["description"],
                now,
                now,
            ),
        )
    return next(
        item
        for item in list_favorites(student_id)
        if item["job_id"] == job_id
    )


def remove_favorite(student_id: int, job_id: str) -> dict:
    with get_db() as db:
        db.execute(
            """
            DELETE FROM job_favorites
            WHERE user_id = ? AND job_id = ?
            """,
            (student_id, job_id),
        )
    return {"job_id": job_id, "favorited": False}


__all__ = [
    "add_favorite",
    "list_favorites",
    "remove_favorite",
]
