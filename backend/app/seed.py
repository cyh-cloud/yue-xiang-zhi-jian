from __future__ import annotations

import sqlite3


DEFAULT_INTEREST_TAGS = (
    ("crop", "荔枝"),
    ("crop", "龙眼"),
    ("crop", "水稻"),
    ("crop", "水产"),
    ("skill", "电商直播"),
    ("skill", "短视频"),
    ("skill", "客服沟通"),
    ("skill", "手工艺"),
    ("job", "农业技术员"),
    ("job", "电商运营"),
    ("job", "客服专员"),
    ("job", "手工艺人"),
)

DEFAULT_COURSES = (
    {
        "title": "荔枝保果与采收管理",
        "direction": "agriculture",
        "status": "published",
        "published_at": "2026-09-01T08:00:00+00:00",
        "summary": "学习荔枝保果、采收与采后处理的关键操作。",
        "teacher_name": "林老师",
        "tag_names": ("荔枝",),
    },
    {
        "title": "水稻绿色种植基础",
        "direction": "agriculture",
        "status": "published",
        "published_at": "2026-09-10T08:00:00+00:00",
        "summary": "掌握水稻绿色种植、田间管理与质量控制基础。",
        "teacher_name": "周老师",
        "tag_names": ("水稻",),
    },
    {
        "title": "农产品直播运营入门",
        "direction": "ecommerce",
        "status": "published",
        "published_at": "2026-09-08T08:00:00+00:00",
        "summary": "从直播筹备到复盘，建立农产品直播运营基础。",
        "teacher_name": "梁老师",
        "tag_names": ("电商直播",),
    },
    {
        "title": "竹编基础与产品设计",
        "direction": "handcraft",
        "status": "offline",
        "published_at": None,
        "summary": "认识竹编材料、基础技法与产品设计方法。",
        "teacher_name": "何老师",
        "tag_names": ("手工艺",),
    },
)


def seed_interest_tags(connection: sqlite3.Connection) -> None:
    connection.executemany(
        """
        INSERT INTO interest_tags (group_key, name, sort_order)
        VALUES (?, ?, ?)
        ON CONFLICT (group_key, name) DO UPDATE SET
            sort_order = excluded.sort_order
        """,
        (
            (group_key, name, sort_order)
            for sort_order, (group_key, name) in enumerate(
                DEFAULT_INTEREST_TAGS,
                start=1,
            )
        ),
    )


def seed_courses(connection: sqlite3.Connection) -> None:
    now = "2026-09-01T00:00:00+00:00"
    for course in DEFAULT_COURSES:
        existing = connection.execute(
            """
            SELECT id
            FROM courses
            WHERE title = ?
            ORDER BY id
            LIMIT 1
            """,
            (course["title"],),
        ).fetchone()
        values = (
            course["title"],
            course["direction"],
            course["status"],
            course["published_at"],
            course["summary"],
            course["teacher_name"],
        )
        if existing is None:
            cursor = connection.execute(
                """
                INSERT INTO courses (
                    title, direction, status, published_at, summary,
                    teacher_name, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (*values, now, now),
            )
            course_id = int(cursor.lastrowid)
        else:
            course_id = int(existing["id"])
            connection.execute(
                """
                UPDATE courses
                SET
                    title = ?,
                    direction = ?,
                    status = ?,
                    published_at = ?,
                    summary = ?,
                    teacher_name = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (*values, now, course_id),
            )

        connection.execute(
            "DELETE FROM course_interest_tags WHERE course_id = ?",
            (course_id,),
        )
        tag_ids = [
            int(row["id"])
            for row in connection.execute(
                """
                SELECT id
                FROM interest_tags
                WHERE name = ? AND is_active = 1
                ORDER BY id
                """,
                (course["tag_names"][0],),
            ).fetchall()
        ]
        if len(tag_ids) != 1:
            raise ValueError(
                f"Seed tag is missing or ambiguous: {course['tag_names'][0]}"
            )
        connection.execute(
            """
            INSERT INTO course_interest_tags (course_id, tag_id)
            VALUES (?, ?)
            """,
            (course_id, tag_ids[0]),
        )
