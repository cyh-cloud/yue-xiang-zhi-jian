import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class PrivateFilesTest(unittest.TestCase):
    def test_private_session_document_is_ignored(self):
        rel = "crawler/docs/private/session.local.md"
        result = subprocess.run(
            ["git", "check-ignore", "-q", rel],
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, f"{rel} must be ignored")

    def test_crawler_database_is_ignored(self):
        rel = "crawler/data/crawler.db"
        result = subprocess.run(
            ["git", "check-ignore", "-q", rel],
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(result.returncode, 0, f"{rel} must be ignored")