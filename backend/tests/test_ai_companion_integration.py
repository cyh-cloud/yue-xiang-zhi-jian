import ast
import io
import tokenize
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import httpx
from werkzeug.security import generate_password_hash

from app import create_app
from app.agri_skills.ai_client import (
    OpenAiCompatibleAiClient,
    set_ai_client,
)
from app.agri_skills.errors import AiUnavailableError
from app.ai_companion.constants import (
    AI_UNAVAILABLE_MESSAGE,
    REFUSAL_MESSAGE,
)
from app.ai_companion.knowledge_provider import (
    set_assistant_feature_knowledge_provider,
)
from app.ai_companion.speech import SPEECH_TO_TEXT_CALL_POINT
from app.db import get_db


PASSWORD = "password8"
TIMESTAMP = "2026-09-21T10:00:00+08:00"
AI_SOURCE_ROOT = Path(__file__).parents[1] / "app" / "ai_companion"

# 计划 Task 8 固定的六个业务代办示例：每条都命中"代办短语 + 业务动作"。
BUSINESS_PROXY_EXAMPLES = (
    "帮我投简历",
    "替我兑换奖品",
    "代我审核这个职位",
    "帮我发消息给老师",
    "替我修改个人资料",
    "帮我删除这条内容",
)

FORBIDDEN_WRITE_MODULES = (
    "app.enterprise_console.applications",
    "app.job_matching",
    "app.handcraft_inheritance",
    "app.messaging",
    "app.profiles",
    "app.admin_console.routes",
    "app.admin_console.presets",
)

# 011 契约只允许经这两个模块进入 12；provider 的传递依赖不写进 12 源文本。
ALLOWED_ADMIN_CONSOLE_MODULES = frozenset(
    {
        "app.admin_console.providers",
        "app.admin_console.errors",
    }
)


def read_ai_companion_source() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(AI_SOURCE_ROOT.glob("*.py"))
    )


def direct_imports(source: str) -> list[str]:
    tree = ast.parse(source)
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            modules.append(node.module)
    return modules


def code_without_comments(source: str) -> str:
    """去掉注释后的源码；配置键扫描只看代码，不看说明文字。"""
    tokens = tokenize.generate_tokens(io.StringIO(source).readline)
    return "".join(
        token.string
        for token in tokens
        if token.type != tokenize.COMMENT
    )


def _raises(error: Exception):
    def _stub(*args, **kwargs):
        raise error

    return _stub


def _returns(value):
    def _stub(*args, **kwargs):
        return value

    return _stub


def _intent_then(intent: str, second_stub):
    """第一次调用返回意图，第二次调用走第二段 stub。

    Mock 的 iterable side_effect 只按值返回、不执行其中的可调用对象，因此
    多段调用必须用一个可调用 side_effect 自己排序。
    """
    calls: list = []

    def _stub(*args, **kwargs):
        calls.append(args)
        if len(calls) == 1:
            return {"intent": intent}
        return second_stub(*args, **kwargs)

    return _stub


class RecordingKnowledgeProvider:
    def __init__(self, entries):
        self.entries = list(entries)
        self.calls = 0

    def list_entries(self, enabled_only=True):
        self.calls += 1
        return self.entries if enabled_only else list(self.entries)


class FailingTransport(httpx.BaseTransport):
    def handle_request(self, request):
        raise httpx.ConnectError("connection refused", request=request)


class AiCompanionIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
                "AI_API_URL": "",
                "AI_API_KEY": "",
                "AI_MODEL": "test-model",
                "AI_ASR_URL": "",
                "AI_ASR_MODEL": "test-asr-model",
            }
        )
        self.ai = Mock()
        self.ai.transcribe.return_value = "识别文字"
        self.ai.complete_json.return_value = {"intent": "out_of_scope"}
        set_ai_client(self.app, self.ai)

    def tearDown(self):
        self.temp_dir.cleanup()

    def entry(self, knowledge_id, title, body, jump_target):
        return {
            "knowledge_id": knowledge_id,
            "title": title,
            "body": body,
            "feature_key": knowledge_id.removeprefix("knowledge-"),
            "jump_target": jump_target,
            "is_enabled": 1,
            "version": 1,
            "updated_at": "2026-09-20T10:00:00+08:00",
        }

    def _insert_user(self, user_id: int, username: str, role: str) -> int:
        with self.app.app_context():
            db = get_db()
            db.execute(
                """
                INSERT INTO users (
                    id, username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    user_id,
                    username,
                    generate_password_hash(PASSWORD),
                    username,
                    role,
                    TIMESTAMP,
                    TIMESTAMP,
                ),
            )
            db.commit()
            return user_id

    def _login(self, username: str):
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": PASSWORD},
        )
        self.assertEqual(response.status_code, 200)
        return client

    def _ask(self, client, question: str, request_id: str, **extra):
        return client.post(
            "/api/ai-companion/messages",
            json={
                "question": question,
                "client_request_id": request_id,
                **extra,
            },
        )

    def _count(self, table: str, user_id: int) -> int:
        with self.app.app_context():
            row = get_db().execute(
                f"SELECT COUNT(*) AS total FROM {table} WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return int(row["total"])

    def test_provider_hot_replacement_changes_next_answer(self):
        self._insert_user(101, "provider-student", "student")
        student = self._login("provider-student")
        provider = RecordingKnowledgeProvider(
            [
                self.entry(
                    "knowledge-job",
                    "如何投递简历",
                    "进入就业对接后投递岗位",
                    "/student/employment/jobs",
                )
            ]
        )
        set_assistant_feature_knowledge_provider(self.app, provider)
        self.ai.complete_json.side_effect = [
            {"intent": "platform_usage"},
            {"answer": "进入就业对接后选择岗位投递。"},
        ]
        first = self._ask(student, "怎么投简历", "provider-1")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(
            first.get_json()["jump_target"],
            "/student/employment/jobs",
        )
        self.assertEqual(provider.calls, 1)

        # 11 侧维护变更：在同一个 provider 实例上更新条目；若 12 建立了长期
        # 缓存，第二次提问仍会返回旧的 jump_target。
        provider.entries = [
            self.entry(
                "knowledge-points",
                "积分怎么算",
                "积分通过完成课程获得",
                "/student/points",
            )
        ]
        self.ai.complete_json.side_effect = [
            {"intent": "platform_usage"},
            {"answer": "积分通过完成课程与实训获得。"},
        ]
        second = self._ask(student, "积分怎么算", "provider-2")
        self.assertEqual(second.status_code, 200)
        body = second.get_json()
        self.assertEqual(body["jump_target"], "/student/points")
        self.assertEqual(
            body["assistant_message"]["content"],
            "积分通过完成课程与实训获得。",
        )
        # 每次平台问答都重新读取来源，不建立长期缓存。
        self.assertEqual(provider.calls, 2)

        # 换槽：替换 provider 对象本身，新对象的读取次数从 0 重新计数。
        replacement = RecordingKnowledgeProvider(
            [
                self.entry(
                    "knowledge-points",
                    "积分怎么算",
                    "积分通过完成课程获得",
                    "/student/points",
                )
            ]
        )
        set_assistant_feature_knowledge_provider(self.app, replacement)
        self.ai.complete_json.side_effect = [
            {"intent": "platform_usage"},
            {"answer": "换槽后的答案。"},
        ]
        third = self._ask(student, "积分怎么算", "provider-3")
        self.assertEqual(third.status_code, 200)
        self.assertEqual(third.get_json()["jump_target"], "/student/points")
        self.assertEqual(replacement.calls, 1)
        self.assertEqual(provider.calls, 2)

    def test_ai_failure_matrix_returns_exact_503_without_local_fallback(self):
        self._insert_user(102, "failure-student", "student")
        student = self._login("failure-student")
        provider = RecordingKnowledgeProvider(
            [
                self.entry(
                    "knowledge-job",
                    "如何投递简历",
                    "进入就业对接后投递岗位",
                    "/student/employment/jobs",
                )
            ]
        )
        set_assistant_feature_knowledge_provider(self.app, provider)
        matrix = (
            ("timeout", _raises(AiUnavailableError("upstream timeout"))),
            ("not-an-object", _returns(["platform_usage"])),
            ("missing-field", _returns({"answers": ["没有 intent 字段"]})),
            ("unknown-intent", _returns({"intent": "unknown_intent"})),
            ("empty-intent", _returns({"intent": ""})),
        )
        for name, stub in matrix:
            with self.subTest(case=name):
                ai_calls_before = self.ai.complete_json.call_count
                # 可调用 stub：Mock 每次调用都真正执行它，用例必然到达
                # classify_intent 的对应分支，而不是被一次性返回值绕过。
                self.ai.complete_json.side_effect = stub
                response = self._ask(
                    student,
                    "平台怎么用",
                    f"failure-{name}",
                )
                self.assertEqual(response.status_code, 503)
                self.assertEqual(
                    response.get_json(),
                    {"success": False, "message": AI_UNAVAILABLE_MESSAGE},
                )
                # 请求确实走到了意图分类调用，失败就发生在这一段。
                self.assertEqual(
                    self.ai.complete_json.call_count,
                    ai_calls_before + 1,
                )
        # 零本地知识兜底：意图阶段就失败，不读知识来源，也不落库。
        self.assertEqual(provider.calls, 0)
        self.assertEqual(self._count("ai_companion_conversations", 102), 0)
        self.assertEqual(self._count("ai_companion_messages", 102), 0)

    def test_second_stage_failures_map_to_503_for_every_call_point(self):
        self._insert_user(107, "second-stage-student", "student")
        student = self._login("second-stage-student")
        provider = RecordingKnowledgeProvider(
            [
                self.entry(
                    "knowledge-job",
                    "如何投递简历",
                    "进入就业对接后投递岗位",
                    "/student/employment/jobs",
                )
            ]
        )
        set_assistant_feature_knowledge_provider(self.app, provider)
        # 意图 stub + 第二段 stub：第一次调用返回意图，第二次调用走第二段，
        # 分别打 ai_companion_feature_answer 与 ai_companion_learning_guidance。
        cases = (
            (
                "feature-answer-timeout",
                "platform_usage",
                _raises(AiUnavailableError("upstream timeout")),
                True,
            ),
            (
                "feature-answer-illegal-shape",
                "platform_usage",
                _returns({"answers": []}),
                True,
            ),
            (
                "feature-answer-empty-answer",
                "platform_usage",
                _returns({"answer": "  "}),
                True,
            ),
            (
                "learning-guidance-timeout",
                "learning_question",
                _raises(AiUnavailableError("upstream timeout")),
                False,
            ),
            (
                "learning-guidance-illegal-shape",
                "learning_question",
                _returns({"bullets": []}),
                False,
            ),
            (
                "learning-guidance-unknown-module",
                "learning_question",
                _returns({"bullets": ["要点一"], "module_key": "unknown"}),
                False,
            ),
        )
        for name, intent, second_stub, reads_knowledge in cases:
            with self.subTest(case=name):
                ai_calls_before = self.ai.complete_json.call_count
                provider_calls_before = provider.calls
                self.ai.complete_json.side_effect = _intent_then(
                    intent,
                    second_stub,
                )
                response = self._ask(student, "怎么投简历", f"second-{name}")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(
                    response.get_json(),
                    {"success": False, "message": AI_UNAVAILABLE_MESSAGE},
                )
                # 意图段成功后才进第二段：整次请求恰好两次 AI 调用。
                self.assertEqual(
                    self.ai.complete_json.call_count,
                    ai_calls_before + 2,
                )
                if reads_knowledge:
                    # 失败发生在第二段而非意图段：知识来源已被读取过。
                    self.assertGreater(provider.calls, provider_calls_before)
                self.assertEqual(
                    self._count("ai_companion_conversations", 107),
                    0,
                )
                self.assertEqual(
                    self._count("ai_companion_messages", 107),
                    0,
                )

    def test_refusals_only_write_ai_companion_tables(self):
        self._insert_user(103, "refusal-student", "student")
        student = self._login("refusal-student")
        statements = []
        with self.app.app_context():
            connection = get_db()
            connection.set_trace_callback(statements.append)
            for index, question in enumerate(BUSINESS_PROXY_EXAMPLES):
                response = self._ask(
                    student,
                    question,
                    f"refusal-{index}",
                )
                self.assertEqual(response.status_code, 200)
                body = response.get_json()
                self.assertEqual(
                    body["assistant_message"]["intent"],
                    "out_of_scope",
                )
                self.assertIn(
                    REFUSAL_MESSAGE,
                    body["assistant_message"]["content"],
                )
                self.assertIsNone(body["jump_target"])
            connection.set_trace_callback(None)

        writes = [
            statement
            for statement in statements
            if statement.lstrip().upper().startswith(
                ("INSERT", "UPDATE", "DELETE")
            )
        ]
        self.assertTrue(writes)
        # 001 的 load_session 每次请求都会清理过期会话，这是共享认证层的既有
        # 行为，不属于 AI 学伴的业务写路径；除该语句外不允许写其它任何表。
        for statement in writes:
            if "AI_COMPANION_" not in statement.upper():
                self.assertTrue(
                    statement.lstrip().upper().startswith(
                        "DELETE FROM SESSIONS"
                    ),
                    statement,
                )
        self.assertTrue(
            any(
                "AI_COMPANION_" in statement.upper() for statement in writes
            )
        )
        # 规则前置拒绝不调用任何 AI。
        self.ai.complete_json.assert_not_called()

    def test_imports_never_reach_business_write_modules(self):
        modules = direct_imports(read_ai_companion_source())
        self.assertTrue(modules)
        for module in modules:
            with self.subTest(module=module):
                for forbidden in FORBIDDEN_WRITE_MODULES:
                    self.assertFalse(
                        module == forbidden
                        or module.startswith(f"{forbidden}."),
                        module,
                    )
                if module.startswith("app.admin_console"):
                    self.assertIn(module, ALLOWED_ADMIN_CONSOLE_MODULES)

    def test_cross_user_conversation_read_is_not_found(self):
        self._insert_user(104, "owner-student", "student")
        self._insert_user(105, "intruder-teacher", "teacher")
        owner = self._login("owner-student")
        provider = RecordingKnowledgeProvider(
            [
                self.entry(
                    "knowledge-job",
                    "如何投递简历",
                    "进入就业对接后投递岗位",
                    "/student/employment/jobs",
                )
            ]
        )
        set_assistant_feature_knowledge_provider(self.app, provider)
        self.ai.complete_json.side_effect = [
            {"intent": "platform_usage"},
            {"answer": "唯一答案正文，仅属主可见"},
        ]
        created = self._ask(owner, "怎么投简历", "owner-read")
        self.assertEqual(created.status_code, 200)
        conversation_id = created.get_json()["conversation_id"]

        intruder = self._login("intruder-teacher")
        response = intruder.get(
            f"/api/ai-companion/conversations/{conversation_id}"
        )
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.get_json(),
            {"success": False, "message": "会话不存在"},
        )
        body = response.get_data(as_text=True)
        self.assertNotIn("唯一答案正文，仅属主可见", body)
        self.assertNotIn("怎么投简历", body)
        self.assertNotIn(conversation_id, body)

    def test_source_has_no_legacy_knowledge_or_asr_paths(self):
        source = read_ai_companion_source()
        self.assertNotIn("select_local_knowledge_entry", source)
        self.assertNotIn("local_resources_dialect_answer", source)
        self.assertNotIn("government_policies", source)
        self.assertNotIn("government_news", source)
        self.assertEqual(source.count("def transcribe("), 0)

    def test_speech_to_text_is_the_only_asr_call_point(self):
        source = read_ai_companion_source()
        code = code_without_comments(source)
        self.assertEqual(SPEECH_TO_TEXT_CALL_POINT, "speech_to_text")
        self.assertNotIn("AI_ASR_", code)
        self.assertEqual(code.count(".transcribe("), 1)
        self.assertIn("call_point=SPEECH_TO_TEXT_CALL_POINT", source)
        self.assertNotIn("httpx", source)
        self.assertNotIn("urllib", source)
        self.assertNotIn("socket", source)

    def test_owner_deletion_cascades_ai_companion_rows(self):
        self._insert_user(106, "cascade-student", "student")
        student = self._login("cascade-student")
        response = self._ask(student, "今天天气怎么样", "cascade-1")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self._count("ai_companion_conversations", 106), 1)
        self.assertEqual(self._count("ai_companion_messages", 106), 2)

        with self.app.app_context():
            db = get_db()
            db.execute("DELETE FROM users WHERE id = ?", (106,))
            db.commit()

        self.assertEqual(self._count("ai_companion_conversations", 106), 0)
        self.assertEqual(self._count("ai_companion_messages", 106), 0)

    def test_schema_and_source_have_no_audio_storage(self):
        with self.app.app_context():
            db = get_db()
            for table in ("ai_companion_conversations", "ai_companion_messages"):
                columns = [
                    row["name"]
                    for row in db.execute(f"PRAGMA table_info({table})")
                ]
                self.assertTrue(columns)
                for column in columns:
                    with self.subTest(table=table, column=column):
                        lowered = column.lower()
                        self.assertNotIn("audio", lowered)
                        self.assertNotIn("blob", lowered)
                        self.assertNotIn("file", lowered)

        source = read_ai_companion_source()
        self.assertNotIn("wb", source)
        self.assertNotIn("write_bytes", source)
        self.assertNotIn("tempfile", source)
        self.assertNotIn("NamedTemporaryFile", source)
        self.assertNotIn("mkstemp", source)

    def test_ai_failure_log_hides_private_question_and_user_id(self):
        self._insert_user(12345, "privacy-student", "student")
        set_ai_client(
            self.app,
            OpenAiCompatibleAiClient(
                api_url="https://ai.example/v1/chat/completions",
                api_key="test-only-key",
                model="test-model",
                timeout=0.01,
                transport=FailingTransport(),
            ),
        )
        student = self._login("privacy-student")
        question = "私有问题正文：我家果园的土质和施肥情况"
        with self.assertLogs(self.app.logger, level="WARNING") as captured:
            response = self._ask(student, question, "privacy-1")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.get_json(),
            {"success": False, "message": AI_UNAVAILABLE_MESSAGE},
        )

        output = "\n".join(captured.output)
        self.assertNotIn("私有问题正文", output)
        self.assertNotIn("12345", output)
        self.assertTrue(captured.records)
        for record in captured.records:
            call_point, metadata = record.args
            self.assertEqual(call_point, "ai_companion_intent")
            self.assertEqual(set(metadata), {"operation", "message_count"})
            self.assertEqual(metadata["operation"], "complete_json")


if __name__ == "__main__":
    unittest.main()
