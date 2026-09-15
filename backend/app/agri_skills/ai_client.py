from __future__ import annotations

from collections.abc import Iterator

from flask import Flask, current_app

from app.agri_skills.errors import AiUnavailableError


class NullAiClient:
    def stream_chat(self, messages: list[dict], *, call_point: str) -> Iterator[str]:
        raise AiUnavailableError("AI service is not configured")

    def complete_json(self, messages: list[dict], *, call_point: str) -> dict:
        raise AiUnavailableError("AI service is not configured")

    def transcribe(self, audio: bytes, filename: str, *, call_point: str) -> str:
        raise AiUnavailableError("AI service is not configured")


def set_ai_client(app: Flask, client) -> None:
    app.extensions["agri_ai_client"] = client


def get_ai_client():
    return current_app.extensions.get("agri_ai_client", NullAiClient())
