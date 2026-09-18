from __future__ import annotations

import sqlite3

from app.handcraft_inheritance.presets import PLACEHOLDER_VIDEOS
from app.handcraft_inheritance.providers import (
    normalize_video_review_status,
)


def seed_handcraft_fixtures(connection: sqlite3.Connection) -> None:
    for video in PLACEHOLDER_VIDEOS:
        if not str(video["video_id"]).startswith("demo-"):
            raise ValueError("Only demo handcraft videos may be seeded")
        connection.execute(
            """
            INSERT OR IGNORE INTO heritage_videos (
                video_id, craft_key, title, review_status,
                source_available, media_url, version, rejection_opinion,
                published_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                video["video_id"],
                video["craft_key"],
                video["title"],
                normalize_video_review_status(video["review_status"]),
                1 if video["source_available"] else 0,
                video["media_url"],
                video["version"],
                video["rejection_opinion"],
                video["published_at"],
                video["created_at"],
                video["updated_at"],
            ),
        )
