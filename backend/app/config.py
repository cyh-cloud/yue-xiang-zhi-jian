from __future__ import annotations

import os
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SECRET_KEY = "dev-only-change-me"


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def build_config() -> dict[str, object]:
    is_production = os.environ.get("FLASK_ENV", "").strip().lower() == "production"
    secret_key = os.environ.get("SECRET_KEY", DEFAULT_SECRET_KEY).strip()
    session_cookie_secure = _env_bool("SESSION_COOKIE_SECURE", False)

    if is_production:
        if not secret_key or secret_key == DEFAULT_SECRET_KEY:
            raise RuntimeError(
                "Production SECRET_KEY must be set to a non-default value"
            )
        if not session_cookie_secure:
            raise RuntimeError("Production SESSION_COOKIE_SECURE must be true")

    return {
        "SECRET_KEY": secret_key,
        "APP_TIMEZONE": os.environ.get(
            "APP_TIMEZONE", "Asia/Shanghai"
        ).strip(),
        "DATABASE_PATH": os.environ.get(
            "DATABASE_PATH", str(BACKEND_ROOT.parent / "data" / "yuexiang.db")
        ),
        "SESSION_HOURS": int(os.environ.get("SESSION_HOURS", "24")),
        "SESSION_COOKIE_SECURE": session_cookie_secure,
        "MAX_CONTENT_LENGTH": 2 * 1024 * 1024,
        "AI_API_URL": os.environ.get("AI_API_URL", "").strip(),
        "AI_API_KEY": os.environ.get("AI_API_KEY", "").strip(),
        "AI_MODEL": os.environ.get("AI_MODEL", "Qwen/Qwen3-32B").strip(),
        "AI_ASR_URL": os.environ.get("AI_ASR_URL", "").strip(),
        "AI_ASR_MODEL": os.environ.get(
            "AI_ASR_MODEL", "FunAudioLLM/SenseVoiceSmall"
        ).strip(),
        "AI_TIMEOUT_SECONDS": float(os.environ.get("AI_TIMEOUT_SECONDS", "60")),
    }
