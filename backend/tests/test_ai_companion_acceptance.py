"""012 AI 学伴 whole-feature acceptance and 011 provider reconciliation.

This module is the final acceptance gate for feature 012. It deliberately
re-asserts the seven whole-feature behaviours at the API level instead of
trusting the per-task suites, and it proves the 011 provider-ownership facts
as facts (identity, single definition, the missing
`admin_assistant_feature_knowledge` table and the entry field shape). No test
here creates the 011 table, registers a provider on behalf of 011, or stubs
around a gap: every assertion reads live repository state.
"""

import ast
import io
import re
import sqlite3
import tempfile
import tokenize
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

from werkzeug.security import generate_password_hash

from app import create_app
from app.admin_console import providers as admin_providers
from app.admin_console.presets import (
    DatabaseAssistantFeatureKnowledgeProvider,
    _serialize_knowledge_entry,
)
from app.admin_console.routes import admin_console_bp
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.errors import (
    AgriValidationError,
    AiUnavailableError,
)
from app.ai_companion import knowledge_provider
from app.ai_companion.constants import (
    AI_UNAVAILABLE_MESSAGE,
    ASR_FAILURE_MESSAGE,
    KNOWLEDGE_UNAVAILABLE_MESSAGE,
    REFUSAL_MESSAGE,
)
from app.ai_companion.knowledge import KNOWLEDGE_FIELDS
from app.ai_companion.speech import SPEECH_TO_TEXT_CALL_POINT
from app.db import get_db


PASSWORD = "password8"
TIMESTAMP = "2026-09-21T10:00:00+08:00"
AI_SOURCE_ROOT = Path(__file__).parents[1] / "app" / "ai_companion"
APP_SOURCE_ROOT = Path(__file__).parents[1] / "app"
PROVIDERS_SOURCE_PATH = APP_SOURCE_ROOT / "admin_console" / "providers.py"
PRESETS_SOURCE_PATH = APP_SOURCE_ROOT / "admin_console" / "presets.py"
KNOWLEDGE_PROVIDER_SOURCE_PATH = (
    APP_SOURCE_ROOT / "ai_companion" / "knowledge_provider.py"
)

COMPANION_ROLES = ("student", "teacher", "enterprise", "government")
ADMIN_ROLES = ("super_admin", "admin")

# 计划 Task 8 固定的六个业务代办示例：每条都命中"代办短语 + 业务动作"。
BUSINESS_PROXY_EXAMPLES = (
    "帮我投简历",
    "替我兑换奖品",
    "代我审核这个职位",
    "帮我发消息给老师",
    "替我修改个人资料",
    "帮我删除这条内容",
)

# 012 源码绝不直接 import 的业务写模块；这是"拒绝代办零业务写"的静态证据。
FORBIDDEN_WRITE_MODULES = (
    "app.enterprise_console.applications",
    "app.job_matching",
    "app.handcraft_inheritance",
    "app.messaging",
    "app.profiles",
    "app.admin_console.routes",
    "app.admin_console.presets",
)

SETTER_NAME = "set_assistant_feature_knowledge_provider"
GETTER_NAME = "get_assistant_feature_knowledge_provider"
PROVIDER_CLASS_NAMES = (
    "AssistantFeatureKnowledgeProvider",
    "UnavailableAssistantFeatureKnowledgeProvider",
)
KNOWLEDGE_TABLE = "admin_assistant_feature_knowledge"


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


def parse_source(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def definitions_named(root: Path, name: str) -> list[tuple[Path, int]]:
    """全仓库扫描：返回 (文件, 行号) 列表，只有真正的 def 才算定义。"""
    found: list[tuple[Path, int]] = []
    for path in sorted(root.rglob("*.py")):
        for node in ast.walk(parse_source(path)):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == name:
                    found.append((path, node.lineno))
    return found


def create_table_statements(root: Path) -> list[str]:
    """收集源码里所有 CREATE TABLE 字符串常量（db.py 的执行文本即此形态）。"""
    statements: list[str] = []
    for path in sorted(root.rglob("*.py")):
        for node in ast.walk(parse_source(path)):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if "CREATE TABLE" in node.value.upper():
                    statements.append(node.value)
    return statements


def squash_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text)


class RowMapping:
    """只提供 sqlite3.Row 的下标读取，供 011 的序列化函数真实执行。"""

    def __init__(self, values: dict):
        self._values = dict(values)

    def __getitem__(self, key: str):
        return self._values[key]


class RecordingKnowledgeProvider:
    def __init__(self, entries):
        self.entries = list(entries)
        self.calls = 0

    def list_entries(self, enabled_only=True):
        self.calls += 1
        return self.entries if enabled_only else list(self.entries)


class AiCompanionAcceptanceTests(unittest.TestCase):
    """Seven whole-feature items, driven through the real Flask API."""

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

    def entry(
        self,
        knowledge_id,
        title,
        body,
        jump_target,
        feature_key=None,
    ):
        return {
            "knowledge_id": knowledge_id,
            "title": title,
            "body": body,
            "feature_key": feature_key or knowledge_id.removeprefix("knowledge-"),
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

    def _seed_provider(self, entries):
        provider = RecordingKnowledgeProvider(entries)
        knowledge_provider.set_assistant_feature_knowledge_provider(
            self.app,
            provider,
        )
        return provider

    def _count(self, table: str, user_id: int) -> int:
        with self.app.app_context():
            row = get_db().execute(
                f"SELECT COUNT(*) AS total FROM {table} WHERE user_id = ?",
                (user_id,),
            ).fetchone()
            return int(row["total"])

    # ---- Item 1: role matrix, own-history reads, admin 403, anonymous 401.

    def test_four_roles_ask_and_read_own_history(self):
        for index, role in enumerate(COMPANION_ROLES):
            user_id = 300 + index
            with self.subTest(role=role):
                self._insert_user(user_id, f"accept-{role}", role)
                client = self._login(f"accept-{role}")
                asked = self._ask(client, "怎么投简历", f"role-{role}")
                self.assertEqual(asked.status_code, 200)
                body = asked.get_json()
                self.assertTrue(body["success"])
                conversation_id = body["conversation_id"]

                listed = client.get("/api/ai-companion/conversations")
                self.assertEqual(listed.status_code, 200)
                conversations = listed.get_json()["conversations"]
                self.assertEqual(len(conversations), 1)
                self.assertEqual(
                    conversations[0]["conversation_id"],
                    conversation_id,
                )

                detail = client.get(
                    f"/api/ai-companion/conversations/{conversation_id}"
                )
                self.assertEqual(detail.status_code, 200)
                conversation = detail.get_json()["conversation"]
                self.assertEqual(
                    [item["role"] for item in conversation["messages"]],
                    ["user", "assistant"],
                )
                self.assertEqual(
                    self._count("ai_companion_conversations", user_id),
                    1,
                )

    def test_admin_roles_are_forbidden_and_anonymous_is_unauthorized(self):
        for index, role in enumerate(ADMIN_ROLES):
            with self.subTest(role=role):
                self._insert_user(310 + index, f"accept-{role}", role)
                client = self._login(f"accept-{role}")
                response = self._ask(client, "怎么投简历", f"admin-{role}")
                self.assertEqual(response.status_code, 403)
                self.assertEqual(
                    response.get_json(),
                    {"success": False, "message": "当前角色不可使用 AI 学伴"},
                )
                # 管理角色同样读不到对话列表与会话详情。
                self.assertEqual(
                    client.get("/api/ai-companion/conversations").status_code,
                    403,
                )

        anonymous = self.app.test_client()
        response = anonymous.post(
            "/api/ai-companion/messages",
            json={"question": "怎么投简历", "client_request_id": "anon-1"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.get_json()["message"],
            "未登录或会话已过期",
        )

    # ---- Item 2: provider replacement changes the next platform answer.

    def test_provider_replacement_changes_the_next_platform_answer(self):
        self._insert_user(320, "accept-replace-student", "student")
        student = self._login("accept-replace-student")
        first = self._seed_provider(
            [
                self.entry(
                    "knowledge-job",
                    "如何投递简历",
                    "进入就业对接后投递岗位",
                    "/student/employment/jobs",
                )
            ]
        )
        self.ai.complete_json.side_effect = [
            {"intent": "platform_usage"},
            {"answer": "进入就业对接后选择岗位投递。"},
        ]
        response = self._ask(student, "怎么投简历", "replace-1")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["jump_target"], "/student/employment/jobs")
        self.assertEqual(
            body["assistant_message"]["content"],
            "进入就业对接后选择岗位投递。",
        )
        self.assertEqual(first.calls, 1)

        # 换槽：替换 provider 对象本身，新对象的读取次数从 0 重新计数。
        second = self._seed_provider(
            [
                self.entry(
                    "knowledge-points",
                    "积分怎么算",
                    "积分通过完成课程获得",
                    "/student/points",
                )
            ]
        )
        self.ai.complete_json.side_effect = [
            {"intent": "platform_usage"},
            {"answer": "积分通过完成课程与实训获得。"},
        ]
        response = self._ask(student, "积分怎么算", "replace-2")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["jump_target"], "/student/points")
        self.assertEqual(
            body["assistant_message"]["content"],
            "积分通过完成课程与实训获得。",
        )
        # 答案与跳转都随 provider 更换而改变；旧 provider 不再被读取，
        # 新 provider 的读取次数从 1 起算，证明没有跨请求的长期缓存。
        self.assertEqual(second.calls, 1)
        self.assertEqual(first.calls, 1)

    # ---- Item 3: empty provider on the platform path is 422, not a guess.

    def test_empty_knowledge_provider_returns_knowledge_unavailable(self):
        self._insert_user(321, "accept-empty-student", "student")
        student = self._login("accept-empty-student")
        provider = self._seed_provider([])
        self.ai.complete_json.side_effect = [
            {"intent": "platform_usage"},
            {"answer": "这段答案不该被使用。"},
        ]
        response = self._ask(student, "怎么投简历", "empty-1")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            response.get_json(),
            {"success": False, "message": KNOWLEDGE_UNAVAILABLE_MESSAGE},
        )
        self.assertEqual(KNOWLEDGE_UNAVAILABLE_MESSAGE, "暂无法回答，请稍后再试")
        # 意图分类成功过一次，第二段答案生成从未发生：不拿空来源硬编答案。
        self.assertEqual(self.ai.complete_json.call_count, 1)
        self.assertEqual(provider.calls, 1)
        self.assertEqual(self._count("ai_companion_conversations", 321), 0)
        self.assertEqual(self._count("ai_companion_messages", 321), 0)

    # ---- Item 4: AI failure matrix maps to the exact 503 payload.

    def test_ai_failure_matrix_returns_exact_503(self):
        self._insert_user(322, "accept-failure-student", "student")
        student = self._login("accept-failure-student")
        self._seed_provider(
            [
                self.entry(
                    "knowledge-job",
                    "如何投递简历",
                    "进入就业对接后投递岗位",
                    "/student/employment/jobs",
                )
            ]
        )
        matrix = (
            ("ai-unavailable", _raises(AiUnavailableError("upstream timeout"))),
            ("not-a-dict", _returns(["platform_usage"])),
            ("missing-intent", _returns({"answers": ["没有 intent 字段"]})),
            ("empty-intent", _returns({"intent": ""})),
            ("unknown-intent", _returns({"intent": "unknown_intent"})),
        )
        for name, stub in matrix:
            with self.subTest(case=name):
                before = self.ai.complete_json.call_count
                self.ai.complete_json.side_effect = stub
                response = self._ask(student, "平台怎么用", f"matrix-{name}")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(
                    response.get_json(),
                    {"success": False, "message": AI_UNAVAILABLE_MESSAGE},
                )
                self.assertEqual(
                    self.ai.complete_json.call_count,
                    before + 1,
                )
        self.assertEqual(AI_UNAVAILABLE_MESSAGE, "AI 服务暂时不可用")
        # 零本地兜底：失败全部发生在意图段，不读知识来源、不落库。
        self.assertEqual(self._count("ai_companion_conversations", 322), 0)
        self.assertEqual(self._count("ai_companion_messages", 322), 0)

    # ---- Item 5: business-proxy refusals write nothing but ai_companion_*.

    def test_business_proxy_examples_refuse_without_business_writes(self):
        self._insert_user(323, "accept-refusal-student", "student")
        student = self._login("accept-refusal-student")
        statements: list[str] = []
        with self.app.app_context():
            connection = get_db()
            connection.set_trace_callback(statements.append)
            try:
                for index, question in enumerate(BUSINESS_PROXY_EXAMPLES):
                    response = self._ask(
                        student,
                        question,
                        f"accept-refusal-{index}",
                    )
                    self.assertEqual(response.status_code, 200)
                    body = response.get_json()
                    assistant = body["assistant_message"]
                    self.assertEqual(assistant["intent"], "out_of_scope")
                    self.assertIn(REFUSAL_MESSAGE, assistant["content"])
                    self.assertIsNone(body["jump_target"])
            finally:
                connection.set_trace_callback(None)

        writes = [
            statement
            for statement in statements
            if statement.lstrip().upper().startswith(
                ("INSERT", "UPDATE", "DELETE")
            )
        ]
        self.assertTrue(writes)
        for statement in writes:
            if "AI_COMPANION_" not in statement.upper():
                # 只允许共享认证层的过期会话清理，其余任何表都不许写。
                self.assertTrue(
                    statement.lstrip().upper().startswith(
                        "DELETE FROM SESSIONS"
                    ),
                    statement,
                )
        self.assertTrue(
            any("AI_COMPANION_" in s.upper() for s in writes),
            "业务代办路径必须仍落 AI 学伴自己的表",
        )
        # 规则前置拒绝：零 AI 调用。
        self.ai.complete_json.assert_not_called()

        # 静态证据：012 源码没有 import 任何业务写模块。
        for module in direct_imports(read_ai_companion_source()):
            for forbidden in FORBIDDEN_WRITE_MODULES:
                self.assertFalse(
                    module == forbidden or module.startswith(f"{forbidden}."),
                    module,
                )

    # ---- Item 6: ASR reuses the shared client at speech_to_text only.

    def test_speech_transcription_uses_the_shared_client(self):
        self._insert_user(324, "accept-speech-student", "student")
        student = self._login("accept-speech-student")
        response = student.post(
            "/api/ai-companion/speech/transcriptions",
            data={
                "audio": (io.BytesIO(b"acceptance-audio-bytes"), "question.webm")
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"success": True, "text": "识别文字"})

        self.ai.transcribe.assert_called_once()
        args, kwargs = self.ai.transcribe.call_args
        # 只走共享客户端，且只带 call_point；没有方言参数、没有第二个客户端。
        self.assertEqual(kwargs, {"call_point": SPEECH_TO_TEXT_CALL_POINT})
        self.assertEqual(SPEECH_TO_TEXT_CALL_POINT, "speech_to_text")
        self.assertEqual(args, (b"acceptance-audio-bytes", "question.webm"))
        self.assertNotIn("dialect", str(self.ai.transcribe.call_args).lower())

    def test_speech_failure_matrix_maps_422_and_503(self):
        self._insert_user(325, "accept-speech-fail-student", "student")
        student = self._login("accept-speech-fail-student")
        cases = (
            ("validation", AgriValidationError("empty audio"), 422,
             ASR_FAILURE_MESSAGE),
            ("unavailable", AiUnavailableError("asr timeout"), 503,
             AI_UNAVAILABLE_MESSAGE),
        )
        for name, error, status, message in cases:
            with self.subTest(case=name):
                self.ai.transcribe.side_effect = error
                response = student.post(
                    "/api/ai-companion/speech/transcriptions",
                    data={
                        "audio": (io.BytesIO(b"audio"), "question.webm")
                    },
                    content_type="multipart/form-data",
                )
                self.assertEqual(response.status_code, status)
                self.assertEqual(
                    response.get_json(),
                    {"success": False, "message": message},
                )
        self.assertEqual(ASR_FAILURE_MESSAGE, "未能识别，请重说或改用文字")

    def test_asr_has_no_second_client_or_config(self):
        source = read_ai_companion_source()
        code = code_without_comments(source)
        self.assertEqual(code.count(".transcribe("), 1)
        self.assertIn("call_point=SPEECH_TO_TEXT_CALL_POINT", source)
        self.assertNotIn("AI_ASR_", code)
        self.assertNotIn("httpx", source)
        self.assertNotIn("urllib", source)
        self.assertNotIn("socket", source)
        self.assertNotIn("dialect", code)

    # ---- Item 7: retention boundaries at the acceptance level.

    def test_retention_drops_conversations_older_than_180_days(self):
        self._insert_user(326, "accept-180-student", "student")
        student = self._login("accept-180-student")
        created = self._ask(student, "怎么投简历", "retention-180-1")
        self.assertEqual(created.status_code, 200)
        conversation_id = created.get_json()["conversation_id"]

        listed = student.get("/api/ai-companion/conversations").get_json()
        self.assertEqual(
            [item["conversation_id"] for item in listed["conversations"]],
            [conversation_id],
        )

        # 把该会话的 updated_at 推到 180 天之前；留存判定按 updated_at 计算。
        stale = (
            datetime.now(timezone(timedelta(hours=8)))
            - timedelta(days=181)
        ).isoformat()
        with self.app.app_context():
            db = get_db()
            db.execute(
                """
                UPDATE ai_companion_conversations
                SET updated_at = ?
                WHERE conversation_id = ?
                """,
                (stale, conversation_id),
            )
            db.commit()

        # 下一次写入触发清理：过期会话连同读取一起消失。
        self.assertEqual(
            self._ask(student, "怎么投简历", "retention-180-2").status_code,
            200,
        )
        listed = student.get("/api/ai-companion/conversations").get_json()
        remaining = [
            item["conversation_id"] for item in listed["conversations"]
        ]
        self.assertEqual(len(remaining), 1)
        self.assertNotIn(
            conversation_id,
            {item["conversation_id"] for item in listed["conversations"]},
        )
        detail = student.get(
            f"/api/ai-companion/conversations/{conversation_id}"
        )
        self.assertEqual(detail.status_code, 404)

    def test_conversation_cap_of_100_prunes_the_oldest(self):
        self._insert_user(327, "accept-cap-student", "student")
        student = self._login("accept-cap-student")
        conversation_ids = []
        for index in range(101):
            response = self._ask(
                student,
                f"帮我投简历 {index}",
                f"cap-{index}",
            )
            self.assertEqual(response.status_code, 200)
            conversation_ids.append(response.get_json()["conversation_id"])

        listed = student.get("/api/ai-companion/conversations").get_json()
        remaining = [item["conversation_id"] for item in listed["conversations"]]
        self.assertEqual(len(remaining), 100)
        # 第 101 次写入把最旧的一条挤掉，其余 100 条按更新时间倒序保留。
        self.assertNotIn(conversation_ids[0], remaining)
        self.assertEqual(set(remaining), set(conversation_ids[1:]))
        self.assertEqual(self._count("ai_companion_conversations", 327), 100)

    def test_conversation_is_capped_at_200_messages(self):
        self._insert_user(328, "accept-messages-student", "student")
        student = self._login("accept-messages-student")
        created = self._ask(student, "帮我投简历 0", "messages-cap-0")
        self.assertEqual(created.status_code, 200)
        conversation_id = created.get_json()["conversation_id"]
        for index in range(1, 101):
            response = self._ask(
                student,
                f"帮我投简历 {index}",
                f"messages-cap-{index}",
                conversation_id=conversation_id,
            )
            self.assertEqual(response.status_code, 200)

        detail = student.get(
            f"/api/ai-companion/conversations/{conversation_id}"
        )
        self.assertEqual(detail.status_code, 200)
        messages = detail.get_json()["conversation"]["messages"]
        self.assertEqual(len(messages), 200)
        # 202 条写入后最早的一次交换被裁掉，保留的第 1 条是第二次交换的提问。
        self.assertEqual(messages[0]["content"], "帮我投简历 1")
        self.assertEqual(messages[-2]["content"], "帮我投简历 100")
        self.assertEqual(messages[-1]["role"], "assistant")


def _raises(error: Exception):
    def _stub(*args, **kwargs):
        raise error

    return _stub


def _returns(value):
    def _stub(*args, **kwargs):
        return value

    return _stub


class ProviderReconciliationTests(unittest.TestCase):
    """011 ownership facts for the assistant feature knowledge provider."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test-only-secret",
                "SESSION_HOURS": 24,
                "SESSION_COOKIE_SECURE": False,
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_012_reexports_the_011_owned_objects_by_identity(self):
        self.assertIs(
            knowledge_provider.set_assistant_feature_knowledge_provider,
            admin_providers.set_assistant_feature_knowledge_provider,
        )
        self.assertIs(
            knowledge_provider.get_assistant_feature_knowledge_provider,
            admin_providers.get_assistant_feature_knowledge_provider,
        )
        self.assertIs(
            knowledge_provider.AssistantFeatureKnowledgeProvider,
            admin_providers.AssistantFeatureKnowledgeProvider,
        )
        self.assertIs(
            knowledge_provider.UnavailableAssistantFeatureKnowledgeProvider,
            admin_providers.UnavailableAssistantFeatureKnowledgeProvider,
        )

    def test_knowledge_provider_module_defines_nothing(self):
        module = parse_source(KNOWLEDGE_PROVIDER_SOURCE_PATH)
        defined = {
            node.name
            for node in ast.walk(module)
            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
            )
        }
        for name in (SETTER_NAME, GETTER_NAME, *PROVIDER_CLASS_NAMES):
            self.assertNotIn(name, defined)
        # 该文件只做 import / re-export：顶层语句仅限 import 与 __all__ 赋值。
        for node in module.body:
            self.assertIsInstance(
                node,
                (ast.Import, ast.ImportFrom, ast.Assign),
                ast.dump(node)[:80],
            )

    def test_exactly_one_definition_of_each_contract_function(self):
        for name in (SETTER_NAME, GETTER_NAME):
            with self.subTest(function=name):
                found = definitions_named(APP_SOURCE_ROOT, name)
                self.assertEqual(len(found), 1)
                path, _lineno = found[0]
                self.assertEqual(path, PROVIDERS_SOURCE_PATH)

    def test_the_011_knowledge_table_is_not_created_on_this_branch(self):
        statements = create_table_statements(APP_SOURCE_ROOT)
        # Teeth：扫描确实看得到 CREATE TABLE 文本，否则下面的计数是空的。
        self.assertTrue(statements)
        self.assertTrue(
            any(
                "ai_companion_conversations" in statement.lower()
                for statement in statements
            )
        )
        matches = [
            statement
            for statement in statements
            if KNOWLEDGE_TABLE in statement.lower()
        ]
        self.assertEqual(matches, [])

    def test_the_real_db_provider_raises_no_such_table(self):
        # 记录事实而不是绕过事实：真实 provider 在本分支上必然抛
        # "no such table"，因为 011 的表从未被创建。
        with self.app.app_context():
            with self.assertRaises(sqlite3.OperationalError) as caught:
                DatabaseAssistantFeatureKnowledgeProvider().list_entries()
        self.assertIn(
            f"no such table: {KNOWLEDGE_TABLE}",
            str(caught.exception),
        )

    def test_the_real_db_provider_reads_the_missing_table(self):
        source = PRESETS_SOURCE_PATH.read_text(encoding="utf-8")
        module = ast.parse(source, filename=str(PRESETS_SOURCE_PATH))
        provider_class = next(
            node
            for node in module.body
            if isinstance(node, ast.ClassDef)
            and node.name == "DatabaseAssistantFeatureKnowledgeProvider"
        )
        list_entries = next(
            node
            for node in provider_class.body
            if isinstance(node, ast.FunctionDef) and node.name == "list_entries"
        )
        segment = squash_whitespace(
            ast.get_source_segment(source, list_entries) or ""
        )
        self.assertIn(
            f"FROM {KNOWLEDGE_TABLE}",
            segment,
        )

    def test_011_serialized_entry_covers_the_012_whitelist(self):
        row = RowMapping(
            {
                "knowledge_id": "knowledge-job",
                "title": "如何投递简历",
                "body": "进入就业对接后投递岗位",
                "feature_key": "employment",
                "jump_target": "/student/employment/jobs",
                "is_enabled": 1,
                "version": 3,
                "updated_at": "2026-09-20T10:00:00+08:00",
            }
        )
        serialized = _serialize_knowledge_entry(row)
        self.assertEqual(
            set(serialized),
            {
                "knowledge_id",
                "title",
                "body",
                "feature_key",
                "jump_target",
                "is_enabled",
                "version",
                "updated_at",
            },
        )
        # 012 的消费白名单必须被 011 的序列化输出完整覆盖。
        self.assertTrue(set(KNOWLEDGE_FIELDS) <= set(serialized))
        for field in KNOWLEDGE_FIELDS:
            self.assertIn(field, serialized)

    def test_fresh_app_defaults_to_the_011_placeholder_provider(self):
        # 012 默认装的是 011 的占位 provider；真实 DatabaseAssistantFeature
        # KnowledgeProvider 需要 011 侧建表后再注册，本分支不代劳。
        with self.app.app_context():
            provider = admin_providers.get_assistant_feature_knowledge_provider()
        self.assertIsInstance(
            provider,
            admin_providers.UnavailableAssistantFeatureKnowledgeProvider,
        )

    def test_create_app_registers_no_admin_console_routes(self):
        # 011 快照只服务于 provider 契约：create_app 不得注册 admin_console
        # 蓝图，也不得挂出其路由前缀下的任何 rule，否则 012 就替 011 开了
        # 管理端入口。这是"不得注册管理路由"约束的行为守卫。
        self.assertEqual(admin_console_bp.url_prefix, "/api/admin")
        self.assertNotIn("admin_console", self.app.blueprints)
        self.assertEqual(
            [
                rule.rule
                for rule in self.app.url_map.iter_rules()
                if rule.rule == admin_console_bp.url_prefix
                or rule.rule.startswith(f"{admin_console_bp.url_prefix}/")
            ],
            [],
        )
        # 端点名前缀兜底：即使蓝图换个名字注册，端点仍带 admin_console. 前缀。
        self.assertEqual(
            [
                rule.endpoint
                for rule in self.app.url_map.iter_rules()
                if rule.endpoint.startswith("admin_console.")
            ],
            [],
        )


if __name__ == "__main__":
    unittest.main()
