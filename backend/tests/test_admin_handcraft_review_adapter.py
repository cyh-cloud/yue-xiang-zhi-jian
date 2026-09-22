import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.admin_console.errors import (
    ProviderAccessDeniedError,
    ProviderConflictError,
    ProviderNotFoundError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from app.admin_console.handcraft_review_adapter import (
    CompositeContentReviewProvider,
    HandcraftTeachingVideoReviewAdapter,
)
from app.agri_skills.errors import (
    AgriAccessError,
    AgriNotFoundError,
    AgriValidationError,
)
from app.handcraft_inheritance.providers import set_teaching_video_provider


VIDEO_CONTENT_TYPE = "handcraft_teaching_video"


def make_video(
    video_id="video-1",
    *,
    status="pending",
    version=1,
    title="Teaching video",
    media_url="https://example.test/video.mp4",
    submitter_id=7,
):
    return {
        "video_id": video_id,
        "craft_key": "guangxiu",
        "title": title,
        "status": status,
        "source_available": True,
        "media_url": media_url,
        "version": version,
        "submitter_id": submitter_id,
        "rejection_opinion": None,
        "published_at": "2026-09-20T01:00:00Z",
        "created_at": "2026-09-20T00:00:00Z",
        "updated_at": "2026-09-20T01:00:00Z",
    }


class StaticVideoProvider:
    def __init__(self, videos):
        self.videos = copy.deepcopy(videos)
        self.error = None

    def list_videos(self, craft_key=None):
        if self.error is not None:
            raise self.error
        return [
            copy.deepcopy(video)
            for video in self.videos
            if craft_key is None or video["craft_key"] == craft_key
        ]

    def get_video(self, video_id):
        if self.error is not None:
            raise self.error
        return next(
            (
                copy.deepcopy(video)
                for video in self.videos
                if video["video_id"] == video_id
            ),
            None,
        )

    def get_review_status(self, video_id):
        video = self.get_video(video_id)
        return video.get("status") if video is not None else None


class RecordingVideoAction:
    def __init__(self, result=None, error=None):
        self.result = result or {
            "video_id": "video-1",
            "status": "approved",
            "version": 2,
        }
        self.error = error
        self.calls = []

    def __call__(self, action):
        self.calls.append(dict(action))
        if self.error is not None:
            raise self.error
        return dict(self.result)


class RecordingDelegate:
    def __init__(self, list_items=None):
        self.calls = []
        self.list_items = list_items or []

    def _record(self, method, kwargs):
        self.calls.append((method, dict(kwargs)))
        return {"method": method, **kwargs}

    def submit_for_review(self, **kwargs):
        return self._record("submit_for_review", kwargs)

    def get_review_status(self, **kwargs):
        return self._record("get_review_status", kwargs)

    def approve(self, **kwargs):
        return self._record("approve", kwargs)

    def reject(self, **kwargs):
        return self._record("reject", kwargs)

    def edit(self, **kwargs):
        return self._record("edit", kwargs)

    def list_review_items(self, content_type=None):
        self.calls.append(("list_review_items", {"content_type": content_type}))
        return copy.deepcopy(self.list_items)


class HandcraftTeachingVideoReviewAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )
        self.video_provider = StaticVideoProvider([])
        set_teaching_video_provider(self.app, self.video_provider)
        self.video_action = RecordingVideoAction()
        self.adapter = HandcraftTeachingVideoReviewAdapter()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _patch_video_action(self):
        return patch(
            "app.handcraft_inheritance.admin_actions."
            "apply_video_review",
            side_effect=self.video_action,
        )

    def test_approve_calls_05_wrapper_with_reviewer_fields(self):
        with self.app.app_context(), self._patch_video_action() as apply:
            result = self.adapter.approve(
                content_type=VIDEO_CONTENT_TYPE,
                content_id="video-1",
                submitter_id=7,
                reviewer_id=99,
                reviewer_role="admin",
                expected_version=1,
            )

        self.assertEqual(
            self.video_action.calls,
            [
                {
                    "video_id": "video-1",
                    "action": "approve",
                    "version": 1,
                    "submitter_id": 7,
                    "reviewer_id": 99,
                    "reviewer_role": "admin",
                }
            ],
        )
        apply.assert_called_once()
        self.assertEqual(result["content_type"], VIDEO_CONTENT_TYPE)
        self.assertEqual(result["content_id"], "video-1")
        self.assertEqual(result["submitter_id"], 7)
        self.assertEqual(result["review_status"], "approved")
        self.assertEqual(result["version"], 2)

    def test_reject_calls_05_wrapper_with_opinion(self):
        self.video_action.result = {
            "video_id": "video-1",
            "status": "rejected",
            "version": 2,
        }

        with self.app.app_context(), self._patch_video_action():
            result = self.adapter.reject(
                content_type=VIDEO_CONTENT_TYPE,
                content_id="video-1",
                submitter_id=7,
                reviewer_id=99,
                reviewer_role="super_admin",
                expected_version=1,
                opinion="Please re-record.",
            )

        self.assertEqual(
            self.video_action.calls[-1],
            {
                "video_id": "video-1",
                "action": "reject",
                "version": 1,
                "submitter_id": 7,
                "reviewer_id": 99,
                "reviewer_role": "super_admin",
                "opinion": "Please re-record.",
            },
        )
        self.assertEqual(result["review_status"], "rejected")

    def test_get_review_status_maps_published_and_normalizes_timestamps(self):
        self.video_provider.videos = [make_video(status="published")]

        with self.app.app_context():
            result = self.adapter.get_review_status(
                content_type=VIDEO_CONTENT_TYPE,
                content_id="video-1",
            )

        self.assertEqual(result["review_status"], "approved")
        self.assertEqual(result["published_at"], "2026-09-20T09:00:00+08:00")
        self.assertEqual(result["created_at"], "2026-09-20T08:00:00+08:00")
        self.assertEqual(result["updated_at"], "2026-09-20T09:00:00+08:00")
        self.assertEqual(result["craft_key"], "guangxiu")
        self.assertTrue(result["source_available"])

    def test_adapter_rejects_non_video_content_types(self):
        with self.app.app_context():
            with self.assertRaises(ProviderValidationError):
                self.adapter.get_review_status(
                    content_type="course_video",
                    content_id="1",
                )

    def test_submit_missing_video_is_conflict_without_fake_create(self):
        with self.app.app_context(), self._patch_video_action() as apply:
            with self.assertRaises(ProviderConflictError):
                self.adapter.submit_for_review(
                    content_type=VIDEO_CONTENT_TYPE,
                    content_id="missing-video",
                    submitter_id=7,
                    expected_version=1,
                    payload={"title": "New title"},
                )

        apply.assert_not_called()

    def test_submit_rejected_video_does_not_reopen_pending(self):
        self.video_provider.videos = [make_video(status="rejected")]

        with self.app.app_context(), self._patch_video_action() as apply:
            with self.assertRaises(ProviderConflictError):
                self.adapter.submit_for_review(
                    content_type=VIDEO_CONTENT_TYPE,
                    content_id="video-1",
                    submitter_id=7,
                    expected_version=1,
                    payload={"title": "New title"},
                )

        apply.assert_not_called()

    def test_submit_changed_pending_maps_to_owned_edit(self):
        self.video_provider.videos = [make_video()]
        self.video_action.result = {
            "video_id": "video-1",
            "status": "pending",
            "version": 2,
        }

        with self.app.app_context(), self._patch_video_action():
            result = self.adapter.submit_for_review(
                content_type=VIDEO_CONTENT_TYPE,
                content_id="video-1",
                submitter_id=7,
                expected_version=1,
                payload={
                    "title": "Updated title",
                    "media_url": "https://example.test/updated.mp4",
                    "source_available": False,
                },
            )

        self.assertEqual(
            self.video_action.calls[-1],
            {
                "video_id": "video-1",
                "action": "edit",
                "actor_role": "teacher",
                "actor_id": 7,
                "submitter_id": 7,
                "version": 1,
                "title": "Updated title",
                "media_url": "https://example.test/updated.mp4",
            },
        )
        self.assertEqual(result["review_status"], "pending")
        self.assertEqual(result["version"], 2)
        self.assertTrue(result["source_available"])

    def test_submit_approved_changed_payload_reopens_via_edit(self):
        self.video_provider.videos = [make_video(status="approved")]
        self.video_action.result = {
            "video_id": "video-1",
            "status": "pending",
            "version": 2,
        }

        with self.app.app_context(), self._patch_video_action():
            result = self.adapter.submit_for_review(
                content_type=VIDEO_CONTENT_TYPE,
                content_id="video-1",
                submitter_id=7,
                expected_version=1,
                payload={"title": "Replacement title"},
            )

        self.assertEqual(self.video_action.calls[-1]["action"], "edit")
        self.assertEqual(result["review_status"], "pending")

    def test_submit_unchanged_payload_does_not_call_edit(self):
        self.video_provider.videos = [make_video()]

        with self.app.app_context(), self._patch_video_action() as apply:
            result = self.adapter.submit_for_review(
                content_type=VIDEO_CONTENT_TYPE,
                content_id="video-1",
                submitter_id=7,
                expected_version=1,
                payload={
                    "title": "Teaching video",
                    "media_url": "https://example.test/video.mp4",
                },
            )

        apply.assert_not_called()
        self.assertEqual(result["review_status"], "pending")
        self.assertEqual(result["version"], 1)

    def test_craft_key_writes_are_rejected_and_source_available_is_ignored(self):
        self.video_provider.videos = [make_video()]

        with self.app.app_context(), self._patch_video_action() as apply:
            with self.assertRaises(ProviderValidationError):
                self.adapter.submit_for_review(
                    content_type=VIDEO_CONTENT_TYPE,
                    content_id="video-1",
                    submitter_id=7,
                    expected_version=1,
                    payload={"craft_key": "other"},
                )
            with self.assertRaises(ProviderValidationError):
                self.adapter.edit(
                    content_type=VIDEO_CONTENT_TYPE,
                    content_id="video-1",
                    submitter_id=7,
                    expected_version=1,
                    payload={"craft_key": "other"},
                )
            unchanged = self.adapter.submit_for_review(
                content_type=VIDEO_CONTENT_TYPE,
                content_id="video-1",
                submitter_id=7,
                expected_version=1,
                payload={"source_available": False},
            )

        apply.assert_not_called()
        self.assertTrue(unchanged["source_available"])

    def test_edit_omits_read_only_source_available_from_05_action(self):
        self.video_action.result = {
            "video_id": "video-1",
            "status": "pending",
            "version": 2,
        }

        with self.app.app_context(), self._patch_video_action():
            self.adapter.edit(
                content_type=VIDEO_CONTENT_TYPE,
                content_id="video-1",
                submitter_id=7,
                expected_version=1,
                payload={
                    "title": "Updated title",
                    "source_available": False,
                },
            )

        self.assertNotIn("source_available", self.video_action.calls[-1])
        self.assertEqual(
            self.video_action.calls[-1]["actor_role"],
            "teacher",
        )
        self.assertEqual(self.video_action.calls[-1]["actor_id"], 7)

    def test_05_errors_map_to_exact_provider_errors(self):
        cases = (
            (AgriValidationError("驳回意见不能为空"), ProviderValidationError),
            (AgriValidationError("审核版本已变化"), ProviderConflictError),
            (AgriValidationError("当前状态不可编辑"), ProviderConflictError),
            (AgriNotFoundError("视频不存在"), ProviderNotFoundError),
            (AgriAccessError("无管理权限"), ProviderAccessDeniedError),
            (AgriValidationError("只能编辑本人提交的视频"), ProviderAccessDeniedError),
            (RuntimeError("offline"), ProviderUnavailableError),
        )

        with self.app.app_context():
            for source_error, target_error in cases:
                with self.subTest(source_error=type(source_error).__name__):
                    self.video_action.error = source_error
                    with self._patch_video_action():
                        with self.assertRaises(target_error):
                            self.adapter.approve(
                                content_type=VIDEO_CONTENT_TYPE,
                                content_id="video-1",
                                submitter_id=7,
                                reviewer_id=99,
                                reviewer_role="admin",
                                expected_version=1,
                            )

    def test_list_review_items_normalizes_video_records(self):
        self.video_provider.videos = [
            make_video("video-pending", status="pending", version=1),
            make_video("video-published", status="published", version=3),
        ]

        with self.app.app_context():
            items = self.adapter.list_review_items(VIDEO_CONTENT_TYPE)

        self.assertEqual(
            [item["content_id"] for item in items],
            ["video-pending", "video-published"],
        )
        self.assertEqual(
            [item["review_status"] for item in items],
            ["pending", "approved"],
        )
        self.assertEqual(items[1]["version"], 3)
        self.assertEqual(
            items[1]["updated_at"],
            "2026-09-20T09:00:00+08:00",
        )


class CompositeContentReviewProviderTests(unittest.TestCase):
    def setUp(self):
        self.database_provider = RecordingDelegate(
            [{"content_type": "course_video", "content_id": "41"}]
        )
        self.handcraft_adapter = RecordingDelegate(
            [{"content_type": VIDEO_CONTENT_TYPE, "content_id": "video-1"}]
        )
        self.provider = CompositeContentReviewProvider(
            database_provider=self.database_provider,
            handcraft_adapter=self.handcraft_adapter,
        )

    def test_actions_dispatch_by_content_type(self):
        calls = (
            (
                "submit_for_review",
                {
                    "content_type": "job_position",
                    "content_id": "job-1",
                    "submitter_id": 8,
                    "expected_version": 1,
                    "payload": {"title": "Job"},
                },
            ),
            (
                "get_review_status",
                {
                    "content_type": VIDEO_CONTENT_TYPE,
                    "content_id": "video-1",
                },
            ),
            (
                "approve",
                {
                    "content_type": "course_video",
                    "content_id": "41",
                    "submitter_id": 7,
                    "reviewer_id": 99,
                    "reviewer_role": "admin",
                    "expected_version": 1,
                },
            ),
            (
                "reject",
                {
                    "content_type": VIDEO_CONTENT_TYPE,
                    "content_id": "video-1",
                    "submitter_id": 7,
                    "reviewer_id": 99,
                    "reviewer_role": "admin",
                    "expected_version": 1,
                    "opinion": "Rejected",
                },
            ),
            (
                "edit",
                {
                    "content_type": "job_position",
                    "content_id": "job-1",
                    "submitter_id": 8,
                    "expected_version": 1,
                    "payload": {"title": "Updated"},
                },
            ),
        )

        for method_name, kwargs in calls:
            with self.subTest(method_name=method_name):
                getattr(self.provider, method_name)(**kwargs)

        self.assertEqual(
            [call[0] for call in self.database_provider.calls],
            ["submit_for_review", "approve", "edit"],
        )
        self.assertEqual(
            [call[0] for call in self.handcraft_adapter.calls],
            ["get_review_status", "reject"],
        )

    def test_list_review_items_merges_or_filters_by_content_type(self):
        all_items = self.provider.list_review_items()
        video_items = self.provider.list_review_items(VIDEO_CONTENT_TYPE)

        self.assertEqual(
            [item["content_id"] for item in all_items],
            ["41", "video-1"],
        )
        self.assertEqual(video_items[0]["content_id"], "video-1")
        self.assertEqual(
            self.database_provider.calls,
            [
                ("list_review_items", {"content_type": None}),
            ],
        )
        self.assertEqual(
            self.handcraft_adapter.calls,
            [
                (
                    "list_review_items",
                    {"content_type": VIDEO_CONTENT_TYPE},
                ),
                (
                    "list_review_items",
                    {"content_type": VIDEO_CONTENT_TYPE},
                ),
            ],
        )

    def test_default_admin_install_registers_composite_provider(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )

        self.assertIsInstance(
            app.extensions["content_review_provider"],
            CompositeContentReviewProvider,
        )


if __name__ == "__main__":
    unittest.main()
