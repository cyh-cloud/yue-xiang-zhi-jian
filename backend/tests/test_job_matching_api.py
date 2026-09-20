from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db
from app.enterprise_console.errors import ProviderUnavailableError
from app.job_matching import routes
from app.job_matching.errors import (
    AlreadyAppliedError,
    JobMatchingValidationError,
    JobUnavailableError,
    ResumeConflictError,
    ResumeRequiredError,
)
from app.agri_skills.errors import AiUnavailableError


RESUME = {
    "education_experiences": [],
    "work_experiences": [
        {
            "company": "示范农场",
            "role": "运营助理",
            "start_date": "2025-07",
            "end_date": "",
            "description": "",
        }
    ],
    "skills": ["直播运营"],
    "version": 1,
    "saved_at": "2026-09-20T10:00:00+08:00",
    "has_saved_resume": True,
}

OFFER = {
    "offer_id": "offer-1",
    "base_version": 1,
    "suggestions": ["补充量化成果"],
    "rewritten_resume": None,
    "status": "offered",
    "created_at": "2026-09-20T10:05:00+08:00",
}

PROFILE = {
    "items": [],
    "visible_item_ids": [],
    "summary": {
        "live_script": 0,
        "simulation_training": 0,
        "quiz_score": 0,
        "learning_record": 0,
    },
}

JOB = {
    "job_id": "job-1",
    "enterprise_id": 2,
    "enterprise_name": "荔乡电商",
    "title": "电商运营",
    "salary": "7k-9k",
    "location": "佛山",
    "category_id": 10,
    "category_name": "电商运营",
    "description": "负责直播运营。",
    "review_status": "approved",
    "version": 1,
    "published_at": "2026-09-20T09:00:00+08:00",
    "updated_at": "2026-09-20T09:00:00+08:00",
}

APPLICATION = {
    "application_id": "application-1",
    "job_id": "job-1",
    "enterprise_id": 2,
    "enterprise_name": "荔乡电商",
    "student_id": 1,
    "student_name": "学员一",
    "job_title": "电商运营",
    "status": "pending",
    "status_version": 1,
    "position_closed": False,
    "position_closed_at": None,
    "effective_status": "pending",
    "effective_status_label": "待处理",
    "submitted_at": "2026-09-20T10:10:00+08:00",
    "status_label": "待处理",
    "show_closed_marker": False,
}

FAVORITE = {
    "job_id": "job-1",
    "title": "电商运营",
    "enterprise_name": "荔乡电商",
    "salary": "7k-9k",
    "location": "佛山",
    "description": "负责直播运营。",
    "title_snapshot": "电商运营",
    "enterprise_name_snapshot": "荔乡电商",
    "favorited_at": "2026-09-20T10:15:00+08:00",
    "closed": False,
}


class JobMatchingApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(
                    Path(self.temp_dir.name) / "test.db"
                ),
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
            }
        )
        self.student_id = self._create_user(
            "student-api",
            "学员一",
            "student",
        )
        self.enterprise_id = self._create_user(
            "enterprise-api",
            "荔乡电商",
            "enterprise",
        )

    def _create_user(self, username: str, name: str, role: str) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self.app.app_context():
            cursor = get_db().execute(
                """
                INSERT INTO users (
                    username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    username,
                    generate_password_hash("password8"),
                    name,
                    role,
                    now,
                    now,
                ),
            )
            get_db().commit()
        return int(cursor.lastrowid)

    def _login(self, username: str):
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)
        return client

    def test_guest_is_rejected(self):
        response = self.app.test_client().get(
            "/api/job-matching/jobs"
        )

        self.assertEqual(response.status_code, 401)

    def test_enterprise_cannot_read_student_resume(self):
        client = self._login("enterprise-api")

        response = client.get("/api/job-matching/resume")

        self.assertEqual(response.status_code, 401)

    def test_student_can_read_resume(self):
        client = self._login("student-api")

        with patch.object(
            routes,
            "get_resume",
            return_value=RESUME,
        ) as get_resume:
            response = client.get("/api/job-matching/resume")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"success": True, "resume": RESUME},
        )
        get_resume.assert_called_once_with(self.student_id)

    def test_route_map_matches_frozen_contract(self):
        methods_by_path = {}
        for rule in self.app.url_map.iter_rules():
            if rule.rule.startswith("/api/job-matching"):
                methods_by_path.setdefault(rule.rule, set()).update(
                    rule.methods - {"HEAD", "OPTIONS"}
                )

        expected = {
            "/api/job-matching/resume": {"GET", "PUT"},
            "/api/job-matching/resume/optimize": {"POST"},
            (
                "/api/job-matching/resume/optimizations/"
                "<offer_id>/adopt"
            ): {"POST"},
            (
                "/api/job-matching/resume/optimizations/"
                "<offer_id>/discard"
            ): {"POST"},
            "/api/job-matching/skill-profile": {"GET"},
            (
                "/api/job-matching/skill-profile/visibility"
            ): {"PUT"},
            "/api/job-matching/jobs": {"GET"},
            "/api/job-matching/jobs/<job_id>": {"GET"},
            (
                "/api/job-matching/jobs/<job_id>/applications"
            ): {"POST"},
            "/api/job-matching/applications": {"GET"},
            (
                "/api/job-matching/applications/<application_id>"
            ): {"GET"},
            "/api/job-matching/favorites": {"GET"},
            "/api/job-matching/favorites/<job_id>": {
                "POST",
                "DELETE",
            },
        }
        self.assertEqual(methods_by_path, expected)

    def test_resume_put_accepts_exact_shape_and_returns_resume(self):
        client = self._login("student-api")
        payload = {
            "expected_version": 0,
            "education_experiences": [],
            "work_experiences": [],
            "skills": ["直播运营"],
        }

        with patch.object(
            routes,
            "save_resume",
            return_value=RESUME,
        ) as save_resume:
            response = client.put(
                "/api/job-matching/resume",
                json=payload,
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"success": True, "resume": RESUME},
        )
        save_resume.assert_called_once_with(
            self.student_id,
            {
                "education_experiences": [],
                "work_experiences": [],
                "skills": ["直播运营"],
            },
            0,
        )

    def test_optimize_returns_offer_envelope(self):
        client = self._login("student-api")

        with patch.object(
            routes,
            "optimize_resume",
            return_value=OFFER,
        ) as optimize_resume:
            response = client.post(
                "/api/job-matching/resume/optimize",
                json={"expected_version": 1},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"success": True, "offer": OFFER},
        )
        optimize_resume.assert_called_once_with(self.student_id, 1)

    def test_adopt_returns_updated_resume_envelope(self):
        client = self._login("student-api")
        adopted = {**RESUME, "version": 2}

        with patch.object(
            routes,
            "adopt_resume_optimization",
            return_value=adopted,
        ) as adopt_resume:
            response = client.post(
                (
                    "/api/job-matching/resume/optimizations/"
                    "offer-1/adopt"
                ),
                json={"expected_version": 1},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"success": True, "resume": adopted},
        )
        adopt_resume.assert_called_once_with(
            self.student_id,
            "offer-1",
            1,
        )

    def test_discard_returns_updated_offer_envelope(self):
        client = self._login("student-api")
        discarded = {**OFFER, "status": "discarded"}

        with patch.object(
            routes,
            "discard_resume_optimization",
            return_value=discarded,
        ) as discard_resume:
            response = client.post(
                (
                    "/api/job-matching/resume/optimizations/"
                    "offer-1/discard"
                )
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"success": True, "offer": discarded},
        )
        discard_resume.assert_called_once_with(
            self.student_id,
            "offer-1",
        )

    def test_skill_profile_get_and_visibility_put_envelopes(self):
        client = self._login("student-api")
        visible_id = "ecommerce:live_script:21"
        updated = {
            **PROFILE,
            "visible_item_ids": [visible_id],
        }

        with patch.object(
            routes,
            "get_skill_profile",
            return_value=PROFILE,
        ) as get_profile:
            get_response = client.get(
                "/api/job-matching/skill-profile"
            )

        with patch.object(
            routes,
            "set_skill_visibility",
            return_value=updated,
        ) as set_visibility:
            put_response = client.put(
                "/api/job-matching/skill-profile/visibility",
                json={"visible_item_ids": [visible_id]},
            )

        self.assertEqual(
            get_response.get_json(),
            {"success": True, "profile": PROFILE},
        )
        self.assertEqual(
            put_response.get_json(),
            {"success": True, "profile": updated},
        )
        get_profile.assert_called_once_with(self.student_id)
        set_visibility.assert_called_once_with(
            self.student_id,
            [visible_id],
        )

    def test_jobs_list_returns_jobs_and_recommended_jobs(self):
        client = self._login("student-api")
        result = {
            "jobs": [JOB],
            "recommended_jobs": [{**JOB, "category_match_count": 1}],
        }

        with patch.object(
            routes,
            "list_published_jobs",
            return_value=result,
        ) as list_jobs:
            response = client.get("/api/job-matching/jobs")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"success": True, **result},
        )
        list_jobs.assert_called_once_with(self.student_id)

    def test_job_detail_returns_job_or_sanitized_not_found(self):
        client = self._login("student-api")

        with patch.object(
            routes,
            "get_published_job",
            return_value=JOB,
        ) as get_job:
            found = client.get("/api/job-matching/jobs/job-1")

        with patch.object(
            routes,
            "get_published_job",
            return_value=None,
        ):
            missing = client.get("/api/job-matching/jobs/job-missing")

        self.assertEqual(
            found.get_json(),
            {"success": True, "job": JOB},
        )
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(
            missing.get_json(),
            {
                "success": False,
                "code": "job_unavailable",
                "message": "岗位已关闭或暂不可投递",
                "errors": {},
            },
        )
        get_job.assert_called_once_with(self.student_id, "job-1")

    def test_application_post_uses_session_identity_and_exact_application_key(self):
        client = self._login("student-api")

        with patch.object(
            routes,
            "submit_job_application",
            return_value=APPLICATION,
        ) as submit:
            response = client.post(
                "/api/job-matching/jobs/job-1/applications",
                json={
                    "student_id": 999,
                    "attach_skill_profile": True,
                },
            )

        body = response.get_json()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            body,
            {"success": True, "application": APPLICATION},
        )
        self.assertEqual(body["application"]["application_id"], "application-1")
        submit.assert_called_once_with(
            self.student_id,
            "job-1",
            True,
        )

    def test_application_list_and_detail_envelopes(self):
        client = self._login("student-api")

        with patch.object(
            routes,
            "list_my_applications",
            return_value=[APPLICATION],
        ) as list_applications:
            list_response = client.get(
                "/api/job-matching/applications"
            )

        with patch.object(
            routes,
            "get_my_application",
            return_value=APPLICATION,
        ) as get_application:
            detail_response = client.get(
                "/api/job-matching/applications/application-1"
            )

        self.assertEqual(
            list_response.get_json(),
            {"success": True, "applications": [APPLICATION]},
        )
        self.assertEqual(
            detail_response.get_json(),
            {"success": True, "application": APPLICATION},
        )
        list_applications.assert_called_once_with(self.student_id)
        get_application.assert_called_once_with(
            self.student_id,
            "application-1",
        )

    def test_unknown_application_is_404_without_provider_details(self):
        client = self._login("student-api")

        with patch.object(
            routes,
            "get_my_application",
            return_value=None,
        ):
            response = client.get(
                "/api/job-matching/applications/application-hidden"
            )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.get_json(),
            {
                "success": False,
                "code": "application_not_found",
                "message": "申请不存在",
                "errors": {},
            },
        )

    def test_favorites_get_add_and_delete_envelopes(self):
        client = self._login("student-api")
        removed = {"job_id": "job-1", "favorited": False}

        with patch.object(
            routes,
            "list_favorites",
            return_value=[FAVORITE],
        ) as list_favorites:
            get_response = client.get(
                "/api/job-matching/favorites"
            )

        with patch.object(
            routes,
            "add_favorite",
            return_value=FAVORITE,
        ) as add_favorite:
            post_response = client.post(
                "/api/job-matching/favorites/job-1"
            )

        with patch.object(
            routes,
            "remove_favorite",
            return_value=removed,
        ) as remove_favorite:
            delete_response = client.delete(
                "/api/job-matching/favorites/job-1"
            )

        self.assertEqual(
            get_response.get_json(),
            {"success": True, "favorites": [FAVORITE]},
        )
        self.assertEqual(
            post_response.get_json(),
            {"success": True, "favorite": FAVORITE},
        )
        self.assertEqual(
            delete_response.get_json(),
            {"success": True, "favorite": removed},
        )
        list_favorites.assert_called_once_with(self.student_id)
        add_favorite.assert_called_once_with(self.student_id, "job-1")
        remove_favorite.assert_called_once_with(
            self.student_id,
            "job-1",
        )

    def test_resume_required_has_exact_409_envelope(self):
        client = self._login("student-api")

        with patch.object(
            routes,
            "get_resume",
            side_effect=ResumeRequiredError(
                "internal resume detail",
                details={"resume": "required"},
            ),
        ):
            response = client.get("/api/job-matching/resume")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.get_json(),
            {
                "success": False,
                "code": "resume_required",
                "message": "请先创建并保存简历",
                "errors": {"resume": "required"},
            },
        )

    def test_already_applied_has_exact_409_envelope(self):
        client = self._login("student-api")

        with patch.object(
            routes,
            "submit_job_application",
            side_effect=AlreadyAppliedError(
                "internal duplicate detail",
                details={"application_id": "application-1"},
            ),
        ):
            response = client.post(
                "/api/job-matching/jobs/job-1/applications",
                json={"attach_skill_profile": False},
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.get_json(),
            {
                "success": False,
                "code": "already_applied",
                "message": "已投递该岗位",
                "errors": {"application_id": "application-1"},
            },
        )

    def test_job_unavailable_has_exact_409_envelope(self):
        client = self._login("student-api")

        with patch.object(
            routes,
            "submit_job_application",
            side_effect=JobUnavailableError(
                "internal provider detail",
                details={"job_id": "job-1"},
            ),
        ):
            response = client.post(
                "/api/job-matching/jobs/job-1/applications",
                json={"attach_skill_profile": False},
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.get_json(),
            {
                "success": False,
                "code": "job_unavailable",
                "message": "岗位已关闭或暂不可投递",
                "errors": {"job_id": "job-1"},
            },
        )

    def test_ai_unavailable_is_sanitized_503(self):
        client = self._login("student-api")

        with patch.object(
            routes,
            "optimize_resume",
            side_effect=AiUnavailableError(
                "provider timeout at internal-host:443"
            ),
        ):
            response = client.post(
                "/api/job-matching/resume/optimize",
                json={"expected_version": 1},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.get_json(),
            {
                "success": False,
                "code": "ai_unavailable",
                "message": "AI 服务暂时不可用",
                "errors": {},
            },
        )

    def test_validation_maps_to_400(self):
        client = self._login("student-api")

        with patch.object(
            routes,
            "save_resume",
            side_effect=JobMatchingValidationError(
                "至少填写一个简历区块",
                details={"resume": "至少填写一个简历区块"},
            ),
        ):
            response = client.put(
                "/api/job-matching/resume",
                json={
                    "expected_version": 0,
                    "education_experiences": [],
                    "work_experiences": [],
                    "skills": [],
                },
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json(),
            {
                "success": False,
                "code": "validation_error",
                "message": "至少填写一个简历区块",
                "errors": {"resume": "至少填写一个简历区块"},
            },
        )

    def test_resume_conflict_maps_to_409(self):
        client = self._login("student-api")

        with patch.object(
            routes,
            "save_resume",
            side_effect=ResumeConflictError("简历版本已变化"),
        ):
            response = client.put(
                "/api/job-matching/resume",
                json={
                    "expected_version": 0,
                    "education_experiences": [],
                    "work_experiences": [],
                    "skills": ["直播运营"],
                },
            )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.get_json(),
            {
                "success": False,
                "code": "resume_conflict",
                "message": "简历版本已变化",
                "errors": {},
            },
        )

    def test_provider_unavailable_is_sanitized_503(self):
        client = self._login("student-api")

        with patch.object(
            routes,
            "list_published_jobs",
            side_effect=ProviderUnavailableError(
                "Job position data is unavailable"
            ),
        ):
            response = client.get("/api/job-matching/jobs")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.get_json(),
            {
                "success": False,
                "code": "provider_unavailable",
                "message": "就业服务暂时不可用",
                "errors": {},
            },
        )

    def test_malformed_json_body_maps_to_400(self):
        client = self._login("student-api")

        response = client.put(
            "/api/job-matching/resume",
            data="not-json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["code"],
            "validation_error",
        )

    def test_malformed_application_json_maps_to_400(self):
        client = self._login("student-api")

        response = client.post(
            "/api/job-matching/jobs/job-1/applications",
            data="not-json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json()["code"],
            "validation_error",
        )


if __name__ == "__main__":
    unittest.main()
