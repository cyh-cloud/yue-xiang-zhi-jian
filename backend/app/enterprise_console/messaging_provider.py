from __future__ import annotations

from app.db import get_db
from app.messaging.source_provider import NullMessagingSourceProvider


class EnterpriseMessagingProvider(NullMessagingSourceProvider):
    def has_application_relationship(
        self,
        student_id: int,
        enterprise_id: int,
    ) -> bool:
        row = get_db().execute(
            """
            SELECT 1
            FROM job_applications
            WHERE student_id = ? AND enterprise_id = ?
            LIMIT 1
            """,
            (student_id, enterprise_id),
        ).fetchone()
        return row is not None

    def list_applied_enterprise_ids(self, student_id: int) -> list[int]:
        return [
            int(row["enterprise_id"])
            for row in get_db().execute(
                """
                SELECT DISTINCT enterprise_id
                FROM job_applications
                WHERE student_id = ?
                ORDER BY enterprise_id
                """,
                (student_id,),
            ).fetchall()
        ]

    def list_applicant_student_ids(self, enterprise_id: int) -> list[int]:
        return [
            int(row["student_id"])
            for row in get_db().execute(
                """
                SELECT DISTINCT student_id
                FROM job_applications
                WHERE enterprise_id = ?
                ORDER BY student_id
                """,
                (enterprise_id,),
            ).fetchall()
        ]
