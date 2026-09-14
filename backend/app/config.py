from __future__ import annotations

import os
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def build_config() -> dict[str, object]:
    return {
        "SECRET_KEY": os.environ.get("SECRET_KEY", "dev-only-change-me"),
        "DATABASE_PATH": os.environ.get(
            "DATABASE_PATH", str(BACKEND_ROOT.parent / "data" / "yuexiang.db")
        ),
        "SESSION_HOURS": int(os.environ.get("SESSION_HOURS", "24")),
        "SESSION_COOKIE_SECURE": os.environ.get("SESSION_COOKIE_SECURE") == "1",
        "MAX_CONTENT_LENGTH": 2 * 1024 * 1024,
    }
