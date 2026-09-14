from __future__ import annotations

from datetime import datetime, timezone

from app.db import get_db


ROLE_PORTALS = {
    "student": "student",
    "teacher": "teacher",
    "enterprise": "enterprise",
    "government": "government",
    "super_admin": "admin",
    "admin": "admin",
}
ONBOARDING_OUTCOMES = {"completed", "skipped"}


def needs_onboarding(user_id: int, portal: str) -> bool:
    row = get_db().execute(
        """
        SELECT 1
        FROM onboarding_states
        WHERE user_id = ? AND portal = ?
        """,
        (user_id, portal),
    ).fetchone()
    return row is None


def complete_onboarding(user_id: int, portal: str, outcome: str) -> None:
    if outcome not in ONBOARDING_OUTCOMES:
        raise ValueError(f"Unsupported onboarding outcome: {outcome}")

    db = get_db()
    db.execute(
        """
        INSERT INTO onboarding_states (user_id, portal, outcome, completed_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (user_id, portal) DO UPDATE SET
            outcome = excluded.outcome,
            completed_at = excluded.completed_at
        """,
        (user_id, portal, outcome, datetime.now(timezone.utc).isoformat()),
    )
    db.commit()
