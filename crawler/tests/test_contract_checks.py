import json
import tempfile
import unittest
from pathlib import Path

from crawler.tools import check_contracts


class ContractChecksTest(unittest.TestCase):
    def test_repeated_table_name_check_catches_underscored_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            (docs / "bad.md").write_text(
                "std_dialect_pointss\nstage_jobs_itemss\n",
                encoding="utf-8",
            )
            original = check_contracts.DOCS
            try:
                check_contracts.DOCS = docs
                errors = check_contracts.check_docs()
            finally:
                check_contracts.DOCS = original
            self.assertTrue(
                any("std_dialect_pointss" in error for error in errors)
            )
            self.assertTrue(
                any("stage_jobs_itemss" in error for error in errors)
            )

    def test_issue_checker_rejects_nonterminal_status_and_missing_release_condition(self):
        text = """
- P0: 0
- P1: 2
- P2: 0
- 合计: 2
- 阻塞首批: 0
| ID | 来源 | 问题 | 证据链接 | 建议动作 | 状态 | 阻塞首批 |
| --- | --- | --- | --- | --- | --- | --- |
| P1-01 | a | partial | docs/a.md | 继续 | partially-resolved | 否 |
| P1-02 | b | later | docs/b.md | 以后再做 | deferred | 否 |
"""
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            (docs / "ISSUES.md").write_text(text, encoding="utf-8")
            original = check_contracts.DOCS
            try:
                check_contracts.DOCS = docs
                errors = check_contracts.check_issue_counts()
            finally:
                check_contracts.DOCS = original
            self.assertTrue(any("invalid terminal status" in error for error in errors))
            self.assertTrue(any("release condition" in error for error in errors))

    def test_history_baseline_checker_rejects_nonempty_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            operations = docs / "operations"
            operations.mkdir()
            baseline = operations / "history-hygiene-baseline.json"
            baseline.write_text(
                json.dumps({"findings": [{"object": "abc"}]}),
                encoding="utf-8",
            )
            original = check_contracts.DOCS
            try:
                check_contracts.DOCS = docs
                errors = check_contracts.check_history_baseline()
            finally:
                check_contracts.DOCS = original
            self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
