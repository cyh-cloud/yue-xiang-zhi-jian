import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app import create_app
from app.admin_console.errors import ProviderUnavailableError
from app.agri_skills.ai_client import set_ai_client
from app.ai_companion.errors import AiCompanionKnowledgeUnavailableError
from app.ai_companion.knowledge import (
    answer_platform_question,
    load_enabled_entries,
    rank_knowledge_entries,
    validate_knowledge_entry,
)
from app.ai_companion.knowledge_provider import (
    set_assistant_feature_knowledge_provider,
)


class FakeProvider:
    def __init__(self, entries, error=None):
        self.entries = entries
        self.error = error

    def list_entries(self, enabled_only=True):
        if self.error:
            raise self.error
        return self.entries if enabled_only else list(self.entries)


class AiCompanionKnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
            }
        )
        self.ai = Mock()
        set_ai_client(self.app, self.ai)

    def tearDown(self):
        self.temp_dir.cleanup()

    def entry(
        self,
        knowledge_id,
        title,
        body,
        jump_target,
        *,
        is_enabled=1,
    ):
        return {
            "knowledge_id": knowledge_id,
            "title": title,
            "body": body,
            "feature_key": knowledge_id.removeprefix("knowledge-"),
            "jump_target": jump_target,
            "is_enabled": is_enabled,
            "version": 1,
            "updated_at": "2026-09-20T10:00:00+08:00",
        }

    def job_entry(self):
        return self.entry(
            "knowledge-job",
            "如何投递简历",
            "进入就业对接",
            "/student/employment/jobs",
        )

    def test_rank_uses_deterministic_title_body_match(self):
        entries = [
            self.entry(
                "knowledge-job",
                "如何投递简历",
                "进入就业对接投递岗位",
                "/student/employment/jobs",
            )
        ]
        ranked = rank_knowledge_entries("怎么投简历", entries)
        self.assertEqual(
            [item["knowledge_id"] for item in ranked],
            ["knowledge-job"],
        )

    def test_empty_or_unavailable_provider_uses_knowledge_message(self):
        set_assistant_feature_knowledge_provider(self.app, FakeProvider([]))
        with self.app.app_context():
            with self.assertRaises(AiCompanionKnowledgeUnavailableError):
                answer_platform_question("怎么投简历")

    def test_invalid_jump_target_is_removed(self):
        set_assistant_feature_knowledge_provider(
            self.app,
            FakeProvider(
                [
                    self.entry(
                        "knowledge-job",
                        "如何投递简历",
                        "进入就业对接",
                        "https://evil.example",
                    )
                ]
            ),
        )
        self.ai.complete_json.return_value = {"answer": "进入就业对接投递。"}
        with self.app.app_context():
            result = answer_platform_question("怎么投简历")
        self.assertIsNone(result["jump_target"])

    def test_platform_answer_uses_whitelisted_fields(self):
        set_assistant_feature_knowledge_provider(
            self.app,
            FakeProvider(
                [
                    self.entry(
                        "knowledge-job",
                        "如何投递简历",
                        "进入就业对接",
                        "/student/employment/jobs",
                    )
                ]
            ),
        )
        self.ai.complete_json.return_value = {"answer": "进入就业对接，选择岗位后投递。"}
        with self.app.app_context():
            result = answer_platform_question("怎么投简历")
        self.assertEqual(result["jump_target"], "/student/employment/jobs")
        call = self.ai.complete_json.call_args
        self.assertEqual(call.kwargs["call_point"], "ai_companion_feature_answer")
        self.assertNotIn("secret", str(call.args[0]))

    def test_no_match_and_disabled_entries_use_knowledge_message(self):
        set_assistant_feature_knowledge_provider(
            self.app,
            FakeProvider(
                [
                    self.entry(
                        "knowledge-job",
                        "如何投递简历",
                        "进入就业对接",
                        "/student/employment/jobs",
                        is_enabled=0,
                    )
                ]
            ),
        )
        with self.app.app_context():
            with self.assertRaises(AiCompanionKnowledgeUnavailableError):
                answer_platform_question("怎么投简历")

        set_assistant_feature_knowledge_provider(
            self.app,
            FakeProvider([self.job_entry()]),
        )
        with self.app.app_context():
            with self.assertRaises(AiCompanionKnowledgeUnavailableError):
                answer_platform_question("完全无关的问题")

    def test_provider_that_ignores_enabled_only_is_filtered_again(self):
        class IgnoringProvider(FakeProvider):
            def list_entries(self, enabled_only=True):
                return self.entries

        set_assistant_feature_knowledge_provider(
            self.app,
            IgnoringProvider(
                [
                    self.entry(
                        "disabled",
                        "如何投递简历",
                        "进入就业对接",
                        "/student/employment/jobs",
                        is_enabled=0,
                    )
                ]
            ),
        )
        with self.app.app_context():
            self.assertEqual(load_enabled_entries(), [])

    def test_invalid_or_unknown_structure_empties_source(self):
        set_assistant_feature_knowledge_provider(
            self.app,
            FakeProvider(
                [
                    {"knowledge_id": "missing-fields"},
                    {"unknown": "shape"},
                    self.job_entry(),
                ]
            ),
        )
        with self.app.app_context():
            self.assertEqual(load_enabled_entries(), [])

    def test_provider_failure_uses_knowledge_message_not_ai_message(self):
        set_assistant_feature_knowledge_provider(
            self.app,
            FakeProvider(
                [self.job_entry()],
                error=ProviderUnavailableError(
                    "AI 学伴功能说明知识库暂不可用",
                    code="assistant_feature_knowledge_unavailable",
                    details={},
                ),
            ),
        )
        with self.app.app_context():
            with self.assertRaises(AiCompanionKnowledgeUnavailableError):
                answer_platform_question("怎么投简历")
        self.ai.complete_json.assert_not_called()

        set_assistant_feature_knowledge_provider(
            self.app,
            FakeProvider([self.job_entry()], error=RuntimeError("boom")),
        )
        with self.app.app_context():
            with self.assertRaises(AiCompanionKnowledgeUnavailableError):
                answer_platform_question("怎么投简历")
        self.ai.complete_json.assert_not_called()

    def test_validate_knowledge_entry_rejects_broken_entries(self):
        self.assertIsNone(validate_knowledge_entry(None))
        self.assertIsNone(validate_knowledge_entry(["not", "a", "dict"]))
        self.assertIsNone(
            validate_knowledge_entry({"knowledge_id": "missing-fields"})
        )

        broken = self.job_entry()
        broken["body"] = ""
        self.assertIsNone(validate_knowledge_entry(broken))

        broken = self.job_entry()
        broken["version"] = 0
        self.assertIsNone(validate_knowledge_entry(broken))

        broken = self.job_entry()
        broken["version"] = "1"
        self.assertIsNone(validate_knowledge_entry(broken))

        broken = self.job_entry()
        broken["updated_at"] = "2026-09-20T10:00:00"
        self.assertIsNone(validate_knowledge_entry(broken))

        broken = self.job_entry()
        broken["is_enabled"] = 2
        self.assertIsNone(validate_knowledge_entry(broken))

    def test_validate_knowledge_entry_normalizes_enabled_and_jump_target(self):
        entry = validate_knowledge_entry(self.job_entry())
        self.assertIs(entry["is_enabled"], True)
        self.assertEqual(entry["jump_target"], "/student/employment/jobs")

        enabled = self.job_entry()
        enabled["is_enabled"] = True
        self.assertIs(validate_knowledge_entry(enabled)["is_enabled"], True)

        disabled = self.job_entry()
        disabled["is_enabled"] = 0
        self.assertIs(validate_knowledge_entry(disabled)["is_enabled"], False)

        external = self.job_entry()
        external["jump_target"] = "https://evil.example"
        entry = validate_knowledge_entry(external)
        self.assertEqual(entry["knowledge_id"], "knowledge-job")
        self.assertIsNone(entry["jump_target"])

        protocol_relative = self.job_entry()
        protocol_relative["jump_target"] = "//evil.example"
        self.assertIsNone(
            validate_knowledge_entry(protocol_relative)["jump_target"]
        )

        empty = self.job_entry()
        empty["jump_target"] = ""
        self.assertIsNone(validate_knowledge_entry(empty)["jump_target"])


if __name__ == "__main__":
    unittest.main()
