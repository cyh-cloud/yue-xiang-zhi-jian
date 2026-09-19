import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from app import create_app
from app.db import get_db
from app.government_console.errors import (
    ProviderNotFoundError,
    ProviderValidationError,
)
from app.government_console.news import (
    delete_news,
    get_news,
    list_news,
    publish_news,
)


class GovernmentNewsTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
            }
        )
        with self.app.app_context():
            cursor = get_db().execute(
                """
                INSERT INTO users (
                    username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (
                    'government', 'hash', '政府用户', 'government', 1,
                    '2026-09-18T09:00:00+08:00',
                    '2026-09-18T09:00:00+08:00'
                )
                """
            )
            get_db().commit()
            self.government_id = int(cursor.lastrowid)

    def tearDown(self):
        self.temp_dir.cleanup()

    def publication_kwargs(self, **overrides):
        values = {
            "actor_id": self.government_id,
            "request_id": "news-1",
            "title": "暴雨预警",
            "content": "注意防范",
            "category_code": "disaster_warning",
        }
        values.update(overrides)
        return values

    def test_news_has_no_unpublish_or_relist_action(self):
        with self.app.app_context():
            news = publish_news(**self.publication_kwargs())

            self.assertEqual(news["category_label"], "灾害预警")
            self.assertNotIn("status", news)
            self.assertFalse(hasattr(delete_news, "unpublish"))

            delete_news(news["id"], expected_version=news["version"])
            self.assertIsNone(get_news(news["id"]))

    def test_publish_news_never_calls_policy_push(self):
        with self.app.app_context():
            with patch(
                "app.government_console.news.emit_policy_published"
            ) as emit:
                publish_news(
                    actor_id=self.government_id,
                    request_id="news-2",
                    title="本地新闻",
                    content="正文",
                    category_code="news",
                )

            emit.assert_not_called()

    def test_all_three_categories_use_manual_category_labels(self):
        with self.app.app_context():
            expected = (
                ("news", "新闻"),
                ("disaster_warning", "灾害预警"),
                ("policy_update", "政策更新"),
            )
            for category_code, label in expected:
                with self.subTest(category_code=category_code):
                    news = publish_news(
                        **self.publication_kwargs(
                            request_id=f"news-{category_code}",
                            category_code=category_code,
                        )
                    )
                    self.assertEqual(news["category_code"], category_code)
                    self.assertEqual(news["category_label"], label)
                    self.assertNotIn("status", news)

    def test_publish_is_idempotent_for_the_same_request(self):
        with self.app.app_context():
            first = publish_news(**self.publication_kwargs())
            second = publish_news(**self.publication_kwargs())

            self.assertEqual(first["id"], second["id"])
            self.assertEqual(self.count_news(), 1)
            self.assertEqual(self.count_publication_requests(), 1)

    def test_list_filters_by_category_and_orders_by_publication_time(self):
        with self.app.app_context():
            first = publish_news(
                **self.publication_kwargs(request_id="news-first")
            )
            second = publish_news(
                **self.publication_kwargs(
                    request_id="news-second",
                    category_code="news",
                )
            )
            third = publish_news(
                **self.publication_kwargs(
                    request_id="news-third",
                    category_code="policy_update",
                )
            )
            for news_id, published_at in (
                (first["id"], "2026-09-18T10:00:00+08:00"),
                (second["id"], "2026-09-18T09:00:00+08:00"),
                (third["id"], "2026-09-18T11:00:00+08:00"),
            ):
                get_db().execute(
                    """
                    UPDATE government_news
                    SET published_at = ?
                    WHERE id = ?
                    """,
                    (published_at, news_id),
                )
            get_db().commit()

            self.assertEqual(
                [item["id"] for item in list_news()],
                [third["id"], first["id"], second["id"]],
            )
            self.assertEqual(
                [item["id"] for item in list_news(category_code="news")],
                [second["id"]],
            )

    def test_delete_hard_deletes_content_and_associated_view_events(self):
        with self.app.app_context():
            news = publish_news(**self.publication_kwargs())
            get_db().execute(
                """
                INSERT INTO government_view_events (
                    content_type, content_id, view_event_id, created_at
                )
                VALUES ('news', ?, 'view-1', ?)
                """,
                (news["id"], news["updated_at"]),
            )
            get_db().commit()

            delete_news(news["id"], expected_version=news["version"])

            self.assertIsNone(get_news(news["id"]))
            self.assertEqual(list_news(), [])
            self.assertEqual(self.count_view_events(news["id"]), 0)

    def test_delete_rejects_missing_or_stale_version_without_removing_news(self):
        with self.app.app_context():
            news = publish_news(**self.publication_kwargs())

            with self.assertRaises(ProviderNotFoundError):
                delete_news(
                    news["id"],
                    expected_version=news["version"] + 1,
                )

            self.assertIsNotNone(get_news(news["id"]))
            self.assertEqual(self.count_news(), 1)

    def test_validation_rejects_blank_unknown_or_non_text_values(self):
        with self.app.app_context():
            invalid_values = (
                ("request_id", " "),
                ("title", ""),
                ("content", "\t"),
                ("category_code", "unknown"),
                ("actor_id", True),
                ("title", 123),
            )
            for field, value in invalid_values:
                with self.subTest(field=field, value=value):
                    with self.assertRaises(ProviderValidationError):
                        publish_news(
                            **self.publication_kwargs(
                                **{field: value},
                            )
                        )

            self.assertEqual(self.count_news(), 0)
            self.assertEqual(self.count_publication_requests(), 0)

    def test_list_validation_rejects_invalid_category_filter(self):
        with self.app.app_context():
            with self.assertRaises(ProviderValidationError):
                list_news(category_code="unknown")
            with self.assertRaises(ProviderValidationError):
                list_news(category_code=[])

    def count_news(self):
        return int(
            get_db().execute(
                "SELECT COUNT(*) FROM government_news"
            ).fetchone()[0]
        )

    def count_publication_requests(self):
        return int(
            get_db().execute(
                """
                SELECT COUNT(*)
                FROM government_publication_requests
                WHERE content_type = 'news'
                """
            ).fetchone()[0]
        )

    def count_view_events(self, news_id):
        return int(
            get_db().execute(
                """
                SELECT COUNT(*)
                FROM government_view_events
                WHERE content_type = 'news' AND content_id = ?
                """,
                (news_id,),
            ).fetchone()[0]
        )
