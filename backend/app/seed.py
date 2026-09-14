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
