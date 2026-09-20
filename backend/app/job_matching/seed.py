from __future__ import annotations

import json
import os
import sqlite3

from app.enterprise_console.providers import get_job_position_provider
from app.job_matching.skill_profile import list_skill_outcomes


DEMO_TIMESTAMP = "2026-09-19T09:00:00+08:00"
DEMO_RESUME_REVISION = 1
DEMO_AVAILABLE_JOB_ID = "job-demo-approved"
DEMO_CLOSED_JOB_ID = "job-demo-deleted-for-007"

DEMO_RESUME = {
    "education_experiences": [
        {
            "school": "粤乡职业学院",
            "major": "电子商务",
            "degree": "专科",
            "start_date": "2022-09",
            "end_date": "2025-06",
        }
    ],
    "work_experiences": [
        {
            "company": "荔乡示范农场",
            "role": "运营助理",
            "start_date": "2025-07",
            "end_date": "2026-06",
            "description": "负责直播数据记录与选品整理。",
        }
    ],
    "skills": ["直播运营", "客户沟通"],
}

DEMO_CLOSED_FAVORITE = {
    "job_id": DEMO_CLOSED_JOB_ID,
    "title_snapshot": "已关闭岗位（演示）",
    "enterprise_name_snapshot": "粤乡演示企业",
    "salary_snapshot": "6k-8k",
    "location_snapshot": "广州",
    "description_snapshot": "用于就业对接演示的已关闭岗位快照。",
}


def _configured_username(environment_name: str, default: str) -> str:
    return os.environ.get(environment_name, "").strip() or default


def _require_student_id(connection: sqlite3.Connection) -> int:
    username = _configured_username(
        "DEV_SEED_STUDENT_USERNAME",
        "student_demo",
    )
    row = connection.execute(
        """
        SELECT id
        FROM users
        WHERE username = ?
          AND role = 'student'
          AND is_enabled = 1
        """,
        (username,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Demo student user is missing: {username}")
    return int(row["id"])


def _require_resume_id(
    connection: sqlite3.Connection,
    student_id: int,
) -> int:
    row = connection.execute(
        """
        SELECT id
        FROM resumes
        WHERE user_id = ?
        """,
        (student_id,),
    ).fetchone()
    if row is None:
        raise ValueError("Demo student resume relation is missing")
    return int(row["id"])


def _resume_json() -> tuple[str, str, str]:
    return (
        json.dumps(
            DEMO_RESUME["education_experiences"],
            ensure_ascii=False,
        ),
        json.dumps(
            DEMO_RESUME["work_experiences"],
            ensure_ascii=False,
        ),
        json.dumps(DEMO_RESUME["skills"], ensure_ascii=False),
    )


def _seed_resume(
    connection: sqlite3.Connection,
    student_id: int,
) -> int:
    resume_id = _require_resume_id(connection, student_id)
    education_json, work_json, skills_json = _resume_json()
    connection.execute(
        """
        UPDATE resumes
        SET education_json = ?,
            work_experiences_json = ?,
            skills_json = ?,
            version = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            education_json,
            work_json,
            skills_json,
            DEMO_RESUME_REVISION,
            DEMO_TIMESTAMP,
            resume_id,
        ),
    )
    connection.execute(
        """
        INSERT INTO resume_revisions (
            resume_id,
            version,
            education_json,
            work_experiences_json,
            skills_json,
            saved_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (resume_id, version) DO UPDATE SET
            education_json = excluded.education_json,
            work_experiences_json = excluded.work_experiences_json,
            skills_json = excluded.skills_json,
            saved_at = excluded.saved_at
        """,
        (
            resume_id,
            DEMO_RESUME_REVISION,
            education_json,
            work_json,
            skills_json,
            DEMO_TIMESTAMP,
        ),
    )
    return resume_id


def _seed_job_tags(
    connection: sqlite3.Connection,
    student_id: int,
) -> int:
    tag_ids = [
        int(row["id"])
        for row in connection.execute(
            """
            SELECT id
            FROM interest_tags
            WHERE group_key = 'job'
              AND is_active = 1
            ORDER BY id
            """
        ).fetchall()
    ]
    connection.executemany(
        """
        INSERT OR IGNORE INTO student_interest_tags (user_id, tag_id)
        VALUES (?, ?)
        """,
        ((student_id, tag_id) for tag_id in tag_ids),
    )
    return len(tag_ids)


def _seed_visibility(
    connection: sqlite3.Connection,
    student_id: int,
) -> tuple[int, int, int]:
    item_ids = sorted(
        {
            str(item["item_id"])
            for item in list_skill_outcomes(student_id)
        }
    )
    fixtures = [
        (item_id, 1 if index == 0 else 0)
        for index, item_id in enumerate(item_ids[:2])
    ]
    connection.executemany(
        """
        INSERT INTO skill_visibility_settings (
            user_id,
            item_id,
            visible,
            updated_at
        )
        VALUES (?, ?, ?, ?)
        ON CONFLICT (user_id, item_id) DO UPDATE SET
            visible = excluded.visible,
            updated_at = excluded.updated_at
        """,
        (
            (student_id, item_id, visible, DEMO_TIMESTAMP)
            for item_id, visible in fixtures
        ),
    )
    visible_count = sum(visible for _, visible in fixtures)
    return len(fixtures), visible_count, len(fixtures) - visible_count


def _available_favorite() -> dict[str, str]:
    job = get_job_position_provider().get_published_position(
        job_id=DEMO_AVAILABLE_JOB_ID,
    )
    if not isinstance(job, dict):
        raise ValueError("Demo approved enterprise job is missing")
    required = (
        "job_id",
        "title",
        "enterprise_name",
        "salary",
        "location",
        "description",
    )
    missing = [field for field in required if field not in job]
    if missing:
        raise ValueError(
            "Demo approved enterprise job is incomplete: "
            + ", ".join(missing)
        )
    return {
        "job_id": str(job["job_id"]),
        "title_snapshot": str(job["title"]),
        "enterprise_name_snapshot": str(job["enterprise_name"]),
        "salary_snapshot": str(job["salary"]),
        "location_snapshot": str(job["location"]),
        "description_snapshot": str(job["description"]),
    }


def _seed_favorites(
    connection: sqlite3.Connection,
    student_id: int,
) -> int:
    snapshots = [
        _available_favorite(),
        DEMO_CLOSED_FAVORITE,
    ]
    connection.executemany(
        """
        INSERT INTO job_favorites (
            user_id,
            job_id,
            title_snapshot,
            enterprise_name_snapshot,
            salary_snapshot,
            location_snapshot,
            description_snapshot,
            favorited_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT (user_id, job_id) DO UPDATE SET
            title_snapshot = excluded.title_snapshot,
            enterprise_name_snapshot =
                excluded.enterprise_name_snapshot,
            salary_snapshot = excluded.salary_snapshot,
            location_snapshot = excluded.location_snapshot,
            description_snapshot = excluded.description_snapshot,
            updated_at = excluded.updated_at
        """,
        (
            (
                student_id,
                snapshot["job_id"],
                snapshot["title_snapshot"],
                snapshot["enterprise_name_snapshot"],
                snapshot["salary_snapshot"],
                snapshot["location_snapshot"],
                snapshot["description_snapshot"],
                DEMO_TIMESTAMP,
                DEMO_TIMESTAMP,
            )
            for snapshot in snapshots
        ),
    )
    return len(snapshots)


def seed_job_matching_fixtures(
    connection: sqlite3.Connection,
) -> dict[str, int]:
    student_id = _require_student_id(connection)
    _seed_resume(connection, student_id)
    tags = _seed_job_tags(connection, student_id)
    visibility, visible, hidden = _seed_visibility(
        connection,
        student_id,
    )
    favorites = _seed_favorites(connection, student_id)
    return {
        "resumes": 1,
        "resume_revisions": 1,
        "tags": tags,
        "visibility": visibility,
        "visible": visible,
        "hidden": hidden,
        "favorites": favorites,
    }


__all__ = [
    "DEMO_CLOSED_FAVORITE",
    "DEMO_RESUME",
    "DEMO_RESUME_REVISION",
    "seed_job_matching_fixtures",
]
