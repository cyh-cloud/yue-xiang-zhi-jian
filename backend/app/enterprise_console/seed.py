from __future__ import annotations

import json
import os
import sqlite3


DEMO_TIMESTAMP = "2026-09-18T09:00:00+08:00"

DEMO_JOBS = (
    {
        "job_id": "job-demo-pending",
        "title": "待审核农业技术员（演示）",
        "salary": "6k-8k",
        "location": "广州",
        "category_name": "农业技术员",
        "description": "用于企业工作台演示的待审核职位。",
        "review_status": "pending",
        "version": 1,
        "published_at": None,
        "rejection_opinion": None,
    },
    {
        "job_id": "job-demo-approved",
        "title": "电商运营专员（演示）",
        "salary": "7k-9k",
        "location": "佛山",
        "category_name": "电商运营",
        "description": "用于企业工作台演示的已上架职位。",
        "review_status": "approved",
        "version": 1,
        "published_at": "2026-09-18T09:00:00+08:00",
        "rejection_opinion": None,
    },
    {
        "job_id": "job-demo-rejected",
        "title": "客服专员（演示）",
        "salary": "5k-7k",
        "location": "东莞",
        "category_name": "客服专员",
        "description": "用于企业工作台演示的已驳回职位。",
        "review_status": "rejected",
        "version": 2,
        "published_at": None,
        "rejection_opinion": "请补充岗位职责。",
    },
)

DEMO_APPLICATIONS = (
    {
        "application_id": "application-demo-pending",
        "job_id": "job-demo-approved",
        "student_index": 0,
        "status": "pending",
        "status_version": 1,
        "resume_snapshot": {
            "education": "电子商务专科",
            "skills": ["店铺运营", "数据记录"],
        },
        "skill_profile": None,
        "position_closed_at": None,
        "submitted_at": "2026-09-18T10:00:00+08:00",
    },
    {
        "application_id": "application-demo-viewed",
        "job_id": "job-demo-approved",
        "student_index": 1,
        "status": "viewed",
        "status_version": 2,
        "resume_snapshot": {
            "education": "现代农业技术专科",
            "skills": ["田间管理"],
        },
        "skill_profile": {
            "items": [
                {
                    "title": "荔枝保果实践",
                    "outcome": "完成果园实地记录。",
                }
            ]
        },
        "position_closed_at": None,
        "submitted_at": "2026-09-18T11:00:00+08:00",
    },
    {
        "application_id": "application-demo-intent",
        "job_id": "job-demo-approved",
        "student_index": 2,
        "status": "intent",
        "status_version": 3,
        "resume_snapshot": {
            "education": "市场营销本科",
            "skills": ["内容策划", "客户沟通"],
        },
        "skill_profile": {
            "items": [
                {
                    "title": "乡村品牌策划",
                    "outcome": "完成课程展示方案。",
                }
            ]
        },
        "position_closed_at": None,
        "submitted_at": "2026-09-18T12:00:00+08:00",
    },
    {
        "application_id": "application-demo-unsuitable",
        "job_id": "job-demo-rejected",
        "student_index": 0,
        "status": "unsuitable",
        "status_version": 2,
        "resume_snapshot": {
            "education": "电子商务专科",
            "skills": ["售后沟通"],
        },
        "skill_profile": None,
        "position_closed_at": None,
        "submitted_at": "2026-09-18T13:00:00+08:00",
    },
    {
        "application_id": "application-demo-closed-pending",
        "job_id": "job-demo-pending",
        "student_index": 1,
        "status": "pending",
        "status_version": 2,
        "resume_snapshot": {
            "education": "现代农业技术专科",
            "skills": ["农业资料整理"],
        },
        "skill_profile": None,
        "position_closed_at": "2026-09-18T14:00:00+08:00",
        "submitted_at": "2026-09-18T14:00:00+08:00",
    },
)


def _configured_username(environment_name: str, default: str) -> str:
    return os.environ.get(environment_name, "").strip() or default


def _require_demo_user(
    connection: sqlite3.Connection,
    *,
    username: str,
    role: str,
) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT id, username, password_hash, name, role, is_enabled
        FROM users
        WHERE username = ?
        """,
        (username,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Demo {role} user is missing: {username}")
    if row["role"] != role:
        raise ValueError(f"Demo {role} user has the wrong role: {username}")
    if not int(row["is_enabled"]):
        raise ValueError(f"Demo {role} user is disabled: {username}")
    return row


def _ensure_demo_applicant(
    connection: sqlite3.Connection,
    *,
    base_student: sqlite3.Row,
    index: int,
) -> sqlite3.Row:
    username = f"{base_student['username']}_applicant_{index}"
    name = f"{base_student['name']}演示申请{index}"
    existing = connection.execute(
        """
        SELECT id, username, password_hash, name, role, is_enabled
        FROM users
        WHERE username = ?
        """,
        (username,),
    ).fetchone()
    if existing is not None and existing["role"] != "student":
        raise ValueError(
            f"Demo applicant username conflicts with another role: {username}"
        )

    if existing is None:
        cursor = connection.execute(
            """
            INSERT INTO users (
                username,
                password_hash,
                name,
                role,
                is_enabled,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, 'student', 1, ?, ?)
            """,
            (
                username,
                base_student["password_hash"],
                name,
                DEMO_TIMESTAMP,
                DEMO_TIMESTAMP,
            ),
        )
        user_id = int(cursor.lastrowid)
    else:
        user_id = int(existing["id"])
        connection.execute(
            """
            UPDATE users
            SET name = ?, role = 'student', is_enabled = 1, updated_at = ?
            WHERE id = ?
            """,
            (name, DEMO_TIMESTAMP, user_id),
        )

    connection.execute(
        """
        INSERT INTO student_profiles (
            user_id, learning_direction, updated_at
        )
        VALUES (?, 'ecommerce', ?)
        ON CONFLICT (user_id) DO NOTHING
        """,
        (user_id, DEMO_TIMESTAMP),
    )
    connection.execute(
        """
        INSERT INTO resumes (user_id, created_at)
        VALUES (?, ?)
        ON CONFLICT (user_id) DO NOTHING
        """,
        (user_id, DEMO_TIMESTAMP),
    )
    return connection.execute(
        """
        SELECT id, username, password_hash, name, role, is_enabled
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()


def _resolve_job_category(
    connection: sqlite3.Connection,
    category_name: str,
) -> int:
    rows = connection.execute(
        """
        SELECT id
        FROM interest_tags
        WHERE group_key = 'job'
          AND name = ?
          AND is_active = 1
        ORDER BY id
        """,
        (category_name,),
    ).fetchall()
    if len(rows) != 1:
        raise ValueError(
            f"Demo job category is missing or ambiguous: {category_name}"
        )
    return int(rows[0]["id"])


def seed_enterprise_console_fixtures(
    connection: sqlite3.Connection,
) -> dict[str, int]:
    enterprise_username = _configured_username(
        "DEV_SEED_ENTERPRISE_USERNAME",
        "enterprise_demo",
    )
    student_username = _configured_username(
        "DEV_SEED_STUDENT_USERNAME",
        "student_demo",
    )
    enterprise = _require_demo_user(
        connection,
        username=enterprise_username,
        role="enterprise",
    )
    base_student = _require_demo_user(
        connection,
        username=student_username,
        role="student",
    )

    students = [
        base_student,
        _ensure_demo_applicant(
            connection,
            base_student=base_student,
            index=2,
        ),
        _ensure_demo_applicant(
            connection,
            base_student=base_student,
            index=3,
        ),
    ]
    jobs_by_id = {}
    for job in DEMO_JOBS:
        category_id = _resolve_job_category(
            connection,
            job["category_name"],
        )
        jobs_by_id[job["job_id"]] = job
        connection.execute(
            """
            INSERT INTO job_positions (
                job_id,
                enterprise_id,
                title,
                salary,
                location,
                category_id,
                category_name,
                description,
                review_status,
                version,
                rejection_opinion,
                published_at,
                deleted_at,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)
            ON CONFLICT (job_id) DO UPDATE SET
                enterprise_id = excluded.enterprise_id,
                title = excluded.title,
                salary = excluded.salary,
                location = excluded.location,
                category_id = excluded.category_id,
                category_name = excluded.category_name,
                description = excluded.description,
                review_status = excluded.review_status,
                version = excluded.version,
                rejection_opinion = excluded.rejection_opinion,
                published_at = excluded.published_at,
                deleted_at = NULL,
                created_at = excluded.created_at,
                updated_at = excluded.updated_at
            """,
            (
                job["job_id"],
                enterprise["id"],
                job["title"],
                job["salary"],
                job["location"],
                category_id,
                job["category_name"],
                job["description"],
                job["review_status"],
                job["version"],
                job["rejection_opinion"],
                job["published_at"],
                DEMO_TIMESTAMP,
                DEMO_TIMESTAMP,
            ),
        )

    for application in DEMO_APPLICATIONS:
        student = students[application["student_index"]]
        job = jobs_by_id[application["job_id"]]
        skill_profile = application["skill_profile"]
        skill_profile_json = (
            json.dumps(skill_profile, ensure_ascii=False)
            if skill_profile is not None
            else None
        )
        connection.execute(
            """
            INSERT INTO job_applications (
                application_id,
                job_id,
                enterprise_id,
                student_id,
                student_name,
                job_title_snapshot,
                resume_snapshot_json,
                skill_profile_snapshot_json,
                skill_profile_attached,
                status,
                status_version,
                position_closed_at,
                close_reason,
                idempotency_key,
                submitted_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            ON CONFLICT (application_id) DO UPDATE SET
                job_id = excluded.job_id,
                enterprise_id = excluded.enterprise_id,
                student_id = excluded.student_id,
                student_name = excluded.student_name,
                job_title_snapshot = excluded.job_title_snapshot,
                resume_snapshot_json = excluded.resume_snapshot_json,
                skill_profile_snapshot_json =
                    excluded.skill_profile_snapshot_json,
                skill_profile_attached = excluded.skill_profile_attached,
                status = excluded.status,
                status_version = excluded.status_version,
                position_closed_at = excluded.position_closed_at,
                close_reason = excluded.close_reason,
                idempotency_key = excluded.idempotency_key,
                submitted_at = excluded.submitted_at,
                updated_at = excluded.updated_at
            """,
            (
                application["application_id"],
                application["job_id"],
                enterprise["id"],
                student["id"],
                student["name"],
                job["title"],
                json.dumps(
                    application["resume_snapshot"],
                    ensure_ascii=False,
                ),
                skill_profile_json,
                int(skill_profile_json is not None),
                application["status"],
                application["status_version"],
                application["position_closed_at"],
                (
                    "position_deleted"
                    if application["position_closed_at"] is not None
                    else None
                ),
                f"seed:{application['application_id']}",
                application["submitted_at"],
                application["submitted_at"],
            ),
        )

    return {
        "jobs": len(DEMO_JOBS),
        "applications": len(DEMO_APPLICATIONS),
        "students": len(students),
    }


__all__ = [
    "DEMO_APPLICATIONS",
    "DEMO_JOBS",
    "seed_enterprise_console_fixtures",
]
