from __future__ import annotations

from app.db import get_db
from app.messaging.source_provider import get_messaging_source_provider


def application_relationship_exists(student_id: int, enterprise_id: int) -> bool:
    return get_messaging_source_provider().has_application_relationship(
        student_id,
        enterprise_id,
    )


def messaging_relationship(viewer_id: int, other_id: int) -> str | None:
    if viewer_id == other_id:
        return None
    roles = {
        int(row["id"]): str(row["role"])
        for row in get_db().execute(
            "SELECT id, role FROM users WHERE id IN (?, ?)",
            (viewer_id, other_id),
        ).fetchall()
    }
    if len(roles) != 2:
        return None
    viewer_role, other_role = roles[viewer_id], roles[other_id]
    if {viewer_role, other_role} == {"teacher", "student"}:
        return "teacher_student"
    if viewer_role == "student" and other_role == "enterprise":
        return (
            "application"
            if application_relationship_exists(viewer_id, other_id)
            else None
        )
    if viewer_role == "enterprise" and other_role == "student":
        return (
            "application"
            if application_relationship_exists(other_id, viewer_id)
            else None
        )
    return None


def list_allowed_contacts(user_id: int) -> list[dict]:
    user = get_db().execute(
        "SELECT role FROM users WHERE id = ? AND is_enabled = 1",
        (user_id,),
    ).fetchone()
    if user is None:
        return []
    role = str(user["role"])
    if role == "student":
        teacher_rows = get_db().execute(
            """
            SELECT id, name, role, 'teacher_student' AS relationship
            FROM users
            WHERE role = 'teacher' AND is_enabled = 1
            ORDER BY id
            """
        ).fetchall()
        enterprise_ids = (
            get_messaging_source_provider().list_applied_enterprise_ids(user_id)
        )
        enterprise_rows = self_contact_rows(
            enterprise_ids,
            "application",
        )
        rows = [*teacher_rows, *enterprise_rows]
    elif role == "teacher":
        rows = get_db().execute(
            """
            SELECT id, name, role, 'teacher_student' AS relationship
            FROM users
            WHERE role = 'student' AND is_enabled = 1
            ORDER BY id
            """
        ).fetchall()
    elif role == "enterprise":
        student_ids = (
            get_messaging_source_provider().list_applicant_student_ids(user_id)
        )
        rows = self_contact_rows(student_ids, "application")
    else:
        return []
    return [
        {
            "id": int(row["id"]),
            "name": str(row["name"]),
            "role": str(row["role"]),
            "relationship": str(row["relationship"]),
        }
        for row in rows
    ]


def self_contact_rows(user_ids: list[int], relationship: str) -> list[dict]:
    if not user_ids:
        return []
    unique_user_ids = list(dict.fromkeys(user_ids))
    placeholders = ", ".join("?" for _ in unique_user_ids)
    rows = get_db().execute(
        f"""
        SELECT id, name, role
        FROM users
        WHERE id IN ({placeholders}) AND is_enabled = 1
        """,
        unique_user_ids,
    ).fetchall()
    rows_by_id = {int(row["id"]): row for row in rows}
    return [
        {
            "id": user_id,
            "name": str(rows_by_id[user_id]["name"]),
            "role": str(rows_by_id[user_id]["role"]),
            "relationship": relationship,
        }
        for user_id in unique_user_ids
        if user_id in rows_by_id
    ]
