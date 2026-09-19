from app.db import get_db
from app.local_resources.constants import POLICY_LABELS
from app.messaging.source_provider import NullMessagingSourceProvider


class LocalResourcesMessagingProvider(NullMessagingSourceProvider):
    def list_policy_subscriber_ids(self, category: str) -> list[int]:
        category_code = next(
            (
                code
                for code, label in POLICY_LABELS.items()
                if label == category
            ),
            None,
        )
        if category_code is None:
            return []
        rows = get_db().execute(
            """
            SELECT s.user_id
            FROM local_resource_policy_subscriptions s
            JOIN users u ON u.id = s.user_id
            WHERE s.category_code = ?
              AND s.is_active = 1
              AND u.role = 'student'
              AND u.is_enabled = 1
            ORDER BY s.user_id
            """,
            (category_code,),
        ).fetchall()
        return [int(row["user_id"]) for row in rows]
