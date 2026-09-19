from __future__ import annotations

import json
from datetime import datetime, timedelta
from uuid import uuid4

from app.agri_skills.ai_client import get_ai_client
from app.agri_skills.ai_context import build_ai_messages
from app.agri_skills.errors import AiUnavailableError
from app.agri_skills.providers import get_course_provider
from app.db import get_db
from app.teacher_console.dashboard import (
    DIRECTION_GROUPS,
    build_teacher_dashboard,
)
from app.teacher_console.errors import (
    ProviderNotFoundError,
    ProviderUnavailableError,
)
from app.teacher_console.time_utils import (
    now_shanghai_iso,
    parse_provider_time,
)


AI_UNAVAILABLE_MESSAGE = "AI 服务暂时不可用"
REPORT_SECTION_KEYS = (
    "progress_analysis",
    "direction_comparison",
    "risk_warning",
)
AGGREGATE_STAT_KEYS = (
    "student_total",
    "average_progress",
    "completion_rate",
    "quiz_attempt_count",
    "quiz_average_score",
)


def generate_teacher_report(teacher_id: int) -> dict:
    dashboard = build_teacher_dashboard(teacher_id)
    context = {
        "aggregate_stats": _report_stats(dashboard),
        "direction_comparison": _direction_comparison(dashboard),
        "risk_summary": _risk_summary(teacher_id),
    }
    try:
        payload = get_ai_client().complete_json(
            build_ai_messages(
                "teacher_learning_report_generate",
                context,
            ),
            call_point="teacher_learning_report_generate",
        )
        sections = _validate_sections(payload)
    except (AiUnavailableError, TypeError, ValueError) as error:
        raise _provider_unavailable() from error

    report_id = f"report-{uuid4().hex}"
    created_at = now_shanghai_iso()
    db = get_db()
    with db:
        db.execute(
            """
            INSERT INTO teacher_learning_reports (
                report_id, teacher_id, sections_json,
                stats_snapshot_json, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                report_id,
                teacher_id,
                json.dumps(sections, ensure_ascii=False),
                json.dumps(context, ensure_ascii=False),
                created_at,
            ),
        )
    return _report_payload(teacher_id, report_id)


def list_teacher_reports(teacher_id: int) -> list[dict]:
    rows = get_db().execute(
        """
        SELECT report_id, teacher_id, sections_json,
               stats_snapshot_json, created_at
        FROM teacher_learning_reports
        WHERE teacher_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (teacher_id,),
    ).fetchall()
    return [_report_payload_from_row(row) for row in rows]


def get_teacher_report(teacher_id: int, report_id: str) -> dict:
    return _report_payload(teacher_id, report_id)


def _report_stats(dashboard: dict) -> dict:
    return {
        key: dashboard[key]
        for key in AGGREGATE_STAT_KEYS
    }


def _direction_comparison(dashboard: dict) -> dict:
    directions = dashboard["directions"]
    return {
        direction: {
            "student_count": int(directions[direction]["student_count"]),
            "average_progress": float(
                directions[direction]["average_progress"]
            ),
        }
        for direction in DIRECTION_GROUPS
    }


def _risk_summary(teacher_id: int) -> dict:
    students = get_db().execute(
        """
        SELECT users.id, student_profiles.learning_direction
        FROM users
        JOIN student_profiles ON student_profiles.user_id = users.id
        WHERE users.role = 'student' AND users.is_enabled = 1
        ORDER BY users.id
        """
    ).fetchall()
    visible_course_ids, visible_directions = _teacher_visible_course_scope(
        teacher_id
    )
    course_activity_rows = []
    course_activity_rows.extend(
        _course_activity_rows(
            """
            SELECT user_id, updated_at AS occurred_at
            FROM agri_course_progress
            WHERE 1 = 1
            """,
            visible_course_ids,
        )
    )
    course_activity_rows.extend(
        _course_activity_rows(
            """
            SELECT user_id, created_at AS occurred_at
            FROM agri_course_quiz_attempts
            WHERE 1 = 1
            """,
            visible_course_ids,
        )
    )
    activity_rows = list(course_activity_rows)
    if "agriculture" in visible_directions:
        activity_rows.extend(
            get_db().execute(
                """
                SELECT user_id, created_at AS occurred_at
                FROM agri_self_test_attempts
                """
            ).fetchall()
        )
    if "handcraft" in visible_directions:
        activity_rows.extend(
            get_db().execute(
                """
                SELECT user_id, created_at AS occurred_at
                FROM handcraft_learning_outcomes
                """
            ).fetchall()
        )
    if "ecommerce" in visible_directions:
        activity_rows.extend(
            get_db().execute(
                """
                SELECT user_id, created_at AS occurred_at
                FROM ecommerce_live_script_versions
                """
            ).fetchall()
        )
        activity_rows.extend(
            get_db().execute(
                """
                SELECT user_id, completed_at AS occurred_at
                FROM ecommerce_simulation_trainings
                WHERE status = 'completed' AND completed_at IS NOT NULL
                """
            ).fetchall()
        )
        activity_rows.extend(
            get_db().execute(
                """
                SELECT user_id, completed_at AS occurred_at
                FROM ecommerce_copy_training_sessions
                WHERE status = 'completed' AND completed_at IS NOT NULL
                """
            ).fetchall()
        )
        activity_rows.extend(
            get_db().execute(
                """
                SELECT user_id, completed_at AS occurred_at
                FROM ecommerce_customer_sessions
                WHERE status = 'completed' AND completed_at IS NOT NULL
                """
            ).fetchall()
        )
        activity_rows.extend(
            get_db().execute(
                """
                SELECT user_id, created_at AS occurred_at
                FROM ecommerce_store_plans
                """
            ).fetchall()
        )
    latest_activity = _latest_activity_by_student(activity_rows)
    completed_students = {
        int(row["user_id"])
        for row in _course_activity_rows(
            """
            SELECT user_id
            FROM agri_course_progress
            WHERE progress_percent >= 80
            GROUP BY user_id
            """,
            visible_course_ids,
        )
    }
    activity_student_ids = {
        int(row["user_id"])
        for row in activity_rows
    }
    scoped_students = [
        student
        for student in students
        if _student_in_scope(
            int(student["id"]),
            str(student["learning_direction"]),
            visible_directions,
            activity_student_ids,
        )
    ]
    return _risk_summary_payload(
        scoped_students,
        latest_activity,
        completed_students,
    )


def _teacher_visible_course_scope(
    teacher_id: int,
) -> tuple[set[int], set[str]]:
    db = get_db()
    candidate_rows = db.execute(
        """
        SELECT id, direction
        FROM courses
        WHERE teacher_id = ?
        """,
        (teacher_id,),
    ).fetchall()
    provider = get_course_provider()
    visible_rows = [
        row
        for row in candidate_rows
        if provider.get_course(int(row["id"])) is not None
    ]
    return (
        {int(row["id"]) for row in visible_rows},
        {str(row["direction"]) for row in visible_rows},
    )


def _student_in_scope(
    student_id: int,
    direction: str,
    visible_directions: set[str],
    activity_student_ids: set[int],
) -> bool:
    if student_id in activity_student_ids:
        return True
    if not visible_directions:
        return False
    if direction == "comprehensive":
        return True
    return direction in visible_directions


def _course_activity_rows(
    query_without_course_filter: str,
    course_ids: set[int],
) -> list:
    if not course_ids:
        return []
    placeholders = ", ".join("?" for _ in course_ids)
    query = f"{query_without_course_filter.rstrip(';')} AND course_id IN ({placeholders})"
    return get_db().execute(
        query,
        tuple(sorted(course_ids)),
    ).fetchall()


def _latest_activity_by_student(
    activity_rows,
) -> dict[int, datetime]:
    latest_activity = {}
    for row in activity_rows:
        try:
            occurred_at = parse_provider_time(row["occurred_at"])
        except (TypeError, ValueError):
            continue
        student_id = int(row["user_id"])
        current = latest_activity.get(student_id)
        if current is None or occurred_at > current:
            latest_activity[student_id] = occurred_at
    return latest_activity


def _risk_summary_payload(
    students,
    latest_activity: dict[int, datetime],
    completed_students: set[int],
) -> dict:
    now = parse_provider_time(now_shanghai_iso())
    cutoff = now - timedelta(days=30)

    direction_counts = {
        direction: {
            "student_count": 0,
            "at_risk_count": 0,
        }
        for direction in DIRECTION_GROUPS
    }
    at_risk_count = 0
    for student in students:
        student_id = int(student["id"])
        direction = str(student["learning_direction"])
        counts = direction_counts[direction]
        counts["student_count"] += 1

        latest = latest_activity.get(student_id)
        inactive = latest is None or latest < cutoff
        at_risk = inactive and student_id not in completed_students
        if at_risk:
            at_risk_count += 1
            counts["at_risk_count"] += 1

    student_count = len(students)
    directions = {
        direction: {
            **counts,
            "at_risk_ratio": _ratio(
                counts["at_risk_count"],
                counts["student_count"],
            ),
        }
        for direction, counts in direction_counts.items()
    }
    return {
        "student_count": student_count,
        "at_risk_count": at_risk_count,
        "at_risk_ratio": _ratio(at_risk_count, student_count),
        "directions": directions,
    }


def _validate_sections(payload) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("AI report payload must be an object")

    sections = {}
    for key in REPORT_SECTION_KEYS:
        value = payload.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"AI report section is invalid: {key}")
        sections[key] = value.strip()
    return sections


def _report_payload(teacher_id: int, report_id: str) -> dict:
    row = get_db().execute(
        """
        SELECT report_id, teacher_id, sections_json,
               stats_snapshot_json, created_at
        FROM teacher_learning_reports
        WHERE report_id = ? AND teacher_id = ?
        """,
        (report_id, teacher_id),
    ).fetchone()
    if row is None:
        raise ProviderNotFoundError(
            "学情报告不存在",
            code="report_not_found",
            details={"report_id": report_id},
        )
    return _report_payload_from_row(row)


def _report_payload_from_row(row) -> dict:
    return {
        "report_id": str(row["report_id"]),
        "teacher_id": int(row["teacher_id"]),
        "created_at": str(row["created_at"]),
        "stats_snapshot": json.loads(row["stats_snapshot_json"]),
        "sections": json.loads(row["sections_json"]),
    }


def _provider_unavailable() -> ProviderUnavailableError:
    return ProviderUnavailableError(
        AI_UNAVAILABLE_MESSAGE,
        code="ai_unavailable",
        details={},
    )


def _ratio(numerator: int, denominator: int) -> float:
    return round(
        (numerator / denominator * 100) if denominator else 0.0,
        2,
    )
