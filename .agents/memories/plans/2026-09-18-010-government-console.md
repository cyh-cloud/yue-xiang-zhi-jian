# 10-政务工作台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付 010-政务工作台，包括政策三态生命周期与 02 订阅推送、新闻两态发布与删除、幂等浏览计数、严格排除用户/培训数据的只读看板，以及供 06 消费的政策/新闻 producer。

**Architecture:** 后端新增 `backend/app/government_console/` 领域包，使用同一 SQLite schema 保存政策、新闻、发布请求幂等键和浏览事件。政策发布在单个业务事务内调用既有 02 `emit_policy_published`；就业指标只通过可替换的 09 `EmploymentStatisticsProvider` 读取。前端新增政务 Pinia store、政策/新闻管理页和只读看板，复用 01 会话、门户、路由守卫和 Ark 风格。

**Tech Stack:** Python 3.12、Flask、sqlite3、uv、unittest、Vue 3、Vite、Pinia、Vue Router、Vitest、Vue Test Utils、lucide-vue-next。

**Spec:** `specs/010-government-console/spec.md`

**Branch:** `v2/lixKRT/010-government-console`

**Worktree:** `.worktrees/010-government-console`

## Global Constraints

- 只允许 `government` 角色访问 `/api/government/*` 和政务前端路由；身份、角色和禁用账户判断只复用 01 的 `load_session()`。
- 政策与新闻均不经过审核；010 MUST NOT import、consume 或模拟 11 的 `ContentReviewProvider`。
- 010 没有任何 AI 调用；不得新增 AI client、AI allowlist、AI 降级或 AI 相关前端提示。
- 政策只有 `active`、`unpublished`、`deleted` 三态；新闻只有 `published`、`deleted` 两态。删除均为硬删除，不提供恢复。
- 政策首次发布立即调用 02 的 `emit_policy_published()`；重新上架不重复推送，同类多条不合并。
- 订阅关系和已推通知不由 010 删除；删除政策时调用 02 的 `mark_notification_sources_unavailable()` 标记来源不可用。
- 06 只通过 `PolicyNewsProvider` 读取已上架政策/未删除新闻并记录浏览，不读取 010 数据表。
- 09 尚未合并时，010 使用完整 `EmploymentStatisticsProvider` 占位实现返回 `None`；不得查询不存在的岗位/申请表，不得伪造零值。
- 看板响应只允许 employment、policy、news 三组字段；用户类、培训类字段必须从 schema 中不存在。
- 跨模块稳定 ID 为非空字符串；新 provider 时间统一为 `+08:00` ISO 8601；新增 provider 错误使用冻结的 `ProviderError` 层级。
- 路由 kebab-case，Python snake_case，前端变量/函数 camelCase；旧系统根目录代码禁止参考、导入或迁移。
- 每个任务先写失败测试，再最小实现，再运行定向测试，最后提交一个聚焦中文 commit。

## Confirmed Decisions

- 政策发布与 02 推送强一致；推送事件失败时发布回滚，同一发布请求可安全重试。
- 政策重新上架只恢复可见，不重复推送订阅学员。
- 本期不提供已发布政策或新闻的编辑流程；只做发布、生命周期操作和删除。
- 同一学员重复打开同一内容按不同浏览事件重复计数；同一浏览事件重试不重复计数。

## No Placeholders Rule

- 每个任务必须列出精确 Files、Interfaces、失败测试、实现契约、验证命令和 commit。
- 不允许 `TODO`、`TBD`、空实现或“实现时再决定”。
- 09 和 06 未合并部分只能通过本计划命名的 provider 替换点交付，不允许页面或服务直接查对方表。
- 共享文件改动必须保持最小；不得复制 01 会话、02 通知或共享 UI 机制。
- 每个 task 的 implementer 只读取本 task，因此 Interfaces 必须完整声明上下游函数名、参数和返回形状。

## Policy State Machine and Visibility Matrix

| State | Stored value | Student/provider visible | Allowed actions | Push behavior | Delete behavior |
| --- | --- | --- | --- | --- | --- |
| 在架 | `active` | Yes | unpublish、delete | first publish sends once | hard delete content and views |
| 下架 | `unpublished` | No | relist、delete | no push | hard delete content and views |
| 删除 | row absent | No | none | none | subscriptions/history retained; source marked unavailable |

## News State Machine and Visibility Matrix

| State | Stored value | Student/provider visible | Allowed actions | Unpublish/re-list |
| --- | --- | --- | --- | --- |
| 已发布 | `published` | Yes | delete | Not supported |
| 已删除 | row absent | No | none | Not supported |

## Employment Data Placeholder and 09 Replacement Point

| Metric | Consumer contract | Current placeholder | 09 replacement |
| --- | --- | --- | --- |
| 在招岗位数 | `EmploymentStatisticsProvider.get_active_job_count() -> int \| None` | returns `None`; card shows `就业数据暂不可用` | `set_employment_statistics_provider(app, provider)` |
| 累计投递量 | `EmploymentStatisticsProvider.get_cumulative_application_count() -> int \| None` | returns `None`; card shows `就业数据暂不可用` | same registration slot |

- 010 does not create a `jobs` or `applications` table and does not query any 09 table.
- 09 provider must return all-platform published-job and successful-application totals.
- `累计投递量` is not deduplicated by student; each successful application record counts once.
- `configure_government_providers()` only delegates to the two required `set_*` functions.

## Policy/News Producer Interface for 06

```python
class PolicyNewsProvider(Protocol):
    def list_published_policies(self, category: str | None = None) -> list[dict]: ...
    def get_published_policy(self, policy_id: str) -> dict | None: ...
    def list_published_news(self, category: str | None = None) -> list[dict]: ...
    def get_published_news(self, news_id: str) -> dict | None: ...
    def record_policy_view(self, policy_id: str, view_event_id: str) -> int: ...
    def record_news_view(self, news_id: str, view_event_id: str) -> int: ...
```

- Registration: `set_policy_news_provider(app, provider)` and `get_policy_news_provider()`.
- 06 owns the final consumer signature; if it changes the signature, it must update its own spec before implementation. 010 owns the producer behavior and registration slot.
- `list_*` returns complete lists ordered by `published_at DESC, id ASC`; no page/page-size fields.
- `get_*` returns `None` for missing, unpublished, or deleted content.
- `record_*` returns the new cumulative count and deduplicates only `(content_type, view_event_id)` retries.
- Policy/news dict fields: `id`, `title`, `content`, `category_code`, `category_label`, `published_at`, `updated_at`, `version`.

## Dashboard Positive and Negative Metric List

| Group | Metric key | Displayed | Source/rule | Negative test |
| --- | --- | --- | --- | --- |
| employment | `active_job_count` | Yes | 09 provider | provider absent => `None` + unavailable |
| employment | `cumulative_application_count` | Yes | 09 provider | provider absent => `None` + unavailable |
| policy | `active_count` | Yes | `status='active'` | deleted excluded |
| policy | `unpublished_count` | Yes | `status='unpublished'` | deleted excluded |
| policy | `total_count` | Yes | active + unpublished | equals split sum |
| policy | `view_count` | Yes | retained policy view counter sum | deleted views excluded |
| news | `total_count` | Yes | undeleted news count | deleted excluded |
| news | `view_count` | Yes | retained news view counter sum | deleted views excluded |
| user | `total_users` | No | absent from schema | recursive forbidden-key assertion |
| user | `role_distribution` | No | absent from schema | recursive forbidden-key assertion |
| user | `region_distribution` | No | absent from schema | recursive forbidden-key assertion |
| user | `direction_distribution` | No | absent from schema | recursive forbidden-key assertion |
| training | `course_count` | No | absent from schema | recursive forbidden-key assertion |
| training | `learning_behavior_count` | No | absent from schema | recursive forbidden-key assertion |
| training | `progress` | No | absent from schema | recursive forbidden-key assertion |
| training | `completion_rate` | No | absent from schema | recursive forbidden-key assertion |

## Reuse Points with 001/02/09/11

| Module | Reused contract | 010 usage | Must not create |
| --- | --- | --- | --- |
| 01 | `load_session()`, government portal role and default path | active government authorization and portal routing | second auth/session/role system |
| 02 | `emit_policy_published()`, `mark_notification_sources_unavailable()`, `system_notifications` | policy publication push and source availability | notification table, unread state, message center |
| 09 | future `EmploymentStatisticsProvider` registration slot | dashboard employment metrics | job/application table or direct SQL |
| 11 | super-admin-only user/training statistics | no 010 dependency; exclusion tests preserve boundary | hidden government route to full-platform stats |
| 11 review | `ContentReviewProvider` | explicitly not consumed | policy/news approval state or review adapter |

## File Structure

| Path | Responsibility |
| --- | --- |
| `backend/app/government_console/__init__.py` | Default service installation and public exports |
| `backend/app/government_console/errors.py` | Frozen provider/domain error hierarchy and route mapping helpers |
| `backend/app/government_console/constants.py` | Exact policy/news category codes and labels |
| `backend/app/government_console/providers.py` | `PolicyNewsProvider`, `EmploymentStatisticsProvider`, placeholders and registration slots |
| `backend/app/government_console/policy.py` | Policy validation, lifecycle service and 02 publication event |
| `backend/app/government_console/news.py` | News validation, publish/delete service |
| `backend/app/government_console/views.py` | Idempotent policy/news view recording and counter reads |
| `backend/app/government_console/dashboard.py` | Read-only dashboard aggregation and 09 provider consumption |
| `backend/app/government_console/routes.py` | `/api/government/*` routes, role checks and JSON error mapping |
| `backend/tests/test_government_*.py` | Foundation, lifecycle, provider, dashboard, API and integration tests |
| `frontend/src/stores/governmentConsole.ts` | Government policy/news/dashboard API state |
| `frontend/src/stores/governmentConsole.test.ts` | Store behavior and response-boundary tests |
| `frontend/src/components/GovernmentConsoleNav.vue` | 010 workspace navigation |
| `frontend/src/views/GovernmentPolicyView.vue` | Policy list, publish and lifecycle controls |
| `frontend/src/views/GovernmentNewsView.vue` | News list, publish and delete controls |
| `frontend/src/views/GovernmentDashboardView.vue` | Read-only dashboard |
| `frontend/src/views/GovernmentPortalView.vue` | Government workspace shell and core entries |
| `frontend/src/views/Government*View.test.ts` | Frontend behavior, exclusion and responsive tests |
| `frontend/src/router/governmentRoutes.test.ts` | Government route metadata and role guards |

## Shared File Changes

| Shared file | Change | Why it cannot be bypassed |
| --- | --- | --- |
| `backend/app/db.py` | Add 010 tables and indexes to `SCHEMA_SQL` | This is the only schema initialization entry |
| `backend/app/__init__.py` | Install 010 providers, register blueprint and protect `/api/government` | This is the only app assembly point |
| `frontend/src/api/types.ts` | Add government DTOs and exact dashboard schema | API types are centralized |
| `frontend/src/router/index.ts` | Add government policy/news/dashboard routes | Router is the only page reachability point |
| `frontend/src/data/portal-guides.ts` | Add hrefs and guides for 010 entries | 01 onboarding reads this catalog |
| `frontend/src/views/GovernmentPortalView.vue` | Replace placeholder-only shell with real workspace entry | Existing government portal is the default route |

---

### Task 1: Backend Foundation, Schema, Providers, and Registration

**Files:**
- Create: `backend/app/government_console/__init__.py`
- Create: `backend/app/government_console/constants.py`
- Create: `backend/app/government_console/errors.py`
- Create: `backend/app/government_console/providers.py`
- Create: `backend/tests/test_government_foundation.py`
- Modify: `backend/app/db.py`
- Modify: `backend/app/__init__.py`

**Interfaces:**
- Consumes: `get_db()`, `init_db()`, Flask `app.extensions`, frozen `ProviderError` target semantics.
- Produces: `install_default_government_services(app)`.
- Produces: `set_policy_news_provider(app, provider)`, `get_policy_news_provider()`, `set_employment_statistics_provider(app, provider)`, `get_employment_statistics_provider()`.
- Produces: `configure_government_providers(app, *, policy_news=None, employment_statistics=None)`.
- Produces Protocols: `PolicyNewsProvider` and `EmploymentStatisticsProvider` exactly as declared in the spec.
- Produces tables: `government_policies`, `government_news`, `government_publication_requests`, `government_view_events`.

- [ ] **Step 1: Write failing schema and provider tests**

```python
# backend/tests/test_government_foundation.py
from unittest import TestCase

from app import create_app
from app.db import get_db
from app.government_console.providers import (
    get_employment_statistics_provider,
    get_policy_news_provider,
)


class GovernmentFoundationTests(TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "DATABASE_PATH": ":memory:"})

    def test_government_tables_exist(self):
        with self.app.app_context():
            names = {
                row["name"]
                for row in get_db().execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        self.assertTrue(
            {
                "government_policies",
                "government_news",
                "government_publication_requests",
                "government_view_events",
            }.issubset(names)
        )

    def test_default_employment_provider_returns_unavailable(self):
        with self.app.app_context():
            provider = get_employment_statistics_provider()
            self.assertIsNone(provider.get_active_job_count())
            self.assertIsNone(provider.get_cumulative_application_count())

    def test_default_policy_news_provider_is_complete(self):
        with self.app.app_context():
            provider = get_policy_news_provider()
            self.assertEqual(provider.list_published_policies(), [])
            self.assertEqual(provider.list_published_news(), [])
            self.assertIsNone(provider.get_published_policy("missing"))
            self.assertIsNone(provider.get_published_news("missing"))
```

- [ ] **Step 2: Run the failing test**

Run: `uv run --directory backend python -m unittest tests.test_government_foundation -v`

Expected: FAIL because `app.government_console` does not exist.

- [ ] **Step 3: Add exact constants, errors, providers, and schema**

```python
# backend/app/government_console/constants.py
POLICY_CATEGORIES = {
    "subsidy": "补贴",
    "ecommerce": "电商",
    "heritage": "非遗",
    "training": "培训",
    "certification": "认证",
    "general": "综合",
    "entrepreneurship": "创业支持",
}

NEWS_CATEGORIES = {
    "news": "新闻",
    "disaster_warning": "灾害预警",
    "policy_update": "政策更新",
}
```

```python
# backend/app/government_console/errors.py
class ProviderError(RuntimeError):
    code = "provider_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ProviderValidationError(ProviderError):
    code = "validation_error"


class ProviderNotFoundError(ProviderError):
    code = "not_found"


class ProviderConflictError(ProviderError):
    code = "conflict"


class ProviderUnavailableError(ProviderError):
    code = "unavailable"


class ProviderAccessDeniedError(ProviderError):
    code = "access_denied"
```

```python
# backend/app/government_console/providers.py
class NullPolicyNewsProvider:
    def list_published_policies(self, category: str | None = None) -> list[dict]:
        return []

    def get_published_policy(self, policy_id: str) -> dict | None:
        return None

    def list_published_news(self, category: str | None = None) -> list[dict]:
        return []

    def get_published_news(self, news_id: str) -> dict | None:
        return None

    def record_policy_view(self, policy_id: str, view_event_id: str) -> int:
        raise ProviderUnavailableError("政策浏览计数暂不可用")

    def record_news_view(self, news_id: str, view_event_id: str) -> int:
        raise ProviderUnavailableError("新闻浏览计数暂不可用")


class UnavailableEmploymentStatisticsProvider:
    def get_active_job_count(self) -> int | None:
        return None

    def get_cumulative_application_count(self) -> int | None:
        return None
```

```sql
CREATE TABLE IF NOT EXISTS government_policies (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    category_code TEXT NOT NULL CHECK (
        category_code IN (
            'subsidy', 'ecommerce', 'heritage', 'training',
            'certification', 'general', 'entrepreneurship'
        )
    ),
    status TEXT NOT NULL CHECK (status IN ('active', 'unpublished')),
    view_count INTEGER NOT NULL DEFAULT 0 CHECK (view_count >= 0),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_by INTEGER NOT NULL REFERENCES users(id),
    published_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS government_news (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    category_code TEXT NOT NULL CHECK (
        category_code IN ('news', 'disaster_warning', 'policy_update')
    ),
    view_count INTEGER NOT NULL DEFAULT 0 CHECK (view_count >= 0),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    created_by INTEGER NOT NULL REFERENCES users(id),
    published_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS government_publication_requests (
    content_type TEXT NOT NULL CHECK (content_type IN ('policy', 'news')),
    request_id TEXT NOT NULL,
    content_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (content_type, request_id)
);

CREATE TABLE IF NOT EXISTS government_view_events (
    content_type TEXT NOT NULL CHECK (content_type IN ('policy', 'news')),
    content_id TEXT NOT NULL,
    view_event_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (content_type, view_event_id)
);
```

- [ ] **Step 4: Install defaults and register the protected prefix**

```python
# backend/app/government_console/__init__.py
def install_default_government_services(app: Flask) -> None:
    if "government_policy_news_provider" not in app.extensions:
        set_policy_news_provider(app, NullPolicyNewsProvider())
    if "government_employment_statistics_provider" not in app.extensions:
        set_employment_statistics_provider(
            app, UnavailableEmploymentStatisticsProvider()
        )
```

In `backend/app/__init__.py`, call `install_default_government_services(app)` after existing service installation and add `/api/government` to `PROTECTED_API_PREFIXES`.

Task 7 replaces the default `NullPolicyNewsProvider()` with `DatabasePolicyNewsProvider()` once the complete read/view contract exists.

- [ ] **Step 5: Run tests and commit**

Run: `uv run --directory backend python -m unittest tests.test_government_foundation -v`

Expected: PASS.

```powershell
git add backend/app/government_console backend/app/db.py backend/app/__init__.py backend/tests/test_government_foundation.py
git commit -m "feat(government): 建立政务工作台基础契约"
```

---

### Task 2: Policy Lifecycle and 02 Subscription Push

**Files:**
- Create: `backend/app/government_console/policy.py`
- Create: `backend/tests/test_government_policy.py`
- Modify: `backend/app/government_console/__init__.py`

**Interfaces:**
- Consumes: Task 1 tables, `POLICY_CATEGORIES`, `emit_policy_published`, `mark_notification_sources_unavailable`.
- Produces: `publish_policy(*, actor_id: int, request_id: str, title: str, content: str, category_code: str) -> dict`.
- Produces: `list_policies(*, status: str | None = None, category_code: str | None = None) -> list[dict]`.
- Produces: `unpublish_policy(policy_id: str, *, expected_version: int) -> dict`.
- Produces: `relist_policy(policy_id: str, *, expected_version: int) -> dict`.
- Produces: `delete_policy(policy_id: str, *, expected_version: int) -> None`.

- [ ] **Step 1: Write failing lifecycle and push tests**

```python
# backend/tests/test_government_policy.py
from unittest.mock import patch

from app.government_console.policy import (
    delete_policy,
    publish_policy,
    relist_policy,
    unpublish_policy,
)


def test_publish_is_idempotent_and_pushes_once(self):
    with patch(
        "app.government_console.policy.emit_policy_published",
        return_value={"created_count": 1},
    ) as emit:
        first = publish_policy(
            actor_id=self.government_id,
            request_id="publish-1",
            title="创业补贴",
            content="补贴内容",
            category_code="entrepreneurship",
        )
        second = publish_policy(
            actor_id=self.government_id,
            request_id="publish-1",
            title="创业补贴",
            content="补贴内容",
            category_code="entrepreneurship",
        )
    self.assertEqual(first["id"], second["id"])
    emit.assert_called_once()
    emit.assert_called_once_with(
        event_id="policy:publish-1",
        policy_id=first["id"],
        title="创业补贴",
        category="创业支持",
    )


def test_unpublish_relist_delete_preserve_and_remove_correctly(self):
    policy = self.publish_policy()
    unpublished = unpublish_policy(
        policy["id"], expected_version=policy["version"]
    )
    self.assertEqual(unpublished["status"], "unpublished")
    relisted = relist_policy(
        policy["id"], expected_version=unpublished["version"]
    )
    self.assertEqual(relisted["status"], "active")
    with patch(
        "app.government_console.policy.mark_notification_sources_unavailable"
    ) as mark:
        delete_policy(policy["id"], expected_version=relisted["version"])
        mark.assert_called_once_with(
            source_type="policy",
            source_id=policy["id"],
        )
    self.assertIsNone(self.get_policy_row(policy["id"]))
```

- [ ] **Step 2: Run the failing test**

Run: `uv run --directory backend python -m unittest tests.test_government_policy -v`

Expected: FAIL because policy service functions do not exist.

- [ ] **Step 3: Implement exact validation and idempotency**

```python
def publish_policy(
    *,
    actor_id: int,
    request_id: str,
    title: str,
    content: str,
    category_code: str,
) -> dict:
    normalized = _validate_publication_input(
        request_id=request_id,
        title=title,
        content=content,
        category_code=category_code,
        categories=POLICY_CATEGORIES,
    )
    existing = _find_publication_request("policy", normalized["request_id"])
    if existing is not None:
        return get_policy(existing["content_id"])

    now = shanghai_now_iso()
    policy_id = f"policy-{uuid4().hex}"
    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO government_policies (
                id, title, content, category_code, status, view_count,
                version, created_by, published_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 'active', 0, 1, ?, ?, ?, ?)
            """,
            (
                policy_id,
                normalized["title"],
                normalized["content"],
                category_code,
                actor_id,
                now,
                now,
                now,
            ),
        )
        db.execute(
            """
            INSERT INTO government_publication_requests (
                content_type, request_id, content_id, created_at
            )
            VALUES ('policy', ?, ?, ?)
            """,
            (normalized["request_id"], policy_id, now),
        )
        emit_policy_published(
            event_id=f"policy:{normalized['request_id']}",
            policy_id=policy_id,
            title=normalized["title"],
            category=POLICY_CATEGORIES[category_code],
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.rollback()
        existing = _find_publication_request("policy", normalized["request_id"])
        if existing is None:
            raise ProviderConflictError("政策发布请求冲突")
        return get_policy(existing["content_id"])
    except Exception:
        db.rollback()
        raise
    return get_policy(policy_id)
```

- [ ] **Step 4: Implement versioned transitions**

```python
def _transition_policy(policy_id: str, expected_version: int, new_status: str) -> dict:
    now = shanghai_now_iso()
    db = get_db()
    result = db.execute(
        """
        UPDATE government_policies
        SET status = ?, version = version + 1, updated_at = ?
        WHERE id = ? AND version = ? AND status != 'deleted'
        """,
        (new_status, now, policy_id, expected_version),
    )
    if result.rowcount != 1:
        db.rollback()
        if _policy_exists(policy_id):
            raise ProviderConflictError("政策状态已变化，请刷新后重试")
        raise ProviderNotFoundError("政策不存在")
    db.commit()
    return get_policy(policy_id)
```

`unpublish_policy()` and `relist_policy()` delegate to this helper and never call `emit_policy_published`. `delete_policy()` deletes the policy and its view events, calls `mark_notification_sources_unavailable(source_type="policy", source_id=policy_id)` before commit, and rolls back both deletion and source-availability changes if the 02 call fails.

- [ ] **Step 5: Run tests and commit**

Run: `uv run --directory backend python -m unittest tests.test_government_policy -v`

Expected: PASS with one push per request and zero push on re-list.

```powershell
git add backend/app/government_console/policy.py backend/app/government_console/__init__.py backend/tests/test_government_policy.py
git commit -m "feat(government): 实现政策三态与订阅推送"
```

---

### Task 3: Policy Management API and Role Boundary

**Files:**
- Create: `backend/app/government_console/routes.py`
- Create: `backend/tests/test_government_policy_api.py`
- Modify: `backend/app/__init__.py`

**Interfaces:**
- Consumes: Task 2 policy services and 01 `load_session(required=True, allowed_states={"active"})`.
- Produces: `government_bp`.
- Produces routes:
  - `GET /api/government/policies`
  - `POST /api/government/policies`
  - `POST /api/government/policies/<policy_id>/unpublish`
  - `POST /api/government/policies/<policy_id>/relist`
  - `DELETE /api/government/policies/<policy_id>`

- [ ] **Step 1: Write failing API and authorization tests**

```python
def test_government_can_publish_list_unpublish_relist_and_delete(self):
    self.login_government()
    created = self.client.post(
        "/api/government/policies",
        json={
            "request_id": "api-policy-1",
            "title": "创业补贴",
            "content": "政策正文",
            "category_code": "entrepreneurship",
        },
    )
    self.assertEqual(created.status_code, 201)
    policy = created.get_json()["policy"]
    self.assertEqual(policy["category_label"], "创业支持")
    self.assertEqual(policy["status"], "active")

    listed = self.client.get(
        "/api/government/policies?status=active&category=entrepreneurship"
    )
    self.assertEqual(len(listed.get_json()["policies"]), 1)

    unpublished = self.client.post(
        f"/api/government/policies/{policy['id']}/unpublish",
        json={"expected_version": policy["version"]},
    )
    self.assertEqual(unpublished.get_json()["policy"]["status"], "unpublished")


def test_non_government_role_is_rejected(self):
    self.login_student()
    response = self.client.get("/api/government/policies")
    self.assertEqual(response.status_code, 403)
```

- [ ] **Step 2: Run the failing test**

Run: `uv run --directory backend python -m unittest tests.test_government_policy_api -v`

Expected: FAIL with 404 because the blueprint is not registered.

- [ ] **Step 3: Implement role guard and JSON error mapping**

```python
government_bp = Blueprint("government_console", __name__, url_prefix="/api/government")


def _government_session() -> dict:
    session = load_session(required=True, allowed_states={"active"})
    if session["role"] != "government":
        raise ProviderAccessDeniedError("仅政府账户可访问政务工作台")
    return session


@government_bp.errorhandler(ProviderError)
def handle_provider_error(error: ProviderError):
    status = {
        "validation_error": 400,
        "not_found": 404,
        "conflict": 409,
        "unavailable": 503,
        "access_denied": 403,
    }.get(error.code, 500)
    return jsonify(
        success=False,
        message=error.message,
        details=error.details,
    ), status
```

- [ ] **Step 4: Implement policy routes**

```python
@government_bp.get("/policies")
def list_policies_route():
    _government_session()
    return jsonify(
        success=True,
        policies=list_policies(
            status=request.args.get("status") or None,
            category_code=request.args.get("category") or None,
        ),
    )


@government_bp.post("/policies")
def publish_policy_route():
    session = _government_session()
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise ProviderValidationError("请求格式不正确")
    policy = publish_policy(
        actor_id=int(session["id"]),
        request_id=payload.get("request_id"),
        title=payload.get("title"),
        content=payload.get("content"),
        category_code=payload.get("category_code"),
    )
    return jsonify(success=True, policy=policy), 201
```

Implement transition and delete routes with `expected_version` from JSON and `None` body for delete.

- [ ] **Step 5: Run tests and commit**

Run: `uv run --directory backend python -m unittest tests.test_government_policy_api -v`

Expected: PASS for all lifecycle and role cases.

```powershell
git add backend/app/government_console/routes.py backend/app/__init__.py backend/tests/test_government_policy_api.py
git commit -m "feat(government): 增加政策管理接口"
```

---

### Task 4: News Publish and Delete Lifecycle

**Files:**
- Create: `backend/app/government_console/news.py`
- Create: `backend/tests/test_government_news.py`
- Create: `backend/tests/test_government_news_api.py`
- Modify: `backend/app/government_console/routes.py`

**Interfaces:**
- Consumes: Task 1 tables, `NEWS_CATEGORIES`, Task 3 role guard and error mapping.
- Produces: `publish_news(*, actor_id: int, request_id: str, title: str, content: str, category_code: str) -> dict`.
- Produces: `list_news(*, category_code: str | None = None) -> list[dict]`.
- Produces: `delete_news(news_id: str, *, expected_version: int) -> None`.
- Produces routes: `GET/POST /api/government/news`, `DELETE /api/government/news/<news_id>`.

- [ ] **Step 1: Write failing state-machine tests**

```python
def test_news_has_no_unpublish_or_relist_action(self):
    news = publish_news(
        actor_id=self.government_id,
        request_id="news-1",
        title="暴雨预警",
        content="注意防范",
        category_code="disaster_warning",
    )
    self.assertEqual(news["category_label"], "灾害预警")
    self.assertNotIn("status", news)
    self.assertFalse(hasattr(delete_news, "unpublish"))
    delete_news(news["id"], expected_version=news["version"])
    self.assertIsNone(get_news(news["id"]))


def test_publish_news_never_calls_policy_push(self):
    with patch(
        "app.government_console.news.emit_policy_published"
    ) as emit:
        publish_news(
            actor_id=self.government_id,
            request_id="news-2",
            title="本地新闻",
            content="正文",
            category_code="news",
        )
    emit.assert_not_called()
```

- [ ] **Step 2: Run the failing tests**

Run: `uv run --directory backend python -m unittest tests.test_government_news tests.test_government_news_api -v`

Expected: FAIL because news service and routes do not exist.

- [ ] **Step 3: Implement news service with two-state semantics**

```python
def publish_news(
    *,
    actor_id: int,
    request_id: str,
    title: str,
    content: str,
    category_code: str,
) -> dict:
    normalized = _validate_publication_input(
        request_id=request_id,
        title=title,
        content=content,
        category_code=category_code,
        categories=NEWS_CATEGORIES,
    )
    existing = _find_publication_request("news", normalized["request_id"])
    if existing is not None:
        return get_news(existing["content_id"])
    return _insert_published_news(actor_id, normalized)


def delete_news(news_id: str, *, expected_version: int) -> None:
    db = get_db()
    result = db.execute(
        "DELETE FROM government_news WHERE id = ? AND version = ?",
        (news_id, expected_version),
    )
    if result.rowcount != 1:
        db.rollback()
        raise ProviderNotFoundError("新闻不存在或版本已变化")
    db.execute(
        "DELETE FROM government_view_events WHERE content_type = 'news' AND content_id = ?",
        (news_id,),
    )
    db.commit()
```

There is no `status` field, no unpublish function, no relist function and no notification call.

- [ ] **Step 4: Add news routes and API tests**

```python
@government_bp.post("/news")
def publish_news_route():
    session = _government_session()
    payload = request.get_json(silent=True)
    news = publish_news(
        actor_id=int(session["id"]),
        request_id=payload.get("request_id"),
        title=payload.get("title"),
        content=payload.get("content"),
        category_code=payload.get("category_code"),
    )
    return jsonify(success=True, news=news), 201
```

Assert that `/unpublish` and `/relist` return 404 and are not registered.

- [ ] **Step 5: Run tests and commit**

Run: `uv run --directory backend python -m unittest tests.test_government_news tests.test_government_news_api -v`

Expected: PASS for all three categories, delete, idempotency and role boundary.

```powershell
git add backend/app/government_console/news.py backend/app/government_console/routes.py backend/tests/test_government_news.py backend/tests/test_government_news_api.py
git commit -m "feat(government): 实现新闻两态发布"
```

---

### Task 5: Idempotent Policy/News View Recording

**Files:**
- Create: `backend/app/government_console/views.py`
- Create: `backend/tests/test_government_views.py`
- Modify: `backend/app/government_console/providers.py`
- Modify: `backend/app/government_console/__init__.py`

**Interfaces:**
- Consumes: `government_policies`, `government_news`, `government_view_events`.
- Produces: `record_policy_view(policy_id: str, view_event_id: str) -> int`.
- Produces: `record_news_view(news_id: str, view_event_id: str) -> int`.
- `DatabasePolicyNewsProvider.record_*` delegates to these functions.

- [ ] **Step 1: Write failing idempotency tests**

```python
def test_repeated_view_event_counts_once_and_new_event_counts_again(self):
    policy = self.publish_policy()
    first = record_policy_view(policy["id"], "view-1")
    retry = record_policy_view(policy["id"], "view-1")
    second = record_policy_view(policy["id"], "view-2")
    self.assertEqual((first, retry, second), (1, 1, 2))


def test_view_rejects_unpublished_and_deleted_content(self):
    policy = self.publish_policy()
    unpublished = unpublish_policy(
        policy["id"], expected_version=policy["version"]
    )
    with self.assertRaises(ProviderNotFoundError):
        record_policy_view(policy["id"], "view-unpublished")
    delete_policy(policy["id"], expected_version=unpublished["version"])
    with self.assertRaises(ProviderNotFoundError):
        record_policy_view(policy["id"], "view-deleted")
```

- [ ] **Step 2: Run the failing test**

Run: `uv run --directory backend python -m unittest tests.test_government_views -v`

Expected: FAIL because view functions do not exist.

- [ ] **Step 3: Implement atomic insert and increment**

```python
def _record_view(content_type: str, table: str, content_id: str, event_id: str) -> int:
    if not isinstance(event_id, str) or not event_id.strip():
        raise ProviderValidationError("浏览事件标识不能为空")
    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO government_view_events (
                content_type, content_id, view_event_id, created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (content_type, content_id, event_id.strip(), shanghai_now_iso()),
        )
    except sqlite3.IntegrityError:
        row = db.execute(
            f"SELECT view_count FROM {table} WHERE id = ?",
            (content_id,),
        ).fetchone()
        if row is None:
            raise ProviderNotFoundError("内容不存在")
        return int(row["view_count"])

    result = db.execute(
        f"""
        UPDATE {table}
        SET view_count = view_count + 1, updated_at = ?
        WHERE id = ? AND status = 'active'
        """,
        (shanghai_now_iso(), content_id),
    )
    if result.rowcount != 1:
        db.rollback()
        raise ProviderNotFoundError("内容不存在或不可见")
    db.commit()
    return int(
        db.execute(
            f"SELECT view_count FROM {table} WHERE id = ?",
            (content_id,),
        ).fetchone()["view_count"]
    )
```

For news, the visibility predicate is table existence because news has no status column. Use two explicit SQL branches rather than string interpolation for the predicate.

- [ ] **Step 4: Wire the database provider**

```python
class DatabasePolicyNewsProvider:
    def record_policy_view(self, policy_id: str, view_event_id: str) -> int:
        return record_policy_view(policy_id, view_event_id)

    def record_news_view(self, news_id: str, view_event_id: str) -> int:
        return record_news_view(news_id, view_event_id)
```

- [ ] **Step 5: Run tests and commit**

Run: `uv run --directory backend python -m unittest tests.test_government_views -v`

Expected: PASS; same event counts once, distinct events count repeatedly.

```powershell
git add backend/app/government_console/views.py backend/app/government_console/providers.py backend/app/government_console/__init__.py backend/tests/test_government_views.py
git commit -m "feat(government): 增加幂等浏览计数"
```

---

### Task 6: Read-Only Government Dashboard and 09 Provider Boundary

**Files:**
- Create: `backend/app/government_console/dashboard.py`
- Create: `backend/tests/test_government_dashboard.py`
- Modify: `backend/app/government_console/routes.py`

**Interfaces:**
- Consumes: `get_employment_statistics_provider()`, policy/news tables and view counters.
- Produces: `get_government_dashboard() -> dict` with exactly `employment`, `policy`, `news`.
- Produces route: `GET /api/government/dashboard`.
- Produces no user/training keys or endpoints.

- [ ] **Step 1: Write failing positive/negative dashboard tests**

```python
FORBIDDEN_KEYS = {
    "total_users",
    "role_distribution",
    "region_distribution",
    "direction_distribution",
    "user_details",
    "course_count",
    "learning_behavior_count",
    "progress",
    "completion_rate",
    "certificate_count",
}


def _walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def test_dashboard_has_exact_allowed_shape(self):
    dashboard = get_government_dashboard()
    self.assertEqual(
        set(dashboard),
        {"employment", "policy", "news"},
    )
    self.assertFalse(FORBIDDEN_KEYS.intersection(_walk_keys(dashboard)))


def test_employment_placeholder_is_unavailable_not_zero(self):
    dashboard = get_government_dashboard()
    self.assertEqual(
        dashboard["employment"],
        {
            "active_job_count": None,
            "cumulative_application_count": None,
            "available": False,
        },
    )


def test_fake_09_provider_replaces_values_without_consumer_branch(self):
    set_employment_statistics_provider(
        self.app,
        FakeEmploymentStatisticsProvider(active=8, applications=21),
    )
    dashboard = get_government_dashboard()
    self.assertEqual(dashboard["employment"]["active_job_count"], 8)
    self.assertEqual(
        dashboard["employment"]["cumulative_application_count"], 21
    )
    self.assertTrue(dashboard["employment"]["available"])
```

- [ ] **Step 2: Run the failing tests**

Run: `uv run --directory backend python -m unittest tests.test_government_dashboard -v`

Expected: FAIL because dashboard module and route do not exist.

- [ ] **Step 3: Implement exact aggregation**

```python
def get_government_dashboard() -> dict:
    db = get_db()
    policy = db.execute(
        """
        SELECT
            SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) AS active_count,
            SUM(CASE WHEN status = 'unpublished' THEN 1 ELSE 0 END) AS unpublished_count,
            COALESCE(SUM(view_count), 0) AS view_count
        FROM government_policies
        """
    ).fetchone()
    news = db.execute(
        """
        SELECT COUNT(*) AS total_count, COALESCE(SUM(view_count), 0) AS view_count
        FROM government_news
        """
    ).fetchone()
    provider = get_employment_statistics_provider()
    active_jobs = provider.get_active_job_count()
    applications = provider.get_cumulative_application_count()
    return {
        "employment": {
            "active_job_count": active_jobs,
            "cumulative_application_count": applications,
            "available": active_jobs is not None and applications is not None,
        },
        "policy": {
            "active_count": int(policy["active_count"] or 0),
            "unpublished_count": int(policy["unpublished_count"] or 0),
            "total_count": int(policy["active_count"] or 0)
            + int(policy["unpublished_count"] or 0),
            "view_count": int(policy["view_count"] or 0),
        },
        "news": {
            "total_count": int(news["total_count"] or 0),
            "view_count": int(news["view_count"] or 0),
        },
    }
```

- [ ] **Step 4: Add dashboard route and recursive forbidden-key API test**

```python
@government_bp.get("/dashboard")
def government_dashboard_route():
    _government_session()
    dashboard = get_government_dashboard()
    assert not FORBIDDEN_DASHBOARD_KEYS.intersection(_walk_keys(dashboard))
    return jsonify(success=True, dashboard=dashboard)
```

The assertion helper must exist in production code or a shared testable validator so the same boundary is enforced at runtime and in tests.

- [ ] **Step 5: Run tests and commit**

Run: `uv run --directory backend python -m unittest tests.test_government_dashboard -v`

Expected: PASS; zero forbidden keys, no fake employment counts.

```powershell
git add backend/app/government_console/dashboard.py backend/app/government_console/routes.py backend/tests/test_government_dashboard.py
git commit -m "feat(government): 实现只读政务看板"
```

---

### Task 7: 06 Policy/News Producer Contract

**Files:**
- Modify: `backend/app/government_console/providers.py`
- Modify: `backend/app/government_console/policy.py`
- Modify: `backend/app/government_console/news.py`
- Create: `backend/tests/test_government_provider_contract.py`

**Interfaces:**
- Consumes: Task 2 policy data, Task 4 news data, Task 5 view recording.
- Produces: complete `DatabasePolicyNewsProvider` implementing all six Protocol methods.
- Produces stable dict fields and deterministic order:
  `published_at DESC, id ASC`.

- [ ] **Step 1: Write failing provider contract tests**

```python
def test_provider_returns_only_published_content_in_stable_order(self):
    active = self.publish_policy(title="B", published_at="2026-09-18T10:00:00+08:00")
    older = self.publish_policy(title="A", published_at="2026-09-17T10:00:00+08:00")
    hidden = self.publish_policy(title="C")
    unpublish_policy(hidden["id"], expected_version=hidden["version"])

    provider = DatabasePolicyNewsProvider()
    items = provider.list_published_policies(category="entrepreneurship")
    self.assertEqual([item["id"] for item in items], [active["id"], older["id"]])
    self.assertIsNone(provider.get_published_policy(hidden["id"]))


def test_provider_records_views_without_exposing_database(self):
    news = self.publish_news()
    provider = DatabasePolicyNewsProvider()
    self.assertEqual(provider.record_news_view(news["id"], "view-1"), 1)
    self.assertEqual(provider.record_news_view(news["id"], "view-1"), 1)
    self.assertEqual(provider.record_news_view(news["id"], "view-2"), 2)
```

- [ ] **Step 2: Run the failing test**

Run: `uv run --directory backend python -m unittest tests.test_government_provider_contract -v`

Expected: FAIL until provider methods return the exact contract fields.

- [ ] **Step 3: Implement stable record projection**

```python
def _policy_payload(row) -> dict:
    return {
        "id": str(row["id"]),
        "title": str(row["title"]),
        "content": str(row["content"]),
        "category_code": str(row["category_code"]),
        "category_label": POLICY_CATEGORIES[row["category_code"]],
        "published_at": normalize_shanghai_iso(row["published_at"]),
        "updated_at": normalize_shanghai_iso(row["updated_at"]),
        "version": int(row["version"]),
    }
```

Use the equivalent `_news_payload()` projection. Provider methods must not include `created_by`, `view_count`, database row objects, or internal status values.

- [ ] **Step 4: Implement list filters and deterministic ordering**

```python
def list_published_policies(self, category: str | None = None) -> list[dict]:
    sql = """
        SELECT id, title, content, category_code, published_at, updated_at, version
        FROM government_policies
        WHERE status = 'active'
    """
    params: list[object] = []
    if category is not None:
        category_code = normalize_category_filter(category, POLICY_CATEGORIES)
        sql += " AND category_code = ?"
        params.append(category_code)
    sql += " ORDER BY published_at DESC, id ASC"
    return [_policy_payload(row) for row in get_db().execute(sql, params)]
```

- [ ] **Step 5: Run tests and commit**

Run: `uv run --directory backend python -m unittest tests.test_government_provider_contract -v`

Expected: PASS; only active/undeleted content is returned and retries do not double-count views.

```powershell
git add backend/app/government_console/providers.py backend/app/government_console/policy.py backend/app/government_console/news.py backend/tests/test_government_provider_contract.py
git commit -m "feat(government): 冻结政策新闻生产者契约"
```

---

### Task 8: Frontend DTOs and Government Store

**Files:**
- Modify: `frontend/src/api/types.ts`
- Create: `frontend/src/stores/governmentConsole.ts`
- Create: `frontend/src/stores/governmentConsole.test.ts`

**Interfaces:**
- Consumes: `/api/government/policies`, `/api/government/news`, `/api/government/dashboard`.
- Produces types: `GovernmentPolicy`, `GovernmentNews`, `GovernmentDashboard`.
- Produces store actions: `loadPolicies`, `publishPolicy`, `unpublishPolicy`, `relistPolicy`, `deletePolicy`, `loadNews`, `publishNews`, `deleteNews`, `loadDashboard`.
- Produces state: `policies`, `news`, `dashboard`, `loading`, `error`.

- [ ] **Step 1: Write failing store tests**

```typescript
it('loads dashboard without adding user or training keys', async () => {
  vi.mocked(apiFetch).mockResolvedValue({
    success: true,
    dashboard: {
      employment: {
        active_job_count: null,
        cumulative_application_count: null,
        available: false
      },
      policy: {
        active_count: 1,
        unpublished_count: 1,
        total_count: 2,
        view_count: 9
      },
      news: { total_count: 3, view_count: 7 }
    }
  })

  const store = useGovernmentConsoleStore()
  await store.loadDashboard()

  expect(Object.keys(store.dashboard!)).toEqual([
    'employment',
    'policy',
    'news'
  ])
})


it('publishes a policy and refreshes the list', async () => {
  vi.mocked(apiFetch)
    .mockResolvedValueOnce({ success: true, policy: policyFixture })
    .mockResolvedValueOnce({ success: true, policies: [policyFixture] })

  const store = useGovernmentConsoleStore()
  await store.publishPolicy({
    request_id: crypto.randomUUID(),
    title: '创业补贴',
    content: '正文',
    category_code: 'entrepreneurship'
  })

  expect(store.policies).toEqual([policyFixture])
})
```

- [ ] **Step 2: Run the failing test**

Run: `cd frontend; npm test -- governmentConsole.test.ts`

Expected: FAIL because the store and types do not exist.

- [ ] **Step 3: Add exact DTOs**

```typescript
export interface GovernmentPolicy {
  id: string
  title: string
  content: string
  category_code: 'subsidy' | 'ecommerce' | 'heritage' | 'training'
    | 'certification' | 'general' | 'entrepreneurship'
  category_label: string
  status: 'active' | 'unpublished'
  view_count: number
  version: number
  published_at: string
  updated_at: string
}

export interface GovernmentNews {
  id: string
  title: string
  content: string
  category_code: 'news' | 'disaster_warning' | 'policy_update'
  category_label: string
  view_count: number
  version: number
  published_at: string
  updated_at: string
}

export interface GovernmentDashboard {
  employment: {
    active_job_count: number | null
    cumulative_application_count: number | null
    available: boolean
  }
  policy: {
    active_count: number
    unpublished_count: number
    total_count: number
    view_count: number
  }
  news: {
    total_count: number
    view_count: number
  }
}
```

- [ ] **Step 4: Implement the Pinia store**

```typescript
export const useGovernmentConsoleStore = defineStore('governmentConsole', () => {
  const policies = ref<GovernmentPolicy[]>([])
  const news = ref<GovernmentNews[]>([])
  const dashboard = ref<GovernmentDashboard | null>(null)
  const loading = ref(false)
  const error = ref('')

  async function publishPolicy(payload: PublishPolicyPayload) {
    await apiFetch<{ success: true; policy: GovernmentPolicy }>(
      '/api/government/policies',
      { method: 'POST', body: JSON.stringify(payload) }
    )
    await loadPolicies()
  }

  async function loadDashboard() {
    const response = await apiFetch<{
      success: true
      dashboard: GovernmentDashboard
    }>('/api/government/dashboard')
    dashboard.value = response.dashboard
  }

  return {
    policies,
    news,
    dashboard,
    loading,
    error,
    loadPolicies,
    publishPolicy,
    unpublishPolicy,
    relistPolicy,
    deletePolicy,
    loadNews,
    publishNews,
    deleteNews,
    loadDashboard
  }
})
```

- [ ] **Step 5: Run tests and commit**

Run: `cd frontend; npm test -- governmentConsole.test.ts`

Expected: PASS.

```powershell
git add frontend/src/api/types.ts frontend/src/stores/governmentConsole.ts frontend/src/stores/governmentConsole.test.ts
git commit -m "feat(government): 增加政务前端数据层"
```

---

### Task 9: Policy Management UI

**Files:**
- Create: `frontend/src/components/GovernmentConsoleNav.vue`
- Create: `frontend/src/views/GovernmentPolicyView.vue`
- Create: `frontend/src/views/GovernmentPolicyView.test.ts`

**Interfaces:**
- Consumes: Task 8 store.
- Produces: policy create form, category/status filters, active/unpublished table, unpublish/relist/delete controls.
- Produces no review, approval, export, subsidy application or user data controls.

- [ ] **Step 1: Write failing policy view tests**

```typescript
it('publishes the seven-category policy form', async () => {
  const wrapper = mount(GovernmentPolicyView, { global: { plugins: [pinia] } })
  await wrapper.get('[data-test="policy-title"]').setValue('创业补贴')
  await wrapper.get('[data-test="policy-content"]').setValue('正文')
  await wrapper.get('[data-test="policy-category"]').setValue('entrepreneurship')
  await wrapper.get('form').trigger('submit')

  expect(store.publishPolicy).toHaveBeenCalledWith(
    expect.objectContaining({
      title: '创业补贴',
      category_code: 'entrepreneurship'
    })
  )
})


it('does not render approval or export controls', () => {
  const wrapper = mount(GovernmentPolicyView, { global: { plugins: [pinia] } })
  expect(wrapper.text()).not.toContain('审核')
  expect(wrapper.text()).not.toContain('导出')
})
```

- [ ] **Step 2: Run the failing test**

Run: `cd frontend; npm test -- GovernmentPolicyView.test.ts`

Expected: FAIL because the view does not exist.

- [ ] **Step 3: Build the management view**

Use `GovernmentConsoleNav`, a form with `title`, `content`, `category_code`, and a generated `request_id: crypto.randomUUID()`. Use a `select` containing exactly:

```typescript
const policyCategories = [
  ['subsidy', '补贴'],
  ['ecommerce', '电商'],
  ['heritage', '非遗'],
  ['training', '培训'],
  ['certification', '认证'],
  ['general', '综合'],
  ['entrepreneurship', '创业支持']
] as const
```

The table displays title, category, status, view count, published time and versioned actions. Buttons use `lucide-vue-next` icons with accessible labels.

- [ ] **Step 4: Add lifecycle interaction tests**

```typescript
it('uses the current version for unpublish, relist and delete', async () => {
  store.policies = [policyFixture]
  const wrapper = mount(GovernmentPolicyView, { global: { plugins: [pinia] } })
  await wrapper.get('[data-test="unpublish-policy"]').trigger('click')
  expect(store.unpublishPolicy).toHaveBeenCalledWith(
    policyFixture.id,
    policyFixture.version
  )
})
```

Delete must use an explicit confirmation state; no one-click destructive action.

- [ ] **Step 5: Run tests and commit**

Run: `cd frontend; npm test -- GovernmentPolicyView.test.ts`

Expected: PASS.

```powershell
git add frontend/src/components/GovernmentConsoleNav.vue frontend/src/views/GovernmentPolicyView.vue frontend/src/views/GovernmentPolicyView.test.ts
git commit -m "feat(government): 增加政策管理界面"
```

---

### Task 10: News Management UI

**Files:**
- Create: `frontend/src/views/GovernmentNewsView.vue`
- Create: `frontend/src/views/GovernmentNewsView.test.ts`

**Interfaces:**
- Consumes: Task 8 store and Task 9 navigation.
- Produces: news create form, category filter, news list and delete confirmation.
- Produces no unpublish/relist controls.

- [ ] **Step 1: Write failing news view tests**

```typescript
it('publishes the three-category news form', async () => {
  const wrapper = mount(GovernmentNewsView, { global: { plugins: [pinia] } })
  await wrapper.get('[data-test="news-title"]').setValue('暴雨预警')
  await wrapper.get('[data-test="news-content"]').setValue('请提前防范')
  await wrapper.get('[data-test="news-category"]').setValue('disaster_warning')
  await wrapper.get('form').trigger('submit')

  expect(store.publishNews).toHaveBeenCalledWith(
    expect.objectContaining({ category_code: 'disaster_warning' })
  )
})


it('does not render unpublish or relist actions', () => {
  const wrapper = mount(GovernmentNewsView, { global: { plugins: [pinia] } })
  expect(wrapper.text()).not.toContain('下架')
  expect(wrapper.text()).not.toContain('重新上架')
})
```

- [ ] **Step 2: Run the failing test**

Run: `cd frontend; npm test -- GovernmentNewsView.test.ts`

Expected: FAIL because the view does not exist.

- [ ] **Step 3: Implement exact three-category form and delete-only list**

```typescript
const newsCategories = [
  ['news', '新闻'],
  ['disaster_warning', '灾害预警'],
  ['policy_update', '政策更新']
] as const
```

The table displays title, category, publication time, view count and delete. Delete uses a confirmation state and calls `store.deleteNews(news.id, news.version)`.

- [ ] **Step 4: Add deletion and empty-state tests**

```typescript
it('confirms before deleting news', async () => {
  store.news = [newsFixture]
  const wrapper = mount(GovernmentNewsView, { global: { plugins: [pinia] } })
  await wrapper.get('[data-test="delete-news"]').trigger('click')
  expect(store.deleteNews).not.toHaveBeenCalled()
  await wrapper.get('[data-test="confirm-delete-news"]').trigger('click')
  expect(store.deleteNews).toHaveBeenCalledWith(
    newsFixture.id,
    newsFixture.version
  )
})
```

When no news exists, render `暂无新闻` without exposing a hidden unpublish route.

- [ ] **Step 5: Run tests and commit**

Run: `cd frontend; npm test -- GovernmentNewsView.test.ts`

Expected: PASS.

```powershell
git add frontend/src/views/GovernmentNewsView.vue frontend/src/views/GovernmentNewsView.test.ts
git commit -m "feat(government): 增加新闻管理界面"
```

---

### Task 11: Read-Only Dashboard UI

**Files:**
- Create: `frontend/src/views/GovernmentDashboardView.vue`
- Create: `frontend/src/views/GovernmentDashboardView.test.ts`

**Interfaces:**
- Consumes: Task 8 `loadDashboard()` and exact `GovernmentDashboard`.
- Produces cards for employment, policy and news only.
- Produces no user/training cards, drill-down, export or mutation controls.

- [ ] **Step 1: Write failing dashboard UI tests**

```typescript
it('renders only allowed metric labels', async () => {
  store.dashboard = dashboardFixture
  const wrapper = mount(GovernmentDashboardView, {
    global: { plugins: [pinia] }
  })
  await flushPromises()

  expect(wrapper.text()).toContain('在招岗位数')
  expect(wrapper.text()).toContain('累计投递量')
  expect(wrapper.text()).toContain('在架政策数')
  expect(wrapper.text()).toContain('下架政策数')
  expect(wrapper.text()).toContain('政策累计点击浏览量')
  expect(wrapper.text()).toContain('新闻总数')
  expect(wrapper.text()).toContain('新闻累计点击浏览量')
  expect(wrapper.text()).not.toMatch(/总用户|用户分布|课程数|完课率|学习行为/)
})


it('shows unavailable employment copy without hiding content metrics', () => {
  store.dashboard = {
    ...dashboardFixture,
    employment: {
      active_job_count: null,
      cumulative_application_count: null,
      available: false
    }
  }
  const wrapper = mount(GovernmentDashboardView, {
    global: { plugins: [pinia] }
  })
  expect(wrapper.findAll('[data-test="employment-unavailable"]')).toHaveLength(2)
  expect(wrapper.text()).toContain('政策累计点击浏览量')
  expect(wrapper.text()).toContain('新闻累计点击浏览量')
})
```

- [ ] **Step 2: Run the failing test**

Run: `cd frontend; npm test -- GovernmentDashboardView.test.ts`

Expected: FAIL because the dashboard view does not exist.

- [ ] **Step 3: Implement the exact positive metric list**

Create three unframed page bands or one compact metric grid:

```typescript
const employmentCards = computed(() => [
  {
    key: 'active_job_count',
    label: '在招岗位数',
    value: store.dashboard?.employment.active_job_count
  },
  {
    key: 'cumulative_application_count',
    label: '累计投递量',
    value: store.dashboard?.employment.cumulative_application_count
  }
])

const policyCards = computed(() => [
  { label: '在架政策数', value: store.dashboard?.policy.active_count },
  { label: '下架政策数', value: store.dashboard?.policy.unpublished_count },
  { label: '政策累计点击浏览量', value: store.dashboard?.policy.view_count }
])
```

Render `--` plus `就业数据暂不可用` when employment `available=false`. Do not render a disabled placeholder for any user/training metric.

- [ ] **Step 4: Add responsive and no-export tests**

```typescript
it('has no horizontal overflow at narrow width', () => {
  Object.defineProperty(window, 'innerWidth', { value: 320, configurable: true })
  const wrapper = mount(GovernmentDashboardView, {
    global: { plugins: [pinia] }
  })
  expect(wrapper.find('[data-test="government-dashboard"]').exists()).toBe(true)
  expect(wrapper.text()).not.toContain('导出')
})
```

CSS must use responsive grid tracks and wrapping labels; no fixed width greater than the viewport.

- [ ] **Step 5: Run tests and commit**

Run: `cd frontend; npm test -- GovernmentDashboardView.test.ts`

Expected: PASS.

```powershell
git add frontend/src/views/GovernmentDashboardView.vue frontend/src/views/GovernmentDashboardView.test.ts
git commit -m "feat(government): 增加政务只读看板"
```

---

### Task 12: Government Routes, Portal, and Onboarding Integration

**Files:**
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/views/GovernmentPortalView.vue`
- Modify: `frontend/src/data/portal-guides.ts`
- Create: `frontend/src/router/governmentRoutes.test.ts`
- Create: `frontend/src/views/GovernmentPortalView.test.ts`

**Interfaces:**
- Consumes: Task 9-11 views and 01 `authGuard`.
- Produces routes:
  - `/government/policies`
  - `/government/news`
  - `/government/dashboard`
- Produces portal entries with exact hrefs and no “后续开放” for the three 010 features.

- [ ] **Step 1: Write failing route and portal tests**

```typescript
it('protects every government route with the government role', () => {
  const routes = router.getRoutes()
  for (const path of [
    '/government/policies',
    '/government/news',
    '/government/dashboard'
  ]) {
    const route = routes.find(item => item.path === path)
    expect(route?.meta.requiresAuth).toBe(true)
    expect(route?.meta.roles).toEqual(['government'])
  }
})


it('redirects non-government users through the existing role guard', async () => {
  const result = await authGuard(
    routeLocation('/government/dashboard'),
    { ...authStore, user: { role: 'student' }, isAuthenticated: true }
  )
  expect(result).toBe('/student')
})
```

- [ ] **Step 2: Run the failing tests**

Run: `cd frontend; npm test -- governmentRoutes.test.ts GovernmentPortalView.test.ts`

Expected: FAIL because routes and portal links are absent.

- [ ] **Step 3: Register exact routes**

```typescript
{
  path: '/government/policies',
  name: 'government-policies',
  component: GovernmentPolicyView,
  meta: { requiresAuth: true, roles: ['government'] }
},
{
  path: '/government/news',
  name: 'government-news',
  component: GovernmentNewsView,
  meta: { requiresAuth: true, roles: ['government'] }
},
{
  path: '/government/dashboard',
  name: 'government-dashboard',
  component: GovernmentDashboardView,
  meta: { requiresAuth: true, roles: ['government'] }
}
```

- [ ] **Step 4: Replace placeholder portal with real entries**

`GovernmentPortalView.vue` renders `GovernmentConsoleNav` and concise workspace entry links:

```typescript
const governmentEntries = [
  { label: '政策管理', href: '/government/policies' },
  { label: '新闻管理', href: '/government/news' },
  { label: '数据看板', href: '/government/dashboard' },
  { label: '消息中心', href: '/messages' }
]
```

Update `portal-guides.ts` government entries with the matching hrefs and keep onboarding selectors stable:

```typescript
{ id: 'government-policy-publish', href: '/government/policies' }
{ id: 'government-news-publish', href: '/government/news' }
{ id: 'government-dashboard', href: '/government/dashboard' }
```

- [ ] **Step 5: Run tests and commit**

Run: `cd frontend; npm test -- governmentRoutes.test.ts GovernmentPortalView.test.ts`

Expected: PASS.

```powershell
git add frontend/src/router/index.ts frontend/src/router/governmentRoutes.test.ts frontend/src/views/GovernmentPortalView.vue frontend/src/views/GovernmentPortalView.test.ts frontend/src/data/portal-guides.ts
git commit -m "feat(government): 接入政务门户路由"
```

---

### Task 13: Backend Integration, Boundary Regression, and Full Verification

**Files:**
- Create: `backend/tests/test_government_integration.py`
- Modify: any 010 file only if integration tests reveal a real defect

**Interfaces:**
- Consumes: all previous tasks.
- Produces: end-to-end evidence for policy push, news visibility, view counts, dashboard exclusion, provider replacement and no-AI/no-review boundaries.

- [ ] **Step 1: Write the end-to-end integration test**

```python
def test_government_console_end_to_end(self):
    self.login_government()
    policy = self.client.post(
        "/api/government/policies",
        json={
            "request_id": "policy-e2e",
            "title": "创业支持政策",
            "content": "正文",
            "category_code": "entrepreneurship",
        },
    ).get_json()["policy"]
    self.assertEqual(
        self.subscriber_notification_titles(),
        ["创业支持政策"],
    )

    provider = get_policy_news_provider()
    self.assertEqual(provider.record_policy_view(policy["id"], "view-1"), 1)
    self.assertEqual(provider.record_policy_view(policy["id"], "view-1"), 1)

    dashboard = self.client.get("/api/government/dashboard").get_json()["dashboard"]
    self.assertEqual(dashboard["policy"]["active_count"], 1)
    self.assertEqual(dashboard["policy"]["view_count"], 1)
    self.assertFalse(
        {
            "total_users",
            "role_distribution",
            "course_count",
            "completion_rate",
        }.intersection(_walk_keys(dashboard))
    )
```

- [ ] **Step 2: Add static boundary tests**

```python
def test_government_module_has_no_ai_or_review_dependency(self):
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in Path("app/government_console").glob("*.py")
    )
    self.assertNotIn("ContentReviewProvider", source)
    self.assertNotIn("get_ai_client", source)
    self.assertNotIn("complete_json", source)
    self.assertNotIn("ai_unavailable", source)
```

Add a second assertion that no 010 source contains `FROM jobs`, `FROM applications`, `job_positions` or `employment_applications`.

- [ ] **Step 3: Run all backend tests**

Run: `uv run --directory backend python -m unittest discover -s tests -v`

Expected: PASS with zero failures. If any existing 02 test fails, fix the 010 caller rather than modifying 02 semantics.

- [ ] **Step 4: Run all frontend tests, type-check, and build**

Run:

```powershell
cd frontend
npm test
npx tsc -b --noEmit
npm run build
```

Expected: all tests pass, type-check exits 0, production build succeeds.

- [ ] **Step 5: Browser-check and commit**

Start the app using the RUNBOOK command, then verify at 320, 375 and 1280 widths:

- `/government` exposes exactly policy, news, dashboard and message entries.
- `/government/policies` renders seven categories and no review/export controls.
- `/government/news` renders three categories and no unpublish/re-list controls.
- `/government/dashboard` renders exactly seven positive metric labels and no user/training labels.
- No page has horizontal overflow or overlapping text.

```powershell
git add backend/tests/test_government_integration.py
git commit -m "test(government): 完成政务工作台回归验证"
```

---

## Self-Review

### Spec Coverage

| Spec area | Tasks |
| --- | --- |
| FR-001..006 role, reuse, no review, no AI, boundaries | Tasks 1, 3, 13 |
| FR-007..021 policy lifecycle, seven categories and push | Tasks 2, 3, 13 |
| FR-022..028 news two-state lifecycle and three categories | Tasks 4, 10 |
| FR-029..034 view source, idempotency and retention | Tasks 5, 7 |
| FR-035..044 dashboard positive/negative metrics and 09 boundary | Tasks 6, 11, 13 |
| FR-045..057 provider registration, 06 interface, 09 replacement, errors and time | Tasks 1, 5, 6, 7 |
| SC-001..012 measurable outcomes | Tasks 2-13 |

### Placeholder Scan

- No `TODO`, `TBD`, “implement later” or “similar to Task N” remains.
- Every provider replacement has a concrete registration function.
- Every UI negative boundary has an explicit test.

### Type Consistency

- Policy state values are consistently `active` / `unpublished`; deleted is row absence.
- News has no status field and only `published` / deleted semantics.
- `PolicyNewsProvider` method names match between spec, provider, store calls and tests.
- `EmploymentStatisticsProvider` method names match between spec, placeholder, dashboard and fake-provider test.
- Dashboard keys are identical in backend response, frontend DTO, store and view.
