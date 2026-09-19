from __future__ import annotations

import json
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from app.agri_skills.ai_client import get_ai_client
from app.agri_skills.ai_context import build_ai_messages
from app.agri_skills.errors import AiUnavailableError
from app.db import get_db
from app.job_matching.constants import AI_UNAVAILABLE_MESSAGE
from app.job_matching.errors import (
    JobMatchingValidationError,
    ResumeConflictError,
)
from app.job_matching.resumes import (
    _normalize_payload,
    _save_normalized_resume,
    get_resume,
)


RESUME_SECTION_KEYS = {
    "education_experiences",
    "work_experiences",
    "skills",
}
AI_RESULT_KEYS = {"suggestions", "rewritten_resume"}


def _now_iso() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def _normalize_ai_result(result) -> dict:
    if not isinstance(result, dict):
        raise JobMatchingValidationError("AI 优化结果格式不正确")
    if set(result) - AI_RESULT_KEYS:
        raise JobMatchingValidationError("AI 优化结果包含不支持的字段")

    raw_suggestions = result.get("suggestions")
    if not isinstance(raw_suggestions, list):
        raise JobMatchingValidationError("AI 优化建议必须是列表")

    suggestions = []
    for suggestion in raw_suggestions:
        if not isinstance(suggestion, str):
            raise JobMatchingValidationError("AI 优化建议必须是文本")
        text = suggestion.strip()
        if text and text not in suggestions:
            suggestions.append(text)
    if not suggestions:
        raise JobMatchingValidationError("AI 优化建议不能为空")

    rewritten = result.get("rewritten_resume")
    if rewritten is None:
        normalized_rewritten = None
    else:
        if not isinstance(rewritten, dict):
            raise JobMatchingValidationError("AI 改写稿必须是对象")
        if set(rewritten) != RESUME_SECTION_KEYS:
            raise JobMatchingValidationError("AI 改写稿必须包含完整简历区块")
        normalized_rewritten = _normalize_payload(rewritten)

    return {
        "suggestions": suggestions,
        "rewritten_resume": normalized_rewritten,
    }


def _insert_offer(student_id: int, offer: dict) -> None:
    db = get_db()
    with db:
        db.execute(
            """
            INSERT INTO resume_optimization_offers (
                offer_id,
                student_id,
                base_version,
                suggestions_json,
                rewritten_json,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                offer["offer_id"],
                student_id,
                offer["base_version"],
                json.dumps(offer["suggestions"], ensure_ascii=False),
                (
                    json.dumps(
                        offer["rewritten_resume"],
                        ensure_ascii=False,
                    )
                    if offer["rewritten_resume"] is not None
                    else None
                ),
                offer["status"],
                offer["created_at"],
            ),
        )


def _owned_offer(student_id: int, offer_id: str) -> dict:
    row = get_db().execute(
        """
        SELECT offer_id, base_version, suggestions_json, rewritten_json,
               status, created_at, resolved_at
        FROM resume_optimization_offers
        WHERE offer_id = ?
          AND student_id = ?
        """,
        (offer_id, student_id),
    ).fetchone()
    if row is None:
        raise JobMatchingValidationError("优化稿不存在")

    return {
        "offer_id": row["offer_id"],
        "base_version": int(row["base_version"]),
        "suggestions": json.loads(row["suggestions_json"]),
        "rewritten_resume": (
            json.loads(row["rewritten_json"])
            if row["rewritten_json"] is not None
            else None
        ),
        "status": row["status"],
        "created_at": row["created_at"],
        "resolved_at": row["resolved_at"],
    }


def optimize_resume(student_id: int, expected_version: int) -> dict:
    resume = get_resume(student_id)
    if resume["version"] != expected_version:
        raise ResumeConflictError("简历版本已变化")

    context = {
        "education_experiences": resume["education_experiences"],
        "work_experiences": resume["work_experiences"],
        "skills": resume["skills"],
    }
    try:
        result = get_ai_client().complete_json(
            build_ai_messages("resume_optimize", context),
            call_point="resume_optimize",
        )
    except AiUnavailableError as error:
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE) from error

    try:
        normalized = _normalize_ai_result(result)
    except (JobMatchingValidationError, TypeError, ValueError) as error:
        raise AiUnavailableError(AI_UNAVAILABLE_MESSAGE) from error

    offer = {
        "offer_id": f"resume-offer-{uuid.uuid4().hex}",
        "base_version": expected_version,
        "suggestions": normalized["suggestions"],
        "rewritten_resume": normalized["rewritten_resume"],
        "status": "offered",
        "created_at": _now_iso(),
    }
    _insert_offer(student_id, offer)
    return offer


def adopt_resume_optimization(
    student_id: int,
    offer_id: str,
    expected_version: int,
) -> dict:
    offer = _owned_offer(student_id, offer_id)
    if offer["status"] != "offered":
        raise JobMatchingValidationError("优化稿已处理")

    rewritten = offer["rewritten_resume"]
    if rewritten is None:
        raise JobMatchingValidationError("该结果仅包含建议，不能自动替换")

    current = get_resume(student_id)
    if current["version"] != expected_version:
        raise ResumeConflictError("简历版本已变化")
    if offer["base_version"] != expected_version:
        raise ResumeConflictError("优化稿已过期")

    return _save_normalized_resume(
        student_id,
        rewritten,
        expected_version,
        offer_id=offer_id,
    )


def discard_resume_optimization(student_id: int, offer_id: str) -> dict:
    db = get_db()
    with db:
        db.execute("BEGIN IMMEDIATE")
        offer = _owned_offer(student_id, offer_id)
        if offer["status"] != "offered":
            raise JobMatchingValidationError("优化稿已处理")

        resolved_at = _now_iso()
        resolution = db.execute(
            """
            UPDATE resume_optimization_offers
            SET status = 'discarded',
                resolved_at = ?
            WHERE offer_id = ?
              AND student_id = ?
              AND status = 'offered'
            """,
            (resolved_at, offer_id, student_id),
        )
        if resolution.rowcount != 1:
            raise JobMatchingValidationError("优化稿已处理")

    return {
        **offer,
        "status": "discarded",
        "resolved_at": resolved_at,
    }
