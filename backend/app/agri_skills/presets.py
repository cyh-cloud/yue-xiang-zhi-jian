from __future__ import annotations

from flask import Flask, current_app


PLACEHOLDER_PRODUCTS = [
    {"key": "litchi", "name": "荔枝", "sort_order": 1},
    {"key": "longan", "name": "龙眼", "sort_order": 2},
    {"key": "aquaculture", "name": "水产", "sort_order": 3},
]

PLACEHOLDER_CALENDAR = {
    ("litchi", 4): {
        "tasks": ["保果施肥", "检查蒂蛀虫"],
        "management": ["保持果园通风", "雨后及时排水"],
        "solar_terms": ["清明", "谷雨"],
        "reminder": "荔枝正值保果关键期",
    },
    ("litchi", 5): {
        "tasks": ["疏果", "病虫害巡查"],
        "management": ["控制夏梢", "关注强降雨"],
        "solar_terms": ["立夏", "小满"],
        "reminder": "注意果实膨大期水分管理",
    },
}

PLACEHOLDER_PESTS = [
    {
        "id": "litchi-stem-borer",
        "sort_order": 1,
        "pest_name": "荔枝蒂蛀虫",
        "product_names": ["荔枝"],
        "symptoms": ["虫蛀", "落果"],
        "aliases": ["蒂蛀虫", "蛀果"],
        "answer": "及时清理落果，重点保护果实和结果母枝，并按当地规范轮换用药。",
    },
    {
        "id": "litchi-downy-blight",
        "sort_order": 2,
        "pest_name": "荔枝霜疫霉病",
        "product_names": ["荔枝"],
        "symptoms": ["斑点", "落果", "霉层"],
        "aliases": ["霜疫病", "果腐"],
        "answer": "改善果园通风，雨前雨后加强检查，及时清除病果并采用登记药剂防治。",
    },
]


class PlaceholderPresetProvider:
    def list_products(self) -> list[dict]:
        return [dict(item) for item in PLACEHOLDER_PRODUCTS]

    def get_product(self, product_key: str) -> dict | None:
        return next(
            (dict(item) for item in PLACEHOLDER_PRODUCTS if item["key"] == product_key),
            None,
        )

    def get_calendar_entry(self, product_key: str, month: int) -> dict | None:
        value = PLACEHOLDER_CALENDAR.get((product_key, month))
        return dict(value) if value else None

    def list_calendar_entries(self, product_key: str) -> list[dict]:
        return [
            {"month": month, **value}
            for (current_key, month), value in PLACEHOLDER_CALENDAR.items()
            if current_key == product_key
        ]

    def list_pest_entries(self) -> list[dict]:
        return [dict(item) for item in PLACEHOLDER_PESTS]


def set_preset_provider(app: Flask, provider) -> None:
    app.extensions["agri_preset_provider"] = provider


def get_preset_provider():
    return current_app.extensions.get("agri_preset_provider", PlaceholderPresetProvider())
