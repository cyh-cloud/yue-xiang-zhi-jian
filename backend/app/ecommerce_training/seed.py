from __future__ import annotations

import sqlite3


FIXTURES = (
    (1001, "电商直播开场实战（占位）", "ecommerce", "published", 300, "电商直播"),
    (1002, "电商产品讲解与促单（占位）", "ecommerce", "published", 360, "电商运营"),
    (1003, "待审核电商课程（占位）", "ecommerce", "pending", 300, "电商运营"),
    (1004, "农业对照课程（占位）", "agriculture", "published", 300, None),
    (1005, "无效时长电商课程（占位）", "ecommerce", "published", None, "电商运营"),
)


def seed_ecommerce_course_fixtures(connection: sqlite3.Connection) -> None:
    now = "2026-09-16T00:00:00+00:00"
    for (
        course_id,
        title,
        direction,
        status,
        duration_seconds,
        tag_name,
    ) in FIXTURES:
        connection.execute(
            """
            INSERT OR IGNORE INTO courses (
                id, title, direction, status, duration_seconds,
                published_at, summary, teacher_name, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                course_id,
                title,
                direction,
                status,
                duration_seconds,
                now if status == "published" else None,
                f"{title}，用于开发演示与验收测试。",
                "占位教师",
                now,
                now,
            ),
        )
        if tag_name is None:
            continue
        tag_rows = connection.execute(
            """
            SELECT id
            FROM interest_tags
            WHERE name = ? AND is_active = 1
            ORDER BY id
            """,
            (tag_name,),
        ).fetchall()
        if len(tag_rows) != 1:
            raise ValueError(f"Seed tag is missing or ambiguous: {tag_name}")
        connection.execute(
            """
            INSERT OR IGNORE INTO course_interest_tags (course_id, tag_id)
            VALUES (?, ?)
            """,
            (course_id, int(tag_rows[0]["id"])),
        )
