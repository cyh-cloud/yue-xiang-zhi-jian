import copy
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.agri_skills.errors import AgriValidationError
from app.db import get_db
from app.handcraft_inheritance.providers import (
    get_teaching_video_provider,
    get_video_review_action_provider,
    set_teaching_video_provider,
)
from app.handcraft_inheritance.videos import (
    get_video_playback,
    list_video_reviews,
    list_student_videos,
    set_video_review_provider,
    update_pending_video_contract,
)


class StaticTeachingVideoProvider:
    def __init__(self, videos):
        self.videos = copy.deepcopy(videos)

    def list_videos(self, craft_key=None):
        return [
            copy.deepcopy(video)
            for video in self.videos
            if craft_key is None or video["craft_key"] == craft_key
        ]

    def get_video(self, video_id):
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
        return video["review_status"] if video is not None else None


class ReplacingVideoReviewProvider(StaticTeachingVideoProvider):
    def apply(self, action):
        return dict(action)


class TestHandcraftVideos(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def _insert_video(
        self,
        video_id,
        *,
        review_status="approved",
        source_available=True,
        media_url="https://example.test/visible.mp4",
        version=1,
        rejection_opinion=None,
    ):
        get_db().execute(
            """
            INSERT INTO heritage_videos (
                video_id, craft_key, title, review_status,
                source_available, media_url, version, rejection_opinion,
                published_at, created_at, updated_at
            )
            VALUES (?, 'guangxiu', ?, ?, ?, ?, ?, ?,
                    '2026-09-18T00:00:00+08:00',
                    '2026-09-18T00:00:00+08:00',
                    '2026-09-18T00:00:00+08:00')
            """,
            (
                video_id,
                video_id,
                review_status,
                int(source_available),
                media_url,
                version,
                rejection_opinion,
            ),
        )

    def test_student_catalog_returns_only_approved_playable_demo_video(self):
        with self.app.app_context():
            videos = list_student_videos("guangxiu")

        self.assertEqual(len(videos), 1)
        video = videos[0]
        self.assertEqual(video["video_id"], "demo-guangxiu-approved")
        self.assertEqual(video["craft_key"], "guangxiu")
        self.assertEqual(video["review_status"], "approved")
        self.assertTrue(video["source_available"])
        self.assertTrue(video["available"])
        self.assertEqual(video["playback_url"], video["media_url"])
        self.assertTrue(video["playback_url"].startswith("https://example.test/"))
        self.assertTrue(video["is_demo"])

    def test_student_catalog_hides_nonapproved_and_media_mismatches(self):
        records = {
            "approved-visible": ("approved", True, "https://example.test/visible.mp4", 1),
            "pending-video": ("pending", True, "https://example.test/pending.mp4", 1),
            "rejected-video": ("rejected", True, "https://example.test/rejected.mp4", 1),
            "offline-video": ("offline", True, "https://example.test/offline.mp4", 1),
            "offline-media": ("approved", False, "https://example.test/offline.mp4", 1),
            "missing-media": ("approved", True, "", 1),
        }
        with self.app.app_context():
            db = get_db()
            for video_id, record in records.items():
                self._insert_video(
                    video_id,
                    review_status=record[0],
                    source_available=record[1],
                    media_url=record[2],
                    version=record[3],
                )
            self._insert_video(
                "mismatch-status",
                review_status="approved",
                media_url="https://example.test/mismatch-status.mp4",
            )
            self._insert_video(
                "mismatch-media",
                review_status="approved",
                media_url="https://example.test/database.mp4",
            )
            self._insert_video(
                "mismatch-version",
                review_status="approved",
                media_url="https://example.test/mismatch-version.mp4",
            )
            self._insert_video(
                "numeric-offline-media",
                review_status="approved",
                media_url="https://example.test/numeric-offline.mp4",
            )
            db.commit()

            provider_videos = [
                {
                    "video_id": video_id,
                    "craft_key": "guangxiu",
                    "review_status": values[0],
                    "source_available": values[1],
                    "media_url": values[2],
                    "version": values[3],
                }
                for video_id, values in records.items()
            ]
            provider_videos.extend(
                [
                    {
                        "video_id": "mismatch-status",
                        "craft_key": "guangxiu",
                        "review_status": "pending",
                        "source_available": True,
                        "media_url": "https://example.test/mismatch-status.mp4",
                        "version": 1,
                    },
                    {
                        "video_id": "mismatch-media",
                        "craft_key": "guangxiu",
                        "review_status": "approved",
                        "source_available": True,
                        "media_url": "https://example.test/provider.mp4",
                        "version": 1,
                    },
                    {
                        "video_id": "mismatch-version",
                        "craft_key": "guangxiu",
                        "review_status": "approved",
                        "source_available": True,
                        "media_url": "https://example.test/mismatch-version.mp4",
                        "version": 2,
                    },
                    {
                        "video_id": "numeric-offline-media",
                        "craft_key": "guangxiu",
                        "review_status": "approved",
                        "source_available": 0,
                        "media_url": "https://example.test/numeric-offline.mp4",
                        "version": 1,
                    },
                ]
            )
            set_teaching_video_provider(
                self.app,
                StaticTeachingVideoProvider(provider_videos),
            )
            videos = list_student_videos("guangxiu")
            mismatch = get_video_playback("mismatch-status")
            provider_missing = get_video_playback("provider-missing")

        self.assertEqual(
            [video["video_id"] for video in videos],
            ["approved-visible"],
        )
        self.assertFalse(mismatch["available"])
        self.assertEqual(
            mismatch["unavailable_reason"],
            "视频媒体信息不一致",
        )
        self.assertFalse(provider_missing["available"])
        self.assertEqual(
            provider_missing["unavailable_reason"],
            "视频不可用",
        )

    def test_review_catalog_keeps_historical_status_after_provider_replacement(self):
        with self.app.app_context():
            self._insert_video("pending-video", review_status="pending")
            self._insert_video("rejected-video", review_status="rejected")
            self._insert_video("offline-video", review_status="offline")
            get_db().commit()
            set_teaching_video_provider(
                self.app,
                StaticTeachingVideoProvider([]),
            )

            reviews = {
                review["video_id"]: review
                for review in list_video_reviews()
            }

        self.assertEqual(reviews["pending-video"]["review_status"], "pending")
        self.assertEqual(reviews["rejected-video"]["review_status"], "rejected")
        self.assertEqual(reviews["offline-video"]["review_status"], "offline")
        self.assertFalse(reviews["pending-video"]["provider_available"])
        self.assertFalse(reviews["pending-video"]["contract_valid"])

    def test_pending_edit_and_approved_edit_follow_review_contract(self):
        with self.app.app_context():
            self._insert_video(
                "pending-video",
                review_status="pending",
                media_url="https://example.test/pending.mp4",
            )
            self._insert_video(
                "approved-video",
                review_status="approved",
                media_url="https://example.test/approved.mp4",
            )
            get_db().commit()
            set_teaching_video_provider(
                self.app,
                StaticTeachingVideoProvider(
                    [
                        {
                            "video_id": "pending-video",
                            "craft_key": "guangxiu",
                            "review_status": "pending",
                            "source_available": True,
                            "media_url": "https://example.test/pending.mp4",
                            "version": 1,
                        },
                        {
                            "video_id": "approved-video",
                            "craft_key": "guangxiu",
                            "review_status": "approved",
                            "source_available": True,
                            "media_url": "https://example.test/approved.mp4",
                            "version": 1,
                        },
                    ]
                ),
            )

            pending = update_pending_video_contract(
                "pending-video",
                version=1,
                title="待审核视频修订",
                media_url="https://example.test/pending-v2.mp4",
                actor_id=1,
                submitter_id=1,
            )
            approved = update_pending_video_contract(
                "approved-video",
                version=1,
                title="已上架视频修订",
                actor_id=1,
                submitter_id=1,
            )
            approved_row = get_db().execute(
                """
                SELECT review_status, version, published_at, title
                FROM heritage_videos
                WHERE video_id = 'approved-video'
                """
            ).fetchone()
            hidden = get_video_playback("approved-video")
            with self.assertRaisesRegex(AgriValidationError, "版本"):
                update_pending_video_contract(
                    "approved-video",
                    version=1,
                    title="冲突修改",
                    actor_id=1,
                    submitter_id=1,
                )
            after_conflict = get_db().execute(
                """
                SELECT review_status, version, title
                FROM heritage_videos
                WHERE video_id = 'approved-video'
                """
            ).fetchone()

        self.assertEqual(pending["status"], "pending")
        self.assertEqual(pending["version"], 2)
        self.assertEqual(approved["status"], "pending")
        self.assertEqual(approved["version"], 2)
        self.assertEqual(approved_row["review_status"], "pending")
        self.assertEqual(approved_row["version"], 2)
        self.assertIsNone(approved_row["published_at"])
        self.assertEqual(approved_row["title"], "已上架视频修订")
        self.assertFalse(hidden["available"])
        self.assertEqual(after_conflict["review_status"], "pending")
        self.assertEqual(after_conflict["version"], 2)
        self.assertEqual(after_conflict["title"], "已上架视频修订")

    def test_review_provider_is_replaceable_without_comment_or_report_storage(self):
        replacement = ReplacingVideoReviewProvider([])
        set_video_review_provider(self.app, replacement)

        with self.app.app_context():
            self.assertIs(get_teaching_video_provider(), replacement)
            self.assertIs(get_video_review_action_provider(), replacement)

            set_teaching_video_provider(
                self.app,
                StaticTeachingVideoProvider(
                    [
                        {
                            "video_id": "demo-guangxiu-approved",
                            "craft_key": "guangxiu",
                            "review_status": "approved",
                            "source_available": True,
                            "media_url": (
                                "https://example.test/handcraft/guangxiu.mp4"
                            ),
                            "version": 1,
                            "is_demo": True,
                        }
                    ]
                ),
            )
            video = list_student_videos("guangxiu")[0]
            table_names = {
                row["name"].lower()
                for row in get_db().execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

        self.assertNotIn("comment", video)
        self.assertNotIn("report", video)
        self.assertFalse(
            any("comment" in name or "report" in name for name in table_names)
        )

    def test_student_video_dto_hides_review_opinion_and_unavailable_media(self):
        with self.app.app_context():
            self._insert_video(
                "rejected-video",
                review_status="rejected",
                media_url="https://private.example.test/rejected.mp4",
                rejection_opinion="画面需要重录。",
            )
            get_db().commit()

            rejected = get_video_playback("rejected-video")
            visible = list_student_videos("guangxiu")
            reviews = {
                review["video_id"]: review
                for review in list_video_reviews()
            }

        self.assertNotIn("rejection_opinion", rejected)
        self.assertIsNone(rejected["media_url"])
        self.assertTrue(visible)
        for video in visible:
            self.assertNotIn("rejection_opinion", video)
        self.assertEqual(
            reviews["rejected-video"]["rejection_opinion"],
            "画面需要重录。",
        )


if __name__ == "__main__":
    unittest.main()
