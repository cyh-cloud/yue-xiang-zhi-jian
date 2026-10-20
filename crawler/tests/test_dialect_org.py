import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from crawler.pipeline import RunConfig, run_source


FIXTURE_ROOT = (
    Path(__file__).resolve().parent / "fixtures" / "evidence" / "dialect-org"
)


class DialectOrgSourceTest(unittest.TestCase):
    def test_fixture_detail_persists_point_lexeme_and_invalid_audio_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config = RunConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=FIXTURE_ROOT,
            )

            first = run_source("dialect-org", "fixture", config)
            second = run_source("dialect-org", "fixture", config)

            self.assertEqual(first.status, "succeeded")
            self.assertEqual(first.discovered_count, 1)
            self.assertEqual(first.written_count, 1)
            self.assertEqual(second.status, "succeeded")
            self.assertEqual(second.written_count, 1)

            conn = sqlite3.connect(config.database_path)
            try:
                point = conn.execute(
                    "SELECT region_raw, province, city, dialect_name, extra "
                    "FROM std_dialect_points"
                ).fetchone()
                lexeme = conn.execute(
                    "SELECT lemma, phonetic, definition, audio_url, audio_status, extra, "
                    "source_id, source_item_id, source_url, long_term_url, detail_url, "
                    "detail_url_status, fetch_url, rights_status, attribution_required, "
                    "attribution_text, rights_evidence_url "
                    "FROM std_dialect_lexemes"
                ).fetchone()
                source = conn.execute(
                    "SELECT source_id, source_item_id, source_url, long_term_url, "
                    "detail_url, detail_url_status, fetch_url, rights_status, "
                    "attribution_required, attribution_text, rights_evidence_url "
                    "FROM std_dialect_lexeme_sources"
                ).fetchone()
            finally:
                conn.close()

            self.assertEqual(point[0], "未知地区")
            self.assertIsNone(point[1])
            self.assertIsNone(point[2])
            self.assertIsNone(point[3])
            point_extra = json.loads(point[4])
            self.assertEqual(point_extra["region_normalization"]["status"], "unresolved")
            self.assertNotIn("latitude", point_extra)
            self.assertNotIn("longitude", point_extra)
            self.assertNotIn("dialect_family", point_extra)

            self.assertEqual(lexeme[0], "食饭")
            self.assertEqual(lexeme[1], "Sik6 faan6")
            self.assertEqual(lexeme[2], "粤语：吃饭")
            self.assertIsNone(lexeme[3])
            self.assertEqual(lexeme[4], "invalid")
            lexeme_extra = json.loads(lexeme[5])
            self.assertEqual(lexeme_extra["audio"]["status"], "invalid")
            self.assertIn("audio", lexeme_extra)
            self.assertEqual(lexeme[6], "dialect-org")
            self.assertEqual(lexeme[7], "1")
            self.assertEqual(lexeme[8], "https://dialect.org.cn/dialect/1")
            self.assertEqual(lexeme[9], "https://dialect.org.cn/dialect/1")
            self.assertEqual(lexeme[10], "https://dialect.org.cn/dialect/1")
            self.assertEqual(lexeme[11], "direct")
            self.assertIsNone(lexeme[12])
            self.assertEqual(lexeme[13], "attribution-required")
            self.assertEqual(lexeme[14], 1)
            self.assertEqual(lexeme[15], "中国方言库")
            self.assertEqual(lexeme[16], "https://dialect.org.cn/")

            self.assertEqual(source[0], "dialect-org")
            self.assertEqual(source[1], "1")
            self.assertEqual(source[2], "https://dialect.org.cn/dialect/1")
            self.assertEqual(source[3], "https://dialect.org.cn/dialect/1")
            self.assertEqual(source[4], "https://dialect.org.cn/dialect/1")
            self.assertEqual(source[5], "direct")
            self.assertIsNone(source[6])
            self.assertEqual(source[7], "attribution-required")
            self.assertEqual(source[8], 1)
            self.assertEqual(source[9], "中国方言库")
            self.assertEqual(source[10], "https://dialect.org.cn/")
            conn = sqlite3.connect(config.database_path)
            try:
                stage = conn.execute(
                    "SELECT source_item_id, source_url, detail_url_status, title, rights_status "
                    "FROM stage_fixture_items"
                ).fetchone()
            finally:
                conn.close()
            self.assertEqual(stage[0], "1")
            self.assertEqual(stage[1], "https://dialect.org.cn/dialect/1")
            self.assertEqual(stage[2], "direct")
            self.assertEqual(stage[3], "食饭")
            self.assertEqual(stage[4], "attribution-required")

            conn = sqlite3.connect(config.database_path)
            try:
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM std_dialect_points").fetchone()[0],
                    1,
                )
                self.assertEqual(
                    conn.execute("SELECT COUNT(*) FROM std_dialect_lexemes").fetchone()[0],
                    1,
                )
                self.assertEqual(
                    conn.execute(
                        "SELECT COUNT(*) FROM std_dialect_lexeme_sources"
                    ).fetchone()[0],
                    1,
                )
            finally:
                conn.close()

    def test_missing_audio_is_distinct_from_invalid_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "dialect-org"
            fixture.mkdir()
            (fixture / "discover.json").write_text(
                json.dumps(
                    {
                        "source_id": "dialect-org",
                        "items": [
                            {
                                "source_item_id": "8",
                                "detail_html": (
                                    '<main><div class="detail-header">'
                                    '<span class="card-tag">广东广州</span></div>'
                                    '<h1 class="detail-word">食饭</h1>'
                                    '<div class="detail-phonetic">Sik6 faan6</div>'
                                    '<div class="audio-box">暂无音频录音</div>'
                                    '<div class="card"><p>粤语</p></div></main>'
                                ),
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            config = RunConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=fixture,
            )

            result = run_source("dialect-org", "fixture", config)

            self.assertEqual(result.status, "succeeded")
            conn = sqlite3.connect(config.database_path)
            try:
                point = conn.execute(
                    "SELECT province, city, extra FROM std_dialect_points"
                ).fetchone()
                lexeme = conn.execute(
                    "SELECT audio_url, audio_status FROM std_dialect_lexemes"
                ).fetchone()
            finally:
                conn.close()
            self.assertEqual(point[0], "广东")
            self.assertEqual(point[1], "广州")
            self.assertEqual(json.loads(point[2])["region_normalization"]["status"], "resolved")
            self.assertIsNone(lexeme[0])
            self.assertEqual(lexeme[1], "missing")
