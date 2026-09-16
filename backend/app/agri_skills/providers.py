from __future__ import annotations

from typing import Protocol

from flask import Flask, current_app


class PresetContentProvider(Protocol):
    def list_products(self) -> list[dict]: ...
    def get_product(self, product_key: str) -> dict | None: ...
    def get_calendar_entry(self, product_key: str, month: int) -> dict | None: ...
    def list_calendar_entries(self, product_key: str) -> list[dict]: ...
    def list_pest_entries(self) -> list[dict]: ...


class QuizQuestion(Protocol):
    id: str
    prompt: str
    question_type: str
    options: list[str]
    answer: str


class AgriCourseProvider(Protocol):
    def list_published_agriculture_courses(self, student_id: int) -> list[dict]: ...
    def get_course(self, course_id: int) -> dict | None: ...
    def get_quiz(self, course_id: int) -> dict | None: ...


class AiClient(Protocol):
    def stream_chat(self, messages: list[dict], *, call_point: str) -> object: ...
    def complete_json(self, messages: list[dict], *, call_point: str) -> dict: ...
    def transcribe(self, audio: bytes, filename: str, *, call_point: str) -> str: ...


def set_course_provider(app: Flask, provider: AgriCourseProvider) -> None:
    app.extensions["agri_course_provider"] = provider


def get_course_provider() -> AgriCourseProvider:
    provider = current_app.extensions.get("agri_course_provider")
    if provider is not None:
        return provider

    from app.agri_skills.course_learning import DatabaseAgriCourseProvider

    return DatabaseAgriCourseProvider()
