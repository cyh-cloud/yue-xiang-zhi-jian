import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from crawler.pipeline.offline_fixture import (
    OfflineFixtureConfig,
    run_offline_fixture,
)


class CassLinguisticsSourceTest(unittest.TestCase):
    def test_public_article_is_written_without_requesting_login_resource(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = root / "cass-linguistics"
            fixture.mkdir()
            article = {
                "source_item_id": "6066095",
                "title": "追寻语言奥秘 回应时代需求",
                "summary": "公开研究资讯摘要",
                "published_at": "2026-09-04",
                "body_text": "公开研究资讯正文",
                "source_url": "http://ling.cass.cn/news/bensuo/202609/t20260904_6066095.html",
                "long_term_url": "http://ling.cass.cn/news/bensuo/202609/t20260904_6066095.html",
                "media": "中国社会科学网",
                "body_access": "public",
                "rights_status": "noncommercial-permitted",
            }
            login_only = {
                "source_item_id": "dialectgrammar-sample",
                "title": "登录后语料样本",
                "body_text": "不得采集",
                "source_url": "http://www.dialectgrammar.com/dialect/1",
                "long_term_url": "http://www.dialectgrammar.com/dialect/1",
                "body_access": "login-required",
            }
            (fixture / "discover.json").write_text(
                json.dumps(
                    {
                        "source_id": "cass-linguistics",
                        "items": [article, login_only],
                        "subresources": [
                            {
                                "name": "汉语方言语法特征语料库",
                                "url": "http://www.dialectgrammar.com",
                                "access": "login-required",
                                "status": "deferred",
                            }
                        ],
                        "requests": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            config = OfflineFixtureConfig(
                database_path=root / "crawler.db",
                download_root=root / "download",
                fixture_root=fixture,
            )

            result = run_offline_fixture("cass-linguistics", "fixture", config)

            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.discovered_count, 1)
            self.assertEqual(result.written_count, 1)
            conn = sqlite3.connect(config.database_path)
            try:
                row = conn.execute(
                    """
                    SELECT source_id, source_item_id, source_url, long_term_url,
                           title, body_text, body_access, content_hash
                    FROM std_research_articles
                    """
                ).fetchone()
                lexeme_count = conn.execute(
                    "SELECT COUNT(*) FROM std_dialect_lexemes"
                ).fetchone()[0]
                research_table_count = conn.execute(
                    "SELECT COUNT(*) FROM sqlite_master WHERE name = 'std_research_articles'"
                ).fetchone()[0]
                raw_urls = [item[0] for item in conn.execute("SELECT request_url FROM raw_fetches")]
            finally:
                conn.close()
            self.assertEqual(row[0], "cass-linguistics")
            self.assertEqual(row[1], "6066095")
            self.assertEqual(row[2], article["source_url"])
            self.assertEqual(row[3], article["long_term_url"])
            self.assertEqual(row[4], article["title"])
            self.assertEqual(row[5], article["body_text"])
            self.assertEqual(row[6], "public")
            self.assertTrue(row[7])
            self.assertEqual(lexeme_count, 0)
            self.assertFalse(any("dialectgrammar" in url for url in raw_urls))
            self.assertEqual(research_table_count, 1)


if __name__ == "__main__":
    unittest.main()
