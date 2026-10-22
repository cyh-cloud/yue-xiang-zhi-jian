from io import BytesIO
import subprocess
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from crawler.tools.generate_public_fixtures import build_pdf
from crawler.tools import check_history_hygiene


class HistoryHygieneTest(unittest.TestCase):
    def test_scan_detects_raw_paths_cookies_and_private_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.test"],
                cwd=root,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=root,
                check=True,
            )
            subprocess.run(
                ["git", "config", "core.autocrlf", "false"],
                cwd=root,
                check=True,
            )
            raw = root / "crawler" / "download" / "example.test"
            raw.mkdir(parents=True)
            (raw / "home.headers").write_text(
                "Set-Cookie: session=secret\n"
                "Authorization: Bearer secret-token\n",
                encoding="utf-8",
            )
            phone = "138" + "0013" + "8000"
            (raw / "sample.html").write_text(
                f"mailto:person@example.com phone {phone}\n",
                encoding="utf-8",
            )
            private = root / "crawler" / "docs" / "private"
            private.mkdir(parents=True)
            (private / "session.txt").write_text(
                "Set-Cookie: private-session=secret\n",
                encoding="utf-8",
            )
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(
                ["git", "commit", "-m", "fixture"],
                cwd=root,
                check=True,
                capture_output=True,
            )

            original_root = check_history_hygiene.ROOT
            try:
                check_history_hygiene.ROOT = root
                findings = check_history_hygiene.scan_history()
            finally:
                check_history_hygiene.ROOT = original_root

            categories = {category for _, _, category in findings}
            self.assertIn("raw-evidence-path", categories)
            self.assertIn("set-cookie", categories)
            self.assertIn("authorization", categories)
            self.assertIn("personal-email", categories)
            self.assertIn("personal-phone", categories)
            self.assertIn("private-session-path", categories)

    def test_scan_detects_binary_evidence_leaks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.test"],
                cwd=root,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"],
                cwd=root,
                check=True,
            )
            subprocess.run(
                ["git", "config", "core.autocrlf", "false"],
                cwd=root,
                check=True,
            )
            evidence = (
                root / "crawler" / "tests" / "fixtures" / "evidence" / "bad"
            )
            evidence.mkdir(parents=True)
            workbook = Workbook()
            sheet = workbook.active
            sheet.append(["产品名称", "联系人"])
            sheet.append(["示例产品", "示例联系人"])
            workbook.properties.creator = "Original Author"
            buffer = BytesIO()
            workbook.save(buffer)
            (evidence / "contact.xlsx").write_bytes(buffer.getvalue())
            (evidence / "hidden.html").write_text(
                '<html><body><input type="hidden" name="__VIEWSTATE" '
                'value="token"></body></html>',
                encoding="utf-8",
            )
            (evidence / "bad.pdf").write_bytes(
                build_pdf(
                    [
                        "SYNTHETIC-FIXTURE",
                        "Contact: Example 13800000000",
                    ],
                    author="Original Author",
                )
            )
            subprocess.run(["git", "add", "."], cwd=root, check=True)
            subprocess.run(
                ["git", "commit", "-m", "binary fixture"],
                cwd=root,
                check=True,
                capture_output=True,
            )

            original_root = check_history_hygiene.ROOT
            try:
                check_history_hygiene.ROOT = root
                findings = check_history_hygiene.scan_history()
            finally:
                check_history_hygiene.ROOT = original_root

            categories = {category for _, _, category in findings}
            self.assertIn("personal-contact-column", categories)
            self.assertIn("hidden-form-state", categories)
            self.assertIn("original-attachment-metadata", categories)
            self.assertIn("personal-phone", categories)


if __name__ == "__main__":
    unittest.main()
