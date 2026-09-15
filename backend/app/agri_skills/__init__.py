from __future__ import annotations

from flask import Flask

from app.agri_skills.ai_client import NullAiClient, set_ai_client


def install_default_agri_services(app: Flask) -> None:
    if "agri_ai_client" not in app.extensions:
        set_ai_client(app, NullAiClient())
