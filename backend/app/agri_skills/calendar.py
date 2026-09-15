from __future__ import annotations

from app.agri_skills.errors import (
    AgriValidationError,
    PresetContentUnavailableError,
)
from app.agri_skills.presets import get_preset_provider
from app.db import get_db
from app.session_manager import utc_now_iso


def list_products() -> list[dict]:
    return sorted(
        get_preset_provider().list_products(),
        key=lambda item: (int(item["sort_order"]), str(item["key"])),
    )


def get_selected_product(user_id: int) -> str:
    row = get_db().execute(
        "SELECT product_key FROM agri_product_selections WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    products = list_products()
    if row and get_preset_provider().get_product(str(row["product_key"])):
        return str(row["product_key"])
    if not products:
        raise PresetContentUnavailableError("暂无该产品农时数据")
    return str(products[0]["key"])


def set_selected_product(user_id: int, product_key: str) -> str:
    if get_preset_provider().get_product(product_key) is None:
        raise AgriValidationError("产品不存在", details={"product_key": "产品不存在"})
    now = utc_now_iso()
    with get_db():
        get_db().execute(
            """
            INSERT INTO agri_product_selections (user_id, product_key, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT (user_id) DO UPDATE SET
                product_key = excluded.product_key,
                updated_at = excluded.updated_at
            """,
            (user_id, product_key, now),
        )
    return product_key


def get_calendar(product_key: str, month: int) -> dict:
    provider = get_preset_provider()
    product = provider.get_product(product_key)
    if product is None:
        raise PresetContentUnavailableError("暂无该产品农时数据")
    entries = provider.list_calendar_entries(product_key)
    if not entries:
        raise PresetContentUnavailableError("暂无该产品农时数据")
    entry = provider.get_calendar_entry(product_key, month)
    if entry is None:
        return {
            "product": product,
            "month": month,
            "tasks": [],
            "management": [],
            "solar_terms": [],
            "reminder": "",
            "empty_state": "当月无该产品农时",
        }
    return {"product": product, "month": month, **entry, "empty_state": None}


def subscribe_product(user_id: int, product_key: str) -> dict:
    if get_preset_provider().get_product(product_key) is None:
        raise AgriValidationError("产品不存在", details={"product_key": "产品不存在"})
    now = utc_now_iso()
    with get_db():
        get_db().execute(
            """
            INSERT INTO agri_product_subscriptions (
                user_id, product_key, is_active, created_at, updated_at
            ) VALUES (?, ?, 1, ?, ?)
            ON CONFLICT (user_id, product_key) DO UPDATE SET
                is_active = 1,
                updated_at = excluded.updated_at
            """,
            (user_id, product_key, now, now),
        )
    return {"product_key": product_key, "subscribed": True}


def unsubscribe_product(user_id: int, product_key: str) -> dict:
    with get_db():
        get_db().execute(
            """
            UPDATE agri_product_subscriptions
            SET is_active = 0, updated_at = ?
            WHERE user_id = ? AND product_key = ?
            """,
            (utc_now_iso(), user_id, product_key),
        )
    return {"product_key": product_key, "subscribed": False}


def list_product_subscriptions(user_id: int) -> list[str]:
    rows = get_db().execute(
        """
        SELECT product_key
        FROM agri_product_subscriptions
        WHERE user_id = ? AND is_active = 1
        ORDER BY product_key
        """,
        (user_id,),
    ).fetchall()
    return [str(row["product_key"]) for row in rows]


def list_product_subscriber_ids(product_key: str) -> list[int]:
    rows = get_db().execute(
        """
        SELECT user_id
        FROM agri_product_subscriptions
        WHERE product_key = ? AND is_active = 1
        ORDER BY user_id
        """,
        (product_key,),
    ).fetchall()
    return [int(row["user_id"]) for row in rows]
