"""Platform points policy storage, provider and admin service.

`platform_points_policy` holds the single authoritative platform rule. 05
reads it through the `handcraft_points_policy_provider` slot, so an admin
edit takes effect on the very next 05 points event with no restart and no
snapshot rewrite. The existing 05 points state (`points_policy_snapshots`,
`points_lots`, `points_transactions`, ...) is never written from here: a
policy change only rewrites the one policy row and records an audit entry.
"""

from __future__ import annotations

import json
import sqlite3

from app.admin_console.audit import record_admin_audit
from app.admin_console.errors import (
    ProviderConflictError,
    ProviderNotFoundError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from app.admin_console.time_utils import platform_now_iso
from app.db import get_db
from app.handcraft_inheritance.presets import (
    PLACEHOLDER_POINTS_POLICY,
    PlaceholderPointsPolicyProvider,
)


# The payload is an exact set: an unknown key is refused instead of ignored,
# and a missing key is refused instead of defaulted, so a half-written rule
# can never silently reach 05.
POLICY_KEYS = frozenset(
    {
        "expected_version",
        "seconds_per_point",
        "training_weights",
        "daily_limit",
        "expiry_mode",
    }
)
TRAINING_WEIGHT_KEYS = (
    "default",
    "live_script",
    "simulation",
    "copy_training",
    "customer_service",
)
EXPIRY_MODES = frozenset({"permanent", "natural_year"})
# The seed has no acting administrator and `platform_points_policy.updated_by`
# carries no foreign key, so 0 marks the system seed itself.
SEED_ACTOR_ID = 0


def _fetch_one(sql: str, parameters: tuple = ()) -> sqlite3.Row | None:
    return get_db().execute(sql, parameters).fetchone()


def _validation(
    message: str,
    *,
    code: str = "points_policy_validation_failed",
    **details,
) -> ProviderValidationError:
    return ProviderValidationError(message, code=code, details=details)


def _not_found(
    message: str,
    code: str,
    **details,
) -> ProviderNotFoundError:
    return ProviderNotFoundError(message, code=code, details=details)


def _conflict(
    message: str,
    code: str,
    **details,
) -> ProviderConflictError:
    return ProviderConflictError(message, code=code, details=details)


def _unavailable(message: str, code: str, **details) -> ProviderUnavailableError:
    return ProviderUnavailableError(message, code=code, details=details)


def _is_positive_integer(value: object) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value > 0
    )


def _positive_integer(value: object, *, field: str) -> int:
    if not _is_positive_integer(value):
        raise _validation(f"{field} 必须是正整数", field=field)
    return int(value)


def _expected_version(value: object) -> int:
    """Read the required optimistic-lock token for the policy update.

    The platform policy has no delete path: the update is the only write, so
    the token is mandatory here. A missing value is refused up front instead
    of being treated as "skip the optimistic check" the way the preset delete
    paths treat their optional token.
    """
    if value is None:
        raise _validation("expected_version 不能为空", field="expected_version")
    return _positive_integer(value, field="expected_version")


def _begin_exclusive(db: sqlite3.Connection) -> None:
    """Take the write lock before the policy row is read.

    `load_session`/`require_admin_session` leave an empty deferred
    transaction open on the request connection, and a deferred transaction
    does not serialize writers, so two super admins could both read the same
    version and both pass the optimistic check. Committing the pending work
    and opening `BEGIN IMMEDIATE` is what makes the second update observe the
    first one's commit.
    """
    if db.in_transaction:
        db.commit()
    db.execute("BEGIN IMMEDIATE")


def _loaded_policy(raw: object) -> dict:
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    try:
        policy = json.loads(raw)
    except (TypeError, ValueError) as error:
        raise _unavailable(
            "平台积分规则已损坏，请联系系统管理员",
            "points_policy_corrupted",
        ) from error
    if not isinstance(policy, dict):
        raise _unavailable(
            "平台积分规则已损坏，请联系系统管理员",
            "points_policy_corrupted",
        )
    return policy


def _decoded_policy(raw: object) -> dict:
    """Decode the stored row into the shape 05's `_normalize_policy` expects.

    A stored row that no longer satisfies the rule shape is reported as
    unavailable rather than served half-valid, because 05 falls back to its
    last snapshot when the provider raises.
    """
    policy = _loaded_policy(raw)
    weights = policy.get("training_weights")
    seconds_per_point = policy.get("seconds_per_point")
    daily_limit = policy.get("daily_limit")
    version = policy.get("version")
    expiry_mode = policy.get("expiry_mode")
    readable = (
        isinstance(version, str)
        and bool(version.strip())
        and expiry_mode in EXPIRY_MODES
        and _is_positive_integer(seconds_per_point)
        and _is_positive_integer(daily_limit)
        and isinstance(weights, dict)
        and set(weights).issubset(set(TRAINING_WEIGHT_KEYS))
        and all(
            _is_positive_integer(weights.get(key)) for key in TRAINING_WEIGHT_KEYS
        )
    )
    if not readable:
        raise _unavailable(
            "平台积分规则已损坏，请联系系统管理员",
            "points_policy_corrupted",
        )
    return {
        "version": version.strip(),
        "seconds_per_point": int(seconds_per_point),
        "training_weights": {
            str(key): int(value) for key, value in weights.items()
        },
        "daily_limit": int(daily_limit),
        "expiry_mode": str(expiry_mode),
        "is_demo": bool(policy.get("is_demo", False)),
        "source_available": bool(policy.get("source_available", True)),
    }


def _serialize_policy(
    version: int,
    policy: dict,
    updated_by: int,
    updated_at: str,
) -> dict:
    """Project the row for the console: lock token plus the rule fields."""
    weights = policy["training_weights"]
    return {
        "version": version,
        "rule_version": policy["version"],
        "seconds_per_point": policy["seconds_per_point"],
        "training_weights": {
            key: weights[key] for key in TRAINING_WEIGHT_KEYS
        },
        "daily_limit": policy["daily_limit"],
        "expiry_mode": policy["expiry_mode"],
        "is_demo": policy["is_demo"],
        "source_available": policy["source_available"],
        "updated_by": updated_by,
        "updated_at": updated_at,
    }


def _validated_policy(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise _validation("请求内容格式不正确", field="payload")
    unknown = sorted(str(key) for key in set(payload) - POLICY_KEYS)
    if unknown:
        raise _validation(
            "积分规则包含不支持的字段",
            code="points_policy_field_unknown",
            fields=unknown,
            allowed=sorted(POLICY_KEYS),
        )
    missing = sorted(POLICY_KEYS - set(payload))
    if missing:
        raise _validation(
            "积分规则缺少必要字段",
            code="points_policy_field_missing",
            fields=missing,
        )
    raw_weights = payload.get("training_weights")
    if not isinstance(raw_weights, dict):
        raise _validation("训练积分权重格式不正确", field="training_weights")
    unknown_weights = sorted(
        str(key) for key in set(raw_weights) - set(TRAINING_WEIGHT_KEYS)
    )
    if unknown_weights:
        raise _validation(
            "训练积分权重包含不支持的类型",
            code="points_policy_weight_unknown",
            fields=unknown_weights,
            allowed=list(TRAINING_WEIGHT_KEYS),
        )
    missing_weights = sorted(set(TRAINING_WEIGHT_KEYS) - set(raw_weights))
    if missing_weights:
        raise _validation(
            "训练积分权重缺少必要类型",
            code="points_policy_weight_missing",
            fields=missing_weights,
        )
    expiry_mode = payload.get("expiry_mode")
    if not isinstance(expiry_mode, str) or expiry_mode not in EXPIRY_MODES:
        raise _validation(
            "积分有效期规则不正确",
            code="points_policy_expiry_mode_invalid",
            field="expiry_mode",
            allowed=sorted(EXPIRY_MODES),
        )
    return {
        "seconds_per_point": _positive_integer(
            payload.get("seconds_per_point"),
            field="seconds_per_point",
        ),
        "training_weights": {
            key: _positive_integer(
                raw_weights[key],
                field=f"training_weights.{key}",
            )
            for key in TRAINING_WEIGHT_KEYS
        },
        "daily_limit": _positive_integer(
            payload.get("daily_limit"),
            field="daily_limit",
        ),
        "expiry_mode": expiry_mode,
    }


class DatabasePointsPolicyProvider(PlaceholderPointsPolicyProvider):
    """Authoritative points policy read from `platform_points_policy`.

    The `PlaceholderPointsPolicyProvider` base class is retained only as a
    compatibility shim: the frozen `tests/test_handcraft_presets.py` and
    `tests/test_handcraft_foundation.py` assert the installed provider is
    still a `PlaceholderPointsPolicyProvider` (and therefore an
    `UnavailablePointsPolicyProvider`). No placeholder content is ever served
    from here; `get_policy` never calls `super()` and never returns
    `deepcopy(PLACEHOLDER_POINTS_POLICY)`. The database row is the single
    source of truth once 011 owns the slot, and `seed_demo_points_policy`
    turns the 05 demo rule into that real row on first start.
    """

    def get_policy(self) -> dict | None:
        row = _fetch_one(
            """
            SELECT policy_json
            FROM platform_points_policy
            WHERE singleton = 1
            """
        )
        if row is None:
            return None
        return _decoded_policy(row["policy_json"])


def get_points_policy() -> dict:
    """Read the platform policy for the admin console."""
    row = _fetch_one(
        """
        SELECT version, policy_json, updated_by, updated_at
        FROM platform_points_policy
        WHERE singleton = 1
        """
    )
    if row is None:
        raise _not_found(
            "平台积分规则不存在",
            "points_policy_not_found",
        )
    return _serialize_policy(
        int(row["version"]),
        _decoded_policy(row["policy_json"]),
        int(row["updated_by"]),
        str(row["updated_at"]),
    )


def update_points_policy(
    actor_id: int,
    payload: dict,
    expected_version: int,
) -> dict:
    """Validate, version and store the platform policy in one transaction."""
    values = _validated_policy(payload)
    locked_version = _expected_version(expected_version)
    db = get_db()
    _begin_exclusive(db)
    try:
        row = db.execute(
            """
            SELECT version, policy_json
            FROM platform_points_policy
            WHERE singleton = 1
            """
        ).fetchone()
        if row is None:
            raise _not_found(
                "平台积分规则不存在",
                "points_policy_not_found",
            )
        current_version = int(row["version"])
        if current_version != locked_version:
            raise _conflict(
                "积分规则已被其他管理员修改",
                "points_policy_version_conflict",
                expected_version=locked_version,
                current_version=current_version,
            )
        before = _decoded_policy(row["policy_json"])
        new_version = current_version + 1
        # `policy_json.version` is the rule version 05 records in
        # `points_policy_snapshots.version`; it is unrelated to the integer
        # optimistic-lock version kept on the row itself.
        after = {
            "version": f"v{new_version}",
            "seconds_per_point": values["seconds_per_point"],
            "training_weights": values["training_weights"],
            "daily_limit": values["daily_limit"],
            "expiry_mode": values["expiry_mode"],
            "is_demo": False,
            "source_available": True,
        }
        now = platform_now_iso()
        cursor = db.execute(
            """
            UPDATE platform_points_policy
            SET version = ?, policy_json = ?, updated_by = ?, updated_at = ?
            WHERE singleton = 1 AND version = ?
            """,
            (
                new_version,
                json.dumps(after, ensure_ascii=False),
                actor_id,
                now,
                current_version,
            ),
        )
        if cursor.rowcount != 1:
            raise _conflict(
                "积分规则已被其他管理员修改",
                "points_policy_version_conflict",
                expected_version=locked_version,
                current_version=current_version,
            )
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="update_points_policy",
            target_type="points_policy",
            target_id="platform",
            before=before,
            after=after,
            result="success",
        )
    except Exception:
        db.rollback()
        raise
    db.commit()
    return _serialize_policy(new_version, after, actor_id, now)


def seed_demo_points_policy(connection) -> None:
    """Seed the 05 demo points policy as the real platform rule.

    The values are read from 05's `PLACEHOLDER_POINTS_POLICY`, which stays
    the single source of truth for the demo rule.
    `ON CONFLICT(singleton) DO NOTHING` keeps admin edits across restarts, so
    the seed only fills an empty table instead of overwriting the console.
    """
    now = platform_now_iso()
    connection.execute(
        """
        INSERT INTO platform_points_policy (
            singleton, version, policy_json, updated_by, updated_at
        )
        VALUES (1, 1, ?, ?, ?)
        ON CONFLICT(singleton) DO NOTHING
        """,
        (
            json.dumps(PLACEHOLDER_POINTS_POLICY, ensure_ascii=False),
            SEED_ACTOR_ID,
            now,
        ),
    )


__all__ = [
    "DatabasePointsPolicyProvider",
    "get_points_policy",
    "seed_demo_points_policy",
    "update_points_policy",
]
