import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.ai_companion.constants import (
    ADMIN_ROLES,
    AI_COMPANION_ROLES,
    INTENTS,
)
from app.ai_companion.knowledge_provider import (
    get_assistant_feature_knowledge_provider,
    set_assistant_feature_knowledge_provider,
)
from app.admin_console.providers import (
    AssistantFeatureKnowledgeProvider,
    DatabaseAssistantFeatureKnowledgeProvider,
    UnavailableAssistantFeatureKnowledgeProvider,
)
from app.admin_console.errors import ProviderUnavailableError
from app.db import get_db


class AiCompanionFoundationTests(unittest.TestCase):
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

    def test_exact_roles_and_intents(self):
        self.assertEqual(
            AI_COMPANION_ROLES,
            ("student", "teacher", "enterprise", "government"),
        )
        self.assertEqual(ADMIN_ROLES, ("super_admin", "admin"))
        self.assertEqual(
            INTENTS,
            ("platform_usage", "learning_question", "out_of_scope"),
        )

    def test_real_provider_default_and_single_slot_replacement(self):
        # 011 合并回收后 fresh app 默认安装真实的
        # DatabaseAssistantFeatureKnowledgeProvider；单槽替换语义不变。
        with self.app.app_context():
            provider = get_assistant_feature_knowledge_provider()
            self.assertIsInstance(
                provider,
                DatabaseAssistantFeatureKnowledgeProvider,
            )
            # 占位 provider 自身仍以 ProviderUnavailableError 失败关闭。
            placeholder = UnavailableAssistantFeatureKnowledgeProvider()
            with self.assertRaises(ProviderUnavailableError):
                placeholder.list_entries()

            replacement = object()
            set_assistant_feature_knowledge_provider(self.app, replacement)
            self.assertIs(
                get_assistant_feature_knowledge_provider(),
                replacement,
            )
            self.assertIs(
                self.app.extensions["assistant_feature_knowledge_provider"],
                replacement,
            )

    def test_reexports_are_the_same_function_objects(self):
        from app.admin_console import providers as admin_providers
        from app.ai_companion import knowledge_provider

        self.assertIs(
            knowledge_provider.set_assistant_feature_knowledge_provider,
            admin_providers.set_assistant_feature_knowledge_provider,
        )
        self.assertIs(
            knowledge_provider.get_assistant_feature_knowledge_provider,
            admin_providers.get_assistant_feature_knowledge_provider,
        )

    def test_conversation_tables_and_indexes_exist(self):
        with self.app.app_context():
            db = get_db()
            names = {
                row["name"]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type IN ('table', 'index')"
                )
            }
        self.assertIn("ai_companion_conversations", names)
        self.assertIn("ai_companion_messages", names)
        self.assertIn("idx_ai_companion_conversations_user", names)
        self.assertIn("idx_ai_companion_messages_conversation", names)
        self.assertIn("idx_ai_companion_messages_request", names)


if __name__ == "__main__":
    unittest.main()
