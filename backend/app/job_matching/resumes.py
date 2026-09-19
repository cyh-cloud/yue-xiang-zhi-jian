from __future__ import annotations

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from app.db import get_db
from app.job_matching.errors import (
    JobMatchingValidationError,
    ResumeConflictError,
    ResumeRequiredError,
)


EDUCATION_REQUIRED_FIELDS = ("school", "major", "start_date")
EDUCATION_OPTIONAL_FIELDS = ("degree", "end_date")
WORK_REQUIRED_FIELDS = ("company", "role", "start_date")
WORK_OPTIONAL_FIELDS = ("end_date", "description")


def _now_iso() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def _normalize_items(
    value,
    required_fields,
    optional_fields,
    field_name,
):
    if not isinstance(value, list):
        raise JobMatchingValidationError(f"{field_name} 必须是列表")
    normalized = []
    for item in value:
        if not isinstance(item, dict):
            raise JobMatchingValidationError(f"{field_name} 条目格式不正确")
        normalized_item = {}
        for key in required_fields:
            text = str(item.get(key, "")).strip()
            if not text:
                raise JobMatchingValidationError(
                    f"{field_name}.{key} 不能为空",
                    details={f"{field_name}.{key}": "不能为空"},
                )
            normalized_item[key] = text
        for key in optional_fields:
            normalized_item[key] = str(item.get(key, "")).strip()
        normalized.append(normalized_item)
    return normalized


def _normalize_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise JobMatchingValidationError("简历格式不正确")
    education = _normalize_items(
        payload.get("education_experiences", []),
        EDUCATION_REQUIRED_FIELDS,
        EDUCATION_OPTIONAL_FIELDS,
        "education_experiences",
    )
    work = _normalize_items(
        payload.get("work_experiences", []),
        WORK_REQUIRED_FIELDS,
        WORK_OPTIONAL_FIELDS,
        "work_experiences",
    )
    raw_skills = payload.get("skills", [])
    if not isinstance(raw_skills, list):
        raise JobMatchingValidationError("skills 必须是列表")
    skills = []
    for skill in raw_skills:
        text = str(skill).strip()
        if text and text not in skills:
            skills.append(text)
    if not education and not work and not skills:
        raise JobMatchingValidationError(
            "至少填写一个简历区块",
            details={"resume": "至少填写一个简历区块"},
        )
    return {
        "education_experiences": education,
        "work_experiences": work,
        "skills": skills,
    }


def _json_dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _row_has_saved_resume(row) -> bool:
    return bool(
        int(row["version"]) > 0
        and (
            json.loads(row["education_json"])
            or json.loads(row["work_experiences_json"])
            or json.loads(row["skills_json"])
        )
    )


def get_resume(student_id: int) -> dict:
    row = get_db().execute(
        """
        SELECT user_id, version, education_json,
               work_experiences_json, skills_json, updated_at
        FROM resumes
        WHERE user_id = ?
        """,
        (student_id,),
    ).fetchone()
    if row is None:
        raise JobMatchingValidationError("简历关系不存在")
    return {
        "education_experiences": json.loads(row["education_json"]),
        "work_experiences": json.loads(row["work_experiences_json"]),
        "skills": json.loads(row["skills_json"]),
        "version": int(row["version"]),
        "saved_at": row["updated_at"],
        "has_saved_resume": _row_has_saved_resume(row),
    }


def resume_exists(student_id: int) -> bool:
    row = get_db().execute(
        """
        SELECT version, education_json,
               work_experiences_json, skills_json
        FROM resumes
        WHERE user_id = ?
        """,
        (student_id,),
    ).fetchone()
    return row is not None and _row_has_saved_resume(row)


def save_resume(
    student_id: int,
    payload: dict,
    expected_version: int,
) -> dict:
    return _save_normalized_resume(
        student_id,
        _normalize_payload(payload),
        expected_version,
    )


def _save_normalized_resume(
    student_id: int,
    payload: dict,
    expected_version: int,
    *,
    offer_id: str | None = None,
) -> dict:
    db = get_db()
    with db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            """
            SELECT id, version
            FROM resumes
            WHERE user_id = ?
            """,
            (student_id,),
        ).fetchone()
        if row is None:
            raise JobMatchingValidationError("简历关系不存在")

        current_version = int(row["version"])
        if current_version != expected_version:
            raise ResumeConflictError("简历版本已变化")

        next_version = current_version + 1
        saved_at = _now_iso()
        education_json = _json_dumps(payload["education_experiences"])
        work_experiences_json = _json_dumps(payload["work_experiences"])
        skills_json = _json_dumps(payload["skills"])

        db.execute(
            """
            UPDATE resumes
            SET education_json = ?,
                work_experiences_json = ?,
                skills_json = ?,
                version = ?,
                updated_at = ?
            WHERE user_id = ?
            """,
            (
                education_json,
                work_experiences_json,
                skills_json,
                next_version,
                saved_at,
                student_id,
            ),
        )
        db.execute(
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
            """,
            (
                int(row["id"]),
                next_version,
                education_json,
                work_experiences_json,
                skills_json,
                saved_at,
            ),
        )
        if offer_id is not None:
            resolution = db.execute(
                """
                UPDATE resume_optimization_offers
                SET status = 'adopted',
                    resolved_at = ?
                WHERE offer_id = ?
                  AND student_id = ?
                  AND status = 'offered'
                """,
                (saved_at, offer_id, student_id),
            )
            if resolution.rowcount != 1:
                raise JobMatchingValidationError("优化稿已处理")

    return get_resume(student_id)


def build_resume_snapshot(student_id: int) -> dict:
    resume = get_resume(student_id)
    if not resume["has_saved_resume"]:
        raise ResumeRequiredError("请先创建并保存简历")
    return {
        "resume_version": resume["version"],
        "saved_at": resume["saved_at"],
        "education_experiences": resume["education_experiences"],
        "work_experiences": resume["work_experiences"],
        "skills": resume["skills"],
    }
