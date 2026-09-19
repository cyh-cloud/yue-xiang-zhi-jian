from __future__ import annotations

from app.content_review import get_content_review_provider


class CourseReviewAdapter:
    def submit(self, course: dict, payload: dict) -> dict:
        return get_content_review_provider().submit_for_review(
            content_type="course_video",
            content_id=str(course["id"]),
            submitter_id=int(course["teacher_id"]),
            expected_version=int(course["version"]),
            payload=payload,
        )

    def read(self, course_id: int) -> dict | None:
        return get_content_review_provider().get_review_status(
            content_type="course_video",
            content_id=str(course_id),
        )

    def edit(self, course: dict, payload: dict) -> dict:
        return get_content_review_provider().edit(
            content_type="course_video",
            content_id=str(course["id"]),
            submitter_id=int(course["teacher_id"]),
            expected_version=int(course["version"]),
            payload=payload,
        )
