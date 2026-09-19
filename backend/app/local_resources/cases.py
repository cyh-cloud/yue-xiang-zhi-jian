from __future__ import annotations

from typing import Protocol

from flask import Flask, current_app

from app.db import get_db
from app.local_resources.errors import LocalResourceUnavailableError


class LocalResourceCaseProvider(Protocol):
    def list_success_cases(self) -> list[dict]: ...

    def get_success_case(self, case_id: str) -> dict | None: ...


DEMO_CASES = (
    {
        "case_id": "case-litchi-coop",
        "title": "荔枝合作社的品牌化起步",
        "summary": "从分散销售到统一品控与品牌包装。",
        "background": "本地荔枝种植户规模小、销售渠道分散。",
        "journey": "先统一采摘标准，再建立分级包装和线上直播渠道。",
        "lessons": "先解决品质一致性，再扩大销售半径。",
        "sort_order": 10,
        "published_at": "2026-09-01T08:00:00+08:00",
    },
    {
        "case_id": "case-rice-ecommerce",
        "title": "水稻产区的电商协作",
        "summary": "用短视频和直播建立稳定复购。",
        "background": "产区缺乏持续内容和客户运营能力。",
        "journey": "以生产节点组织内容，按订单反馈调整产品组合。",
        "lessons": "内容、履约和售后必须同步建设。",
        "sort_order": 20,
        "published_at": "2026-09-02T08:00:00+08:00",
    },
    {
        "case_id": "case-bamboo-studio",
        "title": "竹编工作室的体验式转型",
        "summary": "把非遗技艺转化为可体验、可复购的服务。",
        "background": "传统成品销售客单价低且复购有限。",
        "journey": "设计短时体验课程，再连接定制订单与研学活动。",
        "lessons": "先验证体验流程，再扩张场地和人员。",
        "sort_order": 30,
        "published_at": "2026-09-03T08:00:00+08:00",
    },
)


def _serialize(row) -> dict:
    return {
        "id": row["case_id"],
        "title": row["title"],
        "summary": row["summary"],
        "background": row["background"],
        "journey": row["journey"],
        "lessons": row["lessons"],
        "published_at": row["published_at"],
        "updated_at": row["updated_at"],
        "is_demo": bool(row["is_demo"]),
    }


class DatabaseLocalResourceCaseProvider:
    def list_success_cases(self) -> list[dict]:
        rows = get_db().execute(
            """
            SELECT
                case_id, title, summary, background, journey, lessons,
                published_at, updated_at, is_demo
            FROM local_resource_success_cases
            ORDER BY sort_order ASC, case_id ASC
            """
        ).fetchall()
        return [_serialize(row) for row in rows]

    def get_success_case(self, case_id: str) -> dict | None:
        row = get_db().execute(
            """
            SELECT
                case_id, title, summary, background, journey, lessons,
                published_at, updated_at, is_demo
            FROM local_resource_success_cases
            WHERE case_id = ?
            """,
            (case_id,),
        ).fetchone()
        return _serialize(row) if row is not None else None


class UnavailableLocalResourceCaseProvider:
    def list_success_cases(self) -> list[dict]:
        raise LocalResourceUnavailableError("案例数据暂不可用")

    def get_success_case(self, case_id: str) -> dict | None:
        raise LocalResourceUnavailableError("案例数据暂不可用")


def set_local_resource_case_provider(
    app: Flask,
    provider: LocalResourceCaseProvider,
) -> None:
    app.extensions["local_resource_case_provider"] = provider


def get_local_resource_case_provider() -> LocalResourceCaseProvider:
    return current_app.extensions.get(
        "local_resource_case_provider",
        UnavailableLocalResourceCaseProvider(),
    )


def seed_local_resource_cases(connection) -> None:
    connection.executemany(
        """
        INSERT INTO local_resource_success_cases (
            case_id,
            title,
            summary,
            background,
            journey,
            lessons,
            sort_order,
            published_at,
            updated_at,
            is_demo
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        ON CONFLICT(case_id) DO UPDATE SET
            title = excluded.title,
            summary = excluded.summary,
            background = excluded.background,
            journey = excluded.journey,
            lessons = excluded.lessons,
            sort_order = excluded.sort_order,
            published_at = excluded.published_at,
            updated_at = excluded.updated_at,
            is_demo = 1
        """,
        (
            (
                case["case_id"],
                case["title"],
                case["summary"],
                case["background"],
                case["journey"],
                case["lessons"],
                case["sort_order"],
                case["published_at"],
                case["published_at"],
            )
            for case in DEMO_CASES
        ),
    )
