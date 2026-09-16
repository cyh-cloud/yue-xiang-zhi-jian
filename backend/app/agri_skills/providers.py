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


class CourseProvider(Protocol):
    def list_published_courses(
        self,
        student_id: int,
        direction: str,
    ) -> list[dict]: ...
    def get_course(self, course_id: int) -> dict | None: ...
    def get_quiz(self, course_id: int) -> dict | None: ...


AgriCourseProvider = CourseProvider


REQUIRED_COURSE_TEXT_FIELDS = ("title", "summary", "teacher_name")


def is_eligible_course(course: dict, direction: str) -> bool:
    if not isinstance(course, dict) or course.get("direction") != direction:
        return False
    course_id = course.get("id")
    duration = course.get("duration_seconds")
    if (
        not isinstance(course_id, int)
        or isinstance(course_id, bool)
        or course_id <= 0
        or not isinstance(duration, int)
        or isinstance(duration, bool)
        or duration <= 0
    ):
        return False
    return all(
        isinstance(course.get(field), str) and bool(course[field].strip())
        for field in REQUIRED_COURSE_TEXT_FIELDS
    )


class AiClient(Protocol):
    def stream_chat(self, messages: list[dict], *, call_point: str) -> object: ...
    def complete_json(self, messages: list[dict], *, call_point: str) -> dict: ...
    def transcribe(self, audio: bytes, filename: str, *, call_point: str) -> str: ...


def set_course_provider(app: Flask, provider: CourseProvider) -> None:
    app.extensions["agri_course_provider"] = provider


def get_course_provider() -> CourseProvider:
    provider = current_app.extensions.get("agri_course_provider")
    if provider is not None:
        return provider

    from app.agri_skills.course_learning import DatabaseAgriCourseProvider

    return DatabaseAgriCourseProvider()


def list_provider_courses(student_id: int, direction: str) -> list[dict]:
    provider = get_course_provider()
    directional = getattr(provider, "list_published_courses", None)
    if callable(directional):
        return directional(student_id, direction)
    legacy = getattr(provider, "list_published_agriculture_courses", None)
    if direction == "agriculture" and callable(legacy):
        return legacy(student_id)
    raise ValueError("课程 provider 不支持该方向")
