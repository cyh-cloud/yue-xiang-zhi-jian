from __future__ import annotations

import unittest
from contextlib import contextmanager, ExitStack
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.enterprise_console.providers import (
    set_job_application_intake_provider,
    set_job_application_status_provider,
    set_job_position_provider,
)
from app.job_matching import applications
from app.job_matching.applications import (
    get_my_application,
    list_my_applications,
    submit_job_application,
)
from app.job_matching.errors import (
    AlreadyAppliedError,
    JobUnavailableError,
    ResumeRequiredError,
)


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
    "published_at": "2026-09-19T09:00:00+08:00",
    "updated_at": "2026-09-19T09:00:00+08:00",
}

RESUME_SNAPSHOT = {
    "resume_version": 1,
    "saved_at": "2026-09-19T10:00:00+08:00",
    "education_experiences": [],
    "work_experiences": [],
    "skills": ["直播运营"],
}

SKILL_SNAPSHOT = {
    "schema_version": 1,
    "generated_at": "2026-09-19T10:05:00+08:00",
    "items": [],
    "summary": {
        "live_script": 0,
        "simulation_training": 0,
        "quiz_score": 0,
        "learning_record": 0,
    },
}


def make_application(
    *,
    application_id: str = "application-1",
    student_id: int = 1,
    status: str = "pending",
    effective_status: str | None = None,
    effective_status_label: str | None = None,
    position_closed: bool = False,
) -> dict:
    resolved_effective_status = (
        status if effective_status is None else effective_status
    )
    resolved_effective_label = (
        resolved_effective_status
        if effective_status_label is None
        else effective_status_label
    )
    return {
        "application_id": application_id,
        "job_id": "job-1",
        "enterprise_id": 2,
        "enterprise_name": "荔乡电商",
        "student_id": student_id,
        "student_name": f"学员 {student_id}",
        "job_title": "电商运营",
        "status": status,
        "status_version": 1,
        "position_closed": position_closed,
        "position_closed_at": (
            "2026-09-19T11:00:00+08:00"
            if position_closed
            else None
        ),
        "effective_status": resolved_effective_status,
        "effective_status_label": resolved_effective_label,
        "submitted_at": "2026-09-19T10:00:00+08:00",
    }


class RecordingJobPositionProvider:
    def __init__(self, jobs: list[dict], events: list[tuple]):
        self.jobs = {job["job_id"]: job for job in jobs}
        self.events = events
        self.get_calls = []

    def set_jobs(self, jobs: list[dict]) -> None:
        self.jobs = {job["job_id"]: job for job in jobs}

    def get_published_position(self, *, job_id: str) -> dict | None:
        self.get_calls.append(job_id)
        self.events.append(("job", job_id))
        return self.jobs.get(job_id)


class RecordingStatusProvider:
    def __init__(self, events: list[tuple]):
        self.events = events
        self.applications = []
        self.list_results = []
        self.list_calls = []
        self.get_calls = []

    def set_applications(self, applications: list[dict]) -> None:
        self.applications = list(applications)

    def queue_list_results(self, *results: list[dict]) -> None:
        self.list_results = [list(result) for result in results]

    def list_student_applications(self, *, student_id: int) -> list[dict]:
        self.list_calls.append(student_id)
        self.events.append(("status", student_id))
        if self.list_results:
            return self.list_results.pop(0)
        return [
            application
            for application in self.applications
            if application["student_id"] == student_id
        ]

    def get_student_application(
        self,
        *,
        student_id: int,
        application_id: str,
    ) -> dict | None:
        self.get_calls.append((student_id, application_id))
        self.events.append(("get_status", application_id))
        return next(
            (
                application
                for application in self.applications
                if application["student_id"] == student_id
                and application["application_id"] == application_id
            ),
            None,
        )


class RecordingIntakeProvider:
    def __init__(self, events: list[tuple], application: dict):
        self.events = events
        self.application = application
        self.calls = []
        self.on_submit = None

    def submit_application(
        self,
        *,
        job_id: str,
        student_id: int,
        resume_snapshot: dict,
        skill_profile_snapshot: dict | None,
        idempotency_key: str,
    ) -> dict:
        self.calls.append(
            {
                "job_id": job_id,
                "student_id": student_id,
                "resume_snapshot": resume_snapshot,
                "skill_profile_snapshot": skill_profile_snapshot,
                "idempotency_key": idempotency_key,
            }
        )
        self.events.append(("intake", student_id))
        if self.on_submit is not None:
            self.on_submit()
        return self.application


class JobMatchingApplicationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": ":memory:",
                "SECRET_KEY": "test-only-secret",
            }
        )
        self.student_id = 1
        self.events = []
        self.job_provider = RecordingJobPositionProvider(
            [JOB],
            self.events,
        )
        self.status_provider = RecordingStatusProvider(self.events)
        self.intake_provider = RecordingIntakeProvider(
            self.events,
            make_application(),
        )
        set_job_position_provider(self.app, self.job_provider)
        set_job_application_status_provider(
            self.app,
            self.status_provider,
        )
        set_job_application_intake_provider(
            self.app,
            self.intake_provider,
        )

    @contextmanager
    def _snapshot_functions(
        self,
        *,
        resume_result=RESUME_SNAPSHOT,
        skill_result=SKILL_SNAPSHOT,
    ):
        def build_resume(student_id: int):
            self.events.append(("resume", student_id))
            if isinstance(resume_result, Exception):
                raise resume_result
            return resume_result

        def build_skill(student_id: int):
            self.events.append(("skill", student_id))
            if isinstance(skill_result, Exception):
                raise skill_result
            return skill_result

        with ExitStack() as stack:
            stack.enter_context(
                patch.object(
                    applications,
                    "build_resume_snapshot",
                    side_effect=build_resume,
                )
            )
            stack.enter_context(
                patch.object(
                    applications,
                    "build_skill_profile_snapshot",
                    side_effect=build_skill,
                )
            )
            yield

    def _submit(
        self,
        *,
        attach_skill_profile: bool,
        resume_result=RESUME_SNAPSHOT,
        skill_result=SKILL_SNAPSHOT,
        job_id: str = "job-1",
    ) -> dict:
        with (
            self.app.app_context(),
            self._snapshot_functions(
                resume_result=resume_result,
                skill_result=skill_result,
            ),
        ):
            return submit_job_application(
                self.student_id,
                job_id,
                attach_skill_profile,
            )

    def test_no_resume_blocks_before_status_and_intake(self):
        error = ResumeRequiredError("请先创建并保存简历")

        with self.assertRaises(ResumeRequiredError) as raised:
            self._submit(
                attach_skill_profile=False,
                resume_result=error,
            )

        self.assertIs(raised.exception, error)
        self.assertEqual(
            self.events,
            [("job", "job-1"), ("resume", self.student_id)],
        )
        self.assertEqual(self.status_provider.list_calls, [])
        self.assertEqual(self.intake_provider.calls, [])

    def test_duplicate_blocks_before_skill_snapshot_and_intake(self):
        self.status_provider.set_applications(
            [make_application(student_id=self.student_id)]
        )

        with self.assertRaises(AlreadyAppliedError) as raised:
            self._submit(attach_skill_profile=True)

        self.assertEqual(raised.exception.message, "已投递该岗位")
        self.assertEqual(
            self.events,
            [
                ("job", "job-1"),
                ("resume", self.student_id),
                ("status", self.student_id),
            ],
        )
        self.assertEqual(self.intake_provider.calls, [])

    def test_unavailable_job_blocks_first_and_never_calls_intake(self):
        self.job_provider.set_jobs([])

        with self.assertRaises(JobUnavailableError) as raised:
            self._submit(attach_skill_profile=False)

        self.assertEqual(
            raised.exception.message,
            "岗位已关闭或暂不可投递",
        )
        self.assertEqual(self.events, [("job", "job-1")])
        self.assertEqual(self.status_provider.list_calls, [])
        self.assertEqual(self.intake_provider.calls, [])

    def test_success_uses_exact_order_snapshots_and_idempotency_key(self):
        result = self._submit(attach_skill_profile=True)

        self.assertEqual(result["application_id"], "application-1")
        self.assertEqual(
            self.events,
            [
                ("job", "job-1"),
                ("resume", self.student_id),
                ("status", self.student_id),
                ("skill", self.student_id),
                ("status", self.student_id),
                ("intake", self.student_id),
            ],
        )
        self.assertEqual(self.status_provider.list_calls, [1, 1])
        self.assertEqual(len(self.intake_provider.calls), 1)
        self.assertEqual(
            self.intake_provider.calls[0],
            {
                "job_id": "job-1",
                "student_id": self.student_id,
                "resume_snapshot": RESUME_SNAPSHOT,
                "skill_profile_snapshot": SKILL_SNAPSHOT,
                "idempotency_key": "007:1:job-1",
            },
        )

    def test_attach_false_skips_skill_snapshot_and_sends_none(self):
        result = self._submit(attach_skill_profile=False)

        self.assertEqual(result["application_id"], "application-1")
        self.assertNotIn(("skill", self.student_id), self.events)
        self.assertEqual(
            self.events,
            [
                ("job", "job-1"),
                ("resume", self.student_id),
                ("status", self.student_id),
                ("status", self.student_id),
                ("intake", self.student_id),
            ],
        )
        self.assertIsNone(
            self.intake_provider.calls[0]["skill_profile_snapshot"]
        )

    def test_empty_visible_skill_snapshot_stays_none(self):
        self._submit(
            attach_skill_profile=True,
            skill_result=None,
        )

        self.assertIsNone(
            self.intake_provider.calls[0]["skill_profile_snapshot"]
        )
        self.assertIn(("skill", self.student_id), self.events)

    def test_second_duplicate_check_blocks_before_intake(self):
        self.status_provider.queue_list_results(
            [],
            [make_application(student_id=self.student_id)],
        )

        with self.assertRaises(AlreadyAppliedError):
            self._submit(attach_skill_profile=True)

        self.assertEqual(
            self.events,
            [
                ("job", "job-1"),
                ("resume", self.student_id),
                ("status", self.student_id),
                ("skill", self.student_id),
                ("status", self.student_id),
            ],
        )
        self.assertEqual(self.status_provider.list_calls, [1, 1])
        self.assertEqual(self.intake_provider.calls, [])

    def test_race_after_second_check_returns_provider_original(self):
        original = make_application(student_id=self.student_id)
        self.intake_provider.application = original
        self.intake_provider.on_submit = lambda: (
            self.status_provider.set_applications([original])
        )

        result = self._submit(attach_skill_profile=False)

        self.assertIs(result, original)
        self.assertEqual(self.status_provider.list_calls, [1, 1])
        self.assertEqual(len(self.intake_provider.calls), 1)
        self.assertEqual(
            self.status_provider.applications[0]["application_id"],
            "application-1",
        )

    def test_status_reads_add_exact_five_labels(self):
        expected_labels = {
            "pending": "待处理",
            "viewed": "已查看",
            "intent": "意向沟通",
            "unsuitable": "不合适",
            "closed": "岗位已关闭",
        }
        self.status_provider.set_applications(
            [
                make_application(
                    application_id=f"application-{status}",
                    student_id=self.student_id,
                    status=status,
                    effective_status=status,
                    position_closed=status == "closed",
                )
                for status in expected_labels
            ]
        )

        with self.app.app_context():
            records = list_my_applications(self.student_id)

        self.assertEqual(
            {
                record["effective_status"]: record["status_label"]
                for record in records
            },
            expected_labels,
        )
        self.assertEqual(
            {
                record["effective_status"]: record["show_closed_marker"]
                for record in records
            },
            {
                "pending": False,
                "viewed": False,
                "intent": False,
                "unsuitable": False,
                "closed": True,
            },
        )

    def test_closed_handled_application_preserves_manual_status(self):
        self.status_provider.set_applications(
            [
                make_application(
                    student_id=self.student_id,
                    status="unsuitable",
                    effective_status="unsuitable",
                    effective_status_label="不合适",
                    position_closed=True,
                )
            ]
        )

        with self.app.app_context():
            record = list_my_applications(self.student_id)[0]

        self.assertEqual(record["effective_status"], "unsuitable")
        self.assertEqual(record["effective_status_label"], "不合适")
        self.assertEqual(record["status_label"], "不合适")
        self.assertTrue(record["position_closed"])
        self.assertTrue(record["show_closed_marker"])

    def test_closed_pending_application_uses_closed_effective_status(self):
        self.status_provider.set_applications(
            [
                make_application(
                    student_id=self.student_id,
                    status="pending",
                    effective_status="closed",
                    effective_status_label="岗位已关闭",
                    position_closed=True,
                )
            ]
        )

        with self.app.app_context():
            record = get_my_application(
                self.student_id,
                "application-1",
            )

        self.assertEqual(record["status"], "pending")
        self.assertEqual(record["effective_status"], "closed")
        self.assertEqual(record["effective_status_label"], "岗位已关闭")
        self.assertEqual(record["status_label"], "岗位已关闭")
        self.assertTrue(record["show_closed_marker"])

    def test_status_reads_isolate_students(self):
        own = make_application(
            application_id="application-own",
            student_id=self.student_id,
        )
        other = make_application(
            application_id="application-other",
            student_id=2,
            status="viewed",
        )
        self.status_provider.set_applications([own, other])

        with self.app.app_context():
            own_records = list_my_applications(self.student_id)
            other_records = list_my_applications(2)
            hidden = get_my_application(
                self.student_id,
                "application-other",
            )
            visible = get_my_application(2, "application-other")

        self.assertEqual(
            [record["application_id"] for record in own_records],
            ["application-own"],
        )
        self.assertEqual(
            [record["application_id"] for record in other_records],
            ["application-other"],
        )
        self.assertIsNone(hidden)
        self.assertEqual(visible["status_label"], "已查看")
        self.assertEqual(
            self.status_provider.get_calls,
            [
                (self.student_id, "application-other"),
                (2, "application-other"),
            ],
        )

    def test_application_module_has_no_direct_enterprise_sql(self):
        source = Path(applications.__file__).read_text(encoding="utf-8")

        for forbidden in (
            "app.enterprise_console.applications",
            "record_application_submission",
            "serialize_application",
            "FROM job_applications",
            "INSERT INTO job_applications",
            "UPDATE job_applications",
            "DELETE FROM job_applications",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
