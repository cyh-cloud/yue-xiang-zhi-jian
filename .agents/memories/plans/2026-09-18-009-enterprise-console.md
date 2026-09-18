# 09-企业工作台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付 09-企业工作台，包括职位审核状态机、申请筛选与改标、简历/技能档案快照展示、投递学员私信边界、企业数据看板，以及供 07 消费的稳定岗位 provider。

**Architecture:** 后端新增 `backend/app/enterprise_console/` 领域包，职位、申请、状态历史和通知发件箱使用同一 SQLite 数据库。09 通过唯一 `job_position_provider` 槽实现岗位生产者，通过唯一 `job_application_intake_provider` 槽向 07 提供申请接收契约，并通过唯一 `content_review_provider` 槽接入 11；所有审核动作仍由 11 负责。前端在 `frontend/src/` 增加企业 store、导航、职位与申请视图，并把 `/enterprise` 从占位门户升级为可用看板。

**Tech Stack:** Python 3.12、Flask、sqlite3、uv、unittest、Vue 3、Vite、Pinia、Vue Router、Vitest、Vue Test Utils、lucide-vue-next。

**Spec:** `specs/009-enterprise-console/spec.md`

**Branch:** `v2/lixKRT/009-enterprise-console`

**Worktree:** `.worktrees/009-enterprise-console`

## Global Constraints

- 旧系统 `app.py`、`database.py` 和根目录旧 HTML 页面禁止读取、导入、复制或迁移。
- 所有企业接口只允许 `active` 的 `enterprise` 会话，企业身份必须取自 01 会话；客户端传入的企业 ID 一律忽略。
- 09 只通过 02 的 `emit_application_submitted`、`emit_application_status_changed`、`emit_position_closed` 和 `register_messaging_source_provider` 复用消息能力，不创建第二套消息、通知或未读表。
- 09 是岗位 provider 的生产实现，07 是最终签名所有者；冻结签名为 `list_published_positions()` 和 `get_published_position(job_id: str)`，只能通过 `set_job_position_provider` / `get_job_position_provider` 替换。
- 09 是 `JobApplicationIntakeProvider` 的签名与实现所有者，07 只通过 `submit_application()` 写入投递；唯一注册入口为 `set_job_application_intake_provider` / `get_job_application_intake_provider`。
- 09 只消费 11 的 `ContentReviewProvider`，调用 `submit_for_review`、`get_review_status`、`edit`；不实现 `approve`、`reject`、视频专用 `apply` 或审核通知。`content_review_provider` 只能有一个注册槽，11 替换 09 安装的不可用占位实现。
- 职位删除是可审计逻辑删除，不提供恢复或物理清除；未处理申请冻结为“岗位已关闭”，已处理申请保留最新状态并附加关闭标识；职位关闭后全部申请只读。
- 申请筛选日期按 `Asia/Shanghai` 自然日闭区间；默认按投递时间倒序，再按稳定申请 ID 正序。
- 职位类别只引用 01 的 `job` 兴趣标签稳定 ID；09 不创建类别目录，07 只以稳定类别 ID 匹配推荐。
- 09 无任何 AI 调用；不得导入 `get_ai_client`、`complete_json`、`stream_chat`、`transcribe` 或 AI 错误类型。
- 路由 kebab-case，Python snake_case，前端 camelCase；每个任务先写失败测试，再最小实现，运行定向测试后提交。

## No Placeholders Rule

- 每个任务必须列出精确 Files、Interfaces、测试命令和预期结果。
- 不允许未决标记、空实现、含糊延后或跨任务简写。
- 11 未实现时只能注入完整协议相符的审核 fake/adapter；09 业务代码不得判断 provider 是否为占位实现。
- 07 未实现时测试通过完整 `JobApplicationIntakeProvider` 形成投递记录；生产投递由 07 通过该签名发起，09 不新增学员投递页面或公共投递 API。
- 每个任务至少完成一次 TDD 红绿循环；最终任务运行完整后端、前端、类型检查、构建和浏览器验收。

## AI 调用点与降级矩阵

| 调用点 | 失败表现 | 降级行为 | 代码边界 |
| --- | --- | --- | --- |
| 无 | 不适用 | 不适用 | `backend/app/enterprise_console/` 不导入 AI client，不注册 AI call point |

自动化验证必须断言 `rg -n "get_ai_client|complete_json|stream_chat|transcribe|set_ai_client|AiUnavailable" backend/app/enterprise_console` 无结果。

## 职位状态机与可见性矩阵

| 权威状态 | 数据库条件 | 企业端 | 学员/provider | 允许动作 |
| --- | --- | --- | --- | --- |
| `pending` | `review_status='pending' AND deleted_at IS NULL` | 待审核 | 不返回 | 有变化编辑保持 `pending`；删除 |
| `approved` | `review_status='approved' AND deleted_at IS NULL AND published_at IS NOT NULL` | 已通过/已上架 | 列表、详情、投递可见 | 编辑转 `pending` 并即时下架；删除 |
| `rejected` | `review_status='rejected' AND deleted_at IS NULL` | 已驳回并带意见 | 不返回 | 修改重提转 `pending`；删除 |
| `deleted` | `deleted_at IS NOT NULL` | 当前职位列表不返回 | 永不返回 | 无恢复；冻结申请历史并关闭未处理申请 |

状态转换常量：

```python
JOB_REVIEW_STATUSES = {"pending", "approved", "rejected"}
JOB_TRANSITIONS = {
    ("pending", "pending"): "edit",
    ("pending", "approved"): "approve",
    ("pending", "rejected"): "reject",
    ("approved", "pending"): "edit",
    ("rejected", "pending"): "edit",
}
```

审核通过由 11 provider 写入投影；09 不暴露审核决策入口。任何有实际变化的编辑都必须清空 `published_at`，已通过职位在下一次读取前不可见。

## 岗位 provider 实现说明

冻结 protocol：

```python
class JobPositionProvider(Protocol):
    def list_published_positions(self) -> list[dict]: ...

    def get_published_position(self, *, job_id: str) -> dict | None: ...
```

注册入口：

```python
def set_job_position_provider(app: Flask, provider: JobPositionProvider) -> None: ...
def get_job_position_provider() -> JobPositionProvider: ...
def configure_enterprise_providers(
    app: Flask,
    *,
    job_position_provider: JobPositionProvider | None = None,
    job_application_intake_provider: JobApplicationIntakeProvider | None = None,
    content_review_provider: ContentReviewProvider | None = None,
) -> None: ...
```

返回记录字段与排序：

```text
job_id, enterprise_id, enterprise_name, title, salary, location,
category_id, category_name, description, review_status,
version, published_at, updated_at
```

- 只返回 `approved + deleted_at IS NULL + published_at IS NOT NULL`。
- 列表按 `published_at DESC, job_id ASC`。
- `get_published_position()` 未找到时返回 `None`。
- `job_id`、`application_id` 是非空字符串，不暴露 SQLite 主键。
- provider 错误使用 `code`、`message`、`details`，consumer 不判断来源是否为占位实现。

## ContentReviewProvider 接入说明

09 只依赖通用 protocol：

```python
class ContentReviewProvider(Protocol):
    def submit_for_review(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        expected_version: int,
        payload: dict,
    ) -> dict: ...

    def get_review_status(
        self,
        *,
        content_type: str,
        content_id: str,
    ) -> dict | None: ...

    def approve(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        reviewer_id: int,
        reviewer_role: str,
        expected_version: int,
    ) -> dict: ...

    def reject(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        reviewer_id: int,
        reviewer_role: str,
        expected_version: int,
        opinion: str,
    ) -> dict: ...

    def edit(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        expected_version: int,
        payload: dict,
    ) -> dict: ...
```

09 调用规则：

1. 先持久化携带稳定 `job_id` 的岗位记录。
2. `submit_for_review()` 使用 `content_type="job_position"`、企业 ID 和当前版本。
3. 编辑统一使用 `edit()`；provider 返回的 `review_status`、`version`、`rejection_opinion`、`published_at` 回写本地投影。
4. `get_review_status()` 用于读取 11 的批准/驳回结果；未找到返回 `None`。
5. 09 不调用 `emit_review_result()`，不实现 provider 的 `approve`/`reject` action 分支。
6. 默认 `UnavailableContentReviewProvider` 每个方法抛出 `ProviderUnavailableError`；测试和 11 落地后替换同一注册槽。

## 与 001/02/11 的复用点

| 复用点 | 既有接口/组件 | 09 使用方式 | 禁止事项 |
| --- | --- | --- | --- |
| 会话与角色 | `load_session(required=True, allowed_states={"active"})` | 企业 API 从会话覆盖 `enterprise_id` | 不新增登录、企业 ID 参数或角色缓存 |
| 企业账户 | `users.name`、`users.role='enterprise'` | provider 返回企业展示名；不建立企业资料副本 | 不实现企业注册或账号编辑 |
| 类别目录 | `/api/interest-tags`、`interest_tags(group_key='job')` | 职位保存稳定 `category_id` 和名称快照 | 不建立职位类别表 |
| 私信关系 | `register_messaging_source_provider()`、`MessagingSourceProvider` | 09 注册 `list_applied_enterprise_ids()` 和 `list_applicant_student_ids()` | 不读取/写入 02 会话表，不建旁路 |
| 通知 | `backend/app/messaging/events.py` | 发件箱投递调用申请投递、状态改标和岗位关闭事件 | 不直接写 `system_notifications` |
| 审核 | 11 `ContentReviewProvider` | 直角接入 `submit/get/edit`，测试 fake 驱动 approve/reject | 不复制 05 video action |
| 简历与技能档案 | 07 投递快照 | 09 只读 JSON 快照，按附带/可见项降级展示 | 不读取当前 07 档案补造，不建第二档案源 |

## 与 07 的应用写入边界

09 冻结并实现 `JobApplicationIntakeProvider`，07 只依赖该签名：

```python
class JobApplicationIntakeProvider(Protocol):
    def submit_application(
        self,
        *,
        job_id: str,
        student_id: int,
        resume_snapshot: dict,
        skill_profile_snapshot: dict | None,
        idempotency_key: str,
    ) -> dict: ...
```

注册入口：

```python
def set_job_application_intake_provider(
    app: Flask,
    provider: JobApplicationIntakeProvider,
) -> None: ...

def get_job_application_intake_provider() -> JobApplicationIntakeProvider: ...
```

默认数据库实现只接受已上架未删除职位，强制 `(student_id, job_id)` 唯一和 `(enterprise_id, idempotency_key)` 幂等，保存投递时快照并返回稳定申请记录。07 不得直接写 09 表或导入内部服务。

## Shared File Changes

| Shared file | Change | Why it cannot be bypassed |
| --- | --- | --- |
| `backend/app/db.py` | 增加职位、申请、状态历史和企业通知发件箱表及索引 | 项目只有一个 SQLite schema 初始化入口 |
| `backend/app/__init__.py` | 安装 09 默认 providers，注册企业消息来源适配器和企业 blueprint | `create_app()` 是 provider、blueprint、保护前缀的唯一装配点 |
| `backend/app/seed_dev.py` | 增加可选企业职位和申请演示数据 | 浏览器验收需要可复现的企业演示数据 |
| `frontend/src/api/types.ts` | 增加 09 DTO 和状态联合类型 | 前端 API 类型集中维护 |
| `frontend/src/router/index.ts` | 注册企业职位、申请和企业看板路由 | Vue Router 是页面可达性的唯一入口 |
| `frontend/src/data/portal-guides.ts` | 企业入口从“后续开放”改为真实 href | 01 首次引导读取该目录 |
| `frontend/src/components/PortalShell.vue` | 增加默认 slot，承载企业看板而不复制 01 门户壳 | 企业页仍需复用既有门户、会话和首次引导行为 |
| `frontend/src/views/EnterprisePortalView.vue` | 从静态 PortalShell 升级为企业看板 | 现有 `/enterprise` 必须成为真实首屏 |

不修改 `frontend/src/api/client.ts`、`frontend/src/stores/auth.ts`、`frontend/src/components/AppHeader.vue`、`frontend/src/styles/tokens.css`；现有请求封装、会话 store、头部和设计 token 已满足 09。

## File Structure

| Path | Responsibility |
| --- | --- |
| `backend/app/enterprise_console/errors.py` | 领域和 provider 错误层级 |
| `backend/app/enterprise_console/providers.py` | `JobPositionProvider`、`JobApplicationIntakeProvider`、数据库实现、set/get/configure |
| `backend/app/enterprise_console/review.py` | 11 通用审核 protocol、不可用占位和注册槽 |
| `backend/app/enterprise_console/notifications.py` | 企业通知发件箱、投递和重试 |
| `backend/app/enterprise_console/jobs.py` | 职位校验、状态机、审核投影、逻辑删除 |
| `backend/app/enterprise_console/applications.py` | 投递接收、筛选、详情、改标、状态历史 |
| `backend/app/enterprise_console/dashboard.py` | 企业范围看板统计 |
| `backend/app/enterprise_console/messaging_provider.py` | 02 私信关系桥接 |
| `backend/app/enterprise_console/routes.py` | `/api/enterprise/*` HTTP 边界和错误映射 |
| `backend/app/enterprise_console/seed.py` | 可选企业演示职位与申请 |
| `backend/app/enterprise_console/__init__.py` | 默认 provider 安装及公开导出 |
| `backend/tests/test_enterprise_foundation.py` | schema、provider、review 注册测试 |
| `backend/tests/test_enterprise_notifications.py` | 发件箱幂等、失败和重试测试 |
| `backend/tests/test_enterprise_jobs.py` | 职位状态机、审核接入和持久化测试 |
| `backend/tests/test_enterprise_job_provider.py` | 07 provider 契约替换测试 |
| `backend/tests/test_enterprise_application_provider.py` | 09-owned 申请接收 provider 的签名、幂等和替换测试 |
| `backend/tests/test_enterprise_applications.py` | 投递、筛选、详情和改标测试 |
| `backend/tests/test_enterprise_deletion.py` | 删除三分支、历史冻结测试 |
| `backend/tests/test_enterprise_messaging_dashboard.py` | 私信范围和看板隔离测试 |
| `backend/tests/test_enterprise_api.py` | 企业 API、会话、越权、错误状态测试 |
| `backend/tests/test_enterprise_integration.py` | 07/11/02 替换与端到端后端测试 |
| `frontend/src/stores/enterpriseConsole.ts` | 企业职位、申请、类别和看板状态 |
| `frontend/src/components/EnterpriseConsoleNav.vue` | 企业工作台导航 |
| `frontend/src/components/EnterpriseDashboardCards.vue` | 看板数据卡片 |
| `frontend/src/components/EnterpriseJobForm.vue` | 职位创建/编辑表单 |
| `frontend/src/components/EnterpriseApplicationStatusBadge.vue` | 申请状态和岗位关闭标识 |
| `frontend/src/views/EnterprisePortalView.vue` | 企业看板首页 |
| `frontend/src/views/EnterpriseJobsView.vue` | 职位列表、筛选、创建、编辑、删除 |
| `frontend/src/views/EnterpriseApplicationsView.vue` | 申请筛选、排序、列表 |
| `frontend/src/views/EnterpriseApplicationDetailView.vue` | 简历、技能档案、改标和私信入口 |
| `frontend/src/stores/enterpriseConsole.test.ts` | 企业 store 测试 |
| `frontend/src/router/enterpriseRoutes.test.ts` | 企业路由和门户入口测试 |
| `frontend/src/views/EnterprisePortalView.test.ts` | 看板视图测试 |
| `frontend/src/views/EnterpriseJobsView.test.ts` | 职位交互测试 |
| `frontend/src/views/EnterpriseApplicationsView.test.ts` | 申请筛选与详情测试 |
| `frontend/src/views/EnterpriseConsoleResponsive.test.ts` | 移动端布局和无横向溢出测试 |

---

### Task 1: Backend Foundation, Schema, Provider and Review Slots

**Files:**
- Create: `backend/app/enterprise_console/__init__.py`
- Create: `backend/app/enterprise_console/errors.py`
- Create: `backend/app/enterprise_console/providers.py`
- Create: `backend/app/enterprise_console/review.py`
- Create: `backend/tests/test_enterprise_foundation.py`
- Modify: `backend/app/db.py`
- Modify: `backend/app/__init__.py`

**Interfaces:**
- Consumes: `Flask`, `current_app`, `get_db()`, existing `SCHEMA_SQL`, existing session manager.
- Produces: `install_default_enterprise_services(app)`, `set_job_position_provider(app, provider)`, `get_job_position_provider()`, `set_job_application_intake_provider(app, provider)`, `get_job_application_intake_provider()`, `set_content_review_provider(app, provider)`, `get_content_review_provider()`, `configure_enterprise_providers(...)`.
- Produces tables: `job_positions`, `job_applications`, `job_application_status_history`, `enterprise_notification_outbox`.

- [ ] **Step 1: Write failing foundation tests**

Create `backend/tests/test_enterprise_foundation.py`:

```python
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.db import get_db
from app.enterprise_console.providers import (
    EmptyJobPositionProvider,
    EmptyJobApplicationIntakeProvider,
    get_job_application_intake_provider,
    get_job_position_provider,
    set_job_application_intake_provider,
    set_job_position_provider,
)
from app.enterprise_console.review import (
    UnavailableContentReviewProvider,
    get_content_review_provider,
    set_content_review_provider,
)


class ReplacementJobProvider:
    def list_published_positions(self):
        return [{"job_id": "job-1"}]

    def get_published_position(self, *, job_id):
        return {"job_id": job_id} if job_id == "job-1" else None


class ReplacementReviewProvider:
    def submit_for_review(self, **kwargs):
        return {"review_status": "pending", "version": 1}

    def get_review_status(self, **kwargs):
        return None

    def approve(self, **kwargs):
        return {"review_status": "approved", "version": 2}

    def reject(self, **kwargs):
        return {"review_status": "rejected", "version": 2}

    def edit(self, **kwargs):
        return {"review_status": "pending", "version": 2}


class ReplacementApplicationProvider:
    def submit_application(self, **kwargs):
        return {"application_id": "application-1", **kwargs}


class TestEnterpriseFoundation(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app({
            "TESTING": True,
            "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
            "SECRET_KEY": "test-only-secret",
        })

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_enterprise_tables_exist(self):
        expected = {
            "job_positions",
            "job_applications",
            "job_application_status_history",
            "enterprise_notification_outbox",
        }
        with self.app.app_context():
            names = {
                row["name"]
                for row in get_db().execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        self.assertTrue(expected.issubset(names))

    def test_default_providers_are_installed(self):
        with self.app.app_context():
            self.assertIsInstance(
                get_job_position_provider(),
                EmptyJobPositionProvider,
            )
            self.assertIsInstance(
                get_job_application_intake_provider(),
                EmptyJobApplicationIntakeProvider,
            )
            self.assertIsInstance(
                get_content_review_provider(),
                UnavailableContentReviewProvider,
            )

    def test_providers_are_replaceable(self):
        job_provider = ReplacementJobProvider()
        application_provider = ReplacementApplicationProvider()
        review_provider = ReplacementReviewProvider()
        set_job_position_provider(self.app, job_provider)
        set_job_application_intake_provider(
            self.app,
            application_provider,
        )
        set_content_review_provider(self.app, review_provider)

        with self.app.app_context():
            self.assertIs(get_job_position_provider(), job_provider)
            self.assertIs(
                get_job_application_intake_provider(),
                application_provider,
            )
            self.assertIs(get_content_review_provider(), review_provider)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_enterprise_foundation -v`

Expected: FAIL because `app.enterprise_console` and the enterprise tables do not exist.

- [ ] **Step 3: Add error, provider and review contracts**

Create `backend/app/enterprise_console/errors.py`:

```python
from __future__ import annotations


class EnterpriseConsoleError(RuntimeError):
    code = "enterprise_console_error"

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class EnterpriseValidationError(EnterpriseConsoleError):
    code = "validation_error"


class EnterpriseNotFoundError(EnterpriseConsoleError):
    code = "not_found"


class EnterpriseConflictError(EnterpriseConsoleError):
    code = "conflict"


class ProviderError(EnterpriseConsoleError):
    code = "provider_error"


class ProviderValidationError(ProviderError):
    code = "provider_validation_error"


class ProviderNotFoundError(ProviderError):
    code = "provider_not_found"


class ProviderConflictError(ProviderError):
    code = "provider_conflict"


class ProviderUnavailableError(ProviderError):
    code = "provider_unavailable"


class ProviderAccessDeniedError(ProviderError):
    code = "provider_access_denied"
```

Create `backend/app/enterprise_console/providers.py`:

```python
from __future__ import annotations

from typing import Protocol

from flask import Flask, current_app


class JobPositionProvider(Protocol):
    def list_published_positions(self) -> list[dict]: ...

    def get_published_position(self, *, job_id: str) -> dict | None: ...


class EmptyJobPositionProvider:
    def list_published_positions(self) -> list[dict]:
        return []

    def get_published_position(self, *, job_id: str) -> dict | None:
        return None


class JobApplicationIntakeProvider(Protocol):
    def submit_application(
        self,
        *,
        job_id: str,
        student_id: int,
        resume_snapshot: dict,
        skill_profile_snapshot: dict | None,
        idempotency_key: str,
    ) -> dict: ...


class EmptyJobApplicationIntakeProvider:
    def submit_application(
        self,
        *,
        job_id: str,
        student_id: int,
        resume_snapshot: dict,
        skill_profile_snapshot: dict | None,
        idempotency_key: str,
    ) -> dict:
        from app.enterprise_console.errors import ProviderUnavailableError

        raise ProviderUnavailableError("申请接收服务暂不可用")


def set_job_position_provider(
    app: Flask,
    provider: JobPositionProvider,
) -> None:
    app.extensions["job_position_provider"] = provider


def get_job_position_provider() -> JobPositionProvider:
    return current_app.extensions.get(
        "job_position_provider",
        EmptyJobPositionProvider(),
    )


def set_job_application_intake_provider(
    app: Flask,
    provider: JobApplicationIntakeProvider,
) -> None:
    app.extensions["job_application_intake_provider"] = provider


def get_job_application_intake_provider() -> JobApplicationIntakeProvider:
    return current_app.extensions.get(
        "job_application_intake_provider",
        EmptyJobApplicationIntakeProvider(),
    )


def configure_enterprise_providers(
    app: Flask,
    *,
    job_position_provider: JobPositionProvider | None = None,
    job_application_intake_provider: JobApplicationIntakeProvider | None = None,
    content_review_provider=None,
) -> None:
    if job_position_provider is not None:
        set_job_position_provider(app, job_position_provider)
    if job_application_intake_provider is not None:
        set_job_application_intake_provider(
            app,
            job_application_intake_provider,
        )
    if content_review_provider is not None:
        from app.enterprise_console.review import set_content_review_provider

        set_content_review_provider(app, content_review_provider)
```

Create `backend/app/enterprise_console/review.py` with the exact frozen protocol and unavailable placeholder:

```python
from __future__ import annotations

from typing import Protocol

from flask import Flask, current_app

from app.enterprise_console.errors import ProviderUnavailableError


class ContentReviewProvider(Protocol):
    def submit_for_review(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        expected_version: int,
        payload: dict,
    ) -> dict: ...

    def get_review_status(
        self,
        *,
        content_type: str,
        content_id: str,
    ) -> dict | None: ...

    def approve(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        reviewer_id: int,
        reviewer_role: str,
        expected_version: int,
    ) -> dict: ...

    def reject(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        reviewer_id: int,
        reviewer_role: str,
        expected_version: int,
        opinion: str,
    ) -> dict: ...

    def edit(
        self,
        *,
        content_type: str,
        content_id: str,
        submitter_id: int,
        expected_version: int,
        payload: dict,
    ) -> dict: ...


class UnavailableContentReviewProvider:
    def _unavailable(self):
        raise ProviderUnavailableError("内容审核服务暂不可用")

    submit_for_review = _unavailable
    get_review_status = _unavailable
    approve = _unavailable
    reject = _unavailable
    edit = _unavailable


def set_content_review_provider(app: Flask, provider: ContentReviewProvider) -> None:
    app.extensions["content_review_provider"] = provider


def get_content_review_provider() -> ContentReviewProvider:
    return current_app.extensions.get(
        "content_review_provider",
        UnavailableContentReviewProvider(),
    )
```

Create `backend/app/enterprise_console/__init__.py`:

```python
from __future__ import annotations

from flask import Flask

from app.enterprise_console.providers import (
    EmptyJobApplicationIntakeProvider,
    EmptyJobPositionProvider,
    get_job_application_intake_provider,
    get_job_position_provider,
    set_job_application_intake_provider,
    set_job_position_provider,
)
from app.enterprise_console.review import (
    UnavailableContentReviewProvider,
    get_content_review_provider,
    set_content_review_provider,
)


def install_default_enterprise_services(app: Flask) -> None:
    if "job_position_provider" not in app.extensions:
        set_job_position_provider(app, EmptyJobPositionProvider())
    if "job_application_intake_provider" not in app.extensions:
        set_job_application_intake_provider(
            app,
            EmptyJobApplicationIntakeProvider(),
        )
    if "content_review_provider" not in app.extensions:
        set_content_review_provider(app, UnavailableContentReviewProvider())


__all__ = [
    "get_content_review_provider",
    "get_job_application_intake_provider",
    "get_job_position_provider",
    "install_default_enterprise_services",
    "set_job_application_intake_provider",
    "set_content_review_provider",
    "set_job_position_provider",
]
```

- [ ] **Step 4: Add the SQLite schema and application installation**

Append to `backend/app/db.py` before the closing `"""` of `SCHEMA_SQL`:

```sql
CREATE TABLE IF NOT EXISTS job_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL UNIQUE,
    enterprise_id INTEGER NOT NULL REFERENCES users(id),
    title TEXT NOT NULL,
    salary TEXT NOT NULL,
    location TEXT NOT NULL,
    category_id INTEGER NOT NULL REFERENCES interest_tags(id),
    category_name TEXT NOT NULL,
    description TEXT NOT NULL,
    review_status TEXT NOT NULL CHECK (
        review_status IN ('pending', 'approved', 'rejected')
    ),
    version INTEGER NOT NULL CHECK (version > 0),
    rejection_opinion TEXT,
    published_at TEXT,
    deleted_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_job_positions_enterprise_status
    ON job_positions(enterprise_id, deleted_at, review_status, updated_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_job_positions_public
    ON job_positions(deleted_at, review_status, published_at DESC, job_id);

CREATE TABLE IF NOT EXISTS job_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id TEXT NOT NULL UNIQUE,
    job_id TEXT NOT NULL REFERENCES job_positions(job_id),
    enterprise_id INTEGER NOT NULL REFERENCES users(id),
    student_id INTEGER NOT NULL REFERENCES users(id),
    student_name TEXT NOT NULL,
    job_title_snapshot TEXT NOT NULL,
    resume_snapshot_json TEXT NOT NULL,
    skill_profile_snapshot_json TEXT,
    skill_profile_attached INTEGER NOT NULL DEFAULT 0 CHECK (
        skill_profile_attached IN (0, 1)
    ),
    status TEXT NOT NULL CHECK (
        status IN ('pending', 'viewed', 'intent', 'unsuitable')
    ),
    status_version INTEGER NOT NULL DEFAULT 1 CHECK (status_version > 0),
    position_closed_at TEXT,
    close_reason TEXT,
    idempotency_key TEXT NOT NULL,
    submitted_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (student_id, job_id),
    UNIQUE (enterprise_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS idx_job_applications_enterprise
    ON job_applications(
        enterprise_id, submitted_at DESC, application_id
    );

CREATE INDEX IF NOT EXISTS idx_job_applications_job_status
    ON job_applications(job_id, status, submitted_at DESC, application_id);

CREATE TABLE IF NOT EXISTS job_application_status_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id TEXT NOT NULL REFERENCES job_applications(application_id),
    sequence_no INTEGER NOT NULL CHECK (sequence_no > 0),
    previous_status TEXT NOT NULL,
    new_status TEXT NOT NULL,
    actor_enterprise_id INTEGER NOT NULL REFERENCES users(id),
    event_id TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    UNIQUE (application_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS enterprise_notification_outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL CHECK (
        event_type IN (
            'application_submitted',
            'application_status',
            'position_closed'
        )
    ),
    event_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'sent')
    ),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    last_error TEXT,
    created_at TEXT NOT NULL,
    sent_at TEXT,
    UNIQUE (event_type, event_id)
);

CREATE INDEX IF NOT EXISTS idx_enterprise_outbox_pending
    ON enterprise_notification_outbox(status, created_at, id);
```

In `backend/app/__init__.py`, import and call `install_default_enterprise_services(app)` after the existing handcraft installation. Do not register the blueprint in this task.

- [ ] **Step 5: Run the test and commit**

Run: `uv run --directory backend python -m unittest tests.test_enterprise_foundation -v`

Expected: PASS.

```bash
git add backend/app/enterprise_console backend/app/db.py backend/app/__init__.py backend/tests/test_enterprise_foundation.py
git commit -m "后端：建立企业工作台领域基础"
```

### Task 2: Notification Outbox with Idempotent Delivery

**Files:**
- Create: `backend/app/enterprise_console/notifications.py`
- Create: `backend/tests/test_enterprise_notifications.py`

**Interfaces:**
- Consumes: `enterprise_notification_outbox`, `get_db()`, `app.messaging.events`.
- Produces: `enqueue_enterprise_notification(db, event_type, event_id, payload) -> int`, `deliver_enterprise_outbox(outbox_id) -> dict`, `deliver_after_commit(outbox_id) -> dict`, `retry_pending_enterprise_notifications(limit=100) -> dict`.

- [ ] **Step 1: Write failing outbox tests**

Create `backend/tests/test_enterprise_notifications.py` with a temp app and one enterprise/student user. Include these exact tests:

```python
def test_status_event_is_enqueued_and_delivered_once(self):
    with self.app.app_context():
        db = get_db()
        outbox_id = enqueue_enterprise_notification(
            db,
            event_type="application_status",
            event_id="status-1",
            payload={
                "student_id": self.student_id,
                "application_id": "application-1",
                "status": "意向沟通",
            },
        )
        db.commit()
    first = deliver_enterprise_outbox(outbox_id)
    second = deliver_enterprise_outbox(outbox_id)

    self.assertEqual(first, {"sent": 1, "already_sent": 0, "failed": 0})
    self.assertEqual(second, {"sent": 0, "already_sent": 1, "failed": 0})
    with self.app.app_context():
        notices = list_notifications(self.student_id)
    self.assertEqual(len(notices), 1)
    self.assertIn("意向沟通", notices[0]["body"])


def test_delivery_failure_keeps_pending_row(self):
    with self.app.app_context():
        db = get_db()
        outbox_id = enqueue_enterprise_notification(
            db,
            event_type="application_submitted",
            event_id="application-1",
            payload={
                "enterprise_id": self.enterprise_id,
                "student_id": self.student_id,
                "application_id": "application-1",
                "student_name": "张同学",
                "job_title": "农业技术员",
            },
        )
        db.commit()

    with patch(
        "app.enterprise_console.notifications.emit_application_submitted",
        side_effect=RuntimeError("offline"),
    ):
        with self.assertRaises(RuntimeError):
            deliver_enterprise_outbox(outbox_id)

    with self.app.app_context():
        row = get_db().execute(
            "SELECT status, attempts FROM enterprise_notification_outbox WHERE id = ?",
            (outbox_id,),
        ).fetchone()
    self.assertEqual(dict(row), {"status": "pending", "attempts": 1})


def test_retry_sends_pending_rows_without_duplicates(self):
    with self.app.app_context():
        db = get_db()
        outbox_id = enqueue_enterprise_notification(
            db,
            event_type="position_closed",
            event_id="job-1:closed",
            payload={
                "student_ids": [self.student_id],
                "position_id": "job-1",
                "job_title": "农业技术员",
            },
        )
        db.commit()
    result = retry_pending_enterprise_notifications(limit=10)
    repeated = retry_pending_enterprise_notifications(limit=10)
    self.assertEqual(result["sent"], 1)
    self.assertEqual(repeated["sent"], 0)
```

The test also asserts the exact `event_type` mapping for all three events.

- [ ] **Step 2: Run the test and verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_enterprise_notifications -v`

Expected: FAIL because `app.enterprise_console.notifications` does not exist.

- [ ] **Step 3: Implement the outbox**

Create `backend/app/enterprise_console/notifications.py`:

```python
from __future__ import annotations

import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from app.enterprise_console.errors import (
    EnterpriseNotFoundError,
    EnterpriseValidationError,
)

LOGGER = logging.getLogger(__name__)
PLATFORM_TIMEZONE = ZoneInfo("Asia/Shanghai")
OUTBOX_EVENT_TYPES = {
    "application_submitted",
    "application_status",
    "position_closed",
}


def _now_iso() -> str:
    return datetime.now(PLATFORM_TIMEZONE).isoformat(timespec="seconds")


def enqueue_enterprise_notification(
    db,
    *,
    event_type: str,
    event_id: str,
    payload: dict,
) -> int:
    normalized_type = str(event_type or "").strip()
    normalized_id = str(event_id or "").strip()
    if normalized_type not in OUTBOX_EVENT_TYPES:
        raise EnterpriseValidationError("通知事件类型不正确")
    if not normalized_id or not isinstance(payload, dict):
        raise EnterpriseValidationError("通知内容格式不正确")
    db.execute(
        """
        INSERT INTO enterprise_notification_outbox (
            event_type, event_id, payload_json, status,
            attempts, last_error, created_at, sent_at
        ) VALUES (?, ?, ?, 'pending', 0, NULL, ?, NULL)
        ON CONFLICT (event_type, event_id) DO NOTHING
        """,
        (
            normalized_type,
            normalized_id,
            json.dumps(payload, ensure_ascii=False),
            _now_iso(),
        ),
    )
    row = db.execute(
        """
        SELECT id
        FROM enterprise_notification_outbox
        WHERE event_type = ? AND event_id = ?
        """,
        (normalized_type, normalized_id),
    ).fetchone()
    return int(row["id"])
```

Add delivery callbacks:

```python
def emit_application_submitted(**payload):
    from app.messaging.events import emit_application_submitted as emit
    return emit(**payload)


def emit_application_status_changed(**payload):
    from app.messaging.events import emit_application_status_changed as emit
    return emit(**payload)


def emit_position_closed(**payload):
    from app.messaging.events import emit_position_closed as emit
    return emit(**payload)
```

Implement `deliver_enterprise_outbox` by loading the row, invoking the matching callback, incrementing `attempts` on failure, and conditionally updating `status='sent'` only where the current status is pending. Implement `deliver_after_commit()` to log and return `{"sent": 0, "already_sent": 0, "failed": 1}` instead of raising. Implement `retry_pending_enterprise_notifications()` with `ORDER BY created_at, id LIMIT ?`.

Use these exact event IDs in later tasks:

```text
application_submitted:{application_id}
application_status:{application_id}:v{status_version}:{status}
position_closed:{job_id}:{application_id}
```

- [ ] **Step 4: Run focused tests**

Run: `uv run --directory backend python -m unittest tests.test_enterprise_notifications -v`

Expected: PASS, including no duplicate rows and retained pending state on failure.

- [ ] **Step 5: Commit**

```bash
git add backend/app/enterprise_console/notifications.py backend/tests/test_enterprise_notifications.py
git commit -m "后端：增加企业通知发件箱"
```

### Task 3: Job Lifecycle, Review Projection and Optimistic Editing

**Files:**
- Create: `backend/app/enterprise_console/jobs.py`
- Create: `backend/tests/test_enterprise_jobs.py`
- Modify: `backend/app/enterprise_console/review.py`
- Modify: `backend/app/enterprise_console/__init__.py`

**Interfaces:**
- Consumes: `get_db()`, `get_content_review_provider()`, `ProviderConflictError`, `ProviderUnavailableError`, 01 `interest_tags` and `users`.
- Produces: `create_job(enterprise_id, payload)`, `list_jobs(enterprise_id, review_status=None)`, `get_job(enterprise_id, job_id)`, `edit_job(enterprise_id, job_id, expected_version, payload)`, `sync_job_review_projection(job_id)`, `serialize_job(row)`.

- [ ] **Step 1: Write failing job lifecycle tests**

Create a deterministic fake review provider:

```python
class FakeReviewProvider:
    def __init__(self):
        self.records = {}
        self.calls = []

    def submit_for_review(
        self, *, content_type, content_id, submitter_id,
        expected_version, payload
    ):
        record = {
            "content_type": content_type,
            "content_id": content_id,
            "review_status": "pending",
            "version": expected_version,
            "submitter_id": submitter_id,
            "rejection_opinion": None,
            "published_at": None,
        }
        self.records[content_id] = record
        self.calls.append(("submit", content_id, expected_version))
        return dict(record)

    def get_review_status(self, *, content_type, content_id):
        record = self.records.get(content_id)
        return dict(record) if record else None

    def approve(self, *, content_type, content_id, submitter_id,
                reviewer_id, reviewer_role, expected_version):
        record = dict(self.records[content_id])
        record["review_status"] = "approved"
        record["version"] = expected_version + 1
        record["published_at"] = "2026-09-18T12:00:00+08:00"
        record["rejection_opinion"] = None
        self.records[content_id] = record
        return dict(record)

    def reject(self, *, content_type, content_id, submitter_id,
               reviewer_id, reviewer_role, expected_version, opinion):
        record = dict(self.records[content_id])
        record["review_status"] = "rejected"
        record["version"] = expected_version + 1
        record["published_at"] = None
        record["rejection_opinion"] = opinion
        self.records[content_id] = record
        return dict(record)

    def edit(self, *, content_type, content_id, submitter_id,
             expected_version, payload):
        record = dict(self.records[content_id])
        record["review_status"] = "pending"
        record["version"] = expected_version + 1
        record["published_at"] = None
        record["rejection_opinion"] = None
        self.records[content_id] = record
        self.calls.append(("edit", content_id, expected_version))
        return dict(record)
```

Test cases:

1. Valid create returns `pending`, provider receives exact payload, and editor list shows it.
2. Pending edit with field change remains pending and version advances.
3. Pending edit with identical values keeps version and produces no provider edit call.
4. Fake provider approve followed by `sync_job_review_projection()` moves row to `approved` with publication time.
5. Fake provider reject followed by sync stores non-empty opinion and keeps `published_at IS NULL`.
6. Editing approved or rejected records returns to `pending`, clears publication/opinion, and syncs version.
7. Old `expected_version` raises `ProviderConflictError`.
8. Unavailable provider causes create/edit rollback and raises `ProviderUnavailableError`.
9. `patch("app.messaging.events.emit_review_result")` is not called by any 09 job operation.

Use the exact migration assertion:

```python
with self.app.app_context():
    before = get_db().execute(
        "SELECT review_status, version, title FROM job_positions WHERE job_id = ?",
        (job_id,),
    ).fetchone()
    with self.assertRaises(ProviderConflictError):
        edit_job(self.enterprise_id, job_id, old_version, changed_payload)
    after = get_db().execute(
        "SELECT review_status, version, title FROM job_positions WHERE job_id = ?",
        (job_id,),
    ).fetchone()
self.assertEqual(dict(after), dict(before))
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_enterprise_jobs -v`

Expected: FAIL because `jobs.py` does not exist.

- [ ] **Step 3: Implement normalized validation and state transitions**

Create `backend/app/enterprise_console/jobs.py` with constants and helpers:

```python
JOB_REVIEW_STATUSES = {"pending", "approved", "rejected"}
JOB_REVIEW_CONTENT_TYPE = "job_position"
JOB_TEXT_LIMITS = {
    "title": 100,
    "salary": 80,
    "location": 120,
    "description": 4000,
}
```

Implement `_normalize_payload(db, payload)`:

- require a dictionary;
- trim all five fields and reject empty values with `EnterpriseValidationError`;
- enforce length limits;
- require `category_id` to be a positive integer and not bool;
- query `interest_tags` for `id`, `group_key='job'`, `is_active=1`;
- return normalized values plus `category_name`;
- preserve the existing category snapshot on edits when the same category ID is supplied.

Implement `_payload_has_changes(row, normalized)` by comparing the five content fields and category ID.

Implement `create_job()`:

```python
job_id = f"job-{uuid.uuid4().hex}"
with db:
    db.execute("BEGIN IMMEDIATE")
    normalized = _normalize_payload(db, payload)
    db.execute(
        """
        INSERT INTO job_positions (
            job_id, enterprise_id, title, salary, location,
            category_id, category_name, description, review_status,
            version, rejection_opinion, published_at, deleted_at,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', 1, NULL, NULL, NULL, ?, ?)
        """,
        (job_id, enterprise_id, *normalized_values, now, now),
    )
    record = get_content_review_provider().submit_for_review(
        content_type=JOB_REVIEW_CONTENT_TYPE,
        content_id=job_id,
        submitter_id=enterprise_id,
        expected_version=1,
        payload=_review_payload(normalized),
    )
    _apply_review_record(db, job_id, record, expected_status="pending")
```

Map provider errors to `ProviderValidationError`, `ProviderConflictError` or `ProviderUnavailableError`; do not catch and suppress them. The `with db` block must roll back on any provider exception.

Implement `edit_job()`:

- select owned, non-deleted row;
- compare current version;
- normalize payload using the current row;
- if no change, return serialized current row;
- call `provider.edit(expected_version=current_version, payload=review_payload)`;
- update all content fields and apply provider result in one transaction;
- after success, call `sync_job_review_projection(job_id)` and return the latest serialized row.

Implement `sync_job_review_projection()`:

```python
record = get_content_review_provider().get_review_status(
    content_type=JOB_REVIEW_CONTENT_TYPE,
    content_id=job_id,
)
if record is None:
    return get_job_by_id(job_id)
if record.get("content_id") != job_id:
    raise ProviderValidationError("审核记录标识不匹配")
if record.get("review_status") not in JOB_REVIEW_STATUSES:
    raise ProviderValidationError("审核状态不正确")
if int(record.get("version", 0)) < local_version:
    raise ProviderConflictError("审核版本已回退")
update projection without changing job content
```

- [ ] **Step 4: Run focused tests**

Run: `uv run --directory backend python -m unittest tests.test_enterprise_jobs -v`

Expected: PASS. Verify create/edit rollback and no review notification call.

- [ ] **Step 5: Commit**

```bash
git add backend/app/enterprise_console/jobs.py backend/app/enterprise_console/review.py backend/app/enterprise_console/__init__.py backend/tests/test_enterprise_jobs.py
git commit -m "后端：实现企业职位审核状态机"
```

### Task 4: Database Job Position Provider for Module 07

**Files:**
- Modify: `backend/app/enterprise_console/providers.py`
- Modify: `backend/app/enterprise_console/jobs.py`
- Modify: `backend/app/enterprise_console/__init__.py`
- Create: `backend/tests/test_enterprise_job_provider.py`

**Interfaces:**
- Consumes: `job_positions`, `users`, `interest_tags`, provider registration slot.
- Produces: `DatabaseJobPositionProvider`, `list_published_position_records()`, `get_published_position_record(job_id)`.

- [ ] **Step 1: Write failing provider contract tests**

Create `backend/tests/test_enterprise_job_provider.py` with seeded jobs in each state. Assert:

```python
self.assertEqual(
    [item["job_id"] for item in provider.list_published_positions()],
    ["job-new", "job-old"],
)
self.assertIsNone(provider.get_published_position(job_id="job-pending"))
self.assertIsNone(provider.get_published_position(job_id="job-deleted"))
self.assertEqual(
    set(provider.get_published_position(job_id="job-old")),
    {
        "job_id", "enterprise_id", "enterprise_name", "title",
        "salary", "location", "category_id", "category_name",
        "description", "review_status", "version", "published_at",
        "updated_at",
    },
)
```

Add a replacement provider test:

```python
replacement = ReplacementProvider()
set_job_position_provider(self.app, replacement)
with self.app.app_context():
    self.assertIs(get_job_position_provider(), replacement)
```

Add an invalid row test proving pending/rejected/deleted rows with stale publication times are omitted and no SQLite primary key appears in output.

- [ ] **Step 2: Run the test and verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_enterprise_job_provider -v`

Expected: FAIL because `DatabaseJobPositionProvider` and public read helpers do not exist.

- [ ] **Step 3: Implement query helpers**

Add to `jobs.py`:

```python
def list_published_position_records() -> list[dict]:
    rows = get_db().execute(
        """
        SELECT
            jp.job_id,
            jp.enterprise_id,
            u.name AS enterprise_name,
            jp.title,
            jp.salary,
            jp.location,
            jp.category_id,
            jp.category_name,
            jp.description,
            jp.review_status,
            jp.version,
            jp.published_at,
            jp.updated_at
        FROM job_positions jp
        JOIN users u ON u.id = jp.enterprise_id
        WHERE jp.review_status = 'approved'
          AND jp.deleted_at IS NULL
          AND jp.published_at IS NOT NULL
          AND trim(jp.published_at) <> ''
        ORDER BY jp.published_at DESC, jp.job_id ASC
        """
    ).fetchall()
    return [_visible_position_payload(row) for row in rows]


def get_published_position_record(job_id: str) -> dict | None:
    normalized = str(job_id or "").strip()
    if not normalized:
        return None
    row = get_db().execute(
        """
        SELECT
            jp.job_id,
            jp.enterprise_id,
            u.name AS enterprise_name,
            jp.title,
            jp.salary,
            jp.location,
            jp.category_id,
            jp.category_name,
            jp.description,
            jp.review_status,
            jp.version,
            jp.published_at,
            jp.updated_at
        FROM job_positions jp
        JOIN users u ON u.id = jp.enterprise_id
        WHERE jp.job_id = ?
          AND jp.review_status = 'approved'
          AND jp.deleted_at IS NULL
          AND jp.published_at IS NOT NULL
          AND trim(jp.published_at) <> ''
        """,
        (normalized,),
    ).fetchone()
    return _visible_position_payload(row) if row is not None else None
```

`_visible_position_payload()` must cast IDs and versions to `int`, require non-empty text fields, and return a new dict with only the frozen fields. Invalid rows are omitted from the list rather than partially returned.

- [ ] **Step 4: Replace the default provider and run tests**

Add `DatabaseJobPositionProvider` to `providers.py` with a lazy import:

```python
class DatabaseJobPositionProvider:
    def list_published_positions(self) -> list[dict]:
        from app.enterprise_console.jobs import list_published_position_records
        return list_published_position_records()

    def get_published_position(self, *, job_id: str) -> dict | None:
        from app.enterprise_console.jobs import get_published_position_record
        return get_published_position_record(job_id)
```

Change `install_default_enterprise_services()` to install `DatabaseJobPositionProvider()` instead of `EmptyJobPositionProvider`.

Run: `uv run --directory backend python -m unittest tests.test_enterprise_job_provider tests.test_enterprise_foundation -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/enterprise_console/providers.py backend/app/enterprise_console/jobs.py backend/app/enterprise_console/__init__.py backend/tests/test_enterprise_job_provider.py
git commit -m "后端：实现岗位生产者 provider"
```

---
### Task 5: Application Intake, Snapshots, Filters and Status Marking

**Files:**
- Create: `backend/app/enterprise_console/applications.py`
- Create: `backend/tests/test_enterprise_application_provider.py`
- Create: `backend/tests/test_enterprise_applications.py`
- Modify: `backend/app/enterprise_console/providers.py`
- Modify: `backend/app/enterprise_console/__init__.py`
- Modify: `backend/tests/test_enterprise_foundation.py`

**Interfaces:**
- Consumes: approved `job_positions`, `users`, enterprise notification outbox, 02 event signatures.
- Produces: `record_application_submission(...)`, `DatabaseJobApplicationIntakeProvider`, `list_applications(enterprise_id, filters)`, `get_application(enterprise_id, application_id)`, `change_application_status(...)`, `serialize_application(row)`.

- [ ] **Step 1: Write failing application tests**

Create `backend/tests/test_enterprise_applications.py` with helper functions that create two enterprises, two students, one approved job, and snapshot dictionaries.

Test 1: submission stores immutable snapshots and enqueues one enterprise notice.

```python
with self.app.app_context():
    application = record_application_submission(
        job_id=self.job_id,
        student_id=self.student_id,
        resume_snapshot={"education": ["A"], "skills": ["直播"]},
        skill_profile_snapshot={"items": [{"title": "直播训练", "score": 90}]},
        idempotency_key="07-request-1",
    )
    repeated = record_application_submission(
        job_id=self.job_id,
        student_id=self.student_id,
        resume_snapshot={"education": ["DIFFERENT"]},
        skill_profile_snapshot=None,
        idempotency_key="07-request-1",
    )
    notices = list_notifications(self.enterprise_id)

self.assertEqual(application["application_id"], repeated["application_id"])
self.assertEqual(
    application["resume_snapshot"],
    {"education": ["A"], "skills": ["直播"]},
)
self.assertEqual(len(notices), 1)
```

Add `test_enterprise_application_provider.py` to prove signature replacement and delegation:

```python
class ReplacementIntakeProvider:
    def __init__(self):
        self.calls = []

    def submit_application(self, **kwargs):
        self.calls.append(kwargs)
        return {"application_id": "application-replacement", **kwargs}


def test_application_intake_provider_is_replaceable(self):
    replacement = ReplacementIntakeProvider()
    set_job_application_intake_provider(self.app, replacement)
    with self.app.app_context():
        result = get_job_application_intake_provider().submit_application(
            job_id="job-1",
            student_id=self.student_id,
            resume_snapshot={"education": ["A"]},
            skill_profile_snapshot=None,
            idempotency_key="07-request-1",
        )
    self.assertEqual(result["application_id"], "application-replacement")
    self.assertEqual(replacement.calls[0]["job_id"], "job-1")
```

Test 2: pending/rejected/deleted jobs reject submission; duplicate student-job submission returns the existing record without a second notification.

Test 3: list filtering by job, status and inclusive Shanghai date range; default sort is submission time descending and application ID ascending.

Test 4: detail returns resume and attached visible skill profile. A missing profile and an attached empty profile both serialize `skill_profile=None` and `skill_profile_attached=False`.

Test 5: status changes through the exact allowed graph:

```python
pending -> viewed
pending -> intent
pending -> unsuitable
viewed -> intent
intent -> unsuitable
unsuitable -> viewed
```

Assert each real change advances `status_version`, inserts one history row, updates the latest status, and creates exactly one student notification. Repeated same status returns `changed=False`, does not increment version and does not add a notification.

Test 6: `pending` is rejected as a manual target; after `position_closed_at` is set, any status change raises `EnterpriseConflictError`; old `expected_version` raises `ProviderConflictError`.

- [ ] **Step 2: Run the test and verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_enterprise_applications tests.test_enterprise_application_provider -v`

Expected: FAIL because `applications.py` does not exist.

- [ ] **Step 3: Implement submission and snapshot normalization**

Create `backend/app/enterprise_console/applications.py` with constants:

```python
APPLICATION_STATUSES = {"pending", "viewed", "intent", "unsuitable"}
MANUAL_STATUSES = {"viewed", "intent", "unsuitable"}
STATUS_LABELS = {
    "pending": "待处理",
    "viewed": "已查看",
    "intent": "意向沟通",
    "unsuitable": "不合适",
}
PLATFORM_TIMEZONE = ZoneInfo("Asia/Shanghai")
```

Implement `record_application_submission()`:

```python
def record_application_submission(
    *,
    job_id: str,
    student_id: int,
    resume_snapshot: dict,
    skill_profile_snapshot: dict | None,
    idempotency_key: str,
) -> dict:
```

Validation and idempotency rules:

- `job_id` and `idempotency_key` are trimmed non-empty strings.
- `student_id` is a positive int and the user exists with role `student`.
- resume snapshot is a non-empty dict and is serialized with `ensure_ascii=False`.
- attached is true only when skill snapshot is a dict with at least one visible item; empty dict, `None`, or an object whose `items` list is empty becomes `None` and false.
- the job exists, is approved, has `published_at`, and is not deleted.
- `(student_id, job_id)` unique conflict returns the existing record.
- `(enterprise_id, idempotency_key)` conflict returns the existing record when the job/student match; otherwise raises `ProviderConflictError`.
- one outbox event `application_submitted:{application_id}` is inserted in the same transaction.

Use this insertion skeleton:

```python
application_id = f"application-{uuid.uuid4().hex}"
now = _now_iso()
with db:
    db.execute("BEGIN IMMEDIATE")
    row = _find_job(db, normalized_job_id)
    _validate_visible_job(row)
    existing = _find_idempotent_application(
        db, int(row["enterprise_id"]), idempotency_key
    )
    if existing is not None:
        return _serialize_application(existing)
    db.execute(
        """
        INSERT INTO job_applications (
            application_id, job_id, enterprise_id, student_id,
            student_name, job_title_snapshot, resume_snapshot_json,
            skill_profile_snapshot_json, skill_profile_attached,
            status, status_version, position_closed_at, close_reason,
            idempotency_key, submitted_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 1, NULL, NULL, ?, ?, ?)
        """,
        (
            application_id,
            job_id,
            int(row["enterprise_id"]),
            student_id,
            student_name,
            str(row["title"]),
            json.dumps(resume_snapshot, ensure_ascii=False),
            skill_json,
            int(skill_json is not None),
            idempotency_key,
            now,
            now,
        ),
    )
    outbox_id = enqueue_enterprise_notification(
        db,
        event_type="application_submitted",
        event_id=f"application_submitted:{application_id}",
        payload={
            "enterprise_id": int(row["enterprise_id"]),
            "student_id": student_id,
            "application_id": application_id,
            "student_name": student_name,
            "job_title": str(row["title"]),
        },
    )
deliver_after_commit(outbox_id)
return application
```

Add the producer adapter to `providers.py`:

```python
class DatabaseJobApplicationIntakeProvider:
    def submit_application(
        self,
        *,
        job_id: str,
        student_id: int,
        resume_snapshot: dict,
        skill_profile_snapshot: dict | None,
        idempotency_key: str,
    ) -> dict:
        from app.enterprise_console.applications import (
            record_application_submission,
        )

        return record_application_submission(
            job_id=job_id,
            student_id=student_id,
            resume_snapshot=resume_snapshot,
            skill_profile_snapshot=skill_profile_snapshot,
            idempotency_key=idempotency_key,
        )
```

Change `install_default_enterprise_services()` to install `DatabaseJobApplicationIntakeProvider()` in the `job_application_intake_provider` slot. Keep `EmptyJobApplicationIntakeProvider` only as the explicit unavailable test seam.

Update `test_default_providers_are_installed()` to import and assert `DatabaseJobApplicationIntakeProvider` for the running application; keep a separate explicit test proving `EmptyJobApplicationIntakeProvider` raises `ProviderUnavailableError` when selected.

- [ ] **Step 4: Implement filtering, detail and status transitions**

`list_applications()` accepts:

```python
{
    "job_id": str | None,
    "status": str | None,
    "submitted_from": date | None,
    "submitted_to": date | None,
    "sort": "submitted_desc" | "submitted_asc",
}
```

Validate status values and date order. Convert date boundaries to `Asia/Shanghai`; query with `julianday(submitted_at)`. Return summaries containing:

```text
application_id, student_id, student_name, job_id, job_title,
submitted_at, status, status_label, status_version,
position_closed, position_closed_at, effective_status, effective_status_label
```

For `status='pending' AND position_closed_at IS NOT NULL`, `effective_status='closed'` and label is `岗位已关闭`. All other effective statuses use the latest business status; when closed, `position_closed=True`.

`get_application()` returns the summary plus:

```text
resume_snapshot, skill_profile, skill_profile_attached, status_history
```

Status history is ordered by `sequence_no ASC` and contains:

```text
sequence_no, previous_status, new_status, actor_enterprise_id, event_id, created_at
```

`change_application_status()` skeleton:

```python
with db:
    db.execute("BEGIN IMMEDIATE")
    row = _owned_application(db, enterprise_id, application_id)
    _require_status_version(row, expected_version)
    if row["position_closed_at"] is not None:
        raise EnterpriseConflictError("岗位已关闭，申请状态不可再变更")
    if status not in MANUAL_STATUSES:
        raise EnterpriseValidationError("申请状态不正确")
    if status == row["status"]:
        return {"application": _serialize_application(row), "changed": False}
    next_version = int(row["status_version"]) + 1
    event_id = (
        f"application_status:{application_id}:"
        f"v{next_version}:{status}"
    )
    db.execute(
        """
        UPDATE job_applications
        SET status = ?, status_version = ?, updated_at = ?
        WHERE application_id = ? AND enterprise_id = ? AND status_version = ?
        """,
        (status, next_version, now, application_id, enterprise_id, expected_version),
    )
    db.execute(
        """
        INSERT INTO job_application_status_history (
            application_id, sequence_no, previous_status, new_status,
            actor_enterprise_id, event_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            application_id,
            next_version,
            str(row["status"]),
            status,
            enterprise_id,
            event_id,
            now,
        ),
    )
    outbox_id = enqueue_enterprise_notification(
        db,
        event_type="application_status",
        event_id=event_id,
        payload={
            "student_id": int(row["student_id"]),
            "application_id": application_id,
            "status": STATUS_LABELS[status],
        },
    )
deliver_after_commit(outbox_id)
```

Use a conditional update and verify `rowcount == 1`; a zero row count raises `ProviderConflictError` before history/outbox insertion.

- [ ] **Step 5: Run tests and commit**

Run: `uv run --directory backend python -m unittest tests.test_enterprise_applications -v`

Expected: PASS with exactly one notification per real status change.

```bash
git add backend/app/enterprise_console/applications.py backend/app/enterprise_console/providers.py backend/app/enterprise_console/__init__.py backend/tests/test_enterprise_applications.py backend/tests/test_enterprise_application_provider.py backend/tests/test_enterprise_foundation.py
git commit -m "后端：实现投递处理与状态改标"
```

### Task 6: Job Deletion and Application History Matrix

**Files:**
- Modify: `backend/app/enterprise_console/jobs.py`
- Modify: `backend/app/enterprise_console/applications.py`
- Create: `backend/tests/test_enterprise_deletion.py`

**Interfaces:**
- Consumes: `job_positions`, `job_applications`, notification outbox.
- Produces: `delete_job(enterprise_id, job_id, expected_version=None)`, `close_applications_for_deleted_job(db, job_row, now) -> dict`.

- [ ] **Step 1: Write failing deletion matrix tests**

Create four applications against each test job:

```text
pending + never marked
viewed
intent
unsuitable
```

Delete the job and assert:

```python
result = delete_job(self.enterprise_id, self.job_id, expected_version=1)
self.assertEqual(result["deleted"], True)
self.assertEqual(result["closed_application_count"], 1)
self.assertEqual(result["historical_application_count"], 3)
self.assertIsNone(
    list_published_position_records()
)
```

For the pending application:

- `position_closed_at` is non-null;
- `status` remains `pending` for audit;
- `status_version` advances;
- effective status is `closed`;
- exactly one `position_closed` notification exists;
- a second status change raises `EnterpriseConflictError`.

For each handled application:

- `status` remains `viewed`/`intent`/`unsuitable`;
- `position_closed_at` is non-null;
- `status_version` advances;
- effective status remains the handled label with `position_closed=True`;
- no automatic status notification is added.

Add no-application and repeated-delete cases:

```python
self.assertEqual(delete_job(...), {
    "deleted": True,
    "changed": True,
    "closed_application_count": 0,
    "historical_application_count": 0,
    "notification_count": 0,
})
self.assertEqual(repeated["changed"], False)
self.assertEqual(repeated["notification_count"], 0)
```

Also test that filter options still resolve a deleted job title from `job_title_snapshot`.

- [ ] **Step 2: Run the test and verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_enterprise_deletion -v`

Expected: FAIL because `delete_job()` and closure helpers do not exist.

- [ ] **Step 3: Implement the transactional closure helper**

Add to `applications.py`:

```python
def close_applications_for_deleted_job(db, job_row, now: str) -> dict:
    rows = db.execute(
        """
        SELECT *
        FROM job_applications
        WHERE job_id = ?
        ORDER BY id
        """,
        (str(job_row["job_id"]),),
    ).fetchall()
    closed = 0
    historical = 0
    notification_count = 0
    outbox_ids = []
    for row in rows:
        if row["position_closed_at"] is not None:
            continue
        next_version = int(row["status_version"]) + 1
        db.execute(
            """
            UPDATE job_applications
            SET position_closed_at = ?,
                close_reason = 'position_deleted',
                status_version = ?,
                updated_at = ?
            WHERE application_id = ? AND position_closed_at IS NULL
            """,
            (
                now,
                next_version,
                now,
                str(row["application_id"]),
            ),
        )
        if row["status"] == "pending":
            closed += 1
            event_id = (
                f"position_closed:{job_row['job_id']}:"
                f"{row['application_id']}"
            )
            outbox_ids.append(
                enqueue_enterprise_notification(
                    db,
                    event_type="position_closed",
                    event_id=event_id,
                    payload={
                        "student_ids": [int(row["student_id"])],
                        "position_id": str(job_row["job_id"]),
                        "job_title": str(row["job_title_snapshot"]),
                    },
                )
            )
            notification_count += 1
        else:
            historical += 1
    return {
        "closed_application_count": closed,
        "historical_application_count": historical,
        "notification_count": notification_count,
        "outbox_ids": outbox_ids,
    }
```

- [ ] **Step 4: Implement logical deletion**

Add `delete_job()` to `jobs.py`:

```python
def delete_job(
    enterprise_id: int,
    job_id: str,
    expected_version: int | None = None,
) -> dict:
    db = get_db()
    with db:
        db.execute("BEGIN IMMEDIATE")
        row = _owned_job(db, enterprise_id, job_id, include_deleted=True)
        if row["deleted_at"] is not None:
            return {
                "deleted": True,
                "changed": False,
                "closed_application_count": 0,
                "historical_application_count": 0,
                "notification_count": 0,
            }
        if expected_version is not None:
            _require_version(row, expected_version)
        now = _now_iso()
        closure = close_applications_for_deleted_job(db, row, now)
        cursor = db.execute(
            """
            UPDATE job_positions
            SET deleted_at = ?, updated_at = ?
            WHERE job_id = ? AND enterprise_id = ? AND deleted_at IS NULL
            """,
            (now, now, str(job_id), enterprise_id),
        )
        if cursor.rowcount != 1:
            raise ProviderConflictError("职位状态已变化")
        result = {
            "deleted": True,
            "changed": True,
            "closed_application_count": closure["closed_application_count"],
            "historical_application_count": closure["historical_application_count"],
            "notification_count": closure["notification_count"],
        }
    for outbox_id in closure["outbox_ids"]:
        deliver_after_commit(outbox_id)
    return result
```

Import `close_applications_for_deleted_job` lazily inside the function to avoid a module cycle.

- [ ] **Step 5: Run tests and commit**

Run: `uv run --directory backend python -m unittest tests.test_enterprise_deletion -v`

Expected: PASS for no applications, pending-only, handled-only, mixed and repeated deletion.

```bash
git add backend/app/enterprise_console/jobs.py backend/app/enterprise_console/applications.py backend/tests/test_enterprise_deletion.py
git commit -m "后端：实现职位删除与申请关闭分支"
```

### Task 7: Messaging Relationship Provider and Enterprise Dashboard

**Files:**
- Create: `backend/app/enterprise_console/messaging_provider.py`
- Create: `backend/app/enterprise_console/dashboard.py`
- Create: `backend/tests/test_enterprise_messaging_dashboard.py`
- Modify: `backend/app/__init__.py`
- Modify: `backend/app/enterprise_console/__init__.py`

**Interfaces:**
- Consumes: 02 `register_messaging_source_provider`, `job_applications`.
- Produces: `EnterpriseMessagingProvider`, `get_dashboard(enterprise_id)`.

- [ ] **Step 1: Write failing messaging and dashboard tests**

Create two enterprise/student pairs. Submit applications to enterprise A, including one from a deleted job. Assert:

```python
provider = EnterpriseMessagingProvider()
self.assertTrue(provider.has_application_relationship(student_a, enterprise_a))
self.assertFalse(provider.has_application_relationship(student_b, enterprise_a))
self.assertEqual(provider.list_applied_enterprise_ids(student_a), [enterprise_a])
self.assertEqual(provider.list_applicant_student_ids(enterprise_a), [student_a])
```

Verify the provider is bridged into `get_messaging_source_provider()` after `create_app()` and that `messaging_relationship(student_a, enterprise_a) == "application"`.

Dashboard assertions:

```python
self.assertEqual(get_dashboard(enterprise_a), {
    "active_job_count": 1,
    "received_resume_count": 5,
})
```

Seed two approved not-deleted jobs, one pending job, one deleted job and five applications for enterprise A including a deleted-job application; enterprise B must not affect the counts.

- [ ] **Step 2: Run the test and verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_enterprise_messaging_dashboard -v`

Expected: FAIL because the provider and dashboard module do not exist.

- [ ] **Step 3: Implement the 02 bridge**

Create `backend/app/enterprise_console/messaging_provider.py`:

```python
from __future__ import annotations

from app.db import get_db
from app.messaging.source_provider import NullMessagingSourceProvider


class EnterpriseMessagingProvider(NullMessagingSourceProvider):
    def has_application_relationship(
        self, student_id: int, enterprise_id: int
    ) -> bool:
        row = get_db().execute(
            """
            SELECT 1
            FROM job_applications
            WHERE student_id = ? AND enterprise_id = ?
            LIMIT 1
            """,
            (student_id, enterprise_id),
        ).fetchone()
        return row is not None

    def list_applied_enterprise_ids(self, student_id: int) -> list[int]:
        return [
            int(row["enterprise_id"])
            for row in get_db().execute(
                """
                SELECT DISTINCT enterprise_id
                FROM job_applications
                WHERE student_id = ?
                ORDER BY enterprise_id
                """,
                (student_id,),
            ).fetchall()
        ]

    def list_applicant_student_ids(self, enterprise_id: int) -> list[int]:
        return [
            int(row["student_id"])
            for row in get_db().execute(
                """
                SELECT DISTINCT student_id
                FROM job_applications
                WHERE enterprise_id = ?
                ORDER BY student_id
                """,
                (enterprise_id,),
            ).fetchall()
        ]
```

In `create_app()`, after registering the agri messaging provider, call:

```python
from app.enterprise_console.messaging_provider import EnterpriseMessagingProvider
register_messaging_source_provider(app, EnterpriseMessagingProvider())
```

Do not alter the existing `MessagingSourceProvider` protocol or `CompositeMessagingSourceProvider`.

- [ ] **Step 4: Implement dashboard metrics**

Create `backend/app/enterprise_console/dashboard.py`:

```python
from __future__ import annotations

from app.db import get_db
from app.enterprise_console.errors import EnterpriseValidationError


def get_dashboard(enterprise_id: int) -> dict:
    if (
        isinstance(enterprise_id, bool)
        or not isinstance(enterprise_id, int)
        or enterprise_id <= 0
    ):
        raise EnterpriseValidationError("企业标识必须是正整数")
    db = get_db()
    active = db.execute(
        """
        SELECT COUNT(*) AS total
        FROM job_positions
        WHERE enterprise_id = ?
          AND review_status = 'approved'
          AND deleted_at IS NULL
          AND published_at IS NOT NULL
          AND trim(published_at) <> ''
        """,
        (enterprise_id,),
    ).fetchone()
    received = db.execute(
        """
        SELECT COUNT(*) AS total
        FROM job_applications
        WHERE enterprise_id = ?
        """,
        (enterprise_id,),
    ).fetchone()
    return {
        "active_job_count": int(active["total"]),
        "received_resume_count": int(received["total"]),
    }
```

Export both symbols in `backend/app/enterprise_console/__init__.py`.

- [ ] **Step 5: Run tests and commit**

Run: `uv run --directory backend python -m unittest tests.test_enterprise_messaging_dashboard -v`

Expected: PASS with no cross-enterprise counts and relationship preserved after deletion.

```bash
git add backend/app/enterprise_console/messaging_provider.py backend/app/enterprise_console/dashboard.py backend/app/enterprise_console/__init__.py backend/app/__init__.py backend/tests/test_enterprise_messaging_dashboard.py
git commit -m "后端：接入企业私信关系与看板"
```

### Task 8: Enterprise HTTP API, Session Scoping and Error Mapping

**Files:**
- Create: `backend/app/enterprise_console/routes.py`
- Create: `backend/tests/test_enterprise_api.py`
- Modify: `backend/app/__init__.py`
- Modify: `backend/app/enterprise_console/__init__.py`

**Interfaces:**
- Consumes: jobs/applications/dashboard services, 01 `load_session`.
- Produces blueprint `enterprise_console_bp` at `/api/enterprise`.

- [ ] **Step 1: Write failing API tests**

Create `backend/tests/test_enterprise_api.py` and assert the exact route table:

```python
expected = {
    "/api/enterprise/dashboard": {"GET"},
    "/api/enterprise/jobs": {"GET", "POST"},
    "/api/enterprise/jobs/<job_id>": {"GET", "PUT", "DELETE"},
    "/api/enterprise/applications": {"GET"},
    "/api/enterprise/applications/<application_id>": {"GET"},
    "/api/enterprise/applications/<application_id>/status": {"PATCH"},
}
```

Test session and ownership:

- anonymous requests return 401;
- teacher/student/admin requests cannot access enterprise routes;
- enterprise A cannot read or modify enterprise B job/application;
- body `enterprise_id` is ignored when it conflicts with session identity;
- missing objects return 404 without leaking cross-enterprise existence.

Test request payloads:

```python
POST /api/enterprise/jobs
{"title": "农业技术员", "salary": "6k-8k", "location": "广州",
 "category_id": 9, "description": "负责田间管理"}

PUT /api/enterprise/jobs/job-1
{"expected_version": 1, "title": "...", "salary": "...",
 "location": "...", "category_id": 9, "description": "..."}

PATCH /api/enterprise/applications/application-1/status
{"expected_version": 1, "status": "intent"}
```

Assert successful statuses are `201` for create and `200` for list/detail/edit/status/delete. Error mapping:

```text
EnterpriseValidationError -> 400
EnterpriseNotFoundError   -> 404
ProviderAccessDeniedError -> 403
ProviderConflictError      -> 409
ProviderUnavailableError   -> 503
```

Also test that a user-supplied `enterprise_id`, `review_status`, `version` or `status_version` cannot override server-authoritative values.

- [ ] **Step 2: Run the test and verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_enterprise_api -v`

Expected: FAIL because no enterprise blueprint is registered.

- [ ] **Step 3: Implement the blueprint and session helper**

Create `backend/app/enterprise_console/routes.py` with:

```python
enterprise_console_bp = Blueprint(
    "enterprise_console",
    __name__,
    url_prefix="/api/enterprise",
)


def _enterprise_session() -> dict:
    session = load_session(required=True, allowed_states={"active"})
    if session["role"] != "enterprise":
        abort_session_required()
    get_db().commit()
    return session


def _json_object_payload() -> dict:
    payload = request.get_json(silent=True)
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise EnterpriseValidationError(
            "请求体格式不正确",
            details={"body": "请求体必须是 JSON 对象"},
        )
    return payload
```

Implement routes:

```text
GET    /dashboard
GET    /jobs?review_status=pending|approved|rejected
POST   /jobs
GET    /jobs/<job_id>
PUT    /jobs/<job_id>
DELETE /jobs/<job_id>
GET    /applications?job_id=&status=&submitted_from=&submitted_to=&sort=
GET    /applications/<application_id>
PATCH  /applications/<application_id>/status
```

Each route calls `_enterprise_session()` and passes `int(session["id"])` as `enterprise_id`. `DELETE /jobs/<job_id>` passes `expected_version` only when provided; the frontend always provides the current version. `GET /jobs/<job_id>` calls `sync_job_review_projection()` before reading.

Register error handlers with `app.register_error_handler()`:

```python
def register_enterprise_console_error_handlers(app: Flask) -> None:
    app.register_error_handler(EnterpriseValidationError, _handle_validation)
    app.register_error_handler(EnterpriseNotFoundError, _handle_not_found)
    app.register_error_handler(ProviderAccessDeniedError, _handle_access_denied)
    app.register_error_handler(ProviderConflictError, _handle_conflict)
    app.register_error_handler(ProviderUnavailableError, _handle_unavailable)
```

Responses always use:

```json
{
  "success": false,
  "message": "stable message",
  "errors": {}
}
```

- [ ] **Step 4: Register the blueprint and run the API suite**

In `backend/app/__init__.py`:

- import `enterprise_console_bp` and `register_enterprise_console_error_handlers`;
- register the blueprint;
- register the error handlers;
- leave `/api/enterprise` in `PROTECTED_API_PREFIXES`.

Run:

```bash
uv run --directory backend python -m unittest tests.test_enterprise_api tests.test_enterprise_messaging_dashboard tests.test_enterprise_job_provider -v
```

Expected: PASS.

Then run the complete backend suite:

```bash
uv run --directory backend python -m unittest discover -s tests -v
```

Expected: all existing and new tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/enterprise_console/routes.py backend/app/enterprise_console/__init__.py backend/app/__init__.py backend/tests/test_enterprise_api.py
git commit -m "后端：开放企业工作台接口"
```

---

### Task 9: Frontend DTOs, Enterprise Store and API Mapping

**Files:**
- Modify: `frontend/src/api/types.ts`
- Create: `frontend/src/stores/enterpriseConsole.ts`
- Create: `frontend/src/stores/enterpriseConsole.test.ts`

**Interfaces:**
- Consumes: `/api/enterprise/*`, `/api/interest-tags`, shared `apiFetch`.
- Produces: `useEnterpriseConsoleStore`, 09 DTOs and status union types.

- [ ] **Step 1: Write failing store tests**

Create `frontend/src/stores/enterpriseConsole.test.ts` with the existing `vi.mock('@/api/client')` pattern and assert exact requests:

```typescript
it('loads dashboard, job categories and jobs', async () => {
  mockedApiFetch
    .mockResolvedValueOnce({
      success: true,
      dashboard: { active_job_count: 2, received_resume_count: 5 }
    } as never)
    .mockResolvedValueOnce({
      success: true,
      tags: [
        { id: 9, group_key: 'job', name: '农业技术员' },
        { id: 1, group_key: 'crop', name: '荔枝' }
      ]
    } as never)
    .mockResolvedValueOnce({ success: true, jobs: [] } as never)

  const store = useEnterpriseConsoleStore()
  await store.loadDashboard()
  await store.loadJobCategories()
  await store.loadJobs('pending')

  expect(mockedApiFetch).toHaveBeenNthCalledWith(1, '/api/enterprise/dashboard')
  expect(mockedApiFetch).toHaveBeenNthCalledWith(2, '/api/interest-tags')
  expect(mockedApiFetch).toHaveBeenNthCalledWith(
    3,
    '/api/enterprise/jobs?review_status=pending'
  )
  expect(store.jobCategories).toEqual([
    { id: 9, group_key: 'job', name: '农业技术员' }
  ])
})
```

Add tests for:

- `createJob()` posts only the five editable fields;
- `editJob()` sends `expected_version`;
- `deleteJob()` sends `expected_version`;
- `loadApplications()` serializes job/status/date/sort query parameters and omits blanks;
- `changeApplicationStatus()` sends `expected_version` and updates `activeApplication`;
- API errors populate `error` without clearing existing loaded data.

- [ ] **Step 2: Run the test and verify it fails**

Run: `cd frontend; npm test -- src/stores/enterpriseConsole.test.ts`

Expected: FAIL because the store does not exist.

- [ ] **Step 3: Add exact DTOs**

Append to `frontend/src/api/types.ts`:

```typescript
export type JobReviewStatus = 'pending' | 'approved' | 'rejected'
export type ApplicationStatus =
  | 'pending'
  | 'viewed'
  | 'intent'
  | 'unsuitable'
export type EffectiveApplicationStatus = ApplicationStatus | 'closed'

export interface EnterpriseDashboard {
  active_job_count: number
  received_resume_count: number
}

export interface EnterpriseJobPayload {
  title: string
  salary: string
  location: string
  category_id: number
  description: string
}

export interface EnterpriseJob extends EnterpriseJobPayload {
  job_id: string
  enterprise_id: number
  category_name: string
  review_status: JobReviewStatus
  version: number
  rejection_opinion: string | null
  published_at: string | null
  deleted_at: string | null
  created_at: string
  updated_at: string
}

export interface EnterpriseApplicationSummary {
  application_id: string
  student_id: number
  student_name: string
  job_id: string
  job_title: string
  submitted_at: string
  status: ApplicationStatus
  status_label: string
  status_version: number
  position_closed: boolean
  position_closed_at: string | null
  effective_status: EffectiveApplicationStatus
  effective_status_label: string
}

export interface ApplicationStatusHistory {
  sequence_no: number
  previous_status: ApplicationStatus
  new_status: ApplicationStatus
  actor_enterprise_id: number
  event_id: string
  created_at: string
}

export interface EnterpriseApplicationDetail
  extends EnterpriseApplicationSummary {
  resume_snapshot: Record<string, unknown>
  skill_profile: Record<string, unknown> | null
  skill_profile_attached: boolean
  status_history: ApplicationStatusHistory[]
}

export interface EnterpriseApplicationFilters {
  job_id?: string
  status?: ApplicationStatus
  submitted_from?: string
  submitted_to?: string
  sort?: 'submitted_desc' | 'submitted_asc'
}
```

- [ ] **Step 4: Implement the Pinia store**

Create `frontend/src/stores/enterpriseConsole.ts` with state:

```typescript
interface EnterpriseConsoleState {
  dashboard: EnterpriseDashboard
  jobs: EnterpriseJob[]
  jobReviewFilter: JobReviewStatus | 'all'
  jobCategories: InterestTag[]
  applications: EnterpriseApplicationSummary[]
  applicationFilters: EnterpriseApplicationFilters
  activeApplication: EnterpriseApplicationDetail | null
  loading: boolean
  saving: boolean
  error: string
}
```

Expose actions:

```typescript
loadDashboard(): Promise<boolean>
loadJobCategories(): Promise<boolean>
loadJobs(reviewStatus?: JobReviewStatus | 'all'): Promise<boolean>
createJob(payload: EnterpriseJobPayload): Promise<EnterpriseJob | null>
editJob(jobId: string, expectedVersion: number, payload: EnterpriseJobPayload): Promise<EnterpriseJob | null>
deleteJob(job: EnterpriseJob): Promise<boolean>
loadApplications(filters?: EnterpriseApplicationFilters): Promise<boolean>
loadApplication(applicationId: string): Promise<boolean>
changeApplicationStatus(applicationId: string, expectedVersion: number, status: Exclude<ApplicationStatus, 'pending'>): Promise<boolean>
```

Use `encodeURIComponent` for stable IDs. `loadJobCategories()` must filter `/api/interest-tags` to `group_key === 'job'`. Reset `activeApplication` when changing IDs. After create/edit/delete/status operations, reload the affected jobs or applications and dashboard instead of mutating counts locally.

- [ ] **Step 5: Run tests and commit**

Run:

```bash
cd frontend
npm test -- src/stores/enterpriseConsole.test.ts
npx tsc -b --noEmit
```

Expected: PASS.

```bash
git add frontend/src/api/types.ts frontend/src/stores/enterpriseConsole.ts frontend/src/stores/enterpriseConsole.test.ts
git commit -m "前端：增加企业工作台状态层"
```

### Task 10: Enterprise Routes, Portal Navigation and Dashboard

**Files:**
- Create: `frontend/src/components/EnterpriseConsoleNav.vue`
- Create: `frontend/src/components/EnterpriseDashboardCards.vue`
- Create: `frontend/src/router/enterpriseRoutes.test.ts`
- Create: `frontend/src/views/EnterprisePortalView.test.ts`
- Modify: `frontend/src/components/PortalShell.vue`
- Modify: `frontend/src/data/portal-guides.ts`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/views/EnterprisePortalView.vue`

**Interfaces:**
- Consumes: `useEnterpriseConsoleStore`, `PortalShell`, `AppHeader`.
- Produces routes `/enterprise`, `/enterprise/jobs`, `/enterprise/applications`, `/enterprise/applications/:applicationId`.

- [ ] **Step 1: Write failing route and dashboard tests**

Create `frontend/src/router/enterpriseRoutes.test.ts` following `handcraftRoutes.test.ts`:

```typescript
const enterpriseRoutes = [
  { path: '/enterprise', visitPath: '/enterprise', name: 'enterprise-portal' },
  { path: '/enterprise/jobs', visitPath: '/enterprise/jobs', name: 'enterprise-jobs' },
  {
    path: '/enterprise/applications',
    visitPath: '/enterprise/applications',
    name: 'enterprise-applications'
  },
  {
    path: '/enterprise/applications/:applicationId',
    visitPath: '/enterprise/applications/application-1',
    name: 'enterprise-application-detail'
  }
] as const
```

Assert each route has `requiresAuth: true`, `roles: ['enterprise']`; anonymous users redirect to login; student/teacher roles redirect to their default portals; enterprise users pass.

Assert portal guide entries now contain:

```typescript
{
  id: 'enterprise-job-publish',
  href: '/enterprise/jobs'
}
{
  id: 'enterprise-applications',
  href: '/enterprise/applications'
}
{
  id: 'enterprise-dashboard',
  href: '/enterprise'
}
```

Create `EnterprisePortalView.test.ts`, mock dashboard and jobs APIs, and assert:

```typescript
expect(wrapper.get('[data-test="active-job-count"]').text()).toContain('2')
expect(wrapper.get('[data-test="received-resume-count"]').text()).toContain('5')
expect(wrapper.find('#enterprise-job-publish').attributes('href')).toBe('/enterprise/jobs')
expect(wrapper.find('#enterprise-applications').attributes('href')).toBe('/enterprise/applications')
```

Add an API-failure test that keeps the navigation visible and shows a retry action.

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
cd frontend
npm test -- src/router/enterpriseRoutes.test.ts src/views/EnterprisePortalView.test.ts
```

Expected: FAIL because the routes and views do not exist.

- [ ] **Step 3: Add the enterprise navigation and dashboard cards**

Create `EnterpriseConsoleNav.vue` with these links:

```typescript
const links = [
  { to: '/enterprise', label: '企业看板', icon: Gauge },
  { to: '/enterprise/jobs', label: '职位管理', icon: BriefcaseBusiness },
  { to: '/enterprise/applications', label: '申请处理', icon: ClipboardList }
] as const
```

Use `RouterLink`, `exact-active-class="is-active"`, lucide icons, horizontal scroll only inside the nav, and `aria-label="企业工作台导航"`.

Create `EnterpriseDashboardCards.vue`:

```vue
<script setup lang="ts">
import { BriefcaseBusiness, FileUser } from 'lucide-vue-next'
import type { EnterpriseDashboard } from '@/api/types'

defineProps<{
  dashboard: EnterpriseDashboard
  loading: boolean
}>()
</script>
```

Render exactly two articles with `data-test="active-job-count"` and `data-test="received-resume-count"`. Do not add求购、人才库、面试、签约或 AI cards.

- [ ] **Step 4: Upgrade `/enterprise` and register routes**

Modify `PortalShell.vue` by adding a default slot immediately before the `entry-index` section:

```vue
<slot />
```

This is backward-compatible for teacher/government/admin portals. Existing `PortalShell.test.ts` must remain green.

Replace `EnterprisePortalView.vue` with:

```vue
<script setup lang="ts">
import { onMounted } from 'vue'

import EnterpriseConsoleNav from '@/components/EnterpriseConsoleNav.vue'
import EnterpriseDashboardCards from '@/components/EnterpriseDashboardCards.vue'
import PortalShell from '@/components/PortalShell.vue'
import { useEnterpriseConsoleStore } from '@/stores/enterpriseConsole'

const store = useEnterpriseConsoleStore()

onMounted(() => {
  void store.loadDashboard()
})
</script>

<template>
  <PortalShell portal="enterprise">
    <EnterpriseConsoleNav />
    <section id="enterprise-dashboard" aria-labelledby="enterprise-dashboard-title">
      <h2 id="enterprise-dashboard-title">企业数据</h2>
      <EnterpriseDashboardCards
        :dashboard="store.dashboard"
        :loading="store.loading"
      />
      <p v-if="store.error" role="alert">
        {{ store.error }}
        <button type="button" @click="store.loadDashboard">重新加载</button>
      </p>
    </section>
  </PortalShell>
</template>
```

Add lazy or direct imports for the three enterprise views in `router/index.ts` and register the four routes. Update enterprise portal guide entries with real `href` values.

- [ ] **Step 5: Run tests and commit**

Run:

```bash
cd frontend
npm test -- src/router/enterpriseRoutes.test.ts src/views/EnterprisePortalView.test.ts src/components/PortalShell.test.ts
npx tsc -b --noEmit
```

Expected: PASS.

```bash
git add frontend/src/components/EnterpriseConsoleNav.vue frontend/src/components/EnterpriseDashboardCards.vue frontend/src/components/PortalShell.vue frontend/src/data/portal-guides.ts frontend/src/router/index.ts frontend/src/router/enterpriseRoutes.test.ts frontend/src/views/EnterprisePortalView.vue frontend/src/views/EnterprisePortalView.test.ts
git commit -m "前端：建立企业门户与看板入口"
```

### Task 11: Enterprise Job Management UI

**Files:**
- Create: `frontend/src/components/EnterpriseJobForm.vue`
- Create: `frontend/src/views/EnterpriseJobsView.vue`
- Create: `frontend/src/views/EnterpriseJobsView.test.ts`

**Interfaces:**
- Consumes: `useEnterpriseConsoleStore`, `EnterpriseJob`, `EnterpriseJobPayload`.
- Produces the `/enterprise/jobs` screen.

- [ ] **Step 1: Write failing job UI tests**

Create `EnterpriseJobsView.test.ts` with mocked APIs and assert:

1. Page loads job categories from the store and renders only `job` tags.
2. Job list shows reviewed status labels `待审核`, `已通过`, `已驳回`; rejected jobs show the rejection opinion.
3. Create form sends exact payload and shows `待审核` after success.
4. Editing an approved job sends its current `version` and the returned `pending` job immediately shows `待审核`.
5. Delete confirmation sends `expected_version`; successful delete removes the job.
6. Invalid blank fields render field-specific errors and do not call the create API.
7. Conflict error `409` shows a refresh action and does not optimistically mutate the job.

Use icon-and-text controls for commands:

```vue
<button type="button" aria-label="编辑职位">
  <Pencil :size="16" aria-hidden="true" />
  编辑
</button>
<button type="button" aria-label="删除职位">
  <Trash2 :size="16" aria-hidden="true" />
  删除
</button>
```

Assert the buttons retain stable dimensions in CSS:

```typescript
expect(cssRule(source, '.job-row__actions button')).toContain('min-height: 40px')
expect(source).not.toContain('white-space: nowrap')
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `cd frontend; npm test -- src/views/EnterpriseJobsView.test.ts`

Expected: FAIL because the view does not exist.

- [ ] **Step 3: Implement the job form**

Create `EnterpriseJobForm.vue` with props:

```typescript
defineProps<{
  categories: InterestTag[]
  modelValue: EnterpriseJobPayload
  editing: boolean
  saving: boolean
  fieldErrors: ApiFieldErrors
}>()
```

Emits:

```typescript
defineEmits<{
  'update:modelValue': [value: EnterpriseJobPayload]
  submit: []
  cancel: []
}>()
```

Fields:

```text
title: text, required, max 100
salary: text, required, max 80
location: text, required, max 120
category_id: select from 01 job tags, required
description: textarea, required, max 4000
```

Use native labels and `aria-describedby` for field errors. Do not use a free-text category input.

- [ ] **Step 4: Implement the jobs view**

`EnterpriseJobsView.vue` responsibilities:

- `AppHeader`, `EnterpriseConsoleNav`;
- tabs for全部/待审核/已通过/已驳回 that call `loadJobs(status)`;
- `EnterpriseJobForm` collapsed until create/edit is selected;
- exact field validation before API call;
- `window.confirm` before delete;
- `RouterLink` back to `/enterprise`;
- stable status badges derived from `review_status`;
- no offline/publish/approve button.

The submit handler:

```typescript
async function submitJob() {
  fieldErrors.value = validateJob(form.value)
  if (Object.keys(fieldErrors.value).length) return
  const result = editingJob.value
    ? await store.editJob(
        editingJob.value.job_id,
        editingJob.value.version,
        form.value
      )
    : await store.createJob(form.value)
  if (result) {
    formOpen.value = false
    editingJob.value = null
    resetForm()
  }
}
```

`validateJob()` must trim values and return these exact keys when empty: `title`, `salary`, `location`, `category_id`, `description`.

- [ ] **Step 5: Run tests and commit**

Run:

```bash
cd frontend
npm test -- src/views/EnterpriseJobsView.test.ts src/stores/enterpriseConsole.test.ts
npx tsc -b --noEmit
```

Expected: PASS.

```bash
git add frontend/src/components/EnterpriseJobForm.vue frontend/src/views/EnterpriseJobsView.vue frontend/src/views/EnterpriseJobsView.test.ts
git commit -m "前端：实现企业职位管理"
```

### Task 12: Application Filters, Detail, Status Marking and Messaging Entry

**Files:**
- Create: `frontend/src/components/EnterpriseApplicationStatusBadge.vue`
- Create: `frontend/src/views/EnterpriseApplicationsView.vue`
- Create: `frontend/src/views/EnterpriseApplicationDetailView.vue`
- Create: `frontend/src/views/EnterpriseApplicationsView.test.ts`

**Interfaces:**
- Consumes: enterprise store, `EnterpriseApplicationSummary`, `EnterpriseApplicationDetail`.
- Produces `/enterprise/applications` and `/enterprise/applications/:applicationId`.

- [ ] **Step 1: Write failing application UI tests**

Create `EnterpriseApplicationsView.test.ts` with:

1. Filter controls for job, status, start date, end date and sort.
2. Exact request assertion:

```typescript
expect(mockedApiFetch).toHaveBeenCalledWith(
  '/api/enterprise/applications?job_id=job-1&status=intent&submitted_from=2026-09-01&submitted_to=2026-09-18&sort=submitted_desc'
)
```

3. Default list ordering is preserved from the API; the view does not re-sort client-side.
4. Detail page shows immutable resume fields and only shows a skill-profile section when `skill_profile_attached` is true.
5. Empty/missing skill profile shows the exact state `未附带技能档案` and does not infer current data.
6. Status buttons are exactly `已查看`, `意向沟通`, `不合适`; `待处理` is not a manual target.
7. A status change sends current `status_version`; success refreshes the detail and application list.
8. Closed applications show `岗位已关闭`, preserve handled labels, and disable every status button.
9. A `RouterLink` to `/messages` is present only for an application relationship; no candidate search or invite controls exist.
10. Conflict `409` keeps the previous status and shows a refresh action.

- [ ] **Step 2: Run the test and verify it fails**

Run: `cd frontend; npm test -- src/views/EnterpriseApplicationsView.test.ts`

Expected: FAIL because the views do not exist.

- [ ] **Step 3: Implement the status badge**

Create `EnterpriseApplicationStatusBadge.vue`:

```typescript
defineProps<{
  status: EffectiveApplicationStatus
  positionClosed: boolean
}>()
```

Exact label map:

```typescript
const labels = {
  pending: '待处理',
  viewed: '已查看',
  intent: '意向沟通',
  unsuitable: '不合适',
  closed: '岗位已关闭'
} as const
```

When `positionClosed` is true and status is not `closed`, render the latest status plus a separate `岗位已关闭` badge.

- [ ] **Step 4: Implement list and detail views**

`EnterpriseApplicationsView.vue`:

- use `AppHeader`, `EnterpriseConsoleNav`, status badge;
- filter form submits through `store.loadApplications()`;
- list columns show student, job, submitted time, effective status;
- row action `查看详情` links to `/enterprise/applications/${encodeURIComponent(id)}`;
- empty state `暂无符合条件的申请`.

`EnterpriseApplicationDetailView.vue`:

- load application by route param;
- render resume snapshot as a definition list. Support arbitrary JSON object values by formatting arrays as comma-separated text and nested objects as JSON text;
- render skill profile only when attached and non-empty;
- render status history in ascending sequence;
- status controls call `store.changeApplicationStatus(id, status_version, selectedStatus)`;
- disabled controls when `position_closed` is true;
- `RouterLink` to `/messages` labeled `私信沟通`;
- no export, invite, interview, offer or onboarding controls.

Use these exact section landmarks:

```text
data-test="resume-snapshot"
data-test="skill-profile"
data-test="skill-profile-empty"
data-test="status-history"
data-test="message-applicant"
```

- [ ] **Step 5: Run tests and commit**

Run:

```bash
cd frontend
npm test -- src/views/EnterpriseApplicationsView.test.ts src/stores/enterpriseConsole.test.ts
npx tsc -b --noEmit
```

Expected: PASS.

```bash
git add frontend/src/components/EnterpriseApplicationStatusBadge.vue frontend/src/views/EnterpriseApplicationsView.vue frontend/src/views/EnterpriseApplicationDetailView.vue frontend/src/views/EnterpriseApplicationsView.test.ts
git commit -m "前端：实现申请筛选与状态处理"
```

### Task 13: Demo Seed, Responsive QA and Full End-to-End Verification

**Files:**
- Create: `backend/app/enterprise_console/seed.py`
- Create: `backend/tests/test_enterprise_integration.py`
- Create: `frontend/src/views/EnterpriseConsoleResponsive.test.ts`
- Modify: `backend/app/seed_dev.py`
- Modify: `backend/app/db.py`
- Modify: `backend/app/enterprise_console/__init__.py`

**Interfaces:**
- Consumes: all 09 services and existing local seed entrypoint.
- Produces: `seed_enterprise_console_fixtures(connection)`, end-to-end verification evidence.

- [ ] **Step 1: Write the integration and responsive tests**

Backend integration tests:

1. Create enterprise/student users, install a fake review provider, create a job, approve it, and assert the job provider returns it to a 07-compatible consumer.
2. Edit the approved job and assert it disappears from provider before reapproval.
3. Reject and resubmit, asserting opinion/version transitions.
4. Submit applications with and without skill profiles, filter them, change status, and assert student notifications.
5. Delete the position and assert pending closure, handled history, dashboard count and messaging relationship.
6. Replace `job_position_provider` with a fake and assert consumer-facing field shape is unchanged.
7. Patch `emit_review_result` and assert 09 never calls it.
8. Replace `job_application_intake_provider` with a 07-compatible fake and assert `submit_application()` signature, idempotency and return fields remain stable without direct table access.
9. Replace `UnavailableContentReviewProvider` with a fake through the same `content_review_provider` slot and assert no second slot or 09 branch change exists.

Performance test:

```python
def test_provider_and_filters_cover_target_scale(self):
    seed 500 approved jobs and 5000 applications across 2 enterprises
    started = time.monotonic()
    jobs = get_job_position_provider().list_published_positions()
    applications = list_applications(self.enterprise_id, {"sort": "submitted_desc"})
    dashboard = get_dashboard(self.enterprise_id)
    elapsed = time.monotonic() - started
    self.assertEqual(len(jobs), 500)
    self.assertEqual(len(applications), 2500)
    self.assertEqual(dashboard["received_resume_count"], 2500)
    self.assertLess(elapsed, 2.0)
```

Frontend responsive test:

```typescript
expect(boardSource).toContain('grid-template-columns: repeat(auto-fit, minmax(220px, 1fr))')
expect(boardSource).toContain('overflow-x: clip')
expect(jobsSource).not.toContain('white-space: nowrap')
expect(applicationsSource).toContain('overflow-wrap: anywhere')
```

Mount all three enterprise views at 320px-equivalent test data with long Chinese titles and long student names; assert no element has both `position: fixed` and content-bearing text outside its parent.

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
uv run --directory backend python -m unittest tests.test_enterprise_integration -v
cd frontend
npm test -- src/views/EnterpriseConsoleResponsive.test.ts
```

Expected: FAIL because the seed and integration artifacts do not exist.

- [ ] **Step 3: Add idempotent demo fixtures**

Create `backend/app/enterprise_console/seed.py`:

```python
DEMO_JOBS = (
    {
        "job_id": "job-demo-pending",
        "title": "待审核农业技术员（演示）",
        "salary": "6k-8k",
        "location": "广州",
        "category_name": "农业技术员",
        "description": "用于企业工作台演示的待审核职位。",
        "review_status": "pending",
        "version": 1,
        "published_at": None,
        "rejection_opinion": None,
    },
    {
        "job_id": "job-demo-approved",
        "title": "电商运营专员（演示）",
        "salary": "7k-9k",
        "location": "佛山",
        "category_name": "电商运营",
        "description": "用于企业工作台演示的已上架职位。",
        "review_status": "approved",
        "version": 1,
        "published_at": "2026-09-18T09:00:00+08:00",
        "rejection_opinion": None,
    },
    {
        "job_id": "job-demo-rejected",
        "title": "客服专员（演示）",
        "salary": "5k-7k",
        "location": "东莞",
        "category_name": "客服专员",
        "description": "用于企业工作台演示的已驳回职位。",
        "review_status": "rejected",
        "version": 2,
        "published_at": None,
        "rejection_opinion": "请补充岗位职责。",
    },
)
```

`seed_enterprise_console_fixtures(connection)` must:

- require the `enterprise_demo` user and at least one student demo user;
- resolve each `category_name` uniquely from active `job` tags;
- use `INSERT ... ON CONFLICT(job_id) DO UPDATE` for deterministic demo state;
- insert one application for each allowed status plus one closed pending application, all with stable IDs and snapshots;
- never create notifications during seed;
- be idempotent when `seed_local_data()` is run repeatedly.

Call the function from `seed_local_data()` after `_seed_accounts()` and keep it out of production `create_app()` startup.

- [ ] **Step 4: Run full automated verification**

Run:

```bash
uv run --directory backend python -m unittest discover -s tests -v
```

Expected: all backend tests pass, including the 500-job/5,000-application target-scale test.

Run:

```bash
cd frontend
npm test
npx tsc -b --noEmit
npm run build
```

Expected: all Vitest suites pass, TypeScript emits no errors, and Vite production build succeeds.

Run the no-AI assertion:

```bash
rg -n "get_ai_client|complete_json|stream_chat|transcribe|set_ai_client|AiUnavailable" backend/app/enterprise_console
```

Expected: no output and exit status 1.

Run:

```bash
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 5: Browser verification and commit**

Start the backend and frontend using the repository runbook:

```bash
uv run --frozen python run.py
cd frontend
npm run dev
```

With the seeded `enterprise_demo` account, verify in the browser:

1. `/enterprise` shows the two exact dashboard values.
2. `/enterprise/jobs` creates a pending job, filters all three statuses, edits an approved demo job until it becomes pending, and deletes a job with confirmation.
3. `/enterprise/applications` filters by job/status/date, opens detail, shows resume, shows or omits skill profile correctly, changes status, and shows the closed marker after deletion.
4. `/messages` permits messaging only for applicants of the current enterprise.
5. At 320px, 768px, and 1440px widths, no horizontal overflow, text overlap, clipped controls, or missing status labels occur.

Capture the browser-visible desktop and mobile evidence in the task handoff.

```bash
git add backend/app/enterprise_console/seed.py backend/app/enterprise_console/__init__.py backend/app/seed_dev.py backend/app/db.py backend/tests/test_enterprise_integration.py frontend/src/views/EnterpriseConsoleResponsive.test.ts
git commit -m "测试：完成企业工作台端到端验收"
```

---

## Spec Coverage Map

| Spec range | Tasks |
| --- | --- |
| FR-001..004 session, tenant ownership and enterprise scope | 1, 7, 8 |
| FR-005..017 job creation, validation, review status and versioning | 1, 3, 4, 8 |
| FR-018..023 logical deletion, closure branches and history | 1, 5, 6 |
| FR-024..031 application filters, snapshots and detail fallback | 5, 12 |
| FR-032..039 application status transitions and notifications | 2, 5, 6, 8, 12 |
| FR-040..044 private-message relationship and scope | 7, 12 |
| FR-045..048 enterprise-only dashboard metrics | 7, 10 |
| FR-049..060 job provider signature, shape, replacement and errors | 1, 4, 8, 13 |
| FR-061..066 ContentReviewProvider integration and no duplicate review notice | 1, 3, 13 |
| FR-067..072 01/02/11 reuse and application notification boundaries | 1, 2, 5, 7, 8 |
| FR-073..075 no AI, no talent search and no 11 review actions | 8, 9, 12, 13 |
| FR-076..083 JobApplicationIntakeProvider and single review-provider slot | 1, 5, 8, 13 |
| SC-001..004 job state and deletion matrix | 3, 4, 6, 13 |
| SC-005..007 filters, status notifications and profile fallback | 5, 9, 12, 13 |
| SC-008..010 tenant isolation, dashboard and provider replacement | 4, 7, 8, 13 |
| SC-011..012 review integration and notification retry | 2, 3, 13 |
| SC-013..015 performance, no AI and application submission notice | 2, 5, 8, 13 |
| SC-016..017 application-intake replacement and single review-provider slot | 1, 5, 13 |

## Plan Self-Review

- Spec coverage: every FR and SC appears in the coverage map and at least one executable task.
- Interface consistency: `JobPositionProvider`, `ContentReviewProvider`, job/service/dashboard/store function names and fields match across tasks.
- State consistency: `pending`, `approved`, `rejected`, logical deletion, application `pending/viewed/intent/unsuitable` and effective `closed` are used without synonyms.
- No unresolved markers: every task names files, tests, commands, expected results and commit scope.

