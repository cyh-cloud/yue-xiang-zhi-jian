import tempfile
from pathlib import Path
from unittest import TestCase

from app import create_app
from app.db import get_db
from app.government_console.providers import (
    get_employment_statistics_provider,
    get_policy_news_provider,
)


class GovernmentFoundationTests(TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_government_tables_exist(self):
        with self.app.app_context():
            names = {
                row["name"]
                for row in get_db().execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        self.assertTrue(
            {
                "government_policies",
                "government_news",
                "government_publication_requests",
                "government_view_events",
            }.issubset(names)
        )

    def test_default_employment_provider_returns_unavailable(self):
        with self.app.app_context():
            provider = get_employment_statistics_provider()
            self.assertIsNone(provider.get_active_job_count())
            self.assertIsNone(provider.get_cumulative_application_count())

    def test_default_policy_news_provider_is_complete(self):
        with self.app.app_context():
            provider = get_policy_news_provider()
            self.assertEqual(provider.list_published_policies(), [])
            self.assertEqual(provider.list_published_news(), [])
            self.assertIsNone(provider.get_published_policy("missing"))
            self.assertIsNone(provider.get_published_news("missing"))
