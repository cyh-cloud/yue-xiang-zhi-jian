# 本土资源 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 006 本土资源子系统：三大方言语音问答、成功案例、政策/新闻浏览、政策类别订阅、浏览计数与前端路由。

**Architecture:** 后端新增 `backend/app/local_resources/` 领域包，复用 01 会话与兴趣标签、02 消息来源桥接、003 ASR、10 `PolicyNewsProvider`。06 在自身 SQLite 中只保存方言文本轮次、政策订阅软状态和成功案例预置数据，不保存音频，也不复制政策/新闻表。前端新增 Pinia store、本土资源路由和页面，复用现有 Ark 视觉、`VoiceInputButton`、`AppHeader` 和 `PortalShell`。

**Tech Stack:** Flask + SQLite + unittest；Vue 3 + Vite + Pinia + Vue Router + Vitest；httpx；uv。

**Spec:** `specs/006-local-resources/spec.md`

**Plan Review:** Independent read-only review PASS on 2026-09-19 after four evidence-based revision rounds.

## Global Constraints

- Feature 分支固定为 `v2/lixKRT/006-local-resources`，worktree 固定为 `.worktrees/006-local-resources`。
- 后端模块目录名固定为 `backend/app/local_resources/`，Python 使用 snake_case，路由使用 kebab-case。
- 旧系统根目录 `app.py`、`database.py` 和旧 HTML 不得读取、导入、迁移或作为实现依据。
- 01 会话、角色和兴趣标签是唯一身份与标签来源；不得建立第二套账户、会话、标签目录。
- 02 是唯一通知通道；06 只注册 `MessagingSourceProvider` 桥接，不直接写通知表。
- ASR 唯一复用现有 `POST /api/agri-skills/speech/transcriptions`，底层 call point 仍是 `speech_to_text`；不得新增 ASR 路由、模型配置或转写客户端。
- 10 政策/新闻 provider 唯一注册槽是 `government_policy_news_provider`；06 不得创建占位、第二槽、第二协议或将 10 表作为读取旁路。
- 政策类别固定为 `subsidy/ecommerce/heritage/training/certification/general/entrepreneurship`；新闻类别固定为 `news/disaster_warning/policy_update`。
- 政策三态固定为“上架/下架/删除”；06 只看到上架。新闻两态固定为“已发布/已删除”；06 只看到已发布。
- 浏览事件去重键固定为 `(content_type, view_event_id)`；新打开生成新事件，同一事件重试不重复计数。
- 方言代码固定为 `yue/hak/nan`；TTS 配置键固定为 `AI_TTS_URL`、`AI_TTS_MODEL`、`AI_TTS_API_KEY`、`AI_TTS_VOICE_YUE`、`AI_TTS_VOICE_HAKKA`、`AI_TTS_VOICE_TEOCHEW`。
- 方言助手全部 AI 调用无降级；ASR 不可识别文案固定为“未能识别，请重说或改用文字”，其余 AI/TTS 失败固定为“AI 服务暂时不可用”。
- TTS 为非流式 `POST AI_TTS_URL`，JSON 字段固定为 `model/input/voice/language/response_format`，`response_format` 为 `mp3`，成功响应为非空 `audio/*`。
- 原始录音和合成音频不落盘、不写 BLOB、不做缓存；仅成功轮次的文本字段入库。
- 每个行为先写失败测试，再写最小实现；任务完成前运行定向测试并提交。

---

## Required Design Decisions

### AI Call Points and Degradation Matrix

| ID | Call point | Backend owner | Exact input | Success | Failure | Degradation |
| --- | --- | --- | --- | --- | --- | --- |
| AI-06-01 | `speech_to_text` | Existing 003 `OpenAiCompatibleAiClient.transcribe` via `/api/agri-skills/speech/transcriptions` | multipart `audio` bytes + filename | trimmed recognized text | 422 empty/noise or 503 upstream | None |
| AI-06-02 | `local_resources_dialect_answer` | 006 `dialect_assistant.generate_dialect_answer` | confirmed question + dialect code only | JSON `dialect_text`, `mandarin_text` | “AI 服务暂时不可用” | None |
| AI-06-03 | `local_resources_dialect_tts` | 006 `tts.synthesize_dialect` | dialect text + language code + configured voice + model | non-empty `audio/*` bytes | “AI 服务暂时不可用” | None |

Rules:

- 仅 ASR 的“不可识别”分支使用“未能识别，请重说或改用文字”。
- ASR 连接/上游失败仍使用“AI 服务暂时不可用”。
- 006 MUST NOT import or call `app.agri_skills.qa.select_local_knowledge_entry`, `format_local_answer`, diagnosis, self-test, course quiz or 12 AI 学伴.
- TTS failure MUST NOT return text as if audio succeeded.

### Voice Capability Design

#### ASR reuse path

Frontend calls the exact existing route:

```text
POST /api/agri-skills/speech/transcriptions
Content-Type: multipart/form-data
field: audio=<file>
```

The browser passes the same bytes and filename used by 03. No dialect code is sent to ASR. Backend call point remains `speech_to_text`. The 006 store maps an empty/noise failure message to “未能识别，请重说或改用文字”; it does not duplicate or wrap the ASR provider.

#### TTS call

```python
OpenAiCompatibleTtsClient.synthesize(
    text=dialect_text,
    language_code="yue" | "hak" | "nan",
    voice_code=configured_voice,
    call_point="local_resources_dialect_tts",
) -> TtsAudio
```

HTTP request:

```json
{
  "model": "<AI_TTS_MODEL>",
  "input": "<dialect answer>",
  "voice": "<configured dialect voice>",
  "language": "yue",
  "response_format": "mp3"
}
```

Mapping:

| UI | `dialect_code` | `language_code` | Voice config |
| --- | --- | --- | --- |
| 粤语 | `yue` | `yue` | `AI_TTS_VOICE_YUE` |
| 客家话 | `hak` | `hak` | `AI_TTS_VOICE_HAKKA` |
| 潮汕话 | `nan` | `nan` | `AI_TTS_VOICE_TEOCHEW` |

Display rule:

```text
[方言原文 label + dialect text] [audio controls]
[普通话对照 label + Mandarin text]
```

The browser attempts playback after synthesis. If autoplay is blocked, the same `<audio controls>` remains available for replay. Streaming is not required; the answer endpoint waits for a complete MP3, returns base64 for the current response, and does not store it.

### Content Visibility State Machines

#### Policy

```text
上架 --政府下架--> 下架 --政府重新上架--> 上架
上架/下架 --政府删除--> 删除
```

| State | 06 list/detail | 06 view event | Content | View count | Subscription | Historical notification |
| --- | --- | --- | --- | --- | --- | --- |
| 上架 | visible | allowed | retained by 10 | retained/incrementable | retained | retained |
| 下架 | hidden | rejected | retained by 10 | retained/not incrementable | retained | retained |
| 删除 | hidden | rejected | hard-deleted by 10 | hard-deleted by 10 | retained by 06 | snapshot retained by 02 |

#### News

```text
已发布 --政府删除--> 已删除
```

| State | 06 list/detail | 06 view event | Content | View count |
| --- | --- | --- | --- | --- |
| 已发布 | visible | allowed | retained by 10 | retained/incrementable |
| 已删除 | hidden | rejected | hard-deleted by 10 | hard-deleted by 10 |

No 06 API or UI exposes unpublish/relist for news.

### 10 Provider Consumption

Current import path:

```python
from app.government_console.providers import (
    PolicyNewsProvider,
    get_policy_news_provider,
)
```

This direct import is deliberate for the current release because the frozen 10 implementation and registration slot are already merged. Do not copy the Protocol, create `policy_news/providers.py`, or add a second extension key. The open governance issue is the inconsistency between the 10-owned business package and the independent `content_review/` shared package; this plan does not resolve it.

Every 006 read/write path uses:

```python
provider = get_policy_news_provider()
provider.list_published_policies(category_code)
provider.get_published_policy(policy_id)
provider.list_published_news(category_code)
provider.get_published_news(news_id)
provider.record_policy_view(policy_id, view_event_id)
provider.record_news_view(news_id, view_event_id)
```

Provider exceptions are mapped to local response errors; database row access is forbidden.

### Reuse From 001/02/003

| Dependency | Reused interface | 006 responsibility |
| --- | --- | --- |
| 001 | `load_session(required=True, allowed_states={"active"})`; `student` role check | No second login/session/role or tag tables |
| 001 | `app.profiles.service.get_profile_preferences(user_id)` | Read current interest tag names for policy-category suggestions |
| 02 | `app.messaging.source_provider.register_messaging_source_provider` and `MessagingSourceProvider.list_policy_subscriber_ids` | Implement the policy-subscriber bridge; no second notification store |
| 02 | `emit_policy_published` remains owned by 10/02 flow | 006 never triggers the push itself |
| 003 | `POST /api/agri-skills/speech/transcriptions` and underlying `transcribe(..., call_point="speech_to_text")` | Reuse bytes/filename input and map 006 copy only |
| 003 | `app.agri_skills.ai_client.get_ai_client().complete_json(...)` | Generate dialect + Mandarin answer; no local knowledge-base fallback |

### Shared File Changes

Limit shared-file edits to these exact purposes:

| File | Change | Why |
| --- | --- | --- |
| `backend/app/db.py` | Add three 006 tables/indexes; call 006 case seed | Single schema/init authority |
| `backend/app/config.py` | Add TTS URL/model/API key/voice/timeout config | Shared application configuration |
| `backend/.env.example` | Document empty TTS config keys and timeout | Environment template |
| `backend/app/__init__.py` | Install 006 services, register blueprint, protect `/api/local-resources`, register messaging provider | Application assembly |
| `frontend/src/api/types.ts` | Add 006 DTO types | Shared API type authority |
| `frontend/src/router/index.ts` | Add 006 routes | Shared router registry |
| `frontend/src/views/StudentPortalView.vue` | Add one local-resources portal link | Student portal entry |
| `frontend/src/views/StudentPortalView.test.ts` | Assert the new portal link | Keep portal contract tested |

No shared file is modified for ASR implementation, policy/news providers, review contracts, message storage or tag storage.

### Dependency Direction Self-Check

Required direction:

```text
Task 1 foundation
  -> Tasks 2-7 independent backend capabilities
  -> Task 8 backend routes/application wiring
  -> Task 9 backend cross-module acceptance
  -> Tasks 10-11 frontend stores
  -> Task 12 frontend routes/shell
  -> Tasks 13-16 feature views
  -> Task 17 responsive/accessibility acceptance
  -> Task 18 whole-feature acceptance
```

No task consumes a function, component or route introduced by a later task. Producer/provider registrations happen before consumer tasks:

- 006 case provider is produced in Task 2 before case API consumption in Task 8.
- 006 subscription provider is produced in Task 4 before messaging integration and subscription UI.
- 006 view service is produced in Task 5 before policy/news detail UI.
- TTS client is produced in Task 6 before dialect orchestration in Task 7 and UI in Task 13.
- Shared store methods are produced in Tasks 10-11 before feature views consume them.

---

## Task Index

1. Backend foundation, constants, TTS config and SQLite schema
2. Read-only success-case provider and seed
3. Policy/news catalog facade over the real 10 provider
4. Policy subscriptions, recommendations and 02 messaging bridge
5. Idempotent policy/news view recording service
6. TTS client, dialect mapping and audio validation
7. Dialect answer orchestration and turn persistence
8. Backend routes, error mapping and application wiring
9. Backend cross-module acceptance
10. Frontend API types and local-resources store
11. Frontend dialect store with ASR reuse and audio playback
12. Frontend router, navigation and home
13. Dialect assistant view
14. Success-case list/detail views
15. Policy list/detail/subscription views
16. News list/detail views
17. Responsive and accessibility acceptance
18. Whole-feature acceptance and verification

---

### Task 1: Backend Foundation, Constants, TTS Config, and Schema

**Files:**
- Create: `backend/app/local_resources/__init__.py`
- Create: `backend/app/local_resources/constants.py`
- Create: `backend/app/local_resources/errors.py`
- Create: `backend/tests/test_local_resources_foundation.py`
- Modify: `backend/app/db.py`
- Modify: `backend/app/config.py`
- Modify: `backend/.env.example`

**Interfaces:**
- Consumes: Flask app config; `get_db()`; `init_db()`.
- Produces: `DIALECTS`, `DIALECT_LABELS`, `POLICY_CATEGORIES`, `POLICY_LABELS`, `NEWS_CATEGORIES`, `NEWS_LABELS`, `RECOMMENDATION_TAGS`.
- Produces: `LocalResourceError`, `LocalResourceValidationError`, `LocalResourceNotFoundError`, `LocalResourceConflictError`, `LocalResourceUnavailableError`, `LocalResourceAccessDeniedError`, `LocalResourceAiUnavailableError`.
- Produces config keys: `AI_TTS_URL`, `AI_TTS_MODEL`, `AI_TTS_API_KEY`, `AI_TTS_VOICE_YUE`, `AI_TTS_VOICE_HAKKA`, `AI_TTS_VOICE_TEOCHEW`, `AI_TTS_TIMEOUT_SECONDS`.
- Produces tables: `local_resource_dialect_turns`, `local_resource_policy_subscriptions`, `local_resource_success_cases`.

- [ ] **Step 1: Write failing constants, config, error, and schema tests**

Create `backend/tests/test_local_resources_foundation.py`:

```python
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.db import get_db
from app.local_resources.constants import (
    DIALECTS,
    NEWS_LABELS,
    POLICY_LABELS,
)
from app.local_resources.errors import LocalResourceValidationError


class LocalResourceFoundationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "AI_TTS_URL": "https://tts.example.test/speech",
                "AI_TTS_MODEL": "dialect-tts",
                "AI_TTS_VOICE_YUE": "voice-yue",
                "AI_TTS_VOICE_HAKKA": "voice-hak",
                "AI_TTS_VOICE_TEOCHEW": "voice-nan",
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_exact_constant_maps(self):
        self.assertEqual(
            DIALECTS,
            {"yue": "粤语", "hak": "客家话", "nan": "潮汕话"},
        )
        self.assertEqual(
            list(POLICY_LABELS),
            [
                "subsidy",
                "ecommerce",
                "heritage",
                "training",
                "certification",
                "general",
                "entrepreneurship",
            ],
        )
        self.assertEqual(
            list(NEWS_LABELS),
            ["news", "disaster_warning", "policy_update"],
        )

    def test_config_values_are_loaded(self):
        self.assertEqual(
            self.app.config["AI_TTS_VOICE_HAKKA"],
            "voice-hak",
        )
        self.assertEqual(
            self.app.config["AI_TTS_TIMEOUT_SECONDS"],
            30.0,
        )

    def test_local_resource_tables_exist(self):
        with self.app.app_context():
            names = {
                row["name"]
                for row in get_db().execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        self.assertIn("local_resource_dialect_turns", names)
        self.assertIn("local_resource_policy_subscriptions", names)
        self.assertIn("local_resource_success_cases", names)

    def test_error_details_are_stable(self):
        error = LocalResourceValidationError(
            "参数不正确",
            details={"dialect_code": "不支持"},
        )
        self.assertEqual(error.code, "validation_error")
        self.assertEqual(error.details, {"dialect_code": "不支持"})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
uv run --directory backend python -m unittest tests.test_local_resources_foundation -v
```

Expected: FAIL because `app.local_resources` does not exist and the config keys are absent.

- [ ] **Step 3: Add constants, errors, config, schema and indexes**

Create `backend/app/local_resources/constants.py`:

```python
DIALECTS = {"yue": "粤语", "hak": "客家话", "nan": "潮汕话"}
DIALECT_LABELS = DIALECTS

POLICY_CATEGORIES = (
    "subsidy",
    "ecommerce",
    "heritage",
    "training",
    "certification",
    "general",
    "entrepreneurship",
)
POLICY_LABELS = {
    "subsidy": "补贴",
    "ecommerce": "电商",
    "heritage": "非遗",
    "training": "培训",
    "certification": "认证",
    "general": "综合",
    "entrepreneurship": "创业支持",
}

NEWS_CATEGORIES = ("news", "disaster_warning", "policy_update")
NEWS_LABELS = {
    "news": "新闻",
    "disaster_warning": "灾害预警",
    "policy_update": "政策更新",
}

RECOMMENDATION_TAGS = {
    "荔枝": ("subsidy", "training", "general"),
    "龙眼": ("subsidy", "training", "general"),
    "水稻": ("subsidy", "training", "general"),
    "水产": ("subsidy", "training", "general"),
    "电商直播": ("ecommerce", "entrepreneurship"),
    "短视频": ("ecommerce", "entrepreneurship"),
    "客服沟通": ("ecommerce", "entrepreneurship"),
    "电商运营": ("ecommerce", "entrepreneurship"),
    "客服专员": ("ecommerce", "entrepreneurship"),
    "手工艺": ("heritage",),
    "手工艺人": ("heritage",),
    "农业技术员": ("certification", "entrepreneurship"),
}
```

Create `backend/app/local_resources/errors.py`:

```python
from __future__ import annotations


class LocalResourceError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}


class LocalResourceValidationError(LocalResourceError):
    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message, code="validation_error", details=details)


class LocalResourceNotFoundError(LocalResourceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="not_found")


class LocalResourceConflictError(LocalResourceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="conflict")


class LocalResourceUnavailableError(LocalResourceError):
    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message, code="unavailable", details=details)


class LocalResourceAccessDeniedError(LocalResourceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="access_denied")


class LocalResourceAiUnavailableError(LocalResourceUnavailableError):
    def __init__(self) -> None:
        super().__init__("AI 服务暂时不可用")
```

Add to `backend/app/config.py`:

```python
"AI_TTS_URL": os.environ.get("AI_TTS_URL", "").strip(),
"AI_TTS_MODEL": os.environ.get("AI_TTS_MODEL", "").strip(),
"AI_TTS_API_KEY": os.environ.get("AI_TTS_API_KEY", "").strip(),
"AI_TTS_VOICE_YUE": os.environ.get("AI_TTS_VOICE_YUE", "").strip(),
"AI_TTS_VOICE_HAKKA": os.environ.get("AI_TTS_VOICE_HAKKA", "").strip(),
"AI_TTS_VOICE_TEOCHEW": os.environ.get(
    "AI_TTS_VOICE_TEOCHEW", ""
).strip(),
"AI_TTS_TIMEOUT_SECONDS": float(
    os.environ.get("AI_TTS_TIMEOUT_SECONDS", "30")
),
```

Add `backend/app/local_resources/__init__.py` with the public constants/errors export:

```python
from app.local_resources.constants import (
    DIALECT_LABELS,
    DIALECTS,
    NEWS_CATEGORIES,
    NEWS_LABELS,
    POLICY_CATEGORIES,
    POLICY_LABELS,
    RECOMMENDATION_TAGS,
)
from app.local_resources.errors import (
    LocalResourceAccessDeniedError,
    LocalResourceAiUnavailableError,
    LocalResourceConflictError,
    LocalResourceError,
    LocalResourceNotFoundError,
    LocalResourceUnavailableError,
    LocalResourceValidationError,
)

__all__ = [
    "DIALECTS",
    "DIALECT_LABELS",
    "POLICY_CATEGORIES",
    "POLICY_LABELS",
    "NEWS_CATEGORIES",
    "NEWS_LABELS",
    "RECOMMENDATION_TAGS",
    "LocalResourceError",
    "LocalResourceValidationError",
    "LocalResourceNotFoundError",
    "LocalResourceConflictError",
    "LocalResourceUnavailableError",
    "LocalResourceAccessDeniedError",
    "LocalResourceAiUnavailableError",
]
```

Append these tables inside `SCHEMA_SQL` in `backend/app/db.py`:

```sql
CREATE TABLE IF NOT EXISTS local_resource_dialect_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    turn_id TEXT NOT NULL UNIQUE,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    dialect_code TEXT NOT NULL CHECK (dialect_code IN ('yue', 'hak', 'nan')),
    recognized_text TEXT NOT NULL CHECK (length(trim(recognized_text)) > 0),
    dialect_answer TEXT NOT NULL CHECK (length(trim(dialect_answer)) > 0),
    mandarin_answer TEXT NOT NULL CHECK (length(trim(mandarin_answer)) > 0),
    status TEXT NOT NULL CHECK (status = 'completed'),
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_local_resource_dialect_user
    ON local_resource_dialect_turns(user_id, created_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS local_resource_policy_subscriptions (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category_code TEXT NOT NULL CHECK (
        category_code IN (
            'subsidy', 'ecommerce', 'heritage', 'training',
            'certification', 'general', 'entrepreneurship'
        )
    ),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, category_code)
);

CREATE INDEX IF NOT EXISTS idx_local_resource_policy_subscribers
    ON local_resource_policy_subscriptions(category_code, is_active, user_id);

CREATE TABLE IF NOT EXISTS local_resource_success_cases (
    case_id TEXT PRIMARY KEY,
    title TEXT NOT NULL CHECK (length(trim(title)) > 0),
    summary TEXT NOT NULL CHECK (length(trim(summary)) > 0),
    background TEXT NOT NULL CHECK (length(trim(background)) > 0),
    journey TEXT NOT NULL CHECK (length(trim(journey)) > 0),
    lessons TEXT NOT NULL CHECK (length(trim(lessons)) > 0),
    sort_order INTEGER NOT NULL DEFAULT 0,
    published_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    is_demo INTEGER NOT NULL DEFAULT 1 CHECK (is_demo IN (0, 1))
);

CREATE INDEX IF NOT EXISTS idx_local_resource_cases_order
    ON local_resource_success_cases(sort_order, case_id);
```

Document the seven TTS keys in `backend/.env.example`; the example values stay empty so no secret is committed.

- [ ] **Step 4: Run tests to verify pass**

Run:

```powershell
uv run --directory backend python -m unittest tests.test_local_resources_foundation tests.test_config -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/local_resources/__init__.py backend/app/local_resources/constants.py backend/app/local_resources/errors.py backend/app/db.py backend/app/config.py backend/.env.example backend/tests/test_local_resources_foundation.py
git commit -m "后端：搭建本土资源基础与数据表"
```

---

### Task 2: Read-Only Success-Case Provider and Seed

**Files:**
- Create: `backend/app/local_resources/cases.py`
- Create: `backend/tests/test_local_resources_cases.py`
- Modify: `backend/app/local_resources/__init__.py`
- Modify: `backend/app/db.py`

**Interfaces:**
- Consumes: `get_db()` and `local_resource_success_cases`.
- Produces: `LocalResourceCaseProvider` with `list_success_cases() -> list[dict]` and `get_success_case(case_id: str) -> dict | None`.
- Produces: `DatabaseLocalResourceCaseProvider`, `UnavailableLocalResourceCaseProvider`, `set_local_resource_case_provider(app, provider)`, `get_local_resource_case_provider()`.
- Produces: `seed_local_resource_cases(connection)`.

- [ ] **Step 1: Write failing provider and seed tests**

Create `backend/tests/test_local_resources_cases.py` with these cases:

```python
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.db import get_db
from app.local_resources.cases import (
    DatabaseLocalResourceCaseProvider,
    get_local_resource_case_provider,
    set_local_resource_case_provider,
)
from app.local_resources.errors import LocalResourceUnavailableError


class LocalResourceCaseTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_seed_has_stable_order_and_complete_detail(self):
        with self.app.app_context():
            provider = DatabaseLocalResourceCaseProvider()
            cases = provider.list_success_cases()
            detail = provider.get_success_case(cases[0]["id"])
        self.assertGreaterEqual(len(cases), 3)
        self.assertEqual(
            [item["id"] for item in cases],
            [
                "case-litchi-coop",
                "case-rice-ecommerce",
                "case-bamboo-studio",
            ],
        )
        self.assertEqual(
            set(detail),
            {
                "id",
                "title",
                "summary",
                "background",
                "journey",
                "lessons",
                "published_at",
                "updated_at",
                "is_demo",
            },
        )

    def test_unknown_case_returns_none(self):
        with self.app.app_context():
            self.assertIsNone(
                DatabaseLocalResourceCaseProvider()
                .get_success_case("missing")
            )

    def test_provider_is_replaceable(self):
        class Replacement:
            def list_success_cases(self):
                return [{"id": "real-1"}]

            def get_success_case(self, case_id):
                return {"id": case_id} if case_id == "real-1" else None

        replacement = Replacement()
        set_local_resource_case_provider(self.app, replacement)
        with self.app.app_context():
            self.assertIs(
                get_local_resource_case_provider(),
                replacement,
            )

    def test_unavailable_provider_has_exact_message(self):
        class Unavailable:
            def list_success_cases(self):
                raise LocalResourceUnavailableError("案例数据暂不可用")

            def get_success_case(self, case_id):
                raise LocalResourceUnavailableError("案例数据暂不可用")

        set_local_resource_case_provider(self.app, Unavailable())
        with self.app.app_context():
            with self.assertRaisesRegex(
                LocalResourceUnavailableError,
                "案例数据暂不可用",
            ):
                get_local_resource_case_provider().list_success_cases()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and verify failure**

```powershell
uv run --directory backend python -m unittest tests.test_local_resources_cases -v
```

Expected: FAIL because the provider module and seed do not exist.

- [ ] **Step 3: Implement the provider and deterministic demo seed**

Create `backend/app/local_resources/cases.py` with a `Protocol`, `Database...`, `Unavailable...`, set/get and a `_serialize` helper. The database provider must query:

```sql
SELECT
    case_id, title, summary, background, journey, lessons,
    published_at, updated_at, is_demo
FROM local_resource_success_cases
ORDER BY sort_order ASC, case_id ASC
```

Use the following three stable seed IDs and content themes:

```python
DEMO_CASES = (
    {
        "case_id": "case-litchi-coop",
        "title": "荔枝合作社的品牌化起步",
        "summary": "从分散销售到统一品控与品牌包装。",
        "background": "本地荔枝种植户规模小、销售渠道分散。",
        "journey": "先统一采摘标准，再建立分级包装和线上直播渠道。",
        "lessons": "先解决品质一致性，再扩大销售半径。",
        "sort_order": 10,
        "published_at": "2026-09-01T08:00:00+08:00",
    },
    {
        "case_id": "case-rice-ecommerce",
        "title": "水稻产区的电商协作",
        "summary": "用短视频和直播建立稳定复购。",
        "background": "产区缺乏持续内容和客户运营能力。",
        "journey": "以生产节点组织内容，按订单反馈调整产品组合。",
        "lessons": "内容、履约和售后必须同步建设。",
        "sort_order": 20,
        "published_at": "2026-09-02T08:00:00+08:00",
    },
    {
        "case_id": "case-bamboo-studio",
        "title": "竹编工作室的体验式转型",
        "summary": "把非遗技艺转化为可体验、可复购的服务。",
        "background": "传统成品销售客单价低且复购有限。",
        "journey": "设计短时体验课程，再连接定制订单与研学活动。",
        "lessons": "先验证体验流程，再扩张场地和人员。",
        "sort_order": 30,
        "published_at": "2026-09-03T08:00:00+08:00",
    },
)
```

`seed_local_resource_cases` must use `INSERT ... ON CONFLICT(case_id) DO UPDATE` and set `is_demo=1`. Call it from `init_db()` after `seed_handcraft_fixtures(db)`.

Export the new provider and set/get functions from `backend/app/local_resources/__init__.py`.

- [ ] **Step 4: Run tests to verify pass**

```powershell
uv run --directory backend python -m unittest tests.test_local_resources_cases tests.test_local_resources_foundation -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/local_resources/cases.py backend/app/local_resources/__init__.py backend/app/db.py backend/tests/test_local_resources_cases.py
git commit -m "后端：增加成功案例只读 provider"
```

---

### Task 3: Policy/News Catalog Facade Over the Real 10 Provider

**Files:**
- Create: `backend/app/local_resources/catalog.py`
- Create: `backend/tests/test_local_resources_catalog.py`
- Modify: `backend/app/local_resources/__init__.py`

**Interfaces:**
- Consumes: `app.government_console.providers.get_policy_news_provider`, `PolicyNewsProvider`, `app.government_console.errors.ProviderError`.
- Produces: `list_policies(category_code: str | None = None) -> list[dict]`.
- Produces: `get_policy(policy_id: str) -> dict`.
- Produces: `list_news(category_code: str | None = None) -> list[dict]`.
- Produces: `get_news(news_id: str) -> dict`.
- Behavior: no placeholder; last visible/provider error maps to `LocalResourceNotFoundError` or `LocalResourceUnavailableError`.

- [ ] **Step 1: Write failing tests with a fake real-provider replacement**

Create `backend/tests/test_local_resources_catalog.py`:

```python
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.government_console.providers import set_policy_news_provider
from app.local_resources.catalog import (
    get_news,
    get_policy,
    list_news,
    list_policies,
)
from app.local_resources.errors import (
    LocalResourceNotFoundError,
    LocalResourceValidationError,
)


POLICY = {
    "id": "policy-1",
    "title": "创业补贴",
    "content": "正文",
    "category_code": "entrepreneurship",
    "category_label": "创业支持",
    "published_at": "2026-09-19T10:00:00+08:00",
    "updated_at": "2026-09-19T10:00:00+08:00",
    "version": 1,
}
NEWS = {
    **POLICY,
    "id": "news-1",
    "title": "暴雨预警",
    "category_code": "disaster_warning",
    "category_label": "灾害预警",
}


class FakeProvider:
    def list_published_policies(self, category=None):
        return [POLICY] if category in (None, "entrepreneurship") else []

    def get_published_policy(self, policy_id):
        return POLICY if policy_id == "policy-1" else None

    def list_published_news(self, category=None):
        return [NEWS] if category in (None, "disaster_warning") else []

    def get_published_news(self, news_id):
        return NEWS if news_id == "news-1" else None

    def record_policy_view(self, policy_id, view_event_id):
        return 1

    def record_news_view(self, news_id, view_event_id):
        return 1


class LocalResourceCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
            }
        )
        set_policy_news_provider(self.app, FakeProvider())

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_lists_exact_visible_records(self):
        with self.app.app_context():
            self.assertEqual(list_policies("entrepreneurship"), [POLICY])
            self.assertEqual(
                list_news("disaster_warning"),
                [NEWS],
            )
            self.assertEqual(get_policy("policy-1"), POLICY)
            self.assertEqual(get_news("news-1"), NEWS)

    def test_unknown_categories_are_rejected(self):
        with self.app.app_context():
            with self.assertRaises(LocalResourceValidationError):
                list_policies("unknown")
            with self.assertRaises(LocalResourceValidationError):
                list_news("unknown")

    def test_missing_or_removed_records_are_not_found(self):
        with self.app.app_context():
            with self.assertRaises(LocalResourceNotFoundError):
                get_policy("missing")
            with self.assertRaises(LocalResourceNotFoundError):
                get_news("missing")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and verify failure**

```powershell
uv run --directory backend python -m unittest tests.test_local_resources_catalog -v
```

Expected: FAIL because `catalog.py` does not exist.

- [ ] **Step 3: Implement provider-only catalog reads**

Create `catalog.py` with:

```python
from __future__ import annotations

from app.government_console.errors import ProviderError
from app.government_console.providers import get_policy_news_provider
from app.local_resources.constants import (
    NEWS_LABELS,
    POLICY_LABELS,
)
from app.local_resources.errors import (
    LocalResourceNotFoundError,
    LocalResourceUnavailableError,
    LocalResourceValidationError,
)


def _category(value, allowed, field):
    if value is None:
        return None
    if not isinstance(value, str) or value not in allowed:
        raise LocalResourceValidationError(
            "类别不正确",
            details={field: "类别不属于允许值"},
        )
    return value


def list_policies(category_code=None):
    category = _category(category_code, POLICY_LABELS, "category")
    try:
        return list(get_policy_news_provider().list_published_policies(category))
    except ProviderError as error:
        raise LocalResourceUnavailableError(error.message) from error


def get_policy(policy_id):
    if not isinstance(policy_id, str) or not policy_id.strip():
        raise LocalResourceNotFoundError("政策不存在")
    try:
        item = get_policy_news_provider().get_published_policy(
            policy_id.strip()
        )
    except ProviderError as error:
        raise LocalResourceUnavailableError(error.message) from error
    if item is None:
        raise LocalResourceNotFoundError("政策不存在")
    return dict(item)


def list_news(category_code=None):
    category = _category(category_code, NEWS_LABELS, "category")
    try:
        return list(get_policy_news_provider().list_published_news(category))
    except ProviderError as error:
        raise LocalResourceUnavailableError(error.message) from error


def get_news(news_id):
    if not isinstance(news_id, str) or not news_id.strip():
        raise LocalResourceNotFoundError("新闻不存在")
    try:
        item = get_policy_news_provider().get_published_news(news_id.strip())
    except ProviderError as error:
        raise LocalResourceUnavailableError(error.message) from error
    if item is None:
        raise LocalResourceNotFoundError("新闻不存在")
    return dict(item)
```

Return copied `dict` records so consumers cannot mutate provider-owned objects. Do not add a local policy/news table or fallback list.

- [ ] **Step 4: Run tests to verify pass**

```powershell
uv run --directory backend python -m unittest tests.test_local_resources_catalog tests.test_government_provider_contract -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/local_resources/catalog.py backend/app/local_resources/__init__.py backend/tests/test_local_resources_catalog.py
git commit -m "后端：接入政务政策新闻真 provider"
```

---

### Task 4: Policy Subscriptions, Recommendations, and 02 Messaging Bridge

**Files:**
- Create: `backend/app/local_resources/subscriptions.py`
- Create: `backend/app/local_resources/messaging_provider.py`
- Create: `backend/tests/test_local_resources_subscriptions.py`
- Modify: `backend/app/local_resources/__init__.py`

**Interfaces:**
- Consumes: 01 `get_profile_preferences(user_id)` and `get_db()`.
- Produces: `list_policy_subscriptions(user_id: int) -> dict`.
- Produces: `set_policy_subscription(user_id: int, category_code: str, subscribed: bool) -> dict`.
- Produces: `recommend_policy_categories(user_id: int) -> list[str]`.
- Produces: `LocalResourcesMessagingProvider.list_policy_subscriber_ids(category: str) -> list[int]`.

- [ ] **Step 1: Write failing subscription and audience tests**

Create `backend/tests/test_local_resources_subscriptions.py`:

```python
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.db import get_db
from app.local_resources.messaging_provider import (
    LocalResourcesMessagingProvider,
)
from app.local_resources.subscriptions import (
    list_policy_subscriptions,
    recommend_policy_categories,
    set_policy_subscription,
)


class LocalResourceSubscriptionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
            }
        )
        with self.app.app_context():
            self.student_id = self._insert_user("student01", "student", 1)
            self.disabled_id = self._insert_user("student02", "student", 0)
            self.tag_id = int(
                get_db().execute(
                    "SELECT id FROM interest_tags WHERE name = '荔枝'"
                ).fetchone()["id"]
            )
            get_db().execute(
                """
                INSERT INTO student_profiles (
                    user_id, contact, learning_direction, updated_at
                ) VALUES (?, '', 'comprehensive', ?)
                """,
                (
                    self.student_id,
                    "2026-09-19T00:00:00+08:00",
                ),
            )
            get_db().execute(
                "INSERT INTO student_interest_tags (user_id, tag_id) VALUES (?, ?)",
                (self.student_id, self.tag_id),
            )
            get_db().commit()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _insert_user(self, username, role, enabled):
        cursor = get_db().execute(
            """
            INSERT INTO users (
                username, password_hash, name, role, is_enabled,
                created_at, updated_at
            ) VALUES (?, 'hash', ?, ?, ?, ?, ?)
            """,
            (
                username,
                username,
                role,
                enabled,
                "2026-09-19T00:00:00+08:00",
                "2026-09-19T00:00:00+08:00",
            ),
        )
        return int(cursor.lastrowid)

    def test_subscribe_and_unsubscribe_are_idempotent_soft_state(self):
        with self.app.app_context():
            first = set_policy_subscription(
                self.student_id,
                "ecommerce",
                True,
            )
            second = set_policy_subscription(
                self.student_id,
                "ecommerce",
                True,
            )
            self.assertEqual(first["subscribed"], True)
            self.assertEqual(second["subscribed"], True)
            state = list_policy_subscriptions(self.student_id)
            self.assertEqual(
                next(
                    item for item in state["categories"]
                    if item["code"] == "ecommerce"
                )["subscribed"],
                True,
            )
            set_policy_subscription(
                self.student_id,
                "ecommerce",
                False,
            )
            row = get_db().execute(
                """
                SELECT is_active
                FROM local_resource_policy_subscriptions
                WHERE user_id = ? AND category_code = 'ecommerce'
                """,
                (self.student_id,),
            ).fetchone()
            self.assertEqual(row["is_active"], 0)

    def test_messaging_bridge_filters_label_role_and_enabled(self):
        with self.app.app_context():
            set_policy_subscription(
                self.student_id,
                "ecommerce",
                True,
            )
            set_policy_subscription(
                self.disabled_id,
                "ecommerce",
                True,
            )
            provider = LocalResourcesMessagingProvider()
            self.assertEqual(
                provider.list_policy_subscriber_ids("电商"),
                [self.student_id],
            )
            self.assertEqual(
                provider.list_policy_subscriber_ids("未知"),
                [],
            )

    def test_recommendations_come_from_existing_tags_and_do_not_subscribe(self):
        with self.app.app_context():
            recommended = recommend_policy_categories(self.student_id)
            self.assertEqual(
                recommended,
                ["subsidy", "training", "general"],
            )
            count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM local_resource_policy_subscriptions
                WHERE user_id = ?
                """,
                (self.student_id,),
            ).fetchone()["count"]
            self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and verify failure**

```powershell
uv run --directory backend python -m unittest tests.test_local_resources_subscriptions -v
```

Expected: FAIL because subscription and messaging modules do not exist.

- [ ] **Step 3: Implement subscription state, recommendation mapping, and bridge**

`subscriptions.py` requirements:

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from app.db import get_db
from app.local_resources.constants import (
    POLICY_LABELS,
    RECOMMENDATION_TAGS,
)
from app.local_resources.errors import LocalResourceValidationError
from app.profiles.service import get_profile_preferences


PLATFORM_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _now():
    return datetime.now(PLATFORM_TIMEZONE).isoformat(timespec="seconds")


def _validate_category(category_code):
    if category_code not in POLICY_LABELS:
        raise LocalResourceValidationError(
            "政策类别不正确",
            details={"category_code": "不属于政策类别"},
        )
    return category_code


def recommend_policy_categories(user_id):
    preferences = get_profile_preferences(user_id)
    ordered = []
    for name in preferences["interest_tag_names"]:
        for category in RECOMMENDATION_TAGS.get(name, ()):
            if category not in ordered:
                ordered.append(category)
    return ordered


def list_policy_subscriptions(user_id):
    rows = get_db().execute(
        """
        SELECT category_code, is_active
        FROM local_resource_policy_subscriptions
        WHERE user_id = ?
        """,
        (user_id,),
    ).fetchall()
    active = {
        str(row["category_code"])
        for row in rows
        if bool(row["is_active"])
    }
    recommended = recommend_policy_categories(user_id)
    return {
        "categories": [
            {
                "code": code,
                "label": POLICY_LABELS[code],
                "subscribed": code in active,
                "recommended": code in recommended,
            }
            for code in POLICY_LABELS
        ],
        "recommended_category_codes": recommended,
    }


def set_policy_subscription(user_id, category_code, subscribed):
    category = _validate_category(category_code)
    now = _now()
    with get_db():
        get_db().execute(
            """
            INSERT INTO local_resource_policy_subscriptions (
                user_id, category_code, is_active, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id, category_code) DO UPDATE SET
                is_active = excluded.is_active,
                updated_at = excluded.updated_at
            """,
            (user_id, category, int(bool(subscribed)), now, now),
        )
    return {
        "code": category,
        "label": POLICY_LABELS[category],
        "subscribed": bool(subscribed),
    }
```

`messaging_provider.py` imports `get_db`, `POLICY_LABELS` and
`NullMessagingSourceProvider`, then subclasses it:

```python
from app.db import get_db
from app.local_resources.constants import POLICY_LABELS
from app.messaging.source_provider import NullMessagingSourceProvider


class LocalResourcesMessagingProvider(NullMessagingSourceProvider):
    def list_policy_subscriber_ids(self, category: str) -> list[int]:
        category_code = next(
            (
                code
                for code, label in POLICY_LABELS.items()
                if label == category
            ),
            None,
        )
        if category_code is None:
            return []
        rows = get_db().execute(
            """
            SELECT s.user_id
            FROM local_resource_policy_subscriptions s
            JOIN users u ON u.id = s.user_id
            WHERE s.category_code = ?
              AND s.is_active = 1
              AND u.role = 'student'
              AND u.is_enabled = 1
            ORDER BY s.user_id
            """,
            (category_code,),
        ).fetchall()
        return [int(row["user_id"]) for row in rows]
```

Export set/get? This provider is registered by app assembly in Task 8; no second registry. Task 4 only defines the bridge class and subscription service.

- [ ] **Step 4: Run tests to verify pass**

```powershell
uv run --directory backend python -m unittest tests.test_local_resources_subscriptions tests.test_notification_broadcasts -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/local_resources/subscriptions.py backend/app/local_resources/messaging_provider.py backend/app/local_resources/__init__.py backend/tests/test_local_resources_subscriptions.py
git commit -m "后端：实现政策订阅与消息来源桥接"
```

---

### Task 5: Idempotent Policy/News View Recording

**Files:**
- Create: `backend/app/local_resources/views.py`
- Create: `backend/tests/test_local_resources_views.py`
- Modify: `backend/app/local_resources/__init__.py`

**Interfaces:**
- Consumes: `get_policy_news_provider()` and provider `record_policy_view` / `record_news_view`.
- Produces: `record_policy_view(policy_id: str, view_event_id: str) -> int`.
- Produces: `record_news_view(news_id: str, view_event_id: str) -> int`.
- Behavior: no local counter; 10 provider is authoritative; not-found and unavailable map to local errors.

- [ ] **Step 1: Write failing idempotency/delegation tests**

Create `backend/tests/test_local_resources_views.py`:

```python
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app import create_app
from app.government_console.errors import (
    ProviderAccessDeniedError,
    ProviderConflictError,
    ProviderError,
    ProviderNotFoundError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from app.government_console.providers import set_policy_news_provider
from app.local_resources.errors import (
    LocalResourceAccessDeniedError,
    LocalResourceConflictError,
    LocalResourceNotFoundError,
    LocalResourceUnavailableError,
    LocalResourceValidationError,
)
from app.local_resources.views import (
    record_news_view,
    record_policy_view,
)


class LocalResourceViewTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
            }
        )
        self.provider = Mock()
        set_policy_news_provider(self.app, self.provider)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_views_delegate_and_return_provider_total(self):
        self.provider.record_policy_view.return_value = 4
        self.provider.record_news_view.return_value = 7
        with self.app.app_context():
            self.assertEqual(
                record_policy_view("policy-1", "view-1"),
                4,
            )
            self.assertEqual(
                record_news_view("news-1", "view-1"),
                7,
            )
        self.provider.record_policy_view.assert_called_once_with(
            "policy-1",
            "view-1",
        )
        self.provider.record_news_view.assert_called_once_with(
            "news-1",
            "view-1",
        )

    def test_event_id_is_required_text(self):
        with self.app.app_context():
            for value in (None, "", " ", 123):
                with self.subTest(value=value):
                    with self.assertRaises(LocalResourceValidationError):
                        record_policy_view("policy-1", value)

    def test_provider_not_found_and_unavailable_map_to_local_errors(self):
        self.provider.record_policy_view.side_effect = ProviderNotFoundError(
            "内容不存在"
        )
        with self.app.app_context():
            with self.assertRaises(LocalResourceNotFoundError):
                record_policy_view("policy-1", "view-1")
        self.provider.record_news_view.side_effect = ProviderUnavailableError(
            "新闻浏览计数暂不可用"
        )
        with self.app.app_context():
            with self.assertRaises(LocalResourceUnavailableError):
                record_news_view("news-1", "view-2")

    def test_conflict_access_and_validation_errors_do_not_escape(self):
        cases = (
            (ProviderConflictError("冲突"), LocalResourceConflictError),
            (
                ProviderAccessDeniedError("拒绝"),
                LocalResourceAccessDeniedError,
            ),
            (
                ProviderValidationError("非法"),
                LocalResourceValidationError,
            ),
        )
        with self.app.app_context():
            for provider_error, local_error in cases:
                with self.subTest(error=provider_error):
                    self.provider.record_policy_view.side_effect = provider_error
                    with self.assertRaises(local_error):
                        record_policy_view("policy-1", "view-1")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and verify failure**

```powershell
uv run --directory backend python -m unittest tests.test_local_resources_views -v
```

Expected: FAIL because `views.py` does not exist.

- [ ] **Step 3: Implement exact delegation and error mapping**

Create `views.py`:

```python
from __future__ import annotations

from app.government_console.errors import (
    ProviderAccessDeniedError,
    ProviderConflictError,
    ProviderError,
    ProviderNotFoundError,
    ProviderUnavailableError,
    ProviderValidationError,
)
from app.government_console.providers import get_policy_news_provider
from app.local_resources.errors import (
    LocalResourceAccessDeniedError,
    LocalResourceConflictError,
    LocalResourceNotFoundError,
    LocalResourceUnavailableError,
    LocalResourceValidationError,
)


def _required_id(value, field):
    if not isinstance(value, str) or not value.strip():
        raise LocalResourceValidationError(
            "内容标识不能为空",
            details={field: "必须是文本"},
        )
    return value.strip()


def _required_event_id(value):
    if not isinstance(value, str) or not value.strip():
        raise LocalResourceValidationError(
            "浏览事件标识不能为空",
            details={"view_event_id": "必须是文本"},
        )
    return value.strip()


def _map_provider_error(error: ProviderError, *, missing_message: str):
    if isinstance(error, ProviderValidationError):
        raise LocalResourceValidationError(
            error.message,
            details=error.details,
        ) from error
    if isinstance(error, ProviderNotFoundError):
        raise LocalResourceNotFoundError(missing_message) from error
    if isinstance(error, ProviderConflictError):
        raise LocalResourceConflictError(error.message) from error
    if isinstance(error, ProviderUnavailableError):
        raise LocalResourceUnavailableError(
            error.message,
            details=error.details,
        ) from error
    if isinstance(error, ProviderAccessDeniedError):
        raise LocalResourceAccessDeniedError(error.message) from error
    raise LocalResourceUnavailableError(error.message) from error


def record_policy_view(policy_id, view_event_id):
    policy = _required_id(policy_id, "policy_id")
    event = _required_event_id(view_event_id)
    try:
        return int(
            get_policy_news_provider().record_policy_view(policy, event)
        )
    except ProviderError as error:
        _map_provider_error(error, missing_message="政策不存在或不可见")


def record_news_view(news_id, view_event_id):
    news = _required_id(news_id, "news_id")
    event = _required_event_id(view_event_id)
    try:
        return int(
            get_policy_news_provider().record_news_view(news, event)
        )
    except ProviderError as error:
        _map_provider_error(error, missing_message="新闻不存在或不可见")
```

Do not create a local view table or increment any local count.

- [ ] **Step 4: Run tests to verify pass**

```powershell
uv run --directory backend python -m unittest tests.test_local_resources_views tests.test_government_views -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/local_resources/views.py backend/app/local_resources/__init__.py backend/tests/test_local_resources_views.py
git commit -m "后端：接入政策新闻浏览计数"
```

---

### Task 6: TTS Client, Dialect Mapping, and Audio Validation

**Files:**
- Create: `backend/app/local_resources/tts.py`
- Create: `backend/tests/test_local_resources_tts.py`
- Modify: `backend/app/local_resources/__init__.py`

**Interfaces:**
- Produces: `TtsAudio` with `content: bytes`, `content_type: str`.
- Produces: `TtsClient.synthesize(text: str, language_code: str, voice_code: str, *, call_point: str) -> TtsAudio`.
- Produces: `OpenAiCompatibleTtsClient`, `get_local_tts_client()`, `set_local_tts_client(app, client)`.
- Produces: `synthesize_dialect(dialect_code: str, text: str) -> TtsAudio`.
- Mapping: `yue/hak/nan` to exact config keys.

- [ ] **Step 1: Write failing TTS mapping/request/failure tests**

Create `backend/tests/test_local_resources_tts.py` with:

```python
import tempfile
import unittest
from pathlib import Path

import httpx

from app import create_app
from app.local_resources.errors import LocalResourceAiUnavailableError
from app.local_resources.tts import (
    OpenAiCompatibleTtsClient,
    set_local_tts_client,
    synthesize_dialect,
)


class LocalResourceTtsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "AI_API_KEY": "shared-key",
                "AI_TTS_URL": "https://tts.example.test/speech",
                "AI_TTS_MODEL": "dialect-tts",
                "AI_TTS_VOICE_YUE": "voice-yue",
                "AI_TTS_VOICE_HAKKA": "voice-hak",
                "AI_TTS_VOICE_TEOCHEW": "voice-nan",
                "AI_TTS_TIMEOUT_SECONDS": 5,
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_dialect_voice_mapping_and_http_contract(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["request"] = request
            return httpx.Response(
                200,
                content=b"ID3audio",
                headers={"content-type": "audio/mpeg"},
                request=request,
            )

        client = OpenAiCompatibleTtsClient(
            api_url="https://tts.example.test/speech",
            api_key="shared-key",
            model="dialect-tts",
            timeout=5,
            transport=httpx.MockTransport(handler),
        )
        set_local_tts_client(self.app, client)
        with self.app.app_context():
            audio = synthesize_dialect("hak", "你好")
        request = captured["request"]
        self.assertEqual(audio.content, b"ID3audio")
        self.assertEqual(audio.content_type, "audio/mpeg")
        self.assertIn(b'"language":"hak"', request.content)
        self.assertIn(b'"voice":"voice-hak"', request.content)
        self.assertIn(
            b'"response_format":"mp3"',
            request.content,
        )

    def test_missing_voice_and_empty_audio_are_unavailable(self):
        self.app.config["AI_TTS_VOICE_YUE"] = ""
        with self.app.app_context():
            with self.assertRaises(LocalResourceAiUnavailableError):
                synthesize_dialect("yue", "你好")

    def test_non_audio_response_is_unavailable(self):
        class BadClient:
            def synthesize(self, **kwargs):
                from app.local_resources.tts import TtsAudio
                return TtsAudio(content=b"not-audio", content_type="text/plain")

        set_local_tts_client(self.app, BadClient())
        with self.app.app_context():
            with self.assertRaises(LocalResourceAiUnavailableError):
                synthesize_dialect("nan", "你好")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and verify failure**

```powershell
uv run --directory backend python -m unittest tests.test_local_resources_tts -v
```

Expected: FAIL because `tts.py` does not exist.

- [ ] **Step 3: Implement TTS client and dialect mapping**

Create `tts.py` with:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx
from flask import Flask, current_app

from app.local_resources.constants import DIALECTS
from app.local_resources.errors import (
    LocalResourceAiUnavailableError,
    LocalResourceValidationError,
)


VOICE_CONFIG = {
    "yue": "AI_TTS_VOICE_YUE",
    "hak": "AI_TTS_VOICE_HAKKA",
    "nan": "AI_TTS_VOICE_TEOCHEW",
}


@dataclass(frozen=True)
class TtsAudio:
    content: bytes
    content_type: str


class TtsClient(Protocol):
    def synthesize(
        self,
        text: str,
        language_code: str,
        voice_code: str,
        *,
        call_point: str,
    ) -> TtsAudio: ...


class OpenAiCompatibleTtsClient:
    def __init__(self, *, api_url, api_key, model, timeout, transport=None):
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.transport = transport

    def _client(self):
        kwargs = {"timeout": self.timeout}
        if self.transport is not None:
            kwargs["transport"] = self.transport
        return httpx.Client(**kwargs)

    def synthesize(self, text, language_code, voice_code, *, call_point):
        del call_point
        if not self.api_url or not self.api_key or not self.model:
            raise LocalResourceAiUnavailableError()
        try:
            with self._client() as client:
                response = client.post(
                    self.api_url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "input": text,
                        "voice": voice_code,
                        "language": language_code,
                        "response_format": "mp3",
                    },
                )
                response.raise_for_status()
                content_type = response.headers.get(
                    "content-type",
                    "",
                ).split(";")[0].strip().lower()
                if not response.content or not content_type.startswith("audio/"):
                    raise LocalResourceAiUnavailableError()
                return TtsAudio(
                    content=response.content,
                    content_type=content_type,
                )
        except LocalResourceAiUnavailableError:
            raise
        except Exception as error:
            raise LocalResourceAiUnavailableError() from error


def set_local_tts_client(app: Flask, client: TtsClient) -> None:
    app.extensions["local_resource_tts_client"] = client


def get_local_tts_client() -> TtsClient:
    client = current_app.extensions.get("local_resource_tts_client")
    if client is None:
        raise LocalResourceAiUnavailableError()
    return client


def synthesize_dialect(dialect_code: str, text: str) -> TtsAudio:
    if dialect_code not in DIALECTS:
        raise LocalResourceValidationError(
            "方言代码不正确",
            details={"dialect_code": "不支持"},
        )
    normalized = str(text or "").strip()
    if not normalized:
        raise LocalResourceAiUnavailableError()
    voice_key = VOICE_CONFIG[dialect_code]
    voice = str(current_app.config.get(voice_key, "")).strip()
    if not voice:
        raise LocalResourceAiUnavailableError()
    try:
        audio = get_local_tts_client().synthesize(
            normalized,
            dialect_code,
            voice,
            call_point="local_resources_dialect_tts",
        )
    except LocalResourceAiUnavailableError:
        raise
    except Exception as error:
        raise LocalResourceAiUnavailableError() from error
    content_type = str(
        getattr(audio, "content_type", "")
    ).split(";")[0].strip().lower()
    content = getattr(audio, "content", None)
    if (
        not isinstance(content, bytes)
        or not content
        or not content_type.startswith("audio/")
    ):
        raise LocalResourceAiUnavailableError()
    return TtsAudio(content=content, content_type=content_type)
```

Export `TtsAudio`, client, set/get and `synthesize_dialect` from `local_resources/__init__.py`.

- [ ] **Step 4: Run tests to verify pass**

```powershell
uv run --directory backend python -m unittest tests.test_local_resources_tts -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/local_resources/tts.py backend/app/local_resources/__init__.py backend/tests/test_local_resources_tts.py
git commit -m "后端：新增三方言 TTS 适配器"
```

---

### Task 7: Dialect Answer Orchestration and Turn Persistence

**Files:**
- Create: `backend/app/local_resources/dialect_assistant.py`
- Create: `backend/tests/test_local_resources_dialect.py`
- Modify: `backend/app/local_resources/__init__.py`

**Interfaces:**
- Consumes: 003 `get_ai_client().complete_json(...)`; 006 `synthesize_dialect(...)`; `local_resource_dialect_turns`.
- Produces: `generate_dialect_answer(dialect_code: str, question: str) -> dict[str, str]`.
- Produces: `complete_dialect_turn(user_id: int, dialect_code: str, recognized_text: str) -> dict`.
- Produces turn fields: `id`, `dialect_code`, `dialect_label`, `recognized_text`, `dialect_answer`, `mandarin_answer`, `status`, `created_at`, `audio_content`, `audio_content_type`.

- [ ] **Step 1: Write failing answer and persistence tests**

Create `backend/tests/test_local_resources_dialect.py` with:

```python
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.errors import AiUnavailableError
from app.db import get_db
from app.local_resources.dialect_assistant import (
    complete_dialect_turn,
    generate_dialect_answer,
)
from app.local_resources.errors import (
    LocalResourceAiUnavailableError,
    LocalResourceValidationError,
)
from app.local_resources.tts import TtsAudio, set_local_tts_client


class LocalResourceDialectTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "AI_TTS_VOICE_YUE": "voice-yue",
                "AI_TTS_VOICE_HAKKA": "voice-hak",
                "AI_TTS_VOICE_TEOCHEW": "voice-nan",
            }
        )
        with self.app.app_context():
            cursor = get_db().execute(
                """
                INSERT INTO users (
                    username, password_hash, name, role, is_enabled,
                    created_at, updated_at
                ) VALUES (
                    'student01', 'hash', '学员甲', 'student', 1,
                    '2026-09-19T00:00:00+08:00',
                    '2026-09-19T00:00:00+08:00'
                )
                """
            )
            get_db().commit()
            self.user_id = int(cursor.lastrowid)
        self.ai = Mock()
        self.ai.complete_json.return_value = {
            "dialect_text": "呢个问题要睇种植时间。",
            "mandarin_text": "这个问题要看种植时间。",
        }
        set_ai_client(self.app, self.ai)

        class FakeTts:
            def synthesize(self, **kwargs):
                self.kwargs = kwargs
                return TtsAudio(b"ID3audio", "audio/mpeg")

        self.tts = FakeTts()
        set_local_tts_client(self.app, self.tts)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_answer_uses_single_callpoint_and_exact_allowlist(self):
        with self.app.app_context():
            answer = generate_dialect_answer("yue", "几时种荔枝？")
        self.assertEqual(
            answer,
            {
                "dialect_text": "呢个问题要睇种植时间。",
                "mandarin_text": "这个问题要看种植时间。",
            },
        )
        messages = self.ai.complete_json.call_args.args[0]
        rendered = repr(messages)
        self.assertIn("几时种荔枝？", rendered)
        self.assertIn("yue", rendered)
        self.assertNotIn("password", rendered)
        self.assertEqual(
            self.ai.complete_json.call_args.kwargs["call_point"],
            "local_resources_dialect_answer",
        )

    def test_complete_turn_persists_text_and_returns_audio_without_storing_it(self):
        with self.app.app_context():
            turn = complete_dialect_turn(
                self.user_id,
                "hak",
                "几时种水稻？",
            )
            row = get_db().execute(
                """
                SELECT *
                FROM local_resource_dialect_turns
                WHERE turn_id = ?
                """,
                (turn["id"],),
            ).fetchone()
        self.assertEqual(turn["audio_content"], b"ID3audio")
        self.assertEqual(turn["audio_content_type"], "audio/mpeg")
        self.assertEqual(row["dialect_code"], "hak")
        self.assertEqual(row["recognized_text"], "几时种水稻？")
        self.assertNotIn("audio", row.keys())
        self.assertEqual(self.tts.kwargs["language_code"], "hak")
        self.assertEqual(self.tts.kwargs["voice_code"], "voice-hak")

    def test_ai_failure_has_no_fallback_and_no_turn(self):
        self.ai.complete_json.side_effect = AiUnavailableError("down")
        with self.app.app_context():
            with self.assertRaises(LocalResourceAiUnavailableError):
                complete_dialect_turn(
                    self.user_id,
                    "nan",
                    "问题",
                )
            count = get_db().execute(
                "SELECT COUNT(*) AS count FROM local_resource_dialect_turns"
            ).fetchone()["count"]
        self.assertEqual(count, 0)

    def test_invalid_answer_and_dialect_are_rejected(self):
        self.ai.complete_json.return_value = {
            "dialect_text": "",
            "mandarin_text": "对照",
        }
        with self.app.app_context():
            with self.assertRaises(LocalResourceAiUnavailableError):
                complete_dialect_turn(
                    self.user_id,
                    "yue",
                    "问题",
                )
            with self.assertRaises(LocalResourceValidationError):
                complete_dialect_turn(
                    self.user_id,
                    "mandarin",
                    "问题",
                )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and verify failure**

```powershell
uv run --directory backend python -m unittest tests.test_local_resources_dialect -v
```

Expected: FAIL because `dialect_assistant.py` does not exist.

- [ ] **Step 3: Implement one structured answer call and text-only persistence**

Create `dialect_assistant.py` with these exact behaviors:

```python
from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

from app.agri_skills.ai_client import get_ai_client
from app.agri_skills.errors import AiUnavailableError
from app.db import get_db
from app.local_resources.constants import DIALECTS
from app.local_resources.errors import (
    LocalResourceAiUnavailableError,
    LocalResourceValidationError,
)
from app.local_resources.tts import synthesize_dialect


PLATFORM_TIMEZONE = ZoneInfo("Asia/Shanghai")


def _now() -> str:
    return datetime.now(PLATFORM_TIMEZONE).isoformat(timespec="seconds")


def _build_messages(dialect_code: str, question: str) -> list[dict]:
    label = DIALECTS[dialect_code]
    return [
        {
            "role": "system",
            "content": (
                "你是广东本土资源方言助手。只根据用户问题生成简洁、"
                "可执行的回答。返回 JSON 对象，字段必须是 dialect_text "
                "和 mandarin_text。dialect_text 使用指定方言口语，"
                "mandarin_text 是准确普通话对照；两个字段都不得为空。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"方言：{label}（{dialect_code}）\n"
                f"问题：{question}"
            ),
        },
    ]


def generate_dialect_answer(dialect_code: str, question: str) -> dict:
    if dialect_code not in DIALECTS:
        raise LocalResourceValidationError(
            "方言代码不正确",
            details={"dialect_code": "不支持"},
        )
    normalized = str(question or "").strip()
    if not normalized:
        raise LocalResourceValidationError(
            "问题不能为空",
            details={"question": "不能为空"},
        )
    try:
        payload = get_ai_client().complete_json(
            _build_messages(dialect_code, normalized),
            call_point="local_resources_dialect_answer",
        )
    except (AiUnavailableError, TypeError, ValueError) as error:
        raise LocalResourceAiUnavailableError() from error
    if not isinstance(payload, dict):
        raise LocalResourceAiUnavailableError()
    dialect_text = payload.get("dialect_text")
    mandarin_text = payload.get("mandarin_text")
    if (
        not isinstance(dialect_text, str)
        or not dialect_text.strip()
        or not isinstance(mandarin_text, str)
        or not mandarin_text.strip()
    ):
        raise LocalResourceAiUnavailableError()
    return {
        "dialect_text": dialect_text.strip(),
        "mandarin_text": mandarin_text.strip(),
    }


def complete_dialect_turn(
    user_id: int,
    dialect_code: str,
    recognized_text: str,
) -> dict:
    answer = generate_dialect_answer(dialect_code, recognized_text)
    audio = synthesize_dialect(dialect_code, answer["dialect_text"])
    turn_id = f"dialect-{uuid4().hex}"
    created_at = _now()
    with get_db():
        get_db().execute(
            """
            INSERT INTO local_resource_dialect_turns (
                turn_id, user_id, dialect_code, recognized_text,
                dialect_answer, mandarin_answer, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 'completed', ?)
            """,
            (
                turn_id,
                user_id,
                dialect_code,
                str(recognized_text).strip(),
                answer["dialect_text"],
                answer["mandarin_text"],
                created_at,
            ),
        )
    return {
        "id": turn_id,
        "dialect_code": dialect_code,
        "dialect_label": DIALECTS[dialect_code],
        "recognized_text": str(recognized_text).strip(),
        "dialect_answer": answer["dialect_text"],
        "mandarin_answer": answer["mandarin_text"],
        "status": "completed",
        "created_at": created_at,
        "audio_content": audio.content,
        "audio_content_type": audio.content_type,
    }
```

TTS failure occurs before insertion, so no partial successful turn is stored. Do not add a translation call or local knowledge-base path.

- [ ] **Step 4: Run tests to verify pass**

```powershell
uv run --directory backend python -m unittest tests.test_local_resources_dialect tests.test_agri_qa -v
```

Expected: PASS; the 003 local knowledge-base tests remain green and 006 tests contain no local fallback.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/local_resources/dialect_assistant.py backend/app/local_resources/__init__.py backend/tests/test_local_resources_dialect.py
git commit -m "后端：实现方言回答与轮次持久化"
```

---

### Task 8: Backend Routes, Error Mapping, and Application Wiring

**Files:**
- Create: `backend/app/local_resources/routes.py`
- Create: `backend/tests/test_local_resources_api.py`
- Modify: `backend/app/local_resources/__init__.py`
- Modify: `backend/app/__init__.py`

**Interfaces:**
- Produces endpoints:
  - `GET /api/local-resources/cases`
  - `GET /api/local-resources/cases/<case_id>`
  - `GET /api/local-resources/policies`
  - `GET /api/local-resources/policies/<policy_id>`
  - `GET /api/local-resources/policy-subscriptions`
  - `POST /api/local-resources/policy-subscriptions/<category_code>`
  - `DELETE /api/local-resources/policy-subscriptions/<category_code>`
  - `GET /api/local-resources/news`
  - `GET /api/local-resources/news/<news_id>`
  - `POST /api/local-resources/policies/<policy_id>/views`
  - `POST /api/local-resources/news/<news_id>/views`
  - `POST /api/local-resources/dialect-assistant/turns`
- Produces: `install_default_local_resource_services(app)`, `local_resources_bp`.
- Consumes: all services from Tasks 1-7.
- Wiring: `create_app()` installs case/TTS defaults, registers `LocalResourcesMessagingProvider`, registers blueprint and protects `/api/local-resources`.

- [ ] **Step 1: Write failing API, role, and error tests**

Create `backend/tests/test_local_resources_api.py` with a fixture app and test client:

```python
import base64
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from werkzeug.security import generate_password_hash

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.errors import AiUnavailableError
from app.db import get_db
from app.government_console.dashboard import get_government_dashboard
from app.government_console.providers import set_policy_news_provider
from app.local_resources.tts import TtsAudio, set_local_tts_client


class LocalResourceApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test",
                "AI_TTS_VOICE_YUE": "voice-yue",
                "AI_TTS_VOICE_HAKKA": "voice-hak",
                "AI_TTS_VOICE_TEOCHEW": "voice-nan",
            }
        )
        with self.app.app_context():
            self.student_id = self._insert_user("student01", "student")
            self.teacher_id = self._insert_user("teacher01", "teacher")
        self.provider = Mock()
        self.provider.list_published_policies.return_value = []
        self.provider.list_published_news.return_value = []
        self.provider.record_policy_view.return_value = 1
        self.provider.record_news_view.return_value = 1
        set_policy_news_provider(self.app, self.provider)
        self.ai = Mock()
        self.ai.complete_json.return_value = {
            "dialect_text": "方言回答",
            "mandarin_text": "普通话回答",
        }
        set_ai_client(self.app, self.ai)
        set_local_tts_client(
            self.app,
            Mock(
                synthesize=Mock(
                    return_value=TtsAudio(b"ID3", "audio/mpeg")
                )
            ),
        )
        self.student = self._login("student01")
        self.teacher = self._login("teacher01")

    def tearDown(self):
        self.temp_dir.cleanup()

    def _insert_user(self, username, role):
        cursor = get_db().execute(
            """
            INSERT INTO users (
                username, password_hash, name, role, is_enabled,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (
                username,
                generate_password_hash("password8"),
                username,
                role,
                "2026-09-19T00:00:00+08:00",
                "2026-09-19T00:00:00+08:00",
            ),
        )
        get_db().commit()
        return int(cursor.lastrowid)

    def _login(self, username):
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)
        return client

    def _assign_tag(self, user_id, tag_name):
        get_db().execute(
            """
            INSERT INTO student_interest_tags (user_id, tag_id)
            SELECT ?, id FROM interest_tags WHERE name = ?
            """,
            (user_id, tag_name),
        )
        get_db().commit()

    def test_student_can_list_cases_and_subscribe(self):
        cases = self.student.get("/api/local-resources/cases")
        self.assertEqual(cases.status_code, 200)
        self.assertGreaterEqual(len(cases.get_json()["cases"]), 3)
        subscribed = self.student.post(
            "/api/local-resources/policy-subscriptions/ecommerce"
        )
        self.assertEqual(subscribed.status_code, 200)
        self.assertEqual(
            subscribed.get_json()["subscription"]["subscribed"],
            True,
        )

    def test_teacher_and_anonymous_are_rejected(self):
        self.assertEqual(
            self.app.test_client().get(
                "/api/local-resources/cases"
            ).status_code,
            401,
        )
        self.assertEqual(
            self.teacher.get(
                "/api/local-resources/cases"
            ).status_code,
            403,
        )

    def test_dialect_endpoint_returns_base64_audio_without_storing_it(self):
        response = self.student.post(
            "/api/local-resources/dialect-assistant/turns",
            json={"dialect_code": "yue", "question": "几时种荔枝？"},
        )
        payload = response.get_json()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            base64.b64decode(payload["audio_base64"]),
            b"ID3",
        )
        self.assertEqual(payload["audio_content_type"], "audio/mpeg")
        with self.app.app_context():
            row = get_db().execute(
                "SELECT * FROM local_resource_dialect_turns"
            ).fetchone()
        self.assertEqual(row["dialect_answer"], "方言回答")

    def test_view_endpoint_requires_event_id_and_delegates(self):
        bad = self.student.post(
            "/api/local-resources/policies/policy-1/views",
            json={},
        )
        self.assertEqual(bad.status_code, 400)
        good = self.student.post(
            "/api/local-resources/policies/policy-1/views",
            json={"view_event_id": "view-1"},
        )
        self.assertEqual(good.status_code, 200)
        self.provider.record_policy_view.assert_called_once_with(
            "policy-1",
            "view-1",
        )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run and verify failure**

```powershell
uv run --directory backend python -m unittest tests.test_local_resources_api -v
```

Expected: FAIL because the blueprint and application wiring do not exist.

- [ ] **Step 3: Implement routes and exact app assembly**

Create `routes.py` with `_student_session()` that reads `load_session(required=True, allowed_states={"active"})` and raises `LocalResourceAccessDeniedError` unless `role == "student"`. Register one `@local_resources_bp.errorhandler(LocalResourceError)` with mapping:

```python
status = {
    "validation_error": 400,
    "not_found": 404,
    "conflict": 409,
    "unavailable": 503,
    "access_denied": 403,
}[error.code]
return jsonify(
    success=False,
    message=error.message,
    details=error.details,
), status
```

Define the JSON helper before all route handlers:

```python
def _json_object_payload() -> dict:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise LocalResourceValidationError(
            "请求格式不正确",
            details={"body": "请求体必须是 JSON 对象"},
        )
    return payload
```

The dialect route:

```python
@local_resources_bp.post("/dialect-assistant/turns")
def create_dialect_turn():
    session = _student_session()
    payload = _json_object_payload()
    turn = complete_dialect_turn(
        int(session["id"]),
        payload.get("dialect_code"),
        payload.get("question"),
    )
    return jsonify(
        success=True,
        turn={key: value for key, value in turn.items() if not key.startswith("audio_")},
        audio_base64=base64.b64encode(turn["audio_content"]).decode("ascii"),
        audio_content_type=turn["audio_content_type"],
    ), 201
```

The policy/news list/detail routes call the catalog functions. Subscription routes accept no body and use `set_policy_subscription(..., True/False)`. View routes call the view service with `payload.get("view_event_id")`.

Implement `install_default_local_resource_services(app)` in `local_resources/__init__.py`:

```python
def install_default_local_resource_services(app: Flask) -> None:
    if "local_resource_case_provider" not in app.extensions:
        set_local_resource_case_provider(
            app,
            DatabaseLocalResourceCaseProvider(),
        )
    if "local_resource_tts_client" not in app.extensions:
        set_local_tts_client(
            app,
            OpenAiCompatibleTtsClient(
                api_url=str(app.config.get("AI_TTS_URL", "")),
                api_key=(
                    str(app.config.get("AI_TTS_API_KEY", "")).strip()
                    or str(app.config.get("AI_API_KEY", "")).strip()
                ),
                model=str(app.config.get("AI_TTS_MODEL", "")),
                timeout=float(app.config["AI_TTS_TIMEOUT_SECONDS"]),
            ),
        )
```

Modify `backend/app/__init__.py`:

```python
from app.local_resources import install_default_local_resource_services
from app.local_resources.messaging_provider import (
    LocalResourcesMessagingProvider,
)
from app.local_resources.routes import local_resources_bp

# after install_default_government_services(app)
install_default_local_resource_services(app)

# after EnterpriseMessagingProvider registration
register_messaging_source_provider(
    app,
    LocalResourcesMessagingProvider(),
)

# add "/api/local-resources" to PROTECTED_API_PREFIXES
# register local_resources_bp with the other blueprints
```

Do not modify the 003 ASR route or 10 provider implementation.

- [ ] **Step 4: Run tests to verify pass**

```powershell
uv run --directory backend python -m unittest tests.test_local_resources_api tests.test_notification_broadcasts tests.test_government_provider_contract -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/local_resources/routes.py backend/app/local_resources/__init__.py backend/app/__init__.py backend/tests/test_local_resources_api.py
git commit -m "后端：接通本土资源 API 与应用装配"
```

---

### Task 9: Backend Cross-Module Acceptance

**Files:**
- Create: `backend/tests/test_local_resources_integration.py`

**Interfaces:**
- Consumes: real `DatabasePolicyNewsProvider`, `publish_policy`, `publish_news`, `unpublish_policy`, `delete_policy`, `delete_news`, 006 subscription and view services.
- Produces: end-to-end evidence for visibility, push audience, deletion retention and no local counters.

- [ ] **Step 1: Write the failing cross-module acceptance**

Create `backend/tests/test_local_resources_integration.py` with one `unittest.TestCase` that:

```python
def test_policy_subscribe_publish_view_unpublish_delete_flow(self):
    with self.app.app_context():
        set_policy_subscription(self.student_id, "ecommerce", True)
        policy = publish_policy(
            actor_id=self.government_id,
            request_id="policy-1",
            title="直播培训补贴",
            content="正文",
            category_code="ecommerce",
        )
        visible = get_policy_news_provider().get_published_policy(
            policy["id"]
        )
        first = record_policy_view(policy["id"], "view-1")
        retry = record_policy_view(policy["id"], "view-1")
        second = record_policy_view(policy["id"], "view-2")
        notifications = get_db().execute(
            """
            SELECT recipient_id, title, body
            FROM system_notifications
            WHERE event_type = 'policy_published'
            """
        ).fetchall()
    self.assertEqual(visible["category_label"], "电商")
    self.assertEqual((first, retry, second), (1, 1, 2))
    self.assertEqual(
        [row["recipient_id"] for row in notifications],
        [self.student_id],
    )
    self.assertEqual(notifications[0]["body"], "政策类别：电商")
```

Add another test for news:

```python
def test_news_publish_view_delete_has_no_subscription_or_down_state(self):
    with self.app.app_context():
        news = publish_news(
            actor_id=self.government_id,
            request_id="news-1",
            title="暴雨预警",
            content="注意防范",
            category_code="disaster_warning",
        )
        self.assertEqual(
            get_policy_news_provider().get_published_news(news["id"])["title"],
            "暴雨预警",
        )
        self.assertEqual(record_news_view(news["id"], "news-view-1"), 1)
        delete_news(news["id"], expected_version=news["version"])
        with self.assertRaises(LocalResourceNotFoundError):
            get_news(news["id"])
        with self.assertRaises(LocalResourceNotFoundError):
            record_news_view(news["id"], "news-view-2")
```

Add a static source test:

```python
def test_local_resource_backend_has_no_ai_fallback_or_policy_table_access(self):
    root = Path(__file__).parents[1] / "app" / "local_resources"
    source = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    self.assertNotIn("local_kb", source)
    self.assertNotIn("agri_diagnosis", source)
    self.assertNotIn("FROM government_policies", source)
    self.assertNotIn("FROM government_news", source)
```

- [ ] **Step 2: Run and verify failure**

```powershell
uv run --directory backend python -m unittest tests.test_local_resources_integration -v
```

Expected: FAIL until tasks 1-8 are integrated; then identify any concrete ordering or mapping defect.

- [ ] **Step 3: Apply only integration fixes**

Potential fixes must stay within `backend/app/local_resources/` and the exact assembly lines in `backend/app/__init__.py`. Do not change:

- 10 policy/news implementation or table schema;
- 02 notification storage or broadcast function;
- 003 ASR route/client behavior;
- provider location or add a second provider.

Any fix must include a focused assertion demonstrating the corrected behavior.

- [ ] **Step 4: Run backend integration and full backend tests**

```powershell
uv run --directory backend python -m unittest tests.test_local_resources_integration -v
uv run --directory backend python -m unittest discover -s tests
```

Expected: all tests pass, including the existing 010 provider and 02 broadcast tests.

- [ ] **Step 5: Commit**

```powershell
git add backend/tests/test_local_resources_integration.py backend/app/local_resources backend/app/__init__.py
git commit -m "测试：验证本土资源跨模块闭环"
```

---

### Task 10: Frontend API Types and Local-Resources Store

**Files:**
- Modify: `frontend/src/api/types.ts`
- Create: `frontend/src/stores/localResources.ts`
- Create: `frontend/src/stores/localResources.test.ts`

**Interfaces:**
- Produces types: `LocalResourceCase`, `LocalResourcePolicy`, `LocalResourceNews`, `PolicyCategorySubscription`, `PolicySubscriptionState`.
- Produces store `useLocalResourcesStore` with state `cases`, `caseDetail`, `policies`, `policyDetail`, `news`, `newsDetail`, `subscriptions`, `policyViewEventId`, `newsViewEventId`, `loading`, `error`, `viewNotice`.
- Produces actions: `loadCases`, `openCase`, `loadPolicies`, `openPolicy`, `loadNews`, `openNews`, `loadSubscriptions`, `subscribePolicyCategory`, `unsubscribePolicyCategory`, `recordPolicyView`, `recordNewsView`.

- [ ] **Step 1: Write failing store tests**

Create `frontend/src/stores/localResources.test.ts`:

```ts
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/api/client'

import { useLocalResourcesStore } from './localResources'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return { ...actual, apiFetch: vi.fn() }
})

const mockedApiFetch = vi.mocked(apiFetch)

describe('localResources store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
  })

  it('loads cases, policies, news and subscriptions', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({ success: true, cases: [] } as never)
      .mockResolvedValueOnce({ success: true, policies: [] } as never)
      .mockResolvedValueOnce({ success: true, news: [] } as never)
      .mockResolvedValueOnce({
        success: true,
        subscriptions: {
          categories: [],
          recommended_category_codes: []
        }
      } as never)

    const store = useLocalResourcesStore()
    await store.loadCases()
    await store.loadPolicies()
    await store.loadNews()
    await store.loadSubscriptions()

    expect(mockedApiFetch.mock.calls.map(call => call[0])).toEqual([
      '/api/local-resources/cases',
      '/api/local-resources/policies',
      '/api/local-resources/news',
      '/api/local-resources/policy-subscriptions'
    ])
  })

  it('reuses one event id across retries and keeps content on unavailable', async () => {
    vi.spyOn(crypto, 'randomUUID').mockReturnValue(
      '00000000-0000-4000-8000-000000000001'
    )
    mockedApiFetch
      .mockRejectedValueOnce(new ApiError('unavailable', 503))
      .mockResolvedValueOnce({ success: true, view_count: 1 } as never)
    const store = useLocalResourcesStore()
    store.policyDetail = {
      id: 'policy-1',
      title: '政策',
      content: '正文',
      category_code: 'general',
      category_label: '综合',
      published_at: '2026-09-19T10:00:00+08:00',
      updated_at: '2026-09-19T10:00:00+08:00',
      version: 1
    }

    await store.recordPolicyView('policy-1')
    await store.recordPolicyView('policy-1')

    expect(mockedApiFetch).toHaveBeenNthCalledWith(
      2,
      '/api/local-resources/policies/policy-1/views',
      expect.objectContaining({ method: 'POST' })
    )
    expect(mockedApiFetch.mock.calls[0][1]?.body).toBe(
      mockedApiFetch.mock.calls[1][1]?.body
    )
    expect(store.policyDetail.content).toBe('正文')
    expect(store.viewNotice).toBe('')
  })

  it('clears stale detail when a concurrent delete returns 404', async () => {
    mockedApiFetch.mockRejectedValueOnce(
      new ApiError('政策不存在', 404)
    )
    const store = useLocalResourcesStore()
    store.policyDetail = {
      id: 'policy-1',
      title: '政策',
      content: '正文',
      category_code: 'general',
      category_label: '综合',
      published_at: '2026-09-19T10:00:00+08:00',
      updated_at: '2026-09-19T10:00:00+08:00',
      version: 1
    }

    await store.recordPolicyView('policy-1')

    expect(store.policyDetail).toBeNull()
    expect(store.error).toBe('政策不存在')
    expect(store.viewNotice).toBe('')
  })

  it('resets the policy event id for a new open', async () => {
    vi.spyOn(crypto, 'randomUUID')
      .mockReturnValueOnce('event-1')
      .mockReturnValueOnce('event-2')
    mockedApiFetch
      .mockResolvedValueOnce({
        success: true,
        policy: {
          id: 'policy-1',
          title: '政策一',
          content: '正文一',
          category_code: 'general',
          category_label: '综合',
          published_at: '2026-09-19T10:00:00+08:00',
          updated_at: '2026-09-19T10:00:00+08:00',
          version: 1
        }
      } as never)
      .mockResolvedValueOnce({ success: true, view_count: 1 } as never)
      .mockResolvedValueOnce({
        success: true,
        policy: {
          id: 'policy-2',
          title: '政策二',
          content: '正文二',
          category_code: 'general',
          category_label: '综合',
          published_at: '2026-09-19T11:00:00+08:00',
          updated_at: '2026-09-19T11:00:00+08:00',
          version: 1
        }
      } as never)
      .mockResolvedValueOnce({ success: true, view_count: 1 } as never)
    const store = useLocalResourcesStore()

    await store.openPolicy('policy-1')
    await store.recordPolicyView('policy-1')
    await store.openPolicy('policy-2')
    await store.recordPolicyView('policy-2')

    expect(String(mockedApiFetch.mock.calls[1][1]?.body)).toContain('event-1')
    expect(String(mockedApiFetch.mock.calls[3][1]?.body)).toContain('event-2')
  })

  it('reuses news event ids on retry and clears detail on 404', async () => {
    vi.spyOn(crypto, 'randomUUID').mockReturnValue('news-event-1')
    mockedApiFetch
      .mockRejectedValueOnce(new ApiError('unavailable', 503))
      .mockResolvedValueOnce({ success: true, view_count: 1 } as never)
      .mockRejectedValueOnce(new ApiError('新闻不存在', 404))
    const store = useLocalResourcesStore()
    store.newsDetail = {
      id: 'news-1',
      title: '新闻',
      content: '正文',
      category_code: 'news',
      category_label: '新闻',
      published_at: '2026-09-19T10:00:00+08:00',
      updated_at: '2026-09-19T10:00:00+08:00',
      version: 1
    }

    await store.recordNewsView('news-1')
    await store.recordNewsView('news-1')
    expect(mockedApiFetch.mock.calls[0][1]?.body).toBe(
      mockedApiFetch.mock.calls[1][1]?.body
    )
    await store.recordNewsView('news-1')

    expect(store.newsDetail).toBeNull()
    expect(store.error).toBe('新闻不存在')
  })

  it('subscribes and unsubscribes idempotently through exact routes', async () => {
    mockedApiFetch
      .mockResolvedValueOnce({ success: true, subscription: {} } as never)
      .mockResolvedValueOnce({
        success: true,
        subscriptions: {
          categories: [],
          recommended_category_codes: []
        }
      } as never)
      .mockResolvedValueOnce({ success: true, subscription: {} } as never)
      .mockResolvedValueOnce({
        success: true,
        subscriptions: {
          categories: [],
          recommended_category_codes: []
        }
      } as never)
    const store = useLocalResourcesStore()

    await store.subscribePolicyCategory('ecommerce')
    await store.unsubscribePolicyCategory('ecommerce')

    expect(mockedApiFetch.mock.calls[0]).toEqual([
      '/api/local-resources/policy-subscriptions/ecommerce',
      { method: 'POST' }
    ])
    expect(mockedApiFetch.mock.calls[2]).toEqual([
      '/api/local-resources/policy-subscriptions/ecommerce',
      { method: 'DELETE' }
    ])
  })
})
```

- [ ] **Step 2: Run and verify failure**

```powershell
Set-Location frontend
npm test -- src/stores/localResources.test.ts
```

Expected: FAIL because the store and types do not exist.

- [ ] **Step 3: Add DTOs and implement the store**

Add the exact DTOs to `frontend/src/api/types.ts`:

```ts
export type LocalDialectCode = 'yue' | 'hak' | 'nan'
export type PolicyCategoryCode =
  | 'subsidy'
  | 'ecommerce'
  | 'heritage'
  | 'training'
  | 'certification'
  | 'general'
  | 'entrepreneurship'
export type NewsCategoryCode =
  | 'news'
  | 'disaster_warning'
  | 'policy_update'

export interface LocalResourceCase {
  id: string
  title: string
  summary: string
  published_at: string
  updated_at: string
  is_demo: boolean
}

export interface LocalResourceCaseDetail extends LocalResourceCase {
  background: string
  journey: string
  lessons: string
}

export interface LocalResourcePolicy {
  id: string
  title: string
  content: string
  category_code: PolicyCategoryCode
  category_label: string
  published_at: string
  updated_at: string
  version: number
}

export interface LocalResourceNews {
  id: string
  title: string
  content: string
  category_code: NewsCategoryCode
  category_label: string
  published_at: string
  updated_at: string
  version: number
}

export interface PolicyCategorySubscription {
  code: PolicyCategoryCode
  label: string
  subscribed: boolean
  recommended: boolean
}

export interface PolicySubscriptionState {
  categories: PolicyCategorySubscription[]
  recommended_category_codes: PolicyCategoryCode[]
}
```

Implement `localResources.ts` with Pinia setup store or options store. All loads set/clear `loading` and `error`, call exact API paths. `openPolicy` and `openNews` clear the matching event ID so a new open gets a new ID; retries of `recordPolicyView` or `recordNewsView` reuse the stored ID:

```ts
const policyViewEventId = ref<string | null>(null)

async function recordPolicyView(policyId: string) {
  const eventId = policyViewEventId.value ?? crypto.randomUUID()
  policyViewEventId.value = eventId
  try {
    await apiFetch(`/api/local-resources/policies/${policyId}/views`, {
      method: 'POST',
      body: JSON.stringify({ view_event_id: eventId })
    })
    viewNotice.value = ''
  } catch (caught) {
    if (caught instanceof ApiError && caught.status === 404) {
      policyDetail.value = null
      error.value = '政策不存在'
      viewNotice.value = ''
      return
    }
    viewNotice.value = '浏览量暂未记录'
  }
}
```

Apply the same event-ID and 404 rules to `newsViewEventId` / `recordNewsView`, with error text `新闻不存在`. `openPolicy` and `openNews` must not fetch detail by reading 10 tables; they call the 006 catalog route and clear the matching event ID at the start of each new open so the next successful detail gets a fresh event ID.

- [ ] **Step 4: Run tests to verify pass**

```powershell
Set-Location frontend
npm test -- src/stores/localResources.test.ts src/api/types.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/api/types.ts frontend/src/stores/localResources.ts frontend/src/stores/localResources.test.ts
git commit -m "前端：增加本土资源数据层"
```

---

### Task 11: Frontend Dialect Store With ASR Reuse and Audio Playback

**Files:**
- Create: `frontend/src/stores/dialectAssistant.ts`
- Create: `frontend/src/stores/dialectAssistant.test.ts`

**Interfaces:**
- Produces `useDialectAssistantStore` state: `dialectCode`, `recognizedText`, `lastTurn`, `audioUrl`, `recording`, `loading`, `error`.
- Produces actions: `transcribe(blob, filename)`, `submitTurn(question)`, `clearError`, `disposeAudio`.
- ASR path is fixed to `/api/agri-skills/speech/transcriptions`.
- Turn path is `/api/local-resources/dialect-assistant/turns`.

- [ ] **Step 1: Write failing store tests**

Create `frontend/src/stores/dialectAssistant.test.ts` with:

```ts
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ApiError, apiFetch } from '@/api/client'

import { useDialectAssistantStore } from './dialectAssistant'

vi.mock('@/api/client', async importOriginal => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return { ...actual, apiFetch: vi.fn() }
})

const mockedApiFetch = vi.mocked(apiFetch)

describe('dialectAssistant store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    mockedApiFetch.mockReset()
    vi.restoreAllMocks()
    vi.stubGlobal('URL', {
      createObjectURL: vi.fn(() => 'blob:audio-1'),
      revokeObjectURL: vi.fn()
    })
  })

  it('reuses the exact 003 ASR route and maps its failure copy', async () => {
    mockedApiFetch.mockRejectedValueOnce(
      new ApiError('未能识别，请重试或改用文字输入', 422)
    )
    const store = useDialectAssistantStore()

    const result = await store.transcribe(
      new Blob(['audio'], { type: 'audio/webm' }),
      'question.webm'
    )

    expect(result).toBe('')
    expect(mockedApiFetch.mock.calls[0][0]).toBe(
      '/api/agri-skills/speech/transcriptions'
    )
    const options = mockedApiFetch.mock.calls[0][1]!
    expect(options.headers).toMatchObject({
      'Content-Type': expect.stringContaining(
        'multipart/form-data; boundary='
      )
    })
    const multipart = await (options.body as Blob).text()
    expect(multipart).toContain('name="audio"')
    expect(multipart).toContain('filename="question.webm"')
    expect(multipart).not.toContain('dialect_code')
    expect(store.error).toBe('未能识别，请重说或改用文字')
  })

  it('submits dialect and decodes returned audio without storing it', async () => {
    mockedApiFetch.mockResolvedValueOnce({
      success: true,
      turn: {
        id: 'dialect-1',
        dialect_code: 'yue',
        dialect_label: '粤语',
        recognized_text: '问题',
        dialect_answer: '方言回答',
        mandarin_answer: '普通话回答',
        status: 'completed',
        created_at: '2026-09-19T10:00:00+08:00'
      },
      audio_base64: 'SUQz',
      audio_content_type: 'audio/mpeg'
    } as never)
    const store = useDialectAssistantStore()
    store.dialectCode = 'yue'

    const ok = await store.submitTurn('问题')

    expect(ok).toBe(true)
    expect(mockedApiFetch).toHaveBeenCalledWith(
      '/api/local-resources/dialect-assistant/turns',
      {
        method: 'POST',
        body: JSON.stringify({
          dialect_code: 'yue',
          question: '问题'
        })
      }
    )
    expect(store.audioUrl).toBe('blob:audio-1')
    expect(store.lastTurn?.mandarin_answer).toBe('普通话回答')
  })

  it('uses the exact unavailable copy for answer or TTS failure', async () => {
    mockedApiFetch.mockRejectedValueOnce(
      new ApiError('AI 服务暂时不可用', 503)
    )
    const store = useDialectAssistantStore()
    store.dialectCode = 'nan'

    const ok = await store.submitTurn('问题')

    expect(ok).toBe(false)
    expect(store.error).toBe('AI 服务暂时不可用')
    expect(store.lastTurn).toBeNull()
  })
})
```

- [ ] **Step 2: Run and verify failure**

```powershell
Set-Location frontend
npm test -- src/stores/dialectAssistant.test.ts
```

Expected: FAIL because the store does not exist.

- [ ] **Step 3: Implement multipart ASR reuse and base64 audio playback**

Copy the multipart boundary/file construction pattern from `frontend/src/stores/agriQa.ts`, but target the same 003 route. Normalize only the user-facing message:

```ts
const ASR_FAILURE = '未能识别，请重说或改用文字'
const AI_UNAVAILABLE = 'AI 服务暂时不可用'

function normalizeAsrError(error: unknown): string {
  if (
    error instanceof ApiError &&
    error.message === '未能识别，请重试或改用文字输入'
  ) {
    return ASR_FAILURE
  }
  if (error instanceof ApiError && error.status === 503) {
    return AI_UNAVAILABLE
  }
  return ASR_FAILURE
}
```

`submitTurn` decodes base64 to `Uint8Array`, creates a `Blob` using `audio_content_type`, and calls `URL.createObjectURL`. Revoke the previous URL before replacing it. Do not persist base64 or a Blob anywhere outside the current browser memory.

- [ ] **Step 4: Run tests to verify pass**

```powershell
Set-Location frontend
npm test -- src/stores/dialectAssistant.test.ts src/stores/agriQa.test.ts
```

Expected: PASS; existing 03 ASR tests remain unchanged.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/stores/dialectAssistant.ts frontend/src/stores/dialectAssistant.test.ts
git commit -m "前端：实现方言问答状态与语音播放"
```

---

### Task 12: Frontend Router, Navigation, and Home

**Files:**
- Create: `frontend/src/components/LocalResourcesNav.vue`
- Create: `frontend/src/views/LocalResourcesHomeView.vue`
- Create: `frontend/src/router/localResourcesRoutes.test.ts`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/views/StudentPortalView.vue`
- Modify: `frontend/src/views/StudentPortalView.test.ts`

**Interfaces:**
- Produces routes:
  - `/student/local-resources`
  - `/student/local-resources/dialect`
  - `/student/local-resources/cases`
  - `/student/local-resources/cases/:caseId`
  - `/student/local-resources/policies`
  - `/student/local-resources/policies/:policyId`
  - `/student/local-resources/news`
  - `/student/local-resources/news/:newsId`
- Produces `LocalResourcesNav` links and a student portal entry.

- [ ] **Step 1: Write failing route/portal test**

Create `frontend/src/router/localResourcesRoutes.test.ts` with route metadata expectations and one portal link assertion:

```ts
import { describe, expect, it } from 'vitest'

import router from './index'

const expectedRoutes = [
  ['/student/local-resources', 'local-resources-home'],
  ['/student/local-resources/dialect', 'local-resources-dialect'],
  ['/student/local-resources/cases', 'local-resources-cases'],
  ['/student/local-resources/cases/:caseId', 'local-resources-case-detail'],
  ['/student/local-resources/policies', 'local-resources-policies'],
  ['/student/local-resources/policies/:policyId', 'local-resources-policy-detail'],
  ['/student/local-resources/news', 'local-resources-news'],
  ['/student/local-resources/news/:newsId', 'local-resources-news-detail']
] as const

describe('local resources routes', () => {
  it('registers every route for students only', () => {
    for (const [path, name] of expectedRoutes) {
      const concretePath = path
        .replace(':caseId', 'case-1')
        .replace(':policyId', 'policy-1')
        .replace(':newsId', 'news-1')
      expect(router.resolve(concretePath)).toMatchObject({
        name,
        meta: { requiresAuth: true, roles: ['student'] }
      })
    }
  })
})
```

Extend `StudentPortalView.test.ts` to assert a link with `href="/student/local-resources"` and text “进入本土资源”.

- [ ] **Step 2: Run and verify failure**

```powershell
Set-Location frontend
npm test -- src/router/localResourcesRoutes.test.ts src/views/StudentPortalView.test.ts
```

Expected: FAIL because the routes and portal link do not exist.

- [ ] **Step 3: Add navigation, home view, routes, and portal entry**

`LocalResourcesNav.vue` uses `RouterLink` and lucide icons for:

```text
方言助手 /student/local-resources/dialect
成功案例 /student/local-resources/cases
政策 /student/local-resources/policies
新闻 /student/local-resources/news
```

`LocalResourcesHomeView.vue` uses `AppHeader`, `PortalShell` or the same page shell pattern as other student modules, `LocalResourcesNav`, and four unframed action links. Do not add marketing hero content.

Add a `LocalResourcesNav` link to the student portal:

```vue
<RouterLink to="/student/local-resources">
  <Landmark :size="18" aria-hidden="true" />
  <span>
    <strong>进入本土资源</strong>
    <small>方言助手、案例、政策与新闻</small>
  </span>
</RouterLink>
```

Import the five concrete views into `router/index.ts` and add the eight routes with `meta: { requiresAuth: true, roles: ['student'] }`.

- [ ] **Step 4: Run tests to verify pass**

```powershell
Set-Location frontend
npm test -- src/router/localResourcesRoutes.test.ts src/views/StudentPortalView.test.ts src/router/roleRoutes.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/components/LocalResourcesNav.vue frontend/src/views/LocalResourcesHomeView.vue frontend/src/router/index.ts frontend/src/router/localResourcesRoutes.test.ts frontend/src/views/StudentPortalView.vue frontend/src/views/StudentPortalView.test.ts
git commit -m "前端：增加本土资源入口与路由"
```

---

### Task 13: Dialect Assistant View

**Files:**
- Create: `frontend/src/views/DialectAssistantView.vue`
- Create: `frontend/src/views/DialectAssistantView.test.ts`

**Interfaces:**
- Consumes: `useDialectAssistantStore`, `VoiceInputButton`, `AppHeader`, `LocalResourcesNav`.
- Produces: dialect selector, enlarged voice control, editable recognized text, submit button, answer blocks, audio controls, and exact error regions.

- [ ] **Step 1: Write failing component tests**

Create `frontend/src/views/DialectAssistantView.test.ts`:

```ts
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useDialectAssistantStore } from '@/stores/dialectAssistant'

import DialectAssistantView from './DialectAssistantView.vue'

describe('DialectAssistantView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shows all three dialect choices and an enlarged labelled voice control', () => {
    const wrapper = mount(DialectAssistantView, {
      global: {
        stubs: {
          AppHeader: true,
          LocalResourcesNav: true
        }
      }
    })

    expect(wrapper.text()).toContain('粤语')
    expect(wrapper.text()).toContain('客家话')
    expect(wrapper.text()).toContain('潮汕话')
    expect(wrapper.text()).toContain('语音提问')
    expect(wrapper.find('[data-test="dialect-voice-button"]').exists()).toBe(true)
  })

  it('submits edited recognized text and renders dialect plus Mandarin answer', async () => {
    const store = useDialectAssistantStore()
    store.dialectCode = 'yue'
    store.recognizedText = '几时种荔枝？'
    store.lastTurn = {
      id: 'dialect-1',
      dialect_code: 'yue',
      dialect_label: '粤语',
      recognized_text: '几时种荔枝？',
      dialect_answer: '春天种。',
      mandarin_answer: '春天种植。',
      status: 'completed',
      created_at: '2026-09-19T10:00:00+08:00'
    }
    store.audioUrl = 'blob:audio-1'
    const submit = vi.spyOn(store, 'submitTurn').mockResolvedValue(true)
    const wrapper = mount(DialectAssistantView, {
      global: {
        stubs: {
          AppHeader: true,
          LocalResourcesNav: true,
          VoiceInputButton: true
        }
      }
    })

    await wrapper.get('form').trigger('submit')

    expect(submit).toHaveBeenCalledWith('几时种荔枝？')
    expect(wrapper.get('[data-test="dialect-answer"]').text()).toContain('春天种。')
    expect(wrapper.get('[data-test="mandarin-answer"]').text()).toContain('春天种植。')
    expect(wrapper.get('audio').attributes('src')).toBe('blob:audio-1')
  })

  it('shows exact ASR and AI failure copy from the store', async () => {
    const store = useDialectAssistantStore()
    store.error = '未能识别，请重说或改用文字'
    const wrapper = mount(DialectAssistantView, {
      global: {
        stubs: {
          AppHeader: true,
          LocalResourcesNav: true
        }
      }
    })
    expect(wrapper.text()).toContain('未能识别，请重说或改用文字')
    store.error = 'AI 服务暂时不可用'
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('AI 服务暂时不可用')
  })
})
```

- [ ] **Step 2: Run and verify failure**

```powershell
Set-Location frontend
npm test -- src/views/DialectAssistantView.test.ts
```

Expected: FAIL because the view does not exist.

- [ ] **Step 3: Implement the dialect interaction**

Key template structure:

```vue
<form @submit.prevent="submit">
  <label for="dialect-code">方言</label>
  <select id="dialect-code" v-model="store.dialectCode">
    <option value="yue">粤语</option>
    <option value="hak">客家话</option>
    <option value="nan">潮汕话</option>
  </select>

  <div class="dialect-voice" data-test="dialect-voice-button">
    <VoiceInputButton
      :recording="store.recording"
      :disabled="store.loading"
      :error="store.error"
      @update:recording="store.recording = $event"
      @recorded="handleRecorded"
      @permission-denied="handlePermissionDenied"
    />
    <strong>语音提问</strong>
  </div>

  <label for="recognized-question">识别文本</label>
  <textarea id="recognized-question" v-model="store.recognizedText" />
  <button type="submit" :disabled="store.loading || !store.recognizedText.trim()">
    提交问题
  </button>
</form>

<section v-if="store.lastTurn">
  <article data-test="dialect-answer">
    <span>方言原文</span>
    <p>{{ store.lastTurn.dialect_answer }}</p>
  </article>
  <audio v-if="store.audioUrl" :src="store.audioUrl" controls />
  <article data-test="mandarin-answer">
    <span>普通话对照</span>
    <p>{{ store.lastTurn.mandarin_answer }}</p>
  </article>
</section>
```

`handleRecorded` calls `store.transcribe`; on success writes `store.recognizedText`. `handlePermissionDenied` sets the exact recognition message. The voice wrapper must provide at least a `64px` control target and visible text label; use Ark tokens and no decorative gradient.

The answer section attempts playback with an `<audio ref>` after `submitTurn` returns true, but still renders `controls` so autoplay rejection is harmless.

- [ ] **Step 4: Run tests to verify pass**

```powershell
Set-Location frontend
npm test -- src/views/DialectAssistantView.test.ts src/components/AgriSkillsNav.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/views/DialectAssistantView.vue frontend/src/views/DialectAssistantView.test.ts
git commit -m "前端：完成方言助手交互页"
```

---

### Task 14: Success-Case List and Detail Views

**Files:**
- Create: `frontend/src/views/LocalResourceCasesView.vue`
- Create: `frontend/src/views/LocalResourceCaseDetailView.vue`
- Create: `frontend/src/views/LocalResourceCasesView.test.ts`

**Interfaces:**
- Consumes: `useLocalResourcesStore.loadCases` and `openCase`.
- Produces: stable list, detail with background/journey/lessons, explicit demo marker, empty state.

- [ ] **Step 1: Write failing list/detail tests**

Create `frontend/src/views/LocalResourceCasesView.test.ts`:

```ts
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useLocalResourcesStore } from '@/stores/localResources'

import LocalResourceCaseDetailView from './LocalResourceCaseDetailView.vue'
import LocalResourceCasesView from './LocalResourceCasesView.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { caseId: 'case-1' } }),
  RouterLink: { template: '<a><slot /></a>' }
}))

describe('success-case views', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders list links and empty state', async () => {
    const store = useLocalResourcesStore()
    store.cases = [
      {
        id: 'case-1',
        title: '案例一',
        summary: '摘要',
        published_at: '2026-09-19T10:00:00+08:00',
        updated_at: '2026-09-19T10:00:00+08:00',
        is_demo: true
      }
    ]
    const wrapper = mount(LocalResourceCasesView, {
      global: { stubs: { AppHeader: true, LocalResourcesNav: true } }
    })
    expect(wrapper.text()).toContain('案例一')
    expect(wrapper.text()).toContain('演示')
    store.cases = []
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('暂无成功案例')
  })

  it('renders all three detail sections', async () => {
    const store = useLocalResourcesStore()
    store.caseDetail = {
      id: 'case-1',
      title: '案例一',
      summary: '摘要',
      background: '背景',
      journey: '历程',
      lessons: '启示',
      published_at: '2026-09-19T10:00:00+08:00',
      updated_at: '2026-09-19T10:00:00+08:00',
      is_demo: true
    }
    vi.spyOn(store, 'openCase').mockResolvedValue(true)
    const wrapper = mount(LocalResourceCaseDetailView, {
      global: { stubs: { AppHeader: true, LocalResourcesNav: true } }
    })
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('背景')
    expect(wrapper.text()).toContain('历程')
    expect(wrapper.text()).toContain('经验启示')
  })
})
```

- [ ] **Step 2: Run and verify failure**

```powershell
Set-Location frontend
npm test -- src/views/LocalResourceCasesView.test.ts
```

Expected: FAIL because both views do not exist.

- [ ] **Step 3: Implement the two views**

List view calls `loadCases()` on mount, renders `RouterLink` to `/student/local-resources/cases/${item.id}`, and labels `is_demo` as “演示数据”. Empty and unavailable states use “暂无成功案例” and “案例数据暂不可用”.

Detail view calls `openCase(route.params.caseId as string)` on mount and renders:

```vue
<section>
  <h2>创业背景</h2>
  <p>{{ store.caseDetail.background }}</p>
</section>
<section>
  <h2>创业历程</h2>
  <p>{{ store.caseDetail.journey }}</p>
</section>
<section>
  <h2>经验启示</h2>
  <p>{{ store.caseDetail.lessons }}</p>
</section>
```

No create/edit/delete button, user submission form, comment or favorite control is rendered.

- [ ] **Step 4: Run tests to verify pass**

```powershell
Set-Location frontend
npm test -- src/views/LocalResourceCasesView.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/views/LocalResourceCasesView.vue frontend/src/views/LocalResourceCaseDetailView.vue frontend/src/views/LocalResourceCasesView.test.ts
git commit -m "前端：增加成功案例列表与详情"
```

---

### Task 15: Policy List, Detail, Subscriptions, and View Recording

**Files:**
- Create: `frontend/src/views/LocalResourcePoliciesView.vue`
- Create: `frontend/src/views/LocalResourcePolicyDetailView.vue`
- Create: `frontend/src/views/LocalResourcePoliciesView.test.ts`

**Interfaces:**
- Consumes: store `loadPolicies`, `loadSubscriptions`, `subscribePolicyCategory`, `unsubscribePolicyCategory`, `openPolicy`, `recordPolicyView`.
- Produces: seven exact category filters, subscription controls, recommendation badges, policy detail, non-blocking view notice.

- [ ] **Step 1: Write failing policy UI tests**

Create `frontend/src/views/LocalResourcePoliciesView.test.ts` covering:

The file imports `mount`, `flushPromises`, Pinia helpers, Vitest helpers,
`PolicyCategorySubscription`, the two views and `useLocalResourcesStore`.

```ts
it('renders exactly seven policy categories and subscription state', () => {
  const store = useLocalResourcesStore()
  store.subscriptions = {
    categories: [
      ['subsidy', '补贴'],
      ['ecommerce', '电商'],
      ['heritage', '非遗'],
      ['training', '培训'],
      ['certification', '认证'],
      ['general', '综合'],
      ['entrepreneurship', '创业支持']
    ].map(([code, label]) => ({
      code,
      label,
      subscribed: code === 'ecommerce',
      recommended: code === 'entrepreneurship'
    })) as PolicyCategorySubscription[],
    recommended_category_codes: ['entrepreneurship']
  }
  const wrapper = mount(LocalResourcePoliciesView, {
    global: { stubs: { AppHeader: true, LocalResourcesNav: true } }
  })
  expect(wrapper.findAll('[data-test="policy-category"]')).toHaveLength(7)
  expect(wrapper.get('[data-category="ecommerce"]').classes()).toContain('is-subscribed')
  expect(wrapper.get('[data-category="entrepreneurship"]').text()).toContain('推荐')
})

it('records a view after detail content is visible', async () => {
  const store = useLocalResourcesStore()
  store.policyDetail = policyFixture
  const open = vi.spyOn(store, 'openPolicy').mockResolvedValue(true)
  const record = vi.spyOn(store, 'recordPolicyView').mockResolvedValue(undefined)
  const wrapper = mount(LocalResourcePolicyDetailView, {
    global: { stubs: { AppHeader: true, LocalResourcesNav: true } }
  })
  await flushPromises()
  expect(open).toHaveBeenCalledWith('policy-1')
  expect(record).toHaveBeenCalledWith('policy-1')
  expect(wrapper.text()).toContain(policyFixture.content)
})

it('keeps policy content visible when view recording fails', async () => {
  const store = useLocalResourcesStore()
  store.policyDetail = policyFixture
  store.viewNotice = '浏览量暂未记录'
  const wrapper = mount(LocalResourcePolicyDetailView, {
    global: { stubs: { AppHeader: true, LocalResourcesNav: true } }
  })
  expect(wrapper.text()).toContain(policyFixture.content)
  expect(wrapper.text()).toContain('浏览量暂未记录')
})
```

- [ ] **Step 2: Run and verify failure**

```powershell
Set-Location frontend
npm test -- src/views/LocalResourcePoliciesView.test.ts
```

Expected: FAIL because both views do not exist.

- [ ] **Step 3: Implement policy list/detail without local counters**

List view:

```vue
<button
  v-for="category in store.subscriptions.categories"
  :key="category.code"
  type="button"
  data-test="policy-category"
  :data-category="category.code"
  :class="{ 'is-subscribed': category.subscribed }"
  @click="selectCategory(category.code)"
>
  {{ category.label }}
  <span v-if="category.recommended">推荐</span>
  <span>{{ category.subscribed ? '已订阅' : '未订阅' }}</span>
</button>
```

Each category has a separate subscribe/unsubscribe button using the store action. Selecting a category calls `loadPolicies(code)`.

Detail view calls `openPolicy`; only after it returns true calls `recordPolicyView`. It must render title, category label, publication time and body. It never renders a count from local state.

The template renders `viewNotice` in a non-blocking status region and never wraps detail visibility with `v-if="!viewNotice"`.

- [ ] **Step 4: Run tests to verify pass**

```powershell
Set-Location frontend
npm test -- src/views/LocalResourcePoliciesView.test.ts src/stores/localResources.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/views/LocalResourcePoliciesView.vue frontend/src/views/LocalResourcePolicyDetailView.vue frontend/src/views/LocalResourcePoliciesView.test.ts
git commit -m "前端：完成政策浏览订阅与浏览上报"
```

---

### Task 16: News List and Detail Views

**Files:**
- Create: `frontend/src/views/LocalResourceNewsView.vue`
- Create: `frontend/src/views/LocalResourceNewsDetailView.vue`
- Create: `frontend/src/views/LocalResourceNewsView.test.ts`

**Interfaces:**
- Consumes: `loadNews`, `openNews`, `recordNewsView`.
- Produces: three exact categories, list/detail, deleted item disappearance, no subscribe or unpublish controls.

- [ ] **Step 1: Write failing news UI tests**

Create `frontend/src/views/LocalResourceNewsView.test.ts`:

```ts
it('renders exactly three news categories and no policy subscription controls', () => {
  const wrapper = mount(LocalResourceNewsView, {
    global: { stubs: { AppHeader: true, LocalResourcesNav: true } }
  })
  expect(wrapper.findAll('[data-test="news-category"]')).toHaveLength(3)
  expect(wrapper.text()).not.toContain('订阅')
  expect(wrapper.text()).not.toContain('下架')
  expect(wrapper.text()).not.toContain('重新上架')
})

it('renders deleted target as not found and keeps view failure non-blocking', async () => {
  const store = useLocalResourcesStore()
  store.newsDetail = newsFixture
  store.viewNotice = '浏览量暂未记录'
  const wrapper = mount(LocalResourceNewsDetailView, {
    global: { stubs: { AppHeader: true, LocalResourcesNav: true } }
  })
  expect(wrapper.text()).toContain(newsFixture.content)
  expect(wrapper.text()).toContain('浏览量暂未记录')
  store.newsDetail = null
  store.error = '新闻不存在'
  await wrapper.vm.$nextTick()
  expect(wrapper.text()).toContain('新闻不存在')
})
```

- [ ] **Step 2: Run and verify failure**

```powershell
Set-Location frontend
npm test -- src/views/LocalResourceNewsView.test.ts
```

Expected: FAIL because both views do not exist.

- [ ] **Step 3: Implement exact three-category news UI**

List categories:

```ts
const categories = [
  { code: 'news', label: '新闻' },
  { code: 'disaster_warning', label: '灾害预警' },
  { code: 'policy_update', label: '政策更新' }
] as const
```

Render the filters with one test hook per category:

```vue
<button
  v-for="category in categories"
  :key="category.code"
  type="button"
  data-test="news-category"
  :class="{ 'is-active': selectedCategory === category.code }"
  @click="selectCategory(category.code)"
>
  {{ category.label }}
</button>
```

Each list item links to detail. Detail calls `openNews`; only after content is present calls `recordNewsView`. Render title, category, publication time and content. Render no unsubscribe, policy push, delete, unpublish, relist or restore action.

- [ ] **Step 4: Run tests to verify pass**

```powershell
Set-Location frontend
npm test -- src/views/LocalResourceNewsView.test.ts src/stores/localResources.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/views/LocalResourceNewsView.vue frontend/src/views/LocalResourceNewsDetailView.vue frontend/src/views/LocalResourceNewsView.test.ts
git commit -m "前端：完成新闻分类浏览"
```

---

### Task 17: Responsive and Accessibility Acceptance

**Files:**
- Create: `frontend/src/views/LocalResourcesResponsive.test.ts`
- Modify as needed: 006 view files from Tasks 12-16

**Interfaces:**
- Consumes: all 006 views.
- Produces: automated evidence for 320/375/1280 widths, keyboard labels, no horizontal overflow, 44px controls, exact copy.

- [ ] **Step 1: Write failing responsive/accessibility checks**

Create `frontend/src/views/LocalResourcesResponsive.test.ts` with a mounted view matrix:

```ts
const widths = [320, 375, 1280]
const views = [
  ['home', LocalResourcesHomeView],
  ['dialect', DialectAssistantView],
  ['cases', LocalResourceCasesView],
  ['case-detail', LocalResourceCaseDetailView],
  ['policies', LocalResourcePoliciesView],
  ['policy-detail', LocalResourcePolicyDetailView],
  ['news', LocalResourceNewsView],
  ['news-detail', LocalResourceNewsDetailView]
] as const

for (const width of widths) {
  it(`keeps ${width}px free of horizontal overflow`, async () => {
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: width
    })
    for (const [name, component] of views) {
      const wrapper = mount(component, {
        attachTo: document.body,
        global: {
          stubs: {
            AppHeader: true,
            LocalResourcesNav: true,
            VoiceInputButton: true
          }
        }
      })
      await wrapper.vm.$nextTick()
      expect(document.documentElement.scrollWidth, name).toBeLessThanOrEqual(
        width
      )
      wrapper.unmount()
    }
  })
}
```

Inspect every button/select/textarea/audio-control:

```ts
const controls = wrapper.findAll('button, select, textarea, audio[controls]')
for (const control of controls) {
  expect(control.attributes('aria-label') ?? control.text()).not.toBe('')
}
```

Assert the dialect voice label "语音提问" is visible and the policy detail has no local view count text such as "浏览量：" or "点击量：".

- [ ] **Step 2: Run and verify failure**

```powershell
Set-Location frontend
npm test -- src/views/LocalResourcesResponsive.test.ts
```

Expected: FAIL if any view overflows or a control lacks a name.

- [ ] **Step 3: Fix only concrete geometry/accessibility failures**

Use stable dimensions and Ark tokens. Required patterns:

```css
.local-resource-page {
  min-width: 0;
  overflow-x: clip;
}

.local-resource-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  min-width: 0;
}

.local-resource-action {
  min-width: 0;
  min-height: 44px;
  overflow-wrap: anywhere;
}

@media (max-width: 720px) {
  .local-resource-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
```

Do not use viewport-based font scaling, negative letter spacing, nested cards, gradient orbs, or decorative bokeh.

- [ ] **Step 4: Run tests to verify pass**

```powershell
Set-Location frontend
npm test -- src/views/LocalResourcesResponsive.test.ts src/router/localResourcesRoutes.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/views/LocalResourcesResponsive.test.ts frontend/src/views/LocalResourcesHomeView.vue frontend/src/views/DialectAssistantView.vue frontend/src/views/LocalResourceCasesView.vue frontend/src/views/LocalResourceCaseDetailView.vue frontend/src/views/LocalResourcePoliciesView.vue frontend/src/views/LocalResourcePolicyDetailView.vue frontend/src/views/LocalResourceNewsView.vue frontend/src/views/LocalResourceNewsDetailView.vue
git commit -m "前端：完成本土资源响应式验收"
```

---

### Task 18: Whole-Feature Acceptance and Verification

**Files:**
- Create: `backend/tests/test_local_resources_acceptance.py`
- Create: `frontend/src/views/LocalResourcesAcceptance.test.ts`
- Modify only if acceptance exposes a concrete defect: 006-owned files

**Interfaces:**
- Consumes: every delivered backend and frontend interface.
- Produces: final requirement-to-test evidence, no new feature behavior.

- [ ] **Step 1: Write the full acceptance matrix that currently fails if any requirement is missing**

Create `backend/tests/test_local_resources_acceptance.py`:

```python
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from werkzeug.security import generate_password_hash

from app import create_app
from app.agri_skills.ai_client import set_ai_client
from app.agri_skills.errors import AgriValidationError, AiUnavailableError
from app.db import get_db
from app.government_console.news import delete_news, publish_news
from app.government_console.policy import (
    delete_policy,
    publish_policy,
    relist_policy,
    unpublish_policy,
)
from app.government_console.providers import (
    get_policy_news_provider,
)
from app.local_resources.catalog import get_news, get_policy
from app.local_resources.dialect_assistant import complete_dialect_turn
from app.local_resources.errors import LocalResourceNotFoundError
from app.local_resources.subscriptions import (
    recommend_policy_categories,
    set_policy_subscription,
)
from app.local_resources.tts import TtsAudio, set_local_tts_client
from app.local_resources.views import (
    record_news_view,
    record_policy_view,
)


class LocalResourceAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "SECRET_KEY": "test",
                "AI_TTS_VOICE_YUE": "voice-yue",
                "AI_TTS_VOICE_HAKKA": "voice-hak",
                "AI_TTS_VOICE_TEOCHEW": "voice-nan",
            }
        )
        with self.app.app_context():
            self.student_id = self._insert_user("student01", "student")
            self.teacher_id = self._insert_user("teacher01", "teacher")
            self.government_id = self._insert_user(
                "government01",
                "government",
            )
        self.ai = Mock()
        self.ai.complete_json.return_value = {
            "dialect_text": "方言回答",
            "mandarin_text": "普通话回答",
        }
        set_ai_client(self.app, self.ai)
        self.tts = Mock()
        self.tts.synthesize.return_value = TtsAudio(b"ID3", "audio/mpeg")
        set_local_tts_client(self.app, self.tts)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _insert_user(self, username, role):
        cursor = get_db().execute(
            """
            INSERT INTO users (
                username, password_hash, name, role, is_enabled,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (
                username,
                generate_password_hash("password8"),
                username,
                role,
                "2026-09-19T00:00:00+08:00",
                "2026-09-19T00:00:00+08:00",
            ),
        )
        get_db().commit()
        if role == "student":
            get_db().execute(
                """
                INSERT INTO student_profiles (
                    user_id, contact, learning_direction, updated_at
                ) VALUES (?, '', 'comprehensive', ?)
                """,
                (
                    int(cursor.lastrowid),
                    "2026-09-19T00:00:00+08:00",
                ),
            )
            get_db().commit()
        return int(cursor.lastrowid)

    def _login(self, username):
        client = self.app.test_client()
        response = client.post(
            "/api/auth/login",
            json={"username": username, "password": "password8"},
        )
        self.assertEqual(response.status_code, 200)
        return client

    def _assign_tag(self, user_id, tag_name):
        get_db().execute(
            """
            INSERT INTO student_interest_tags (user_id, tag_id)
            SELECT ?, id FROM interest_tags WHERE name = ?
            """,
            (user_id, tag_name),
        )
        get_db().commit()

    def test_dialect_three_mappings_and_no_audio_persistence(self):
        captured = []

        class RecordingTts:
            def synthesize(self, text, language_code, voice_code, *, call_point):
                del text, voice_code, call_point
                captured.append(language_code)
                return TtsAudio(b"ID3", "audio/mpeg")

        set_local_tts_client(self.app, RecordingTts())
        with self.app.app_context():
            for dialect_code in ("yue", "hak", "nan"):
                complete_dialect_turn(
                    self.student_id,
                    dialect_code,
                    "问题",
                )
            stored_columns = {
                row["name"]
                for row in get_db().execute(
                    "PRAGMA table_info(local_resource_dialect_turns)"
                )
            }
        self.assertEqual(captured, ["yue", "hak", "nan"])
        self.assertNotIn("audio", stored_columns)

    def test_policy_subscription_audience_and_view_idempotency(self):
        with self.app.app_context():
            set_policy_subscription(
                self.student_id,
                "ecommerce",
                True,
            )
            policy = publish_policy(
                actor_id=self.government_id,
                request_id="policy-acceptance",
                title="电商培训补贴",
                content="正文",
                category_code="ecommerce",
            )
            totals = [
                record_policy_view(policy["id"], "same-event")
                for _ in range(10)
            ]
            totals.extend(
                record_policy_view(policy["id"], event_id)
                for event_id in ("new-event-1", "new-event-2", "new-event-3")
            )
            dashboard = get_government_dashboard()
            notifications = get_db().execute(
                """
                SELECT recipient_id, body
                FROM system_notifications
                WHERE event_type = 'policy_published'
                """
            ).fetchall()
        self.assertEqual(totals[:10], [1] * 10)
        self.assertEqual(totals[10:], [2, 3, 4])
        self.assertEqual(dashboard["policy"]["view_count"], 4)
        self.assertEqual(
            [(row["recipient_id"], row["body"]) for row in notifications],
            [(self.student_id, "政策类别：电商")],
        )

    def test_policy_unpublish_relist_delete_semantics(self):
        with self.app.app_context():
            policy = publish_policy(
                actor_id=self.government_id,
                request_id="policy-lifecycle",
                title="创业支持",
                content="正文",
                category_code="entrepreneurship",
            )
            self.assertEqual(record_policy_view(policy["id"], "view-1"), 1)
            hidden = unpublish_policy(
                policy["id"],
                expected_version=policy["version"],
            )
            with self.assertRaises(LocalResourceNotFoundError):
                get_policy(policy["id"])
            visible = relist_policy(
                policy["id"],
                expected_version=hidden["version"],
            )
            self.assertEqual(
                get_policy(policy["id"])["id"],
                policy["id"],
            )
            self.assertEqual(
                record_policy_view(policy["id"], "view-2"),
                2,
            )
            self.assertEqual(
                get_government_dashboard()["policy"]["view_count"],
                2,
            )
            notification_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM system_notifications
                WHERE event_type = 'policy_published'
                """
            ).fetchone()["count"]
            delete_policy(
                policy["id"],
                expected_version=visible["version"],
            )
            with self.assertRaises(LocalResourceNotFoundError):
                get_policy(policy["id"])
            dashboard = get_government_dashboard()
        self.assertEqual(notification_count, 1)
        self.assertEqual(dashboard["policy"]["total_count"], 0)
        self.assertEqual(dashboard["policy"]["view_count"], 0)

    def test_news_publish_delete_and_no_push(self):
        with self.app.app_context():
            before = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM system_notifications
                WHERE event_type = 'policy_published'
                """
            ).fetchone()["count"]
            news = publish_news(
                actor_id=self.government_id,
                request_id="news-acceptance",
                title="暴雨预警",
                content="注意防范",
                category_code="disaster_warning",
            )
            self.assertEqual(get_news(news["id"])["title"], "暴雨预警")
            self.assertEqual(record_news_view(news["id"], "view-1"), 1)
            visible_dashboard = get_government_dashboard()
            self.assertEqual(visible_dashboard["news"]["total_count"], 1)
            self.assertEqual(visible_dashboard["news"]["view_count"], 1)
            delete_news(news["id"], expected_version=news["version"])
            with self.assertRaises(LocalResourceNotFoundError):
                get_news(news["id"])
            deleted_dashboard = get_government_dashboard()
            self.assertEqual(deleted_dashboard["news"]["total_count"], 0)
            self.assertEqual(deleted_dashboard["news"]["view_count"], 0)
            after = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM system_notifications
                WHERE event_type = 'policy_published'
                """
            ).fetchone()["count"]
        self.assertEqual(after, before)

    def test_asr_route_is_reused_and_ai_path_has_no_local_fallback(self):
        root = Path(__file__).parents[1] / "app"
        local_source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (root / "local_resources").glob("*.py")
        )
        agri_source = (root / "agri_skills" / "routes.py").read_text(
            encoding="utf-8"
        )
        self.assertEqual(
            agri_source.count('@agri_skills_bp.post("/speech/transcriptions")'),
            1,
        )
        self.assertNotIn("local_kb", local_source)
        self.assertNotIn("government_policies", local_source)
        self.assertNotIn("government_news", local_source)
        self.assertNotIn("set_policy_news_provider", local_source)
        self.assertNotIn("def transcribe(", local_source)

    def test_asr_ai_tts_failures_and_case_write_boundary(self):
        student = self._login("student01")
        empty = student.post(
            "/api/agri-skills/speech/transcriptions",
            data={},
            content_type="multipart/form-data",
        )
        self.assertEqual(empty.status_code, 422)
        self.assertEqual(
            empty.get_json()["message"],
            "未能识别，请重试或改用文字输入",
        )
        self.ai.transcribe.side_effect = AgriValidationError(
            "未能识别，请重试或改用文字输入"
        )
        noise = student.post(
            "/api/agri-skills/speech/transcriptions",
            data={
                "audio": (io.BytesIO(b"noise"), "noise.webm")
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(noise.status_code, 422)
        self.assertEqual(
            noise.get_json()["message"],
            "未能识别，请重试或改用文字输入",
        )

        self.ai.complete_json.side_effect = AiUnavailableError("down")
        answer_failure = student.post(
            "/api/local-resources/dialect-assistant/turns",
            json={"dialect_code": "yue", "question": "问题"},
        )
        self.assertEqual(answer_failure.status_code, 503)
        self.assertEqual(
            answer_failure.get_json()["message"],
            "AI 服务暂时不可用",
        )

        self.ai.complete_json.side_effect = None
        self.tts.synthesize.side_effect = RuntimeError("down")
        tts_failure = student.post(
            "/api/local-resources/dialect-assistant/turns",
            json={"dialect_code": "hak", "question": "问题"},
        )
        self.assertEqual(tts_failure.status_code, 503)
        self.assertEqual(
            tts_failure.get_json()["message"],
            "AI 服务暂时不可用",
        )
        write_boundaries = (
            ("post", "/api/local-resources/cases"),
            ("put", "/api/local-resources/cases/missing"),
            ("patch", "/api/local-resources/cases/missing"),
            ("delete", "/api/local-resources/cases/missing"),
        )
        for method, path in write_boundaries:
            with self.subTest(method=method, path=path):
                self.assertEqual(
                    getattr(student, method)(path).status_code,
                    405,
                )
        self.assertEqual(
            student.get(
                "/api/local-resources/cases/missing"
            ).status_code,
            404,
        )

    def test_interest_recommendation_matrix(self):
        with self.app.app_context():
            crop = self._insert_user("crop01", "student")
            ecommerce = self._insert_user("ecommerce01", "student")
            handcraft = self._insert_user("handcraft01", "student")
            job = self._insert_user("job01", "student")
            none = self._insert_user("none01", "student")
            self._assign_tag(crop, "荔枝")
            self._assign_tag(ecommerce, "电商直播")
            self._assign_tag(handcraft, "手工艺")
            self._assign_tag(job, "农业技术员")
            actual = {
                "crop": recommend_policy_categories(crop),
                "ecommerce": recommend_policy_categories(ecommerce),
                "handcraft": recommend_policy_categories(handcraft),
                "job": recommend_policy_categories(job),
                "none": recommend_policy_categories(none),
            }
            subscription_count = get_db().execute(
                """
                SELECT COUNT(*) AS count
                FROM local_resource_policy_subscriptions
                WHERE user_id IN (?, ?, ?, ?, ?)
                """,
                (crop, ecommerce, handcraft, job, none),
            ).fetchone()["count"]
        self.assertEqual(
            actual,
            {
                "crop": ["subsidy", "training", "general"],
                "ecommerce": ["ecommerce", "entrepreneurship"],
                "handcraft": ["heritage"],
                "job": ["certification", "entrepreneurship"],
                "none": [],
            },
        )
        self.assertEqual(subscription_count, 0)

    def test_all_student_routes_and_cross_student_subscription_isolation(self):
        with self.app.app_context():
            second_student_id = self._insert_user(
                "student02",
                "student",
            )
        student = self._login("student01")
        second = self._login("student02")
        teacher = self._login("teacher01")
        anonymous = self.app.test_client()
        with self.app.app_context():
            set_policy_subscription(
                self.student_id,
                "ecommerce",
                True,
            )
            set_policy_subscription(
                second_student_id,
                "ecommerce",
                False,
            )
        paths = [
            "/api/local-resources/cases",
            "/api/local-resources/cases/missing",
            "/api/local-resources/policies",
            "/api/local-resources/policies/policy-1",
            "/api/local-resources/policy-subscriptions",
            "/api/local-resources/news",
            "/api/local-resources/news/news-1",
        ]
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(anonymous.get(path).status_code, 401)
                self.assertEqual(teacher.get(path).status_code, 403)
        protected_posts = (
            "/api/local-resources/policy-subscriptions/ecommerce",
            "/api/local-resources/policies/policy-1/views",
            "/api/local-resources/news/news-1/views",
            "/api/local-resources/dialect-assistant/turns",
        )
        for path in protected_posts:
            with self.subTest(method="POST", path=path):
                self.assertEqual(
                    anonymous.post(path, json={}).status_code,
                    401,
                )
                self.assertEqual(
                    teacher.post(path, json={}).status_code,
                    403,
                )
        anonymous_slots = self.app.test_client()
        teacher_slots = self._login("teacher01")
        self.assertEqual(
            anonymous_slots.delete(
                "/api/local-resources/policy-subscriptions/ecommerce"
            ).status_code,
            401,
        )
        self.assertEqual(
            teacher_slots.delete(
                "/api/local-resources/policy-subscriptions/ecommerce"
            ).status_code,
            403,
        )
        first_state = student.get(
            "/api/local-resources/policy-subscriptions"
        ).get_json()["subscriptions"]
        second_state = second.get(
            "/api/local-resources/policy-subscriptions"
        ).get_json()["subscriptions"]
        self.assertTrue(
            next(
                item for item in first_state["categories"]
                if item["code"] == "ecommerce"
            )["subscribed"]
        )
        self.assertFalse(
            next(
                item for item in second_state["categories"]
                if item["code"] == "ecommerce"
            )["subscribed"]
        )

    def test_non_student_and_direct_table_boundary(self):
        teacher = self._login("teacher01")
        anonymous = self.app.test_client()
        self.assertEqual(
            anonymous.get("/api/local-resources/cases").status_code,
            401,
        )
        self.assertEqual(
            teacher.get("/api/local-resources/cases").status_code,
            403,
        )
        provider = get_policy_news_provider()
        self.assertTrue(
            hasattr(provider, "list_published_policies")
        )


if __name__ == "__main__":
    unittest.main()
```

Create `frontend/src/views/LocalResourcesAcceptance.test.ts`:

```ts
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it } from 'vitest'
import { defineComponent } from 'vue'

import router from '@/router'
import { useDialectAssistantStore } from '@/stores/dialectAssistant'
import { useLocalResourcesStore } from '@/stores/localResources'

import DialectAssistantView from './DialectAssistantView.vue'
import LocalResourceNewsView from './LocalResourceNewsView.vue'
import LocalResourcePoliciesView from './LocalResourcePoliciesView.vue'

describe('local resources acceptance', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('registers all exact routes', () => {
    const expected = [
      'local-resources-home',
      'local-resources-dialect',
      'local-resources-cases',
      'local-resources-case-detail',
      'local-resources-policies',
      'local-resources-policy-detail',
      'local-resources-news',
      'local-resources-news-detail'
    ]
    expect(
      router.getRoutes()
        .map(route => route.name)
        .filter(name => typeof name === 'string' && name.startsWith('local-resources-'))
    ).toEqual(expect.arrayContaining(expected))
  })

  it('renders seven policies and exactly three news categories', () => {
    const resourceStore = useLocalResourcesStore()
    resourceStore.subscriptions = {
      categories: [
        'subsidy',
        'ecommerce',
        'heritage',
        'training',
        'certification',
        'general',
        'entrepreneurship'
      ].map(code => ({
        code,
        label: code,
        subscribed: false,
        recommended: false
      })) as never,
      recommended_category_codes: []
    }
    const policies = mount(LocalResourcePoliciesView, {
      global: { stubs: { AppHeader: true, LocalResourcesNav: true } }
    })
    const news = mount(LocalResourceNewsView, {
      global: { stubs: { AppHeader: true, LocalResourcesNav: true } }
    })
    expect(policies.findAll('[data-test="policy-category"]')).toHaveLength(7)
    expect(news.findAll('[data-test="news-category"]')).toHaveLength(3)
    expect(news.text()).not.toContain('下架')
    expect(news.text()).not.toContain('重新上架')
  })

  it('renders the enlarged voice entry and exact failure copy', async () => {
    const store = useDialectAssistantStore()
    store.error = '未能识别，请重说或改用文字'
    const wrapper = mount(DialectAssistantView, {
      global: {
        stubs: {
          AppHeader: true,
          LocalResourcesNav: true,
          VoiceInputButton: true
        }
      }
    })
    expect(wrapper.text()).toContain('语音提问')
    expect(wrapper.text()).toContain('未能识别，请重说或改用文字')
    expect(wrapper.get('textarea').attributes('disabled')).toBeUndefined()
    store.error = 'AI 服务暂时不可用'
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('AI 服务暂时不可用')
  })

  it('maps browser permission denial to the exact recognition copy', async () => {
    const VoiceStub = defineComponent({
      emits: ['permission-denied'],
      template: `
        <button
          data-test="permission-denied"
          @click="$emit('permission-denied')"
        >
          语音
        </button>
      `
    })
    const store = useDialectAssistantStore()
    const wrapper = mount(DialectAssistantView, {
      global: {
        stubs: {
          AppHeader: true,
          LocalResourcesNav: true,
          VoiceInputButton: VoiceStub
        }
      }
    })
    await wrapper.get('[data-test="permission-denied"]').trigger('click')
    expect(store.error).toBe('未能识别，请重说或改用文字')
  })
})
```

- [ ] **Step 2: Run acceptance tests and expect concrete gaps**

```powershell
uv run --directory backend python -m unittest tests.test_local_resources_acceptance -v
Set-Location frontend
npm test -- src/views/LocalResourcesAcceptance.test.ts
```

Expected: PASS only if Tasks 1-17 are complete. Any failure must name the missing requirement or incorrect interface.

- [ ] **Step 3: Fix only 006-owned defects**

Allowed changes:

- 006 service/UI code and 006 tests;
- exact existing shared-assembly lines listed in “Shared File Changes”;
- no changes to 10 data ownership, 02 notification semantics, 003 ASR input, legacy code, or provider location.

Every fix adds or updates an assertion for the observed defect.

- [ ] **Step 4: Run complete verification**

```powershell
uv run --directory backend python -m unittest discover -s tests
Set-Location frontend
npm test
npx tsc -b --noEmit
npm run build
```

Expected:

- backend: all tests pass;
- frontend: all tests pass;
- TypeScript: no output;
- production build: succeeds.

Run browser geometry only if a concrete responsive defect is suspected; the existing project browser rules apply, including `--no-sandbox` on Windows and image inspection delegated to the required image-understanding subagent.

- [ ] **Step 5: Commit**

```powershell
$paths = @(
  'backend/app/local_resources',
  'backend/app/__init__.py',
  'backend/app/config.py',
  'backend/app/db.py',
  'backend/.env.example',
  'backend/tests/test_local_resources_*.py',
  'frontend/src/api/types.ts',
  'frontend/src/api/types.test.ts',
  'frontend/src/router/index.ts',
  'frontend/src/router/localResourcesRoutes.test.ts',
  'frontend/src/views/StudentPortalView.vue',
  'frontend/src/views/StudentPortalView.test.ts',
  'frontend/src/components/LocalResourcesNav.vue',
  'frontend/src/stores/localResources.ts',
  'frontend/src/stores/localResources.test.ts',
  'frontend/src/stores/dialectAssistant.ts',
  'frontend/src/stores/dialectAssistant.test.ts',
  'frontend/src/views/LocalResourcesHomeView.vue',
  'frontend/src/views/DialectAssistantView.vue',
  'frontend/src/views/DialectAssistantView.test.ts',
  'frontend/src/views/LocalResourceCasesView.vue',
  'frontend/src/views/LocalResourceCaseDetailView.vue',
  'frontend/src/views/LocalResourceCasesView.test.ts',
  'frontend/src/views/LocalResourcePoliciesView.vue',
  'frontend/src/views/LocalResourcePolicyDetailView.vue',
  'frontend/src/views/LocalResourcePoliciesView.test.ts',
  'frontend/src/views/LocalResourceNewsView.vue',
  'frontend/src/views/LocalResourceNewsDetailView.vue',
  'frontend/src/views/LocalResourceNewsView.test.ts',
  'frontend/src/views/LocalResourcesResponsive.test.ts',
  'frontend/src/views/LocalResourcesAcceptance.test.ts'
)
git add -- $paths
git commit -m "测试：完成本土资源端到端验收"
```

---

## Spec Coverage Self-Review

| Spec area | Plan coverage | Verification |
| --- | --- | --- |
| US1 dialect assistant | Tasks 6, 7, 11, 13, 17, 18 | TTS mapping tests, exact failure copy, base64 playback, role/ASR route tests |
| US2 policy browse/subscription/view | Tasks 3, 4, 5, 8, 9, 10, 15, 18 | Real provider acceptance, 02 audience, idempotent views, seven categories |
| US3 news browse/view | Tasks 3, 5, 8, 10, 16, 18 | Three categories, delete visibility, no subscription/up/down controls |
| US4 success cases | Tasks 2, 8, 10, 14 | Seed/provider replacement, list/detail, empty/unavailable state |
| US5 interest tags | Tasks 4, 8, 10, 15 | Exact mapping, no auto-subscription, no second tag table |
| FR-001..007 identity/boundary | Tasks 1, 4, 8, 9, 18 | Student-only API, 01/02/03/10 reuse, static boundary scan |
| FR-008..029 dialect/ASR/TTS/AI | Tasks 6, 7, 11, 13, 17, 18 | Three request mappings, no streaming, no audio storage, no fallback |
| FR-030..045 policy/news states | Tasks 3, 4, 8, 9, 15, 16, 18 | Separate state-machine acceptance; no news re-list |
| FR-046..053 view counting | Tasks 5, 8, 9, 10, 15, 16, 18 | Provider delegation, event retry, delete/unpublish behavior |
| FR-054..061 cases/tags | Tasks 2, 4, 8, 10, 14, 15 | Provider ownership, exact mapping and no auto-subscribe |
| FR-062..068 provider contracts | Tasks 3, 5, 8, 9, 18 | Single 10 slot, no placeholder, no direct table access, location issue preserved |
| SC-001..010 | Tasks 9, 17, 18 | Backend/frontend acceptance and full regression commands |

## Placeholder Scan

Run a scan whose forbidden patterns are assembled from fragments so the scan itself does not create a false positive:

```powershell
$patterns = @(
  ('TO' + 'DO'),
  ('T' + 'BD'),
  ('TK' + 'TK'),
  ('implement' + ' later'),
  ('fill in' + ' details'),
  ('handle edge' + ' cases'),
  ('similar to' + ' Task')
)
$matches = Select-String -Path '.agents/memories/plans/2026-09-19-006-local-resources.md' -Pattern $patterns
if ($matches) { $matches } else { 'NO_PLACEHOLDERS' }
```

Expected: `NO_PLACEHOLDERS`.

## Type and Interface Consistency Check

Required names remain identical across tasks:

| Concept | Exact name |
| --- | --- |
| Policy/news provider accessor | `get_policy_news_provider()` |
| Case provider | `get_local_resource_case_provider()` |
| TTS client | `get_local_tts_client()` |
| Dialect answer | `generate_dialect_answer()` |
| Dialect full turn | `complete_dialect_turn()` |
| Policy list | `list_policies()` |
| News list | `list_news()` |
| View writes | `record_policy_view()`, `record_news_view()` |
| Subscription bridge | `LocalResourcesMessagingProvider.list_policy_subscriber_ids()` |
| Frontend policy/news store | `useLocalResourcesStore()` |
| Frontend dialect store | `useDialectAssistantStore()` |

## Execution Handoff

After implementation tasks are approved, use `superpowers:subagent-driven-development` with fresh implementer and reviewer agents. Do not start SDD as part of this definition task.
