import hashlib
from io import BytesIO
import subprocess
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from crawler.tools.generate_public_fixtures import generate_public_fixtures
from crawler.tools.public_hygiene import (
    MAX_FIXTURE_TOTAL_BYTES,
    scan_fixture_bytes,
)


ROOT = Path(__file__).resolve().parents[2]
DOWNLOAD_PREFIX = "crawler/download/"
EVIDENCE_FIXTURES = ROOT / "crawler" / "tests" / "fixtures" / "evidence"
EVIDENCE_LEDGER = (
    ROOT / "crawler" / "docs" / "operations" / "evidence-ledger.md"
)


def _git(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


class PublicRepositoryHygieneTest(unittest.TestCase):
    def test_download_evidence_is_ignored(self):
        rel = f"{DOWNLOAD_PREFIX}probe.headers"
        result = _git("check-ignore", "-q", rel)
        self.assertEqual(result.returncode, 0, f"{rel} must be ignored")

    def test_local_specs_are_ignored(self):
        rel = ".scratch/crawler/spec.md"
        result = _git("check-ignore", "-q", rel)
        self.assertEqual(result.returncode, 0, f"{rel} must be ignored")

    def test_no_download_evidence_is_tracked(self):
        result = _git("ls-files", "-z", "--", "crawler/download")
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        tracked = [path for path in result.stdout.split(b"\0") if path]
        self.assertEqual(tracked, [], "crawler/download must remain local-only")

    def test_tracked_headers_do_not_expose_session_cookies(self):
        result = _git("ls-files", "-z", "--", "crawler/download")
        self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
        exposed = []
        for raw_path in result.stdout.split(b"\0"):
            if not raw_path.endswith(b".headers"):
                continue
            rel = raw_path.decode(errors="replace")
            content = (ROOT / rel).read_bytes()
            if b"set-cookie:" in content.lower():
                exposed.append(rel)
        self.assertEqual(exposed, [], "tracked headers must not contain Set-Cookie")

    def test_public_evidence_fixtures_are_small_and_sanitized(self):
        files = [path for path in EVIDENCE_FIXTURES.rglob("*") if path.is_file()]
        self.assertTrue(files, "public evidence fixtures must be present")
        self.assertLessEqual(
            sum(path.stat().st_size for path in files),
            MAX_FIXTURE_TOTAL_BYTES,
        )
        for path in files:
            with self.subTest(path=path.relative_to(ROOT)):
                findings = scan_fixture_bytes(path, path.read_bytes())
                self.assertEqual(findings, [], f"{path}: {findings}")

    def test_evidence_ledger_matches_fixture_sizes_and_hashes(self):
        ledger = EVIDENCE_LEDGER.read_text(encoding="utf-8")
        files = [
            path
            for path in EVIDENCE_FIXTURES.rglob("*")
            if path.is_file()
        ]
        self.assertIn(
            f"总字节 {sum(path.stat().st_size for path in files)}",
            ledger,
        )
        self.assertIn(
            f"最大单文件 {max(path.stat().st_size for path in files)} 字节",
            ledger,
        )
        for path in sorted(files):
            relative = path.relative_to(ROOT).as_posix()
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            row = f"| `{relative}` | {path.stat().st_size} | `{digest}` |"
            self.assertIn(row, ledger, relative)

    def test_fixture_generator_is_deterministic(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            generate_public_fixtures(Path(first))
            generate_public_fixtures(Path(second))
            first_files = {
                path.relative_to(first): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in Path(first).rglob("*")
                if path.is_file()
            }
            second_files = {
                path.relative_to(second): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in Path(second).rglob("*")
                if path.is_file()
            }
            self.assertEqual(first_files, second_files)

    def test_scanner_rejects_hidden_form_state_and_contact_data(self):
        html = (
            '<html><head><meta name="fixture-origin" '
            'content="synthetic-fixture"></head><body>'
            '<input type="hidden" name="__VIEWSTATE" value="token">'
            '<p>联系人：示例联系人 13800000000</p>'
            "</body></html>"
        ).encode("utf-8")

        findings = scan_fixture_bytes("bad.html", html)

        self.assertIn("hidden-form-state", findings)
        self.assertIn("personal-contact-field", findings)
        self.assertIn("personal-phone", findings)

    def test_scanner_rejects_contact_columns_and_original_xlsx_metadata(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["产品名称", "联系人"])
        sheet.append(["示例产品", "示例联系人"])
        workbook.properties.creator = "Original Author"
        workbook.properties.lastModifiedBy = "Original Author"
        buffer = BytesIO()
        workbook.save(buffer)

        findings = scan_fixture_bytes("bad.xlsx", buffer.getvalue())

        self.assertIn("missing-synthetic-marker", findings)
        self.assertIn("original-attachment-metadata", findings)
        self.assertIn("personal-contact-column", findings)


if __name__ == "__main__":
    unittest.main()
