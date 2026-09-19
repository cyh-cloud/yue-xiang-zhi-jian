from __future__ import annotations

from app.agri_skills.providers import get_course_provider
from app.db import get_db
from app.teacher_console.errors import ProviderValidationError
from app.teacher_console.providers import DatabaseTeacherCourseProvider


DIRECTION_GROUPS = (
    "agriculture",
    "ecommerce",
    "handcraft",
    "comprehensive",
)
COMPREHENSIVE_DIRECTIONS = (
    "agriculture",
    "ecommerce",
    "handcraft",
)
COMPLETION_THRESHOLD = 80


def build_teacher_dashboard(teacher_id: int) -> dict:
    normalized_teacher_id = _normalize_teacher_id(teacher_id)
    db = get_db()
    students = db.execute(
        """
        SELECT users.id, student_profiles.learning_direction
        FROM users
        JOIN student_profiles ON student_profiles.user_id = users.id
        WHERE users.role = 'student' AND users.is_enabled = 1
        ORDER BY users.id
        """
    ).fetchall()

    progress_by_student = {
        int(student["id"]): _student_progress(
            int(student["id"]),
            str(student["learning_direction"]),
        )
        for student in students
    }
    student_total = len(students)
    average_progress = _rounded(
        (
            sum(progress_by_student.values()) / student_total
            if student_total
            else 0.0
        )
        * 100
    )
    completed_students = sum(
        progress == 1.0 for progress in progress_by_student.values()
    )
    completion_rate = _rounded(
        (completed_students / student_total if student_total else 0.0) * 100
    )

    directions = {
        direction: {
            "student_count": 0,
            "average_progress": 0.0,
        }
        for direction in DIRECTION_GROUPS
    }
    for student in students:
        group = str(student["learning_direction"])
        directions[group]["student_count"] += 1
    for group, summary in directions.items():
        group_progress = [
            progress_by_student[int(student["id"])]
            for student in students
            if str(student["learning_direction"]) == group
        ]
        summary["average_progress"] = _rounded(
            (
                sum(group_progress) / len(group_progress)
                if group_progress
                else 0.0
            )
            * 100
        )

    quiz_attempt_count, quiz_average_score = _teacher_quiz_stats(
        normalized_teacher_id
    )
    return {
        "student_total": student_total,
        "average_progress": average_progress,
        "completion_rate": completion_rate,
        "quiz_attempt_count": quiz_attempt_count,
        "quiz_average_score": quiz_average_score,
        "directions": directions,
    }


def _student_progress(student_id: int, direction: str) -> float:
    directions = (
        COMPREHENSIVE_DIRECTIONS
        if direction == "comprehensive"
        else (direction,)
    )
    ratios = []
    provider = get_course_provider()
    db = get_db()
    for item in directions:
        published_ids = sorted(
            {
                int(course["id"])
                for course in provider.list_published_courses(
                    student_id,
                    item,
                )
            }
        )
        if not published_ids:
            ratios.append(0.0)
            continue

        placeholders = ", ".join("?" for _ in published_ids)
        row = db.execute(
            f"""
            SELECT COUNT(*) AS count
            FROM agri_course_progress
            WHERE user_id = ?
              AND progress_percent >= ?
              AND course_id IN ({placeholders})
            """,
            (
                student_id,
                COMPLETION_THRESHOLD,
                *published_ids,
            ),
        ).fetchone()
        ratios.append(int(row["count"]) / len(published_ids))
    return sum(ratios) / len(ratios)


def _teacher_quiz_stats(teacher_id: int) -> tuple[int, float]:
    db = get_db()
    candidate_rows = db.execute(
        """
        SELECT id
        FROM courses
        WHERE teacher_id = ?
        ORDER BY id
        """,
        (teacher_id,),
    ).fetchall()
    provider = DatabaseTeacherCourseProvider()
    published_ids = [
        int(row["id"])
        for row in candidate_rows
        if provider.get_course(int(row["id"])) is not None
    ]
    if not published_ids:
        return 0, 0.0

    placeholders = ", ".join("?" for _ in published_ids)
    row = db.execute(
        f"""
        SELECT COUNT(*) AS count, AVG(score) AS average_score
        FROM agri_course_quiz_attempts
        WHERE course_id IN ({placeholders})
        """,
        tuple(published_ids),
    ).fetchone()
    return int(row["count"]), _rounded(float(row["average_score"] or 0.0))


def _normalize_teacher_id(teacher_id: int) -> int:
    if (
        isinstance(teacher_id, bool)
        or not isinstance(teacher_id, int)
        or teacher_id <= 0
    ):
        raise ProviderValidationError(
            "teacher_id 必须为正整数",
            code="dashboard_validation_failed",
            details={"field": "teacher_id"},
        )
    return teacher_id


def _rounded(value: float) -> float:
    return round(float(value), 2)
