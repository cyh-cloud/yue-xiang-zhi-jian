# 011 Admin Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 011 系统管理后台，并完成内容审核、积分规则、奖品履约、预置内容、功能知识库和全平台统计等跨模块 provider 的真实落地。

**Architecture:** 新增 `backend/app/admin_console/` 作为唯一管理后台模块，复用 01 会话、02 通知、03/05/06 读取 provider、05 积分与履约领域状态机。统一审核由 `CompositeContentReviewProvider` 组合课程/职位数据库真实现与 05 非遗视频适配器；前端在 `/admin` 下增加按角色裁剪的桌面/移动后台壳和各功能区。

**Tech Stack:** Python 3, Flask, SQLite, unittest, Vue 3, Vite, Pinia, TypeScript, Vitest, lucide-vue-next.

**Spec:** `specs/011-admin-console/spec.md`

## Global Constraints

- 后端模块目录固定为 `backend/app/admin_console/`；旧根目录系统代码不得参考、导入或迁移。
- 所有管理员 API 必须从 01 会话读取身份和角色；客户端传入的 actor/reviewer/admin 角色无效。
- 统一审核 `content_type` 固定为 `course_video`、`job_position`、`handcraft_teaching_video`。
- 审核状态固定为 `pending`、`approved`、`rejected`；驳回意见去空白后长度必须为 1 至 500。
- `training_weights` 只允许 `default`、`live_script`、`simulation`、`copy_training`、`customer_service`，值必须为正整数。
- 积分有效期只允许 `permanent` 和 `natural_year`；平台自然日/自然年使用 `Asia/Shanghai`。
- 普管看板递归禁止 `total_users`、`role_distribution`、`student_total`、`student_count`、`user_details`、`average_progress`、`completion_rate`、`quiz_attempt_count`、`quiz_average_score`、`training_progress`、`learning_behavior_count`。
- 05 首次 `submit_for_review` 与 `rejected -> pending` 不存在；11 适配器必须返回 `ProviderConflictError` 或 `ProviderUnavailableError`，不得伪造。
- 政策/新闻常规编辑仍归政府；超管仅纠错、下架/删除。账户不提供物理删除。
- 02 是唯一通知投递边界；所有事件使用稳定 `event_id` 并保持幂等。
- 每个任务先写失败测试，再实现，再运行定向测试；完成前运行 `git diff --check` 并提交单一意图 commit。

## File Structure

**Backend create**

- `backend/app/admin_console/__init__.py`: 模块导出、provider 安装、蓝图和错误处理器注册。
- `backend/app/admin_console/errors.py`: 管理后台错误和标准 provider 错误层级。
- `backend/app/admin_console/time_utils.py`: `Asia/Shanghai` 时间和版本工具。
- `backend/app/admin_console/audit.py`: 管理审计写入与查询。
- `backend/app/admin_console/accounts.py`: 账户查询、创建、启停、重置和首个超管初始化。
- `backend/app/admin_console/points_policy.py`: 平台积分规则读写与 provider。
- `backend/app/admin_console/content_review_service.py`: 审核队列与管理员动作。
- `backend/app/admin_console/content_review_provider.py`: 课程/职位数据库审核真实现。
- `backend/app/admin_console/handcraft_review_adapter.py`: 05 非遗视频专用适配器。
- `backend/app/admin_console/providers.py`: 组合审核 provider、预置/知识/反馈 provider 槽和默认注册。
- `backend/app/admin_console/moderation.py`: 评论、举报、反馈领域服务。
- `backend/app/admin_console/presets.py`: 六类预置内容领域服务与读取适配器。
- `backend/app/admin_console/rewards.py`: 权威奖品目录、库存、兑换和履约查询。
- `backend/app/admin_console/data_management.py`: 政策/新闻、课程、职位、视频、评论和预置内容管理。
- `backend/app/admin_console/system_announcements.py`: 系统公告和 02 群发。
- `backend/app/admin_console/dashboard.py`: 超管与普管看板。
- `backend/app/admin_console/routes.py`: `/api/admin` 蓝图、角色校验和响应序列化。
- `backend/app/admin_console/seed.py`: 首个超管和演示后台数据幂等初始化。

**Backend modify**

- `backend/app/db.py`: 新增后台表、逻辑删除列、初始化迁移和 seed 调用。
- `backend/app/__init__.py`: 安装默认 admin provider、注册蓝图和错误处理器。
- `backend/app/messaging/events.py`: 新增系统公告事件；复用 `emit_password_reset`。
- `backend/app/content_review/providers.py`: 使用共享 provider 错误类型并保持既有 Protocol。
- `backend/app/handcraft_inheritance/providers.py`: 只补充 05 读取动作所需的最小兼容字段，不改变既有方法签名。

**Backend tests create**

- `backend/tests/test_admin_console_foundation.py`
- `backend/tests/test_admin_accounts.py`
- `backend/tests/test_admin_points_policy.py`
- `backend/tests/test_admin_content_review.py`
- `backend/tests/test_admin_handcraft_review_adapter.py`
- `backend/tests/test_admin_moderation.py`
- `backend/tests/test_admin_presets.py`
- `backend/tests/test_admin_rewards_fulfillment.py`
- `backend/tests/test_admin_data_management.py`
- `backend/tests/test_admin_dashboard.py`
- `backend/tests/test_admin_permissions.py`
- `backend/tests/test_admin_provider_acceptance.py`

**Frontend create**

- `frontend/src/stores/adminConsole.ts`
- `frontend/src/components/AdminConsoleNav.vue`
- `frontend/src/components/AdminMetricGroup.vue`
- `frontend/src/views/AdminDashboardView.vue`
- `frontend/src/views/AdminAccountsView.vue`
- `frontend/src/views/AdminPointsPolicyView.vue`
- `frontend/src/views/AdminReviewView.vue`
- `frontend/src/views/AdminModerationView.vue`
- `frontend/src/views/AdminPresetsView.vue`
- `frontend/src/views/AdminRewardsView.vue`
- `frontend/src/views/AdminRedemptionsView.vue`
- `frontend/src/views/AdminContentManagementView.vue`
- `frontend/src/views/AdminAnnouncementsView.vue`

**Frontend modify**

- `frontend/src/views/AdminPortalView.vue`: 改为后台布局容器。
- `frontend/src/router/index.ts`: 增加 `/admin` 子路由和角色元数据。
- `frontend/src/api/types.ts`: 增加后台 DTO、角色和状态联合类型。
- `frontend/src/data/portal-guides.ts`: 更新管理员入口链接。

## Provider Delivery Map

| 槽键 | Protocol | 消费方 | 任务 |
| --- | --- | --- | --- |
| `content_review_provider` | `ContentReviewProvider` | 08、09、05 适配器 | T007, T008, T009 |
| `handcraft_points_policy_provider` | `PointsPolicyProvider` | 05 积分、有效期、履约 | T016 |
| `handcraft_reward_catalog_provider` | `RewardCatalogProvider` | 05 商城、兑换、库存 | T010 |
| `handcraft_fulfillment_action` | `FulfillmentAdminActionProvider` | 05 履约动作 | T011 |
| `agri_preset_provider` | `PresetContentProvider` | 03 日历、诊断、离线问答 | T021 |
| `handcraft_craft_preset_provider` | `CraftPresetProvider` | 05 非遗技艺 | T022 |
| `local_resource_case_provider` | `LocalResourceCaseProvider` | 06 成功案例 | T022 |
| `assistant_feature_knowledge_provider` | `AssistantFeatureKnowledgeProvider` | 12 AI 学伴 | T022 |
| `feedback_intake_provider` | `FeedbackIntakeProvider` | 07 或 12 提交入口 | T020 |

## Spec Coverage Map

| Spec requirement block | Plan tasks |
| --- | --- |
| 角色、入口与审计 FR-001 至 FR-006 | T001, T003, T006, T028 |
| 超管全量看板 FR-007 至 FR-013 | T005, T013, T029 |
| 账号与权限 FR-014 至 FR-022 | T006, T014, T028 |
| 积分规则 FR-023 至 FR-032 | T016, T017, T027 |
| 全平台数据管理 FR-033 至 FR-042 | T024, T025 |
| 兑换记录 FR-043 至 FR-047 | T011, T015 |
| 内容审核 FR-048 至 FR-062 | T007, T009, T026, T027 |
| 05 视频适配器 FR-063 至 FR-070 | T008, T027 |
| 评论、举报与反馈 FR-071 至 FR-079 | T018, T019, T020 |
| 六类预置内容 FR-080 至 FR-089 | T021, T022, T023, T027 |
| 奖品库与履约 FR-090 至 FR-100 | T010, T011, T015 |
| 双角色权限矩阵 | T003, T014, T017, T028, T030 |
| 普管看板排除项 FR-101 至 FR-103 | T005, T029, T030 |
| Provider 清单与注册 FR-104 至 FR-110 | T002, T007, T008, T010, T016, T019, T021, T022, T027, T031 |
| 通知与失败处理 FR-111 至 FR-117 | T012, T026, T028 |

## 05 Adapter Map

| 通用动作 | 05 调用 | 结果映射 | 禁止行为 |
| --- | --- | --- | --- |
| `get_review_status` | `get_teaching_video_provider().get_video(video_id)` | `status`/`review_status` -> `review_status` | 不读取 05 数据库内部表 |
| `submit_for_review` | 已存在且允许 `edit` 时调用 `apply(action="edit")` | 05 `status` -> 通用 `review_status` | 不创建视频；不伪造首次提交 |
| `approve` | `apply(action="approve")` | `approved` + `published_at` | 不重复发通知 |
| `reject` | `apply(action="reject")` | `rejected` + `opinion` | 不重复发通知 |
| `edit` | `apply(action="edit")` | `pending` 或原状态 | 不允许非教师所有者编辑 |
| `rejected -> pending` | 无对应 05 动作 | 抛 `ProviderConflictError` | 不把 reject 后编辑伪装成支持 |

## Permission Matrix Test Map

| 矩阵项 | 后端测试 | 前端测试 |
| --- | --- | --- |
| 账号管理仅超管 | `test_admin_permissions.py::test_only_super_admin_can_manage_accounts` | `adminConsole.test.ts::hides accounts from ordinary admin` |
| 积分规则仅超管写 | `test_admin_permissions.py::test_only_super_admin_can_write_points_policy` | `adminConsole.test.ts::hides points policy from ordinary admin` |
| 普管审核/监管/预置/奖品/履约 | `test_admin_permissions.py::test_ordinary_admin_can_run_content_operations` | `AdminReviewView.test.ts` + `AdminModerationView.test.ts` |
| 普管履约上下文用户数据 | `test_admin_permissions.py::test_ordinary_admin_reads_user_context_only_from_fulfillment` | `AdminRedemptionsView.test.ts::shows fulfillment context without account actions` |
| 普管看板排除用户/培训指标 | `test_admin_dashboard.py::test_admin_dashboard_recursively_excludes_user_and_training_keys` | `AdminDashboardView.test.ts::does not render forbidden metrics` |
| 普管不能生产业务内容 | `test_admin_permissions.py::test_ordinary_admin_cannot_create_course_job_or_policy` | `AdminContentManagementView.test.ts::ordinary admin sees review-only actions` |

## 普管看板排除项

- 允许键固定为 `pending_review.course_video`、`pending_review.job_position`、`pending_review.handcraft_teaching_video`、`published_course_count`、`active_job_count`、`comment_processed_count`、`report_processed_count`、`feedback_processed_count`、`reward_stock`、`pending_fulfillment_count`。
- 禁止键按递归扫描处理，包含 `total_users`、`role_distribution`、`student_total`、`student_count`、`user_details`、`average_progress`、`completion_rate`、`quiz_attempt_count`、`quiz_average_score`、`training_progress`、`learning_behavior_count`。
- 断言方式：后端对完整 response JSON 递归收集键；前端对渲染文本和 store DTO 双重断言禁止指标为 0 次出现。

## 与 001-010 的复用点

- 001: `users`、`sessions`、`authenticate()`、`load_session()`、禁用账户拦截、角色默认路径。
- 002: `emit_review_result()`、`emit_password_reset()`、履约事件、通知幂等键。
- 003: `agri_preset_provider`、`list_learning_outcomes()`、课程 provider 的只读统计。
- 004: `list_ecommerce_learning_outcomes()`，仅用于超管全量培训统计，不得进入普管看板。
- 005: `get_points_policy_provider()`、`get_reward_catalog_provider()`、`get_fulfillment_action_provider()`、`apply_fulfillment_admin_action()`、积分账本、兑换和履约表。
- 006: `local_resource_case_provider`、`local_resource_success_cases`、政策/新闻只读 provider。
- 007: 岗位/申请 provider 只作为跨模块读点，11 不修改申请状态机。
- 008: `CourseReviewAdapter`、课程 provider、课程/评论表。
- 009: `JobPositionProvider`、职位审核调用点、职位表。
- 010: 政策/新闻状态和浏览计数；11 不新增 010 统计 provider。

## 共享文件改动

- `backend/app/db.py`：T001 一次建立全部 `admin_*` 表和基础索引；T006 只增加首个超管 seed 调用；T010/T012/T016/T019/T021/T022 只增加各自索引、约束和 seed，不重复声明建表；T022 增加现有 `local_resource_success_cases.is_enabled` 与 `version` 迁移列；T024 增加 `courses.deleted_at` 和 `heritage_videos.deleted_at`。每次 schema 变化必须是幂等迁移，禁止把领域逻辑写入该文件。
- `backend/app/__init__.py`：只增加 admin 默认服务安装、蓝图注册和错误处理器注册。
- `backend/app/messaging/events.py`：只增加系统公告事件，不改现有事件签名。
- `backend/app/content_review/providers.py`：只替换错误类型来源，不改 Protocol 签名。
- `frontend/src/router/index.ts`：只把现有 `/admin` 单页改为父布局加子路由。
- `frontend/src/api/types.ts`：只追加后台 DTO，不重排既有类型。
- `frontend/src/data/portal-guides.ts`：只更新 admin entries 的 href。
- `frontend/src/views/AdminPortalView.vue`：全量重写为 `/admin` 父布局容器（渲染
  `AdminConsoleNav` 与 `<RouterView />`，`/admin` 重定向到 `/admin/dashboard`，子路由使用
  `adminMeta`/`superAdminMeta`）；不再使用 `PortalShell`，但 `PortalShell` 本身不动；
  无跨模块回归（2026-09-22 补登：最终审查 O3，当时遗漏于本清单）。

## Dependency Direction Check

- T002 provider 注册先于所有 producer 实现。
- T007/T008 审核 provider 先于 T009 审核管理路由和 T028 provider 验收。
- T010/T011 奖品与履约先于 T015 奖品/履约前端。
- T016 积分规则先于 T017 前端和 T027 provider 验收。
- T021/T022 预置 provider 先于 T023 前端和 T027 provider 验收。
- T019 反馈 provider 先于 T020 监管前端。
- T024 数据管理先于 T025 前端和 T029 排除断言。
- T027-T034 在所有 producer 和管理面完成后执行，不存在消费方排在生产者之前。

---

### Task 1: 后台数据库、错误层级与审计基础

**Files:**
- Create: `backend/app/admin_console/__init__.py`
- Create: `backend/app/admin_console/errors.py`
- Create: `backend/app/admin_console/time_utils.py`
- Create: `backend/app/admin_console/audit.py`
- Modify: `backend/app/db.py`
- Test: `backend/tests/test_admin_console_foundation.py`

**Interfaces:**
- Consumes: `app.db.get_db`, existing SQLite connection helpers.
- Produces: `ProviderError`, `ProviderValidationError`, `ProviderNotFoundError`, `ProviderConflictError`, `ProviderUnavailableError`, `ProviderAccessDeniedError`; `platform_now_iso() -> str`; `record_admin_audit(db, *, actor_id: int, action: str, target_type: str, target_id: str, before: dict | None, after: dict | None, result: str) -> int`; tables `admin_audit_log`, `admin_notification_outbox`, `content_review_records`, `platform_points_policy`, `admin_rewards`, `comment_reports`, `feedback_records`, `admin_assistant_feature_knowledge`, `admin_agri_products`, `admin_agri_calendar`, `admin_pest_knowledge`, `admin_handcraft_crafts`, `system_announcements`.

- [x] **Step 1: Write failing schema and error tests**

```python
def test_admin_foundation_tables_and_provider_errors(self):
    from app.admin_console.errors import ProviderConflictError
    names = {
        row["name"]
        for row in get_db().execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
    }
    self.assertIn("admin_audit_log", names)
    self.assertIn("content_review_records", names)
    self.assertEqual(ProviderConflictError("x", code="c", details={}).code, "c")
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_admin_console_foundation -v`

Expected: FAIL with `ModuleNotFoundError: app.admin_console`.

- [x] **Step 3: Add schema and foundation implementation**

```python
class ProviderError(RuntimeError):
    def __init__(self, message: str, *, code: str, details: dict):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = dict(details)


class ProviderConflictError(ProviderError):
    pass
```

```sql
CREATE TABLE IF NOT EXISTS content_review_records (
    content_type TEXT NOT NULL,
    content_id TEXT NOT NULL,
    submitter_id INTEGER NOT NULL,
    review_status TEXT NOT NULL CHECK (review_status IN ('pending','approved','rejected')),
    version INTEGER NOT NULL CHECK (version > 0),
    rejection_opinion TEXT,
    published_at TEXT,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (content_type, content_id)
);
```

`admin_audit_log` stores `actor_id`, `action`, `target_type`, `target_id`, `before_json`, `after_json`, `result`, `created_at`. `admin_notification_outbox` stores `event_type`, `event_id`, `payload_json`, `status`, `attempts`, `last_error`, `created_at`, `sent_at` with unique `(event_type, event_id)`.

- [x] **Step 4: Run foundation tests**

Run: `uv run --directory backend python -m unittest tests.test_admin_console_foundation -v`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add backend/app/admin_console backend/app/db.py backend/tests/test_admin_console_foundation.py
git commit -m "实现 011 后台基础表与错误层级"
```

### Task 2: Provider 槽、注册表与默认安装

**Files:**
- Create: `backend/app/admin_console/providers.py`
- Modify: `backend/app/admin_console/__init__.py`
- Modify: `backend/app/__init__.py`
- Test: `backend/tests/test_admin_console_foundation.py`

**Interfaces:**
- Consumes: Task 1 errors and table constants.
- Produces: `AssistantFeatureKnowledgeProvider`, `FeedbackIntakeProvider`, `DatabaseAssistantFeatureKnowledgeProvider`, `DatabaseFeedbackIntakeProvider`, `UnavailableAssistantFeatureKnowledgeProvider`, `UnavailableFeedbackIntakeProvider`; `set_assistant_feature_knowledge_provider`, `get_assistant_feature_knowledge_provider`, `set_feedback_intake_provider`, `get_feedback_intake_provider`, `configure_admin_providers`, `install_default_admin_services`.

- [x] **Step 1: Write failing registration tests**

```python
def test_admin_provider_slots_use_single_registry(self):
    from app.admin_console.providers import (
        get_assistant_feature_knowledge_provider,
        set_assistant_feature_knowledge_provider,
    )
    replacement = object()
    set_assistant_feature_knowledge_provider(self.app, replacement)
    self.assertIs(get_assistant_feature_knowledge_provider(), replacement)
    self.assertIs(
        self.app.extensions["assistant_feature_knowledge_provider"],
        replacement,
    )
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_admin_console_foundation.AdminConsoleFoundationTests.test_admin_provider_slots_use_single_registry -v`

Expected: FAIL because provider functions do not exist.

- [x] **Step 3: Implement provider registration**

```python
def set_assistant_feature_knowledge_provider(app: Flask, provider) -> None:
    app.extensions["assistant_feature_knowledge_provider"] = provider


def get_assistant_feature_knowledge_provider():
    return current_app.extensions.get(
        "assistant_feature_knowledge_provider",
        UnavailableAssistantFeatureKnowledgeProvider(),
    )
```

`configure_admin_providers()` delegates to each `set_*`. At T002,
`install_default_admin_services(app)` installs only the new knowledge and
feedback default slots. T007/T008/T010/T016/T021/T022 extend that same function
to replace the known 03/05 placeholder slots with admin true providers; this is
the single producer replacement point required by the provider contract.

- [x] **Step 4: Run registration tests**

Run: `uv run --directory backend python -m unittest tests.test_admin_console_foundation -v`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add backend/app/admin_console/providers.py backend/app/admin_console/__init__.py backend/app/__init__.py backend/tests/test_admin_console_foundation.py
git commit -m "注册 011 管理后台 provider 槽"
```

### Task 3: 管理 API 蓝图、角色校验与错误映射

**Files:**
- Create: `backend/app/admin_console/routes.py`
- Modify: `backend/app/admin_console/__init__.py`
- Modify: `backend/app/__init__.py`
- Test: `backend/tests/test_admin_permissions.py`

**Interfaces:**
- Consumes: `load_session`, Task 1 errors.
- Produces: `admin_console_bp` at `/api/admin`; `require_admin_session(*, roles: set[str]) -> dict`; `register_admin_console_error_handlers(app) -> None`; JSON error shape `{success:false, code, message, details}`.

- [x] **Step 1: Write failing role and error tests**

```python
def test_anonymous_admin_request_is_rejected(self):
    response = self.client.get("/api/admin/dashboard")
    self.assertIn(response.status_code, {401, 403})


def test_provider_conflict_maps_to_409(self):
    response = self.client.post(
        "/api/admin/review/course_video/1/reject",
        json={"expected_version": 1, "opinion": ""},
    )
    self.assertEqual(response.status_code, 409)
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_admin_permissions -v`

Expected: FAIL with 404.

- [x] **Step 3: Implement blueprint and handlers**

```python
admin_console_bp = Blueprint("admin_console", __name__, url_prefix="/api/admin")


def require_admin_session(*, roles: set[str]) -> dict:
    session = load_session(required=True, allowed_states={"active"})
    if session["role"] not in roles:
        raise ProviderAccessDeniedError(
            "无管理权限",
            code="admin_access_denied",
            details={},
        )
    return session
```

Register handlers for `ProviderValidationError -> 400`, `ProviderAccessDeniedError -> 403`, `ProviderNotFoundError -> 404`, `ProviderConflictError -> 409`, `ProviderUnavailableError -> 503`.

- [x] **Step 4: Run permission tests**

Run: `uv run --directory backend python -m unittest tests.test_admin_permissions -v`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add backend/app/admin_console/routes.py backend/app/admin_console/__init__.py backend/app/__init__.py backend/tests/test_admin_permissions.py
git commit -m "建立 011 管理后台路由与权限边界"
```

### Task 4: 前端后台壳、类型与子路由

**Files:**
- Create: `frontend/src/components/AdminConsoleNav.vue`
- Create: `frontend/src/components/AdminMetricGroup.vue`
- Create: `frontend/src/stores/adminConsole.ts`
- Modify: `frontend/src/views/AdminPortalView.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/data/portal-guides.ts`
- Test: `frontend/src/stores/adminConsole.test.ts`
- Test: `frontend/src/views/AdminConsoleResponsive.test.ts`

**Interfaces:**
- Consumes: existing `apiFetch`, `ApiError`, `useAuthStore`, Ark CSS variables.
- Produces: admin DTO types; `useAdminConsoleStore`; nav links `/admin`, `/admin/review`, `/admin/moderation`, `/admin/presets`, `/admin/rewards`, `/admin/redemptions`, `/admin/accounts`, `/admin/points-policy`, `/admin/content`, `/admin/announcements`; role-filtered nav.

- [x] **Step 1: Write failing route/nav tests**

```ts
it('hides super-admin-only links from ordinary admins', async () => {
  const wrapper = mount(AdminConsoleNav, {
    global: { plugins: [router], stubs: { RouterLink: RouterLinkStub } },
    props: { role: 'admin' }
  })
  expect(wrapper.find('[data-test="admin-nav-accounts"]').exists()).toBe(false)
  expect(wrapper.find('[data-test="admin-nav-review"]').exists()).toBe(true)
})
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd frontend; npm test -- --run src/stores/adminConsole.test.ts src/views/AdminConsoleResponsive.test.ts`

Expected: FAIL because files do not exist.

- [x] **Step 3: Implement shell and route scaffolding**

```ts
export interface AdminDashboardResponse {
  scope: 'platform' | 'content_operations'
  metrics: Record<string, number>
}

const adminMeta = { requiresAuth: true, roles: ['super_admin', 'admin'] as const }
```

`AdminPortalView.vue` renders `AdminConsoleNav` and `<RouterView />`; `/admin` redirects to `/admin/dashboard`; each child route uses `adminMeta`. `AdminMetricGroup.vue` renders stable metric tiles with `data-test` per metric.

- [x] **Step 4: Run frontend unit tests**

Run: `cd frontend; npm test -- --run src/stores/adminConsole.test.ts src/views/AdminConsoleResponsive.test.ts`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add frontend/src/components/AdminConsoleNav.vue frontend/src/components/AdminMetricGroup.vue frontend/src/stores/adminConsole.ts frontend/src/stores/adminConsole.test.ts frontend/src/views/AdminPortalView.vue frontend/src/views/AdminConsoleResponsive.test.ts frontend/src/router/index.ts frontend/src/api/types.ts frontend/src/data/portal-guides.ts
git commit -m "搭建 011 管理后台前端壳"
```

### Task 5: 超管与普管看板后端

**Files:**
- Create: `backend/app/admin_console/dashboard.py`
- Modify: `backend/app/admin_console/routes.py`
- Test: `backend/tests/test_admin_dashboard.py`

**Interfaces:**
- Consumes: `get_db`, `get_employment_statistics_provider`, existing course/job/policy/news/comments/points/reward/fulfillment tables.
- Produces: `get_super_admin_dashboard() -> dict`; `get_content_operations_dashboard() -> dict`; `assert_admin_dashboard_boundary(dashboard: dict) -> None`; routes `GET /api/admin/dashboard` and `GET /api/admin/content-dashboard`.

- [x] **Step 1: Write failing metric and exclusion tests**

```python
def test_content_dashboard_recursively_excludes_user_and_training_keys(self):
    response = self.admin.get("/api/admin/content-dashboard")
    dashboard = response.get_json()["dashboard"]
    forbidden = {
        "total_users", "role_distribution", "student_total", "student_count",
        "user_details", "average_progress", "completion_rate",
        "quiz_attempt_count", "quiz_average_score", "training_progress",
        "learning_behavior_count",
    }
    self.assertFalse(forbidden.intersection(walk_keys(dashboard)))
    self.assertEqual(dashboard["pending_review"]["course_video"], 2)
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_admin_dashboard -v`

Expected: FAIL with 404 or missing keys.

- [x] **Step 3: Implement both dashboard projections**

```python
def get_content_operations_dashboard() -> dict:
    dashboard = {
        "pending_review": {
            "course_video": _pending_count("course_video"),
            "job_position": _pending_count("job_position"),
            "handcraft_teaching_video": _pending_count("handcraft_teaching_video"),
        },
        "published_course_count": _published_course_count(),
        "active_job_count": _active_job_count(),
        "comment_processed_count": _processed_comment_count(),
        "report_processed_count": _processed_report_count(),
        "feedback_processed_count": _processed_feedback_count(),
        "reward_stock": _reward_stock_total(),
        "pending_fulfillment_count": _pending_fulfillment_count(),
    }
    assert_admin_dashboard_boundary(dashboard)
    return dashboard
```

`get_super_admin_dashboard()` additionally returns role counts, student count, pending review counts, policy/news counts and views, points issued, redemption count, and pending fulfillment count. Source failures return `{"available": false, "value": None}` for that metric.

- [x] **Step 4: Run dashboard tests**

Run: `uv run --directory backend python -m unittest tests.test_admin_dashboard -v`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add backend/app/admin_console/dashboard.py backend/app/admin_console/routes.py backend/tests/test_admin_dashboard.py
git commit -m "实现 011 双角色看板"
```

### Task 6: 账户管理、首个超管与密码重置

**Files:**
- Create: `backend/app/admin_console/accounts.py`
- Create: `backend/app/admin_console/seed.py`
- Modify: `backend/app/admin_console/routes.py`
- Modify: `backend/app/db.py`
- Test: `backend/tests/test_admin_accounts.py`

**Interfaces:**
- Consumes: `generate_password_hash`, `validate_registration`, `record_admin_audit`, `emit_password_reset`.
- Produces: `list_accounts(role: str | None = None, keyword: str | None = None) -> list[dict]`; `get_account(user_id: int) -> dict`; `create_managed_account(actor_id: int, payload: dict) -> dict`; `set_account_enabled(actor_id: int, user_id: int, enabled: bool) -> dict`; `reset_account_password(actor_id: int, user_id: int) -> dict`; `seed_initial_super_admin() -> int | None`.

- [x] **Step 1: Write failing account lifecycle tests**

```python
def test_create_disable_reset_and_login_with_initial_password(self):
    created = self.admin.post(
        "/api/admin/accounts",
        json={
            "role": "enterprise",
            "username": "enterprise-new",
            "name": "新企业",
            "password": "password8",
        },
    ).get_json()["account"]
    self.admin.post(
        f"/api/admin/accounts/{created['id']}/status",
        json={"enabled": False},
    )
    self.assertEqual(self.login("enterprise-new", "password8").status_code, 403)
    reset = self.admin.post(
        f"/api/admin/accounts/{created['id']}/password-reset",
    ).get_json()
    self.assertTrue(reset["success"])
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_admin_accounts -v`

Expected: FAIL with 404.

- [x] **Step 3: Implement account operations and seed**

```python
MANAGED_ROLES = {"enterprise", "government", "admin", "super_admin"}


def create_managed_account(actor_id: int, payload: dict) -> dict:
    role = _require_managed_role(payload.get("role"))
    username = _required_username(payload.get("username"))
    password = _required_password(payload.get("password"))
    name = _required_text(payload.get("name"), "姓名不能为空")
    with get_db() as db:
        cursor = db.execute(
            """
            INSERT INTO users (
                username, password_hash, name, role, is_enabled,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, 1, ?, ?)
            """,
            (
                username,
                generate_password_hash(password),
                name,
                role,
                platform_now_iso(),
                platform_now_iso(),
            ),
        )
        user_id = int(cursor.lastrowid)
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="create_account",
            target_type="user",
            target_id=str(user_id),
            before=None,
            after={"role": role, "username": username},
            result="success",
        )
    return get_account(user_id)
```

`reset_account_password()` writes a hash of the configured initial password, enqueues `password_reset` with event ID `admin-password-reset:{user_id}:{version}`, and returns the event ID. `seed_initial_super_admin()` inserts `superadmin` only when `COUNT(*) FROM users WHERE role='super_admin'` is zero; password comes from `INITIAL_SUPER_ADMIN_PASSWORD` and is never persisted in plaintext.

- [x] **Step 4: Run account tests**

Run: `uv run --directory backend python -m unittest tests.test_admin_accounts -v`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add backend/app/admin_console/accounts.py backend/app/admin_console/seed.py backend/app/admin_console/routes.py backend/app/db.py backend/tests/test_admin_accounts.py
git commit -m "实现 011 账户与权限管理"
```

### Task 7: 课程/职位统一审核真实现

**Files:**
- Create: `backend/app/admin_console/content_review_provider.py`
- Modify: `backend/app/content_review/providers.py`
- Modify: `backend/app/admin_console/providers.py`
- Test: `backend/tests/test_admin_content_review.py`

**Interfaces:**
- Consumes: Task 1 `content_review_records`, Task 2 provider registry, Task 3 errors.
- Produces: `DatabaseContentReviewProvider` implementing `ContentReviewProvider` for `course_video` and `job_position`, plus internal `list_review_items(content_type: str | None = None) -> list[dict]`; internal `_sync_course_projection(db, record)` and `_sync_job_projection(db, record)`.

- [x] **Step 1: Write failing state-machine tests**

```python
def test_rejected_can_be_edited_back_to_pending_without_stale_opinion(self):
    first = self.provider.submit_for_review(
        content_type="job_position",
        content_id="job-1",
        submitter_id=self.enterprise_id,
        expected_version=1,
        payload={"title": "职位"},
    )
    rejected = self.provider.reject(
        content_type="job_position",
        content_id="job-1",
        submitter_id=self.enterprise_id,
        reviewer_id=self.admin_id,
        reviewer_role="admin",
        expected_version=first["version"],
        opinion="补充薪资范围",
    )
    pending = self.provider.edit(
        content_type="job_position",
        content_id="job-1",
        submitter_id=self.enterprise_id,
        expected_version=rejected["version"],
        payload={"title": "职位", "salary": "5000-7000"},
    )
    self.assertEqual(pending["review_status"], "pending")
    self.assertIsNone(pending["rejection_opinion"])


def test_provider_lists_course_and_job_review_items_with_counts(self):
    items = self.provider.list_review_items()
    self.assertEqual(
        {item["content_type"] for item in items},
        {"course_video", "job_position"},
    )
    self.assertEqual(
        self.provider.list_review_items("job_position")[0]["content_id"],
        "job-1",
    )
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_admin_content_review -v`

Expected: FAIL because `DatabaseContentReviewProvider` does not exist.

- [x] **Step 3: Implement provider methods and projections**

```python
class DatabaseContentReviewProvider:
    def approve(self, *, content_type, content_id, submitter_id,
                reviewer_id, reviewer_role, expected_version):
        return self._transition(
            action="approve",
            content_type=content_type,
            content_id=content_id,
            submitter_id=submitter_id,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            expected_version=expected_version,
            opinion=None,
            payload=None,
        )
```

`_transition()` validates `reviewer_role in {"admin","super_admin"}`, opens `BEGIN IMMEDIATE`, compares `expected_version`, applies only the frozen transitions, increments version only on actual change, writes `published_at`, clears opinions on approve/pending, and inserts a notification outbox row with event ID `review:{content_type}:{content_id}:v{expected_version}:{action}`. `submit_for_review()` inserts a record only when the domain row already exists at `expected_version`; `edit()` updates record payload and moves `approved` to `pending`.

`list_review_items()` reads `content_review_records`, joins the owning
`courses` or `job_positions` row for title/owner/update metadata, filters
domain tombstones, and returns deterministic `(updated_at, content_id)` order.
It never returns payload-only records for deleted content.

- [x] **Step 4: Run content-review tests**

Run: `uv run --directory backend python -m unittest tests.test_admin_content_review tests.test_content_review_provider_contract -v`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add backend/app/admin_console/content_review_provider.py backend/app/admin_console/providers.py backend/app/content_review/providers.py backend/tests/test_admin_content_review.py
git commit -m "实现 011 课程职位审核 provider"
```

### Task 8: 05 非遗视频适配器与组合审核 provider

**Files:**
- Create: `backend/app/admin_console/handcraft_review_adapter.py`
- Modify: `backend/app/admin_console/providers.py`
- Modify: `backend/app/handcraft_inheritance/providers.py`
- Test: `backend/tests/test_admin_handcraft_review_adapter.py`

**Interfaces:**
- Consumes: 05 `get_teaching_video_provider()`, `apply_video_review()`, `AgriValidationError`, `AgriNotFoundError`, `AgriAccessError`, Task 1 errors.
- Produces: `HandcraftTeachingVideoReviewAdapter` implementing all `ContentReviewProvider` methods plus internal `list_review_items(content_type: str) -> list[dict]`; `CompositeContentReviewProvider` routing course/job to `DatabaseContentReviewProvider`, video actions to the adapter, and `list_review_items()` to the matching producer; default `content_review_provider` registration.

- [x] **Step 1: Write failing mapping and unsupported-capability tests**

```python
def test_adapter_maps_approve_and_reject_to_05_apply(self):
    result = self.adapter.approve(
        content_type="handcraft_teaching_video",
        content_id="video-1",
        submitter_id=self.teacher_id,
        reviewer_id=self.admin_id,
        reviewer_role="admin",
        expected_version=1,
    )
    self.assertEqual(result["review_status"], "approved")
    self.assertEqual(self.video_action.calls[-1]["action"], "approve")
    self.assertEqual(self.video_delivery.calls, [1])


def test_adapter_does_not_fake_first_submit_or_rejected_reopen(self):
    with self.assertRaises(ProviderConflictError):
        self.adapter.submit_for_review(
            content_type="handcraft_teaching_video",
            content_id="missing-video",
            submitter_id=self.teacher_id,
            expected_version=1,
            payload={"title": "x", "media_url": "https://example.test/x.mp4"},
        )


def test_adapter_maps_05_errors_to_provider_errors(self):
    self.video_action.error = AgriValidationError("审核版本已变化")
    with self.assertRaises(ProviderConflictError):
        self.adapter.approve(
            content_type="handcraft_teaching_video",
            content_id="video-1",
            submitter_id=self.teacher_id,
            reviewer_id=self.admin_id,
            reviewer_role="admin",
            expected_version=1,
        )


def test_adapter_distinguishes_validation_not_found_and_access_errors(self):
    cases = (
        (AgriValidationError("驳回意见不能为空"), ProviderValidationError),
        (AgriValidationError("审核版本已变化"), ProviderConflictError),
        (AgriNotFoundError("视频不存在"), ProviderNotFoundError),
        (AgriAccessError("无管理权限"), ProviderAccessDeniedError),
    )
    for source_error, target_error in cases:
        with self.subTest(source_error=type(source_error).__name__):
            self.video_action.error = source_error
            with self.assertRaises(target_error):
                self.adapter.approve(
                    content_type="handcraft_teaching_video",
                    content_id="video-1",
                    submitter_id=self.teacher_id,
                    reviewer_id=self.admin_id,
                    reviewer_role="admin",
                    expected_version=1,
                )
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_admin_handcraft_review_adapter -v`

Expected: FAIL because adapter does not exist.

- [x] **Step 3: Implement exact 05 mapping**

```python
def approve(self, *, content_type, content_id, submitter_id,
            reviewer_id, reviewer_role, expected_version):
    self._require_video_type(content_type)
    if reviewer_role not in {"admin", "super_admin"}:
        raise ProviderAccessDeniedError("无审核权限", code="review_access_denied", details={})
    result = self._call_05(
        {
            "video_id": content_id,
            "action": "approve",
            "version": expected_version,
            "submitter_id": submitter_id,
            "reviewer_id": reviewer_id,
            "reviewer_role": reviewer_role,
        }
    )
    return self._common_record(content_id, result)
```

`_call_05()` MUST call `app.handcraft_inheritance.admin_actions.apply_video_review(action)`, not the raw action provider. That wrapper owns 05 outbox delivery after commit. `_map_05_error()` uses this exact mapping:

| 05 source | Target |
| --- | --- |
| `AgriNotFoundError` | `ProviderNotFoundError` |
| `AgriAccessError` or message containing `无管理权限/仅教师/只能编辑本人` | `ProviderAccessDeniedError` |
| `AgriValidationError` with `版本` or `状态不可`/`状态已变化` | `ProviderConflictError` |
| other `AgriValidationError` (invalid action, ID, title, media URL, empty opinion) | `ProviderValidationError` |
| unexpected source/runtime failure | `ProviderUnavailableError` |

`submit_for_review()` calls `get_video(video_id)`, rejects missing or `rejected` records, and maps only `pending`/`approved` records with changed payload to `apply_video_review(action="edit")`. It never inserts into `heritage_videos`. `list_review_items()` calls `get_teaching_video_provider().list_videos()` and normalizes records for the queue without direct database access.

- [x] **Step 4: Run adapter tests**

Run: `uv run --directory backend python -m unittest tests.test_admin_handcraft_review_adapter tests.test_handcraft_admin_actions -v`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add backend/app/admin_console/handcraft_review_adapter.py backend/app/admin_console/providers.py backend/app/handcraft_inheritance/providers.py backend/tests/test_admin_handcraft_review_adapter.py
git commit -m "适配 011 与 05 非遗视频审核"
```

### Task 9: 统一审核队列、动作路由与审核前端

**Files:**
- Create: `backend/app/admin_console/content_review_service.py`
- Create: `frontend/src/views/AdminReviewView.vue`
- Create: `frontend/src/views/AdminReviewView.test.ts`
- Modify: `backend/app/admin_console/routes.py`
- Modify: `frontend/src/stores/adminConsole.ts`
- Modify: `frontend/src/router/index.ts`
- Test: `backend/tests/test_admin_content_review.py`

**Interfaces:**
- Consumes: Task 7 provider, Task 8 composite provider, Task 3 session helper.
- Produces: `list_review_queue(content_type: str | None = None) -> dict` with `items` and `counts`; `approve_review(actor: dict, *, content_type, content_id, expected_version) -> dict`; `reject_review(actor: dict, *, content_type, content_id, expected_version, opinion) -> dict`; routes `GET /api/admin/review`, `POST /api/admin/review/<content_type>/<content_id>/approve`, `POST .../reject`.

- [x] **Step 1: Write failing queue and action tests**

```python
def test_queue_lists_three_content_types_with_counts(self):
    data = self.admin.get("/api/admin/review").get_json()
    self.assertEqual(
        set(data["counts"]),
        {"course_video", "job_position", "handcraft_teaching_video"},
    )
    self.assertEqual(
        {item["content_type"] for item in data["items"]},
        {"course_video", "job_position", "handcraft_teaching_video"},
    )
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_admin_content_review -v`

Expected: FAIL with 404.

- [x] **Step 3: Implement queue, routes, and view**

```python
def list_review_queue(content_type: str | None = None) -> dict:
    allowed = {None, "course_video", "job_position", "handcraft_teaching_video"}
    if content_type not in allowed:
        raise ProviderValidationError("内容类型不正确", code="review_type_invalid", details={})
    rows = get_content_review_provider().list_review_items(content_type)
    rows.sort(key=lambda item: (item["updated_at"], item["content_type"], item["content_id"]), reverse=False)
    return {"items": rows, "counts": _counts(rows)}
```

`CompositeContentReviewProvider.list_review_items()` dispatches
`course_video`/`job_position` to `DatabaseContentReviewProvider` and
`handcraft_teaching_video` to `HandcraftTeachingVideoReviewAdapter`. The admin
service never reads `heritage_videos` or 05 tables directly.

`AdminReviewView.vue` renders a segmented `content_type` filter, three counts, a table with status/version/submitter/updated time, and approve/reject dialogs. Reject dialog uses a 500-character counter and disables submit when trimmed length is zero.

- [x] **Step 4: Run backend and frontend review tests**

Run: `uv run --directory backend python -m unittest tests.test_admin_content_review -v`

Run: `cd frontend; npm test -- --run src/views/AdminReviewView.test.ts`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add backend/app/admin_console/content_review_service.py backend/app/admin_console/routes.py backend/tests/test_admin_content_review.py frontend/src/views/AdminReviewView.vue frontend/src/views/AdminReviewView.test.ts frontend/src/stores/adminConsole.ts frontend/src/router/index.ts
git commit -m "实现 011 统一审核队列与页面"
```

### Task 10: 权威奖品目录与库存 provider

**Files:**
- Create: `backend/app/admin_console/rewards.py`
- Modify: `backend/app/admin_console/providers.py`
- Modify: `backend/app/admin_console/routes.py`
- Modify: `backend/app/db.py`
- Test: `backend/tests/test_admin_rewards_fulfillment.py`

**Interfaces:**
- Consumes: Task 1 `admin_rewards` and existing `reward_stock_reservations`, Task 2 registry.
- Produces: `DatabaseRewardCatalogProvider.list_rewards()`, `reserve_stock(reward_id, quantity, reservation_id) -> str | None`, `release_stock(reservation_id) -> bool`; `list_rewards_admin()`, `create_reward(actor_id, payload)`, `update_reward(actor_id, reward_id, expected_version, payload)`, `set_reward_online(actor_id, reward_id, expected_version, online)`; routes `GET/POST /api/admin/rewards`, `PUT /api/admin/rewards/<reward_id>`, `POST /api/admin/rewards/<reward_id>/online`.

- [x] **Step 1: Write failing catalog and stock tests**

```python
def test_admin_created_reward_is_immediately_visible_to_05(self):
    response = self.admin.post(
        "/api/admin/rewards",
        json={"name": "新奖品", "points_cost": 20, "stock": 3},
    )
    reward_id = response.get_json()["reward"]["reward_id"]
    visible = get_reward_catalog_provider().list_rewards()
    self.assertIn(reward_id, {reward["reward_id"] for reward in visible})


def test_offline_reward_cannot_reserve_stock(self):
    self.assertEqual(
        get_reward_catalog_provider().reserve_stock("reward-offline", 1, "r1"),
        None,
    )
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_admin_rewards_fulfillment -v`

Expected: FAIL because admin reward routes/provider do not exist.

- [x] **Step 3: Implement reward table and provider**

```python
class DatabaseRewardCatalogProvider:
    def list_rewards(self) -> list[dict]:
        rows = get_db().execute(
            """
            SELECT reward_id, name, points_cost, stock, is_online,
                   source_available, version, updated_at
            FROM admin_rewards
            ORDER BY is_online DESC, points_cost ASC, reward_id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def reserve_stock(self, reward_id, quantity, reservation_id):
        return reserve_reward_stock(
            reward_id,
            quantity,
            reservation_id,
            require_online=True,
        )
```

`admin_rewards` columns are `reward_id TEXT PRIMARY KEY`, `name`, `points_cost INTEGER CHECK(points_cost > 0)`, `stock INTEGER CHECK(stock >= 0)`, `is_online INTEGER`, `source_available INTEGER`, `version INTEGER`, `created_at`, `updated_at`. Reservation and release use `BEGIN IMMEDIATE`; reserved rows count against stock.

- [x] **Step 4: Run reward tests**

Run: `uv run --directory backend python -m unittest tests.test_admin_rewards_fulfillment -v`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add backend/app/admin_console/rewards.py backend/app/admin_console/providers.py backend/app/admin_console/routes.py backend/app/db.py backend/tests/test_admin_rewards_fulfillment.py
git commit -m "实现 011 奖品目录与库存 provider"
```

### Task 11: 兑换查询与履约动作

**Files:**
- Modify: `backend/app/admin_console/rewards.py`
- Modify: `backend/app/admin_console/routes.py`
- Test: `backend/tests/test_admin_rewards_fulfillment.py`

**Interfaces:**
- Consumes: Task 10 reward provider, 05 `apply_fulfillment_admin_action()`, `get_points_ledger()`, existing `redemptions`/`fulfillments`.
- Produces: `list_redemptions(actor: dict, filters: dict) -> list[dict]`; `get_redemption_detail(actor: dict, redemption_id: int) -> dict`; `list_fulfillments(actor: dict, filters: dict) -> list[dict]`; `apply_fulfillment_action(actor: dict, fulfillment_id: int, action: str) -> dict`; routes `GET /api/admin/redemptions`, `GET /api/admin/redemptions/<int:id>`, `GET /api/admin/fulfillments`, `POST /api/admin/fulfillments/<int:id>/issue|cancel|verify`.

- [x] **Step 1: Write failing cancellation and context tests**

```python
def test_cancel_restores_points_stock_and_returns_user_context(self):
    before = get_points_account(self.student_id)["balance"]
    response = self.admin.post(f"/api/admin/fulfillments/{self.fulfillment_id}/cancel")
    self.assertEqual(response.status_code, 200)
    self.assertEqual(get_points_account(self.student_id)["balance"], before + 30)
    detail = self.admin.get(f"/api/admin/redemptions/{self.redemption_id}").get_json()
    self.assertEqual(detail["user"]["contact"], "13800000000")
    self.assertTrue(detail["points_ledger"])
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_admin_rewards_fulfillment.AdminRewardFulfillmentTests.test_cancel_restores_points_stock_and_returns_user_context -v`

Expected: FAIL with 404.

- [x] **Step 3: Implement read models and action delegation**

```python
def apply_fulfillment_action(actor: dict, fulfillment_id: int, action: str) -> dict:
    operation = {
        "issue": "issue",
        "cancel": "cancel_pending",
        "verify": "manual_verify",
    }.get(action)
    if operation is None:
        raise ProviderValidationError("履约动作不正确", code="fulfillment_action_invalid", details={})
    result = apply_fulfillment_admin_action(
        {
            "fulfillment_id": fulfillment_id,
            "action": operation,
            "admin_role": actor["role"],
            "actor_id": actor["id"],
        }
    )
    record_admin_audit(
        get_db(),
        actor_id=actor["id"],
        action=f"fulfillment_{action}",
        target_type="fulfillment",
        target_id=str(fulfillment_id),
        before=None,
        after=result,
        result="success",
    )
    return result
```

`get_redemption_detail()` joins redemption, user, fulfillment and reservation, then calls `get_points_ledger(user_id)` for the complete ledger. No account-management fields are included.

`apply_fulfillment_action()` delegates to 05
`apply_fulfillment_admin_action()`, which owns the existing
`fulfillment_notification_outbox` write and delivery. 11 only adds audit and
response projection for these actions; it MUST NOT enqueue or deliver a second
fulfillment notification through `admin_notification_outbox`.

- [x] **Step 4: Run fulfillment tests**

Run: `uv run --directory backend python -m unittest tests.test_admin_rewards_fulfillment tests.test_handcraft_fulfillment -v`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add backend/app/admin_console/rewards.py backend/app/admin_console/routes.py backend/tests/test_admin_rewards_fulfillment.py
git commit -m "实现 011 兑换查询与履约管理"
```

### Task 12: 系统公告与 02 群发

**Files:**
- Create: `backend/app/admin_console/system_announcements.py`
- Modify: `backend/app/admin_console/routes.py`
- Modify: `backend/app/messaging/events.py`
- Modify: `backend/app/db.py`
- Test: `backend/tests/test_admin_console_foundation.py`

**Interfaces:**
- Consumes: `emit_notifications`, Task 1 `admin_notification_outbox`, `system_announcements`.
- Produces: `create_announcement(actor_id: int, payload: dict) -> dict`; `publish_announcement(actor_id: int, announcement_id: str) -> dict`; `list_announcements() -> list[dict]`; `emit_system_announcement(...) -> dict`; routes `GET/POST /api/admin/announcements`, `POST /api/admin/announcements/<id>/publish`.

- [x] **Step 1: Write failing idempotent broadcast test**

```python
def test_publishing_announcement_twice_notifies_once(self):
    created = self.admin.post(
        "/api/admin/announcements",
        json={"title": "维护通知", "body": "系统维护", "target_roles": ["student"]},
    ).get_json()["announcement"]
    first = self.admin.post(f"/api/admin/announcements/{created['announcement_id']}/publish")
    second = self.admin.post(f"/api/admin/announcements/{created['announcement_id']}/publish")
    self.assertTrue(first.get_json()["changed"])
    self.assertFalse(second.get_json()["changed"])
    self.assertEqual(self.notification_count("system_announcement"), 1)
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_admin_console_foundation -v`

Expected: FAIL with 404.

- [x] **Step 3: Implement announcement state and event**

```python
def emit_system_announcement(
    *,
    event_id: str,
    recipient_ids: list[int],
    announcement_id: str,
    title: str,
    body: str,
) -> dict:
    return emit_notifications(
        recipient_ids=recipient_ids,
        event_key=f"system_announcement:{event_id}",
        event_type="system_announcement",
        title=title,
        body=body,
        source_type="system_announcement",
        source_id=announcement_id,
    )
```

`system_announcements` columns are `announcement_id TEXT PRIMARY KEY`, `title`, `body`, `target_roles_json`, `status` (`draft`/`published`), `event_id`, `created_by`, `created_at`, `published_at`. Publish selects active user IDs for target roles, writes one outbox row, then delivers after commit.

- [x] **Step 4: Run announcement tests**

Run: `uv run --directory backend python -m unittest tests.test_admin_console_foundation tests.test_notification_broadcasts -v`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add backend/app/admin_console/system_announcements.py backend/app/admin_console/routes.py backend/app/messaging/events.py backend/app/db.py backend/tests/test_admin_console_foundation.py
git commit -m "实现 011 系统公告与 02 群发"
```

### Task 13: 双看板与公告前端

**Files:**
- Create: `frontend/src/views/AdminDashboardView.vue`
- Create: `frontend/src/views/AdminDashboardView.test.ts`
- Create: `frontend/src/views/AdminAnnouncementsView.vue`
- Create: `frontend/src/views/AdminAnnouncementsView.test.ts`
- Modify: `frontend/src/stores/adminConsole.ts`
- Modify: `frontend/src/router/index.ts`

**Interfaces:**
- Consumes: Task 4 store/route shell, Task 5 dashboard APIs, Task 12 announcement APIs.
- Produces: role-selected dashboard rendering; announcement list/create/publish UI; store actions `loadDashboard`, `loadAnnouncements`, `createAnnouncement`, `publishAnnouncement`.

- [x] **Step 1: Write failing dashboard visibility tests**

```ts
it('ordinary admin renders only content operations metrics', async () => {
  auth.user = { id: 2, username: 'admin', name: '普管', role: 'admin' }
  const wrapper = mount(AdminDashboardView)
  await flushPromises()
  expect(wrapper.find('[data-test="metric-pending-course"]').exists()).toBe(true)
  expect(wrapper.text()).not.toContain('总用户数')
  expect(wrapper.text()).not.toContain('完成率')
})
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd frontend; npm test -- --run src/views/AdminDashboardView.test.ts src/views/AdminAnnouncementsView.test.ts`

Expected: FAIL because views do not exist.

- [x] **Step 3: Implement views and store actions**

```ts
async function loadDashboard(): Promise<boolean> {
  const path = auth.user?.role === 'super_admin'
    ? '/api/admin/dashboard'
    : '/api/admin/content-dashboard'
  const response = await apiFetch<{ success: true; dashboard: AdminDashboard }>(path)
  dashboard.value = response.dashboard
  return true
}
```

`AdminDashboardView.vue` groups metrics by review, content, moderation, and rewards. `AdminAnnouncementsView.vue` is only routed for `super_admin`; ordinary admin receives a 403 page if it calls the API directly.

- [x] **Step 4: Run frontend tests**

Run: `cd frontend; npm test -- --run src/views/AdminDashboardView.test.ts src/views/AdminAnnouncementsView.test.ts`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add frontend/src/views/AdminDashboardView.vue frontend/src/views/AdminDashboardView.test.ts frontend/src/views/AdminAnnouncementsView.vue frontend/src/views/AdminAnnouncementsView.test.ts frontend/src/stores/adminConsole.ts frontend/src/router/index.ts
git commit -m "实现 011 双看板与公告页面"
```

### Task 14: 账户管理前端

**Files:**
- Create: `frontend/src/views/AdminAccountsView.vue`
- Create: `frontend/src/views/AdminAccountsView.test.ts`
- Modify: `frontend/src/stores/adminConsole.ts`
- Modify: `frontend/src/router/index.ts`

**Interfaces:**
- Consumes: Task 4 shell/store, Task 6 account APIs.
- Produces: account filters/search/table/detail/create/disable/enable/reset UI; store actions `loadAccounts`, `createAccount`, `setAccountEnabled`, `resetPassword`.

- [x] **Step 1: Write failing account UI tests**

```ts
it('creates an enterprise account and resets its password', async () => {
  const wrapper = mount(AdminAccountsView)
  await wrapper.get('[data-test="account-create"]').trigger('click')
  await wrapper.get('[data-test="account-role"]').setValue('enterprise')
  await wrapper.get('[data-test="account-username"]').setValue('enterprise-new')
  await wrapper.get('[data-test="account-password"]').setValue('password8')
  await wrapper.get('[data-test="account-submit"]').trigger('click')
  await flushPromises()
  expect(apiFetch).toHaveBeenCalledWith('/api/admin/accounts', expect.any(Object))
})
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd frontend; npm test -- --run src/views/AdminAccountsView.test.ts`

Expected: FAIL because view does not exist.

- [x] **Step 3: Implement account screen**

```vue
<template>
  <section data-test="admin-accounts">
    <form @submit.prevent="submitAccount">
      <select v-model="role" data-test="account-role">...</select>
      <input v-model.trim="username" data-test="account-username" />
      <input v-model="password" type="password" data-test="account-password" />
      <button data-test="account-submit" :disabled="saving">创建账户</button>
    </form>
    <table data-test="account-table">...</table>
  </section>
</template>
```

The route is super-admin only. No delete control exists. Reset confirmation states that the password will be delivered by 02 or offline and never renders a password.

- [x] **Step 4: Run account frontend tests**

Run: `cd frontend; npm test -- --run src/views/AdminAccountsView.test.ts src/stores/adminConsole.test.ts`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add frontend/src/views/AdminAccountsView.vue frontend/src/views/AdminAccountsView.test.ts frontend/src/stores/adminConsole.ts frontend/src/router/index.ts
git commit -m "实现 011 账户管理页面"
```

### Task 15: 奖品、履约与兑换前端

**Files:**
- Create: `frontend/src/views/AdminRewardsView.vue`
- Create: `frontend/src/views/AdminRewardsView.test.ts`
- Create: `frontend/src/views/AdminRedemptionsView.vue`
- Create: `frontend/src/views/AdminRedemptionsView.test.ts`
- Modify: `frontend/src/stores/adminConsole.ts`
- Modify: `frontend/src/router/index.ts`

**Interfaces:**
- Consumes: Task 10/11 APIs, Task 4 shell/store.
- Produces: reward CRUD/online toggle, fulfillment queue actions, redemption search/detail with user context and points ledger; store actions for all reward/fulfillment/redemption operations.

- [x] **Step 1: Write failing reward and fulfillment UI tests**

```ts
it('cancels a pending fulfillment and refreshes redemption detail', async () => {
  const wrapper = mount(AdminRewardsView)
  await wrapper.get('[data-test="fulfillment-cancel-1"]').trigger('click')
  await wrapper.get('[data-test="confirm-cancel"]').trigger('click')
  await flushPromises()
  expect(apiFetch).toHaveBeenCalledWith(
    '/api/admin/fulfillments/1/cancel',
    expect.objectContaining({ method: 'POST' })
  )
})
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd frontend; npm test -- --run src/views/AdminRewardsView.test.ts src/views/AdminRedemptionsView.test.ts`

Expected: FAIL because views do not exist.

- [x] **Step 3: Implement reward/fulfillment/redemption screens**

```ts
async function cancelFulfillment(id: number): Promise<boolean> {
  const response = await apiFetch<{ success: true; fulfillment: AdminFulfillment }>(
    `/api/admin/fulfillments/${id}/cancel`,
    { method: 'POST' }
  )
  replaceFulfillment(response.fulfillment)
  return true
}
```

`AdminRewardsView.vue` uses icon buttons for issue/cancel/verify with accessible labels and tooltips. `AdminRedemptionsView.vue` shows user identity/contact only inside redemption/fulfillment detail, and never renders account status or points-policy controls.

- [x] **Step 4: Run reward frontend tests**

Run: `cd frontend; npm test -- --run src/views/AdminRewardsView.test.ts src/views/AdminRedemptionsView.test.ts`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add frontend/src/views/AdminRewardsView.vue frontend/src/views/AdminRewardsView.test.ts frontend/src/views/AdminRedemptionsView.vue frontend/src/views/AdminRedemptionsView.test.ts frontend/src/stores/adminConsole.ts frontend/src/router/index.ts
git commit -m "实现 011 奖品履约与兑换页面"
```

### Task 16: 积分规则数据库 provider 与管理服务

**Files:**
- Create: `backend/app/admin_console/points_policy.py`
- Modify: `backend/app/admin_console/providers.py`
- Modify: `backend/app/admin_console/routes.py`
- Modify: `backend/app/db.py`
- Test: `backend/tests/test_admin_points_policy.py`

**Interfaces:**
- Consumes: Task 1 `platform_points_policy`, Task 2 registry, 05 `_normalize_policy`-compatible fields.
- Produces: `DatabasePointsPolicyProvider.get_policy() -> dict | None`; `get_points_policy() -> dict`; `update_points_policy(actor_id: int, payload: dict, expected_version: int) -> dict`; routes `GET/PUT /api/admin/points-policy`.

- [x] **Step 1: Write failing policy validation and immediacy tests**

```python
def test_updated_training_weight_is_used_by_05_on_next_event(self):
    policy = get_points_policy()
    response = self.admin.put(
        "/api/admin/points-policy",
        json={
            "expected_version": policy["version"],
            "seconds_per_point": 300,
            "training_weights": {
                "default": 1,
                "live_script": 4,
                "simulation": 3,
                "copy_training": 2,
                "customer_service": 5,
            },
            "daily_limit": 50,
            "expiry_mode": "natural_year",
        },
    )
    self.assertEqual(response.status_code, 200)
    self.assertEqual(get_effective_policy()["training_weights"]["live_script"], 4)
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_admin_points_policy -v`

Expected: FAIL with 404 or placeholder policy.

- [x] **Step 3: Implement policy storage and provider**

```python
class DatabasePointsPolicyProvider:
    def get_policy(self) -> dict | None:
        row = get_db().execute(
            """
            SELECT policy_json
            FROM platform_points_policy
            WHERE singleton = 1
            """
        ).fetchone()
        return json.loads(row["policy_json"]) if row else None
```

`platform_points_policy` has one row with `singleton=1`, `version`, `policy_json`, `updated_by`, `updated_at`. `update_points_policy()` validates exact keys and positive integer weights, checks expected version, writes a new version, and records audit. Existing points snapshots remain untouched.

- [x] **Step 4: Run points policy tests**

Run: `uv run --directory backend python -m unittest tests.test_admin_points_policy tests.test_handcraft_points tests.test_handcraft_points_expiry -v`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add backend/app/admin_console/points_policy.py backend/app/admin_console/providers.py backend/app/admin_console/routes.py backend/app/db.py backend/tests/test_admin_points_policy.py
git commit -m "实现 011 平台积分规则 provider"
```

### Task 17: 积分规则前端

**Files:**
- Create: `frontend/src/views/AdminPointsPolicyView.vue`
- Create: `frontend/src/views/AdminPointsPolicyView.test.ts`
- Modify: `frontend/src/stores/adminConsole.ts`
- Modify: `frontend/src/router/index.ts`

**Interfaces:**
- Consumes: Task 16 API, Task 4 shell/store.
- Produces: super-admin-only form with exact five weight keys, positive integer controls, daily limit, expiry segmented control, version conflict handling.

- [x] **Step 1: Write failing policy form test**

```ts
it('submits all five training weight keys and expiry mode', async () => {
  const wrapper = mount(AdminPointsPolicyView)
  await wrapper.get('[data-test="weight-default"]').setValue('2')
  await wrapper.get('[data-test="weight-live-script"]').setValue('5')
  await wrapper.get('[data-test="daily-limit"]').setValue('80')
  await wrapper.get('[data-test="expiry-natural-year"]').setValue()
  await wrapper.get('[data-test="points-policy-submit"]').trigger('click')
  expect(apiFetch).toHaveBeenCalledWith(
    '/api/admin/points-policy',
    expect.objectContaining({ method: 'PUT' })
  )
})
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd frontend; npm test -- --run src/views/AdminPointsPolicyView.test.ts`

Expected: FAIL because view does not exist.

- [x] **Step 3: Implement policy form**

```ts
const trainingWeights = reactive({
  default: 1,
  live_script: 1,
  simulation: 1,
  copy_training: 1,
  customer_service: 1
})

const expiryMode = ref<'permanent' | 'natural_year'>('permanent')
```

All numeric fields use `min=1`, integer parsing, inline errors, and preserve server values on conflict. The route is super-admin only.

- [x] **Step 4: Run points frontend tests**

Run: `cd frontend; npm test -- --run src/views/AdminPointsPolicyView.test.ts src/stores/adminConsole.test.ts`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add frontend/src/views/AdminPointsPolicyView.vue frontend/src/views/AdminPointsPolicyView.test.ts frontend/src/stores/adminConsole.ts frontend/src/router/index.ts
git commit -m "实现 011 积分规则页面"
```

### Task 18: 评论巡查与静默删除

**Files:**
- Create: `backend/app/admin_console/moderation.py`
- Modify: `backend/app/admin_console/routes.py`
- Test: `backend/tests/test_admin_moderation.py`

**Interfaces:**
- Consumes: existing `content_comments` table, Task 1 audit.
- Produces: `list_moderation_comments(filters: dict) -> list[dict]`; `delete_comment(actor_id: int, comment_id: str) -> dict`; `processed_comment_count() -> int`; routes `GET /api/admin/comments`, `DELETE /api/admin/comments/<comment_id>`.

- [x] **Step 1: Write failing silent-delete test**

```python
def test_delete_comment_hides_it_without_notification(self):
    response = self.admin.delete(f"/api/admin/comments/{self.comment_id}")
    self.assertEqual(response.status_code, 200)
    visible = self.student.get(f"/api/agri-skills/courses/{self.course_id}/comments")
    self.assertNotIn(self.comment_id, [item["comment_id"] for item in visible.get_json()["comments"]])
    self.assertEqual(self.notification_count(self.student_id), 0)
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_admin_moderation -v`

Expected: FAIL with 404.

- [x] **Step 3: Implement moderation service**

```python
def delete_comment(actor_id: int, comment_id: str) -> dict:
    normalized = _required_text(comment_id, "comment_id")
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM content_comments WHERE comment_id = ?",
            (normalized,),
        ).fetchone()
        if row is None:
            raise ProviderNotFoundError("评论不存在", code="comment_not_found", details={})
        db.execute(
            """
            UPDATE content_comments
            SET is_visible = 0, updated_at = ?
            WHERE comment_id = ?
            """,
            (platform_now_iso(), normalized),
        )
        record_admin_audit(
            db,
            actor_id=actor_id,
            action="delete_comment",
            target_type="content_comment",
            target_id=normalized,
            before={"is_visible": bool(row["is_visible"])},
            after={"is_visible": False},
            result="success",
        )
    return {"comment_id": normalized, "is_visible": False}
```

No notification event is emitted for comment deletion.

- [x] **Step 4: Run moderation comment tests**

Run: `uv run --directory backend python -m unittest tests.test_admin_moderation tests.test_teacher_comments -v`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add backend/app/admin_console/moderation.py backend/app/admin_console/routes.py backend/tests/test_admin_moderation.py
git commit -m "实现 011 评论巡查与静默删除"
```

### Task 19: 举报队列与反馈接收 provider

**Files:**
- Modify: `backend/app/admin_console/moderation.py`
- Modify: `backend/app/admin_console/providers.py`
- Modify: `backend/app/admin_console/routes.py`
- Modify: `backend/app/db.py`
- Test: `backend/tests/test_admin_moderation.py`

**Interfaces:**
- Consumes: Task 18 comment service, Task 1 `comment_reports`, `feedback_records`, Task 2 registry.
- Produces: `list_reports(filters)`, `resolve_report(actor_id, report_id, confirmed: bool, result: str)`, `list_feedback(filters)`, `update_feedback(actor_id, feedback_id, status, result)`, `DatabaseFeedbackIntakeProvider.submit_feedback(...)`; routes `GET /api/admin/reports`, `POST /api/admin/reports/<id>/resolve`, `GET /api/admin/feedback`, `PATCH /api/admin/feedback/<id>`.

- [x] **Step 1: Write failing report and feedback tests**

```python
def test_confirmed_report_deletes_comment_and_counts_once(self):
    first = self.admin.post(
        f"/api/admin/reports/{self.report_id}/resolve",
        json={"confirmed": True, "result": "违规"},
    )
    second = self.admin.post(
        f"/api/admin/reports/{self.report_id}/resolve",
        json={"confirmed": True, "result": "违规"},
    )
    self.assertTrue(first.get_json()["changed"])
    self.assertFalse(second.get_json()["changed"])
    self.assertEqual(processed_report_count(), 1)


def test_feedback_intake_is_idempotent(self):
    provider = get_feedback_intake_provider()
    first = provider.submit_feedback(
        submitter_id=self.student_id,
        body="建议增加夜校课程",
        idempotency_key="feedback-1",
    )
    second = provider.submit_feedback(
        submitter_id=self.student_id,
        body="建议增加夜校课程",
        idempotency_key="feedback-1",
    )
    self.assertEqual(first["feedback_id"], second["feedback_id"])
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_admin_moderation -v`

Expected: FAIL with 404 or missing provider.

- [x] **Step 3: Implement report and feedback persistence**

```python
class DatabaseFeedbackIntakeProvider:
    def submit_feedback(self, *, submitter_id, body, idempotency_key):
        normalized_body = _required_text(body, "反馈内容不能为空")
        normalized_key = _required_text(idempotency_key, "请求标识不能为空")
        with get_db() as db:
            existing = db.execute(
                """
                SELECT *
                FROM feedback_records
                WHERE submitter_id = ? AND idempotency_key = ?
                """,
                (submitter_id, normalized_key),
            ).fetchone()
            if existing is not None:
                return _serialize_feedback(existing)
            feedback_id = f"feedback-{uuid.uuid4().hex}"
            db.execute(
                """
                INSERT INTO feedback_records (
                    feedback_id, submitter_id, body, status,
                    idempotency_key, created_at, updated_at
                ) VALUES (?, ?, ?, 'pending', ?, ?, ?)
                """,
                (feedback_id, submitter_id, normalized_body, normalized_key,
                 platform_now_iso(), platform_now_iso()),
            )
        return get_feedback(feedback_id)
```

`comment_reports` uses unique `report_id`, comment/reporter IDs, reason, status (`pending`/`confirmed`/`rejected`), resolver, result and timestamps. Confirmed resolution calls `delete_comment()`; rejected resolution leaves visibility unchanged. Both paths increment processed count only when status changes from `pending`.

- [x] **Step 4: Run report/feedback tests**

Run: `uv run --directory backend python -m unittest tests.test_admin_moderation -v`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add backend/app/admin_console/moderation.py backend/app/admin_console/providers.py backend/app/admin_console/routes.py backend/app/db.py backend/tests/test_admin_moderation.py
git commit -m "实现 011 举报与反馈接收"
```

### Task 20: 评论、举报与反馈前端

**Files:**
- Create: `frontend/src/views/AdminModerationView.vue`
- Create: `frontend/src/views/AdminModerationView.test.ts`
- Modify: `frontend/src/stores/adminConsole.ts`
- Modify: `frontend/src/router/index.ts`

**Interfaces:**
- Consumes: Task 18/19 APIs, Task 4 shell/store.
- Produces: tabs for comments/reports/feedback, filters, delete confirmation, report resolution, feedback status update; ordinary-admin access only.

- [x] **Step 1: Write failing moderation UI tests**

```ts
it('confirms a report and refreshes the processed count', async () => {
  const wrapper = mount(AdminModerationView)
  await wrapper.get('[data-test="moderation-tab-reports"]').trigger('click')
  await wrapper.get('[data-test="report-confirm-report-1"]').trigger('click')
  await wrapper.get('[data-test="confirm-report-action"]').trigger('click')
  await flushPromises()
  expect(apiFetch).toHaveBeenCalledWith(
    '/api/admin/reports/report-1/resolve',
    expect.objectContaining({ method: 'POST' })
  )
})
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd frontend; npm test -- --run src/views/AdminModerationView.test.ts`

Expected: FAIL because view does not exist.

- [x] **Step 3: Implement moderation screen**

```ts
const activeTab = ref<'comments' | 'reports' | 'feedback'>('comments')
const reportAction = ref<'confirm' | 'reject' | null>(null)
```

The delete confirmation explicitly states that no notification is sent. Report resolution requires a result note. Feedback actions use a status menu with `pending`/`processed`/`closed`.

- [x] **Step 4: Run moderation frontend tests**

Run: `cd frontend; npm test -- --run src/views/AdminModerationView.test.ts`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add frontend/src/views/AdminModerationView.vue frontend/src/views/AdminModerationView.test.ts frontend/src/stores/adminConsole.ts frontend/src/router/index.ts
git commit -m "实现 011 评论举报反馈页面"
```

### Task 21: 农产品、农时与病虫害预置 provider

**Files:**
- Create: `backend/app/admin_console/presets.py`
- Modify: `backend/app/admin_console/providers.py`
- Modify: `backend/app/admin_console/routes.py`
- Modify: `backend/app/db.py`
- Test: `backend/tests/test_admin_presets.py`

**Interfaces:**
- Consumes: Task 1 agri preset tables, Task 2 registry, 03 `PresetContentProvider`.
- Produces: `DatabaseAgriPresetContentProvider` implementing `list_products`, `get_product`, `get_calendar_entry`, `list_calendar_entries`, `list_pest_entries`; admin CRUD `list_preset_items(category)`, `create_preset_item`, `update_preset_item`, `delete_preset_item` for `agri_products`, `agri_calendar`, `pest_knowledge`.

- [x] **Step 1: Write failing agri provider tests**

```python
def test_agri_calendar_edit_is_visible_to_03_on_next_read(self):
    self.admin.put(
        "/api/admin/presets/agri_calendar/calendar-litchi-4",
        json={
            "expected_version": 1,
            "product_key": "litchi",
            "month": 4,
            "tasks": ["保果施肥"],
            "management": ["及时排水"],
            "solar_terms": ["清明", "谷雨"],
            "reminder": "更新后的提示",
        },
    )
    entry = get_preset_provider().get_calendar_entry("litchi", 4)
    self.assertEqual(entry["reminder"], "更新后的提示")
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_admin_presets -v`

Expected: FAIL because tables/provider do not exist.

- [x] **Step 3: Implement agri preset provider and CRUD**

```python
class DatabaseAgriPresetContentProvider:
    def list_products(self) -> list[dict]:
        rows = get_db().execute(
            """
            SELECT product_key AS key, name, sort_order
            FROM admin_agri_products
            WHERE is_enabled = 1
            ORDER BY sort_order ASC, product_key ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def list_pest_entries(self) -> list[dict]:
        rows = get_db().execute(
            """
            SELECT item_id AS id, sort_order, pest_name, product_names_json,
                   symptoms_json, aliases_json, answer
            FROM admin_pest_knowledge
            WHERE is_enabled = 1
            ORDER BY sort_order ASC, item_id ASC
            """
        ).fetchall()
        return [_json_fields(dict(row)) for row in rows]
```

`admin_agri_products` stores product key/name/order/enabled/version. `admin_agri_calendar` has unique `(product_key, month)` and JSON arrays. `admin_pest_knowledge` has stable `item_id`, JSON product/symptom/alias arrays, answer, order/enabled/version. Delete is logical disable.

- [x] **Step 4: Run agri preset tests**

Run: `uv run --directory backend python -m unittest tests.test_admin_presets tests.test_agri_calendar tests.test_agri_qa -v`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add backend/app/admin_console/presets.py backend/app/admin_console/providers.py backend/app/admin_console/routes.py backend/app/db.py backend/tests/test_admin_presets.py
git commit -m "实现 011 农业预置内容 provider"
```

### Task 22: 非遗、成功案例与 AI 学伴知识 provider

**Files:**
- Modify: `backend/app/admin_console/presets.py`
- Modify: `backend/app/admin_console/providers.py`
- Modify: `backend/app/admin_console/routes.py`
- Modify: `backend/app/db.py`
- Test: `backend/tests/test_admin_presets.py`

**Interfaces:**
- Consumes: Task 1 tables, Task 2 knowledge provider registry, 05 `CraftPresetProvider`, 06 `LocalResourceCaseProvider`.
- Produces: `DatabaseCraftPresetProvider`; `AdminDatabaseLocalResourceCaseProvider` implementing the 06 protocol with enabled filtering; `DatabaseAssistantFeatureKnowledgeProvider.list_entries(enabled_only: bool = True) -> list[dict]`; CRUD for `handcraft_crafts`, `success_cases`, `assistant_knowledge`.

- [x] **Step 1: Write failing craft/case/knowledge tests**

```python
def test_craft_provider_keeps_stable_key_and_steps(self):
    self.admin.put(
        "/api/admin/presets/handcraft_crafts/guangxiu",
        json={
            "expected_version": 1,
            "name": "广绣",
            "introduction": "更新介绍",
            "steps": [self.step(index) for index in range(1, 7)],
            "material_guide": self.material_guide(),
            "sort_order": 1,
            "source_available": True,
            "is_enabled": True,
        },
    )
    craft = get_craft_preset_provider().get_craft("guangxiu")
    self.assertEqual(craft["craft_key"], "guangxiu")
    self.assertEqual(len(craft["steps"]), 6)
    self.assertTrue(craft["source_available"])


def test_disabled_craft_and_success_case_are_not_visible_to_consumers(self):
    self.admin.delete("/api/admin/presets/handcraft_crafts/guangxiu")
    self.assertIsNone(get_craft_preset_provider().get_craft("guangxiu"))
    self.admin.delete("/api/admin/presets/success_cases/case-litchi-coop")
    self.assertIsNone(
        get_local_resource_case_provider().get_success_case("case-litchi-coop")
    )
    self.assertNotIn(
        "case-litchi-coop",
        {
            item["id"]
            for item in get_local_resource_case_provider().list_success_cases()
        },
    )


def test_incomplete_steps_with_available_source_make_craft_not_learnable(self):
    self.admin.put(
        "/api/admin/presets/handcraft_crafts/guangxiu",
        json={
            "expected_version": 1,
            "name": "广绣",
            "introduction": "更新介绍",
            "steps": [self.step(index) for index in range(1, 6)],
            "material_guide": self.material_guide(),
            "sort_order": 1,
            "source_available": True,
            "is_enabled": True,
        },
    )
    craft = get_craft_preset_provider().get_craft("guangxiu")
    self.assertFalse(craft["available"])
    self.assertTrue(craft["source_available"])


def test_unavailable_source_with_six_steps_makes_craft_not_learnable(self):
    self.admin.put(
        "/api/admin/presets/handcraft_crafts/guangxiu",
        json={
            "expected_version": 1,
            "name": "广绣",
            "introduction": "更新介绍",
            "steps": [self.step(index) for index in range(1, 7)],
            "material_guide": self.material_guide(),
            "sort_order": 1,
            "source_available": False,
            "is_enabled": True,
        },
    )
    craft = get_craft_preset_provider().get_craft("guangxiu")
    self.assertFalse(craft["available"])
    self.assertFalse(craft["source_available"])


def test_six_step_craft_with_source_available_is_learnable(self):
    self.admin.put(
        "/api/admin/presets/handcraft_crafts/guangxiu",
        json={
            "expected_version": 1,
            "name": "广绣",
            "introduction": "更新介绍",
            "steps": [self.step(index) for index in range(1, 7)],
            "material_guide": self.material_guide(),
            "sort_order": 1,
            "source_available": True,
            "is_enabled": True,
        },
    )
    craft = get_craft_preset_provider().get_craft("guangxiu")
    self.assertTrue(craft["available"])
    self.assertEqual(len(craft["steps"]), 6)


def test_assistant_knowledge_provider_returns_enabled_entries(self):
    entries = get_assistant_feature_knowledge_provider().list_entries()
    self.assertEqual(entries[0]["title"], "如何投递简历")
    self.assertTrue(entries[0]["jump_target"])
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_admin_presets -v`

Expected: FAIL because providers do not exist.

- [x] **Step 3: Implement providers and CRUD**

```python
class DatabaseAssistantFeatureKnowledgeProvider:
    def list_entries(self, enabled_only: bool = True) -> list[dict]:
        where = "WHERE is_enabled = 1" if enabled_only else ""
        rows = get_db().execute(
            f"""
            SELECT knowledge_id, title, body, feature_key, jump_target,
                   is_enabled, version, updated_at
            FROM admin_assistant_feature_knowledge
            {where}
            ORDER BY sort_order ASC, knowledge_id ASC
            """
        ).fetchall()
        return [dict(row) for row in rows]
```

`admin_handcraft_crafts` stores `craft_key`, name, introduction, `steps_json`, `material_guide_json`, `source_available`, sort/order/enabled/version. `DatabaseCraftPresetProvider.get_craft()` returns `None` when `is_enabled = 0`; `list_crafts()` returns enabled crafts and derives `available=false` when the source is unavailable or fewer than six valid steps exist. Success cases reuse `local_resource_success_cases`; `AdminDatabaseLocalResourceCaseProvider.list_success_cases()` and `get_success_case()` return only `is_enabled = 1`, while historical records retain the stable case ID and show source unavailable instead of redirecting. `admin_assistant_feature_knowledge` stores stable knowledge ID, title/body/feature key/jump target/enabled/sort/version/timestamps.

- [x] **Step 4: Run preset provider tests**

Run: `uv run --directory backend python -m unittest tests.test_admin_presets tests.test_handcraft_presets tests.test_local_resources_cases -v`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add backend/app/admin_console/presets.py backend/app/admin_console/providers.py backend/app/admin_console/routes.py backend/app/db.py backend/tests/test_admin_presets.py
git commit -m "实现 011 非遗案例与知识库 provider"
```

### Task 23: 六类预置内容前端

**Files:**
- Create: `frontend/src/views/AdminPresetsView.vue`
- Create: `frontend/src/views/AdminPresetsView.test.ts`
- Modify: `frontend/src/stores/adminConsole.ts`
- Modify: `frontend/src/router/index.ts`

**Interfaces:**
- Consumes: Task 21/22 APIs and Task 4 shell/store.
- Produces: category tabs, data tables/forms for six content types, JSON-array subeditors for calendar/pest/craft fields, validation errors, immediate refresh.

- [x] **Step 1: Write failing preset UI test**

```ts
it('edits a pest entry and refreshes the category list', async () => {
  const wrapper = mount(AdminPresetsView)
  await wrapper.get('[data-test="preset-tab-pest_knowledge"]').trigger('click')
  await wrapper.get('[data-test="preset-edit-pest-1"]').trigger('click')
  await wrapper.get('[data-test="preset-answer"]').setValue('更新答案')
  await wrapper.get('[data-test="preset-save"]').trigger('click')
  await flushPromises()
  expect(apiFetch).toHaveBeenCalledWith(
    '/api/admin/presets/pest_knowledge/pest-1',
    expect.objectContaining({ method: 'PUT' })
  )
})
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd frontend; npm test -- --run src/views/AdminPresetsView.test.ts`

Expected: FAIL because view does not exist.

- [x] **Step 3: Implement six-category preset screen**

```ts
const categories = [
  'agri_products',
  'agri_calendar',
  'pest_knowledge',
  'handcraft_crafts',
  'success_cases',
  'assistant_knowledge'
] as const
```

Each category has a focused form component inside the view file. Stable IDs are read-only after creation. Delete actions display whether the item is only disabled or retains a historical stable ID.

- [x] **Step 4: Run preset frontend tests**

Run: `cd frontend; npm test -- --run src/views/AdminPresetsView.test.ts`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add frontend/src/views/AdminPresetsView.vue frontend/src/views/AdminPresetsView.test.ts frontend/src/stores/adminConsole.ts frontend/src/router/index.ts
git commit -m "实现 011 六类预置内容页面"
```

### Task 24: 全平台数据管理后端

**Files:**
- Create: `backend/app/admin_console/data_management.py`
- Modify: `backend/app/admin_console/routes.py`
- Modify: `backend/app/db.py`
- Modify: `backend/app/handcraft_inheritance/providers.py`
- Test: `backend/tests/test_admin_data_management.py`

**Interfaces:**
- Consumes: Task 7/8 review providers, Task 10 rewards, existing government/course/job/video/comment/preset tables.
- Produces: `list_managed_content(content_type: str, filters: dict) -> list[dict]`; `get_managed_content(content_type: str, content_id: str) -> dict`; `correct_managed_content(actor_id: int, content_type: str, content_id: str, expected_version: int, payload: dict) -> dict`; `unpublish_managed_content(...)`; `delete_managed_content(...)`; routes under `/api/admin/content/<content_type>`.

- [x] **Step 1: Write failing semantics tests**

```python
def test_policy_correction_does_not_repush_or_change_status(self):
    response = self.admin.put(
        f"/api/admin/content/policy/{self.policy_id}",
        json={"expected_version": 1, "title": "纠错标题", "content": "纠错正文"},
    )
    self.assertEqual(response.status_code, 200)
    self.assertEqual(self.policy_status(self.policy_id), "active")
    self.assertEqual(self.policy_push_count(self.policy_id), 0)


def test_course_delete_preserves_progress(self):
    self.admin.delete(
        f"/api/admin/content/course/{self.course_id}",
        json={"expected_version": 1},
    )
    self.assertEqual(self.progress_count(self.course_id), 1)
    self.assertIsNone(self.course_provider().get_course(self.course_id))


def test_every_managed_content_type_has_unpublish_delete_and_version_assertions(self):
    cases = (
        ("policy", "unpublish", "active", "unpublished"),
        ("policy", "delete", "active", None),
        ("news", "delete", "published", None),
        ("course", "unpublish", "published", "offline"),
        ("course", "delete", "published", None),
        ("job", "unpublish", "approved", "pending"),
        ("job", "delete", "approved", None),
        ("handcraft_video", "unpublish", "approved", "pending"),
        ("handcraft_video", "delete", "approved", None),
        ("comment", "delete", "visible", "hidden"),
        ("preset", "delete", "enabled", "disabled"),
    )
    for content_type, action, before, after in cases:
        with self.subTest(content_type=content_type, action=action):
            self.run_managed_content_case(content_type, action, before, after)
            self.assert_version_conflict_rejected(content_type)
            self.assert_history_preserved(content_type)


def test_deleted_course_and_job_are_absent_from_review_queue(self):
    self.admin.delete(f"/api/admin/content/course/{self.course_id}", json={"expected_version": 1})
    self.admin.delete(f"/api/admin/content/job/{self.job_id}", json={"expected_version": 1})
    queue = self.admin.get("/api/admin/review").get_json()["items"]
    self.assertNotIn(str(self.course_id), {item["content_id"] for item in queue})
    self.assertNotIn(self.job_id, {item["content_id"] for item in queue})
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_admin_data_management -v`

Expected: FAIL with 404.

- [x] **Step 3: Implement per-type management semantics**

```python
CONTENT_TYPES = {
    "policy",
    "news",
    "course",
    "job",
    "handcraft_video",
    "comment",
    "preset",
}


def delete_managed_content(actor_id, content_type, content_id, expected_version):
    handler = {
        "policy": _delete_policy,
        "news": _delete_news,
        "course": _tombstone_course,
        "job": _tombstone_job,
        "handcraft_video": _tombstone_video,
        "comment": _hide_comment,
        "preset": _disable_preset,
    }[content_type]
    return handler(actor_id, content_id, expected_version)
```

Per-type semantics are fixed as follows:

| Type | Unpublish | Delete | Review projection |
| --- | --- | --- | --- |
| Policy | `active -> unpublished`, preserve views | hard delete and remove views | no review record |
| News | not supported | hard delete | no review record |
| Course | `published -> offline`, preserve progress | `deleted_at` tombstone | filter deleted records from queue and counts |
| Job | `approved -> pending`, clear `published_at`, preserve applications | `deleted_at` tombstone | filter deleted records from queue and counts |
| Handcraft video | `approved -> pending`, clear `published_at` | `deleted_at` tombstone | filter deleted records from queue and counts |
| Comment | not supported | `is_visible=0` | not in review queue |
| Preset | logical disable | logical disable, retain stable ID | not in review queue |

Policy correction updates only title/content and never emits a publication event. News delete is hard delete. Course delete sets `courses.deleted_at` and `DatabaseTeacherCourseProvider` filters it. Job delete sets `deleted_at`; unpublish uses the existing review state. Video delete sets `heritage_videos.deleted_at` and the read provider filters it. All admin queue and dashboard queries must join or filter domain tombstones so deleted content cannot leak through `content_review_records`. Comment delete delegates to Task 18. Preset delete delegates to Task 21/22 logical disable. Every handler uses `expected_version` and writes before/after audit.

- [x] **Step 4: Run data management tests**

Run: `uv run --directory backend python -m unittest tests.test_admin_data_management tests.test_teacher_course_provider tests.test_enterprise_jobs tests.test_government_policy tests.test_government_news -v`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add backend/app/admin_console/data_management.py backend/app/admin_console/routes.py backend/app/db.py backend/app/handcraft_inheritance/providers.py backend/tests/test_admin_data_management.py
git commit -m "实现 011 全平台数据管理"
```

### Task 25: 全平台数据管理前端

**Files:**
- Create: `frontend/src/views/AdminContentManagementView.vue`
- Create: `frontend/src/views/AdminContentManagementView.test.ts`
- Modify: `frontend/src/stores/adminConsole.ts`
- Modify: `frontend/src/router/index.ts`

**Interfaces:**
- Consumes: Task 24 APIs and Task 4 shell/store.
- Produces: type-filtered content table, detail drawer/page, correction form, unpublish/delete confirmations, ordinary-admin read-only review view and super-admin actions.

- [x] **Step 1: Write failing content-management UI tests**

```ts
it('shows correction and delete to super admin and hides them from ordinary admin', async () => {
  auth.user = { id: 1, username: 'superadmin', name: '超管', role: 'super_admin' }
  const superWrapper = mount(AdminContentManagementView)
  expect(superWrapper.find('[data-test="content-correct"]').exists()).toBe(true)
  auth.user = { id: 2, username: 'admin', name: '普管', role: 'admin' }
  const adminWrapper = mount(AdminContentManagementView)
  expect(adminWrapper.find('[data-test="content-correct"]').exists()).toBe(false)
})
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd frontend; npm test -- --run src/views/AdminContentManagementView.test.ts`

Expected: FAIL because view does not exist.

- [x] **Step 3: Implement content-management screen**

```ts
const contentTypes = [
  'policy', 'news', 'course', 'job', 'handcraft_video', 'comment', 'preset'
] as const

const canManage = computed(() => auth.user?.role === 'super_admin')
```

The confirmation text distinguishes reversible unpublish from tombstone/hard delete. Policy correction is labeled as correction, not publishing. Ordinary admin sees review status and moderation context but no production/edit controls.

- [x] **Step 4: Run content-management frontend tests**

Run: `cd frontend; npm test -- --run src/views/AdminContentManagementView.test.ts`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add frontend/src/views/AdminContentManagementView.vue frontend/src/views/AdminContentManagementView.test.ts frontend/src/stores/adminConsole.ts frontend/src/router/index.ts
git commit -m "实现 011 全平台数据管理页面"
```

### Task 26: 通知 outbox 统一投递与失败重试

**Files:**
- Create: `backend/app/admin_console/outbox.py`
- Modify: `backend/app/admin_console/accounts.py`
- Modify: `backend/app/admin_console/content_review_provider.py`
- Modify: `backend/app/admin_console/rewards.py`
- Modify: `backend/app/admin_console/system_announcements.py`
- Test: `backend/tests/test_admin_console_foundation.py`
- Test: `backend/tests/test_admin_content_review.py`

**Interfaces:**
- Consumes: Task 1 `admin_notification_outbox`, existing 02 emit functions.
- Produces: `enqueue_admin_notification(db, *, event_type: str, event_id: str, payload: dict) -> int`; `deliver_admin_notification(outbox_id: int) -> dict`; `retry_admin_notifications(limit: int = 100) -> dict`.

- [x] **Step 1: Write failing commit/retry tests**

```python
def test_review_state_commits_when_notification_delivery_fails(self):
    self.messaging_failure = True
    result = self.provider.approve(
        content_type="job_position",
        content_id="job-1",
        submitter_id=self.enterprise_id,
        reviewer_id=self.admin_id,
        reviewer_role="admin",
        expected_version=1,
    )
    self.assertEqual(result["review_status"], "approved")
    self.assertEqual(self.outbox_status(result["outbox_id"]), "pending")
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_admin_content_review -v`

Expected: FAIL because outbox helper does not exist.

- [x] **Step 3: Implement outbox delivery and retry**

```python
DELIVERERS = {
    "review_approved": emit_review_result,
    "review_rejected": emit_review_result,
    "password_reset": emit_password_reset,
    "system_announcement": emit_system_announcement,
}


def deliver_admin_notification(outbox_id: int) -> dict:
    row = _load_outbox(outbox_id)
    if row["status"] == "sent":
        return {"outbox_id": outbox_id, "changed": False}
    try:
        DELIVERERS[row["event_type"]](**json.loads(row["payload_json"]))
    except Exception as error:
        _record_failure(outbox_id, error)
        raise
    _mark_sent(outbox_id)
    return {"outbox_id": outbox_id, "changed": True}
```

Business transactions enqueue before commit and call delivery after commit. Delivery failure increments attempts and records `last_error`; it never rolls back the business transaction. Retry skips `sent` rows and preserves stable event IDs.

Fulfillment issue/cancel/verify are intentionally absent from this table:
05 `apply_fulfillment_admin_action()` owns that domain outbox and delivery, so
11 only audits the returned result and never creates a duplicate event.

- [x] **Step 4: Run notification tests**

Run: `uv run --directory backend python -m unittest tests.test_admin_console_foundation tests.test_admin_content_review tests.test_handcraft_fulfillment tests.test_notification_broadcasts -v`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add backend/app/admin_console/outbox.py backend/app/admin_console/accounts.py backend/app/admin_console/content_review_provider.py backend/app/admin_console/rewards.py backend/app/admin_console/system_announcements.py backend/tests/test_admin_console_foundation.py backend/tests/test_admin_content_review.py
git commit -m "统一 011 通知 outbox 与失败重试"
```

### Task 27: 跨模块 Provider 契约验收

**Files:**
- Test: `backend/tests/test_admin_provider_acceptance.py`
- Modify: `backend/app/admin_console/providers.py`
- Modify: `backend/app/admin_console/__init__.py`

**Interfaces:**
- Consumes: Tasks 7, 8, 10, 16, 19, 21, 22.
- Produces: replacement tests proving 03/05/06/08/09/12 consumers need no code changes when 11 registers defaults.

- [x] **Step 1: Write failing provider acceptance tests**

```python
def test_all_admin_provider_slots_replace_without_consumer_changes(self):
    replacements = {
        "content_review_provider": ReplacementReviewProvider(),
        "handcraft_points_policy_provider": ReplacementPointsPolicyProvider(),
        "handcraft_reward_catalog_provider": ReplacementRewardCatalogProvider(),
        "agri_preset_provider": ReplacementAgriPresetProvider(),
        "handcraft_craft_preset_provider": ReplacementCraftPresetProvider(),
        "local_resource_case_provider": ReplacementCaseProvider(),
        "assistant_feature_knowledge_provider": ReplacementKnowledgeProvider(),
        "feedback_intake_provider": ReplacementFeedbackProvider(),
    }
    for key, provider in replacements.items():
        self.app.extensions[key] = provider
        self.assertIs(self.app.extensions[key], provider)
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_admin_provider_acceptance -v`

Expected: FAIL until all provider shapes and default registrations are exact.

- [x] **Step 3: Fix only the provider boundary**

```python
def configure_admin_providers(app: Flask, *, content_review=None,
                              points_policy=None, reward_catalog=None,
                              agri_preset=None, craft_preset=None,
                              local_case=None, knowledge=None,
                              feedback_intake=None) -> None:
    for setter, provider in (
        (set_content_review_provider, content_review),
        (set_points_policy_provider, points_policy),
        (set_reward_catalog_provider, reward_catalog),
        (set_preset_provider, agri_preset),
        (set_craft_preset_provider, craft_preset),
        (set_local_resource_case_provider, local_case),
        (set_assistant_feature_knowledge_provider, knowledge),
        (set_feedback_intake_provider, feedback_intake),
    ):
        if provider is not None:
            setter(app, provider)
```

Do not change any consumer method signature to make this test pass.

- [x] **Step 4: Run cross-module provider tests**

Run: `uv run --directory backend python -m unittest tests.test_admin_provider_acceptance tests.test_teacher_console_provider_replacement tests.test_handcraft_presets tests.test_local_resources_cases tests.test_enterprise_jobs tests.test_agri_integration -v`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add backend/app/admin_console/providers.py backend/app/admin_console/__init__.py backend/tests/test_admin_provider_acceptance.py
git commit -m "验收 011 跨模块 provider 契约"
```

### Task 28: 双角色权限矩阵后端验收

**Files:**
- Modify: `backend/tests/test_admin_permissions.py`
- Modify: `backend/app/admin_console/routes.py`

**Interfaces:**
- Consumes: all admin routes and Task 3 session helper.
- Produces: explicit positive and negative assertions for every matrix row.

- [x] **Step 1: Write failing matrix tests**

```python
def test_ordinary_admin_can_run_content_operations_but_not_accounts_or_points(self):
    self.assertEqual(self.admin.get("/api/admin/review").status_code, 200)
    self.assertEqual(self.admin.get("/api/admin/moderation").status_code, 200)
    self.assertEqual(self.admin.get("/api/admin/presets/agri_products").status_code, 200)
    self.assertEqual(self.admin.get("/api/admin/rewards").status_code, 200)
    self.assertEqual(self.admin.get("/api/admin/fulfillments").status_code, 200)
    for method, path, payload in (
        ("get", "/api/admin/accounts", None),
        ("post", "/api/admin/accounts", {"role": "enterprise", "username": "x", "name": "x", "password": "password8"}),
        ("post", "/api/admin/accounts/1/status", {"enabled": False}),
        ("post", "/api/admin/accounts/1/password-reset", None),
        ("put", "/api/admin/points-policy", {"expected_version": 1}),
        ("get", "/api/admin/announcements", None),
        ("post", "/api/admin/announcements", {"title": "x", "body": "x", "target_roles": ["student"]}),
    ):
        response = getattr(self.admin, method)(path, json=payload)
        self.assertEqual(response.status_code, 403, (method, path))


def test_ordinary_admin_cannot_read_or_manage_policy_news(self):
    for method, path, payload in (
        ("get", "/api/admin/content/policy", None),
        ("put", f"/api/admin/content/policy/{self.policy_id}", {"expected_version": 1, "title": "x"}),
        ("delete", f"/api/admin/content/policy/{self.policy_id}", {"expected_version": 1}),
        ("get", "/api/admin/content/news", None),
        ("delete", f"/api/admin/content/news/{self.news_id}", {"expected_version": 1}),
    ):
        response = getattr(self.admin, method)(path, json=payload)
        self.assertEqual(response.status_code, 403, (method, path))


def test_ordinary_admin_cannot_read_platform_dashboard(self):
    self.assertEqual(self.admin.get("/api/admin/dashboard").status_code, 403)
    self.assertEqual(self.admin.get("/api/admin/content-dashboard").status_code, 200)


def test_ordinary_admin_cannot_create_course_job_or_policy(self):
    before = (
        self.count("courses"),
        self.count("job_positions"),
        self.count("government_policies"),
    )
    requests = (
        ("post", "/api/teacher/courses", {"title": "x"}),
        ("post", "/api/enterprise/jobs", {"title": "x"}),
        ("post", "/api/government/policies", {"title": "x", "content": "x"}),
    )
    for method, path, payload in requests:
        response = getattr(self.admin, method)(path, json=payload)
        self.assertEqual(response.status_code, 403)
    self.assertEqual(
        (self.count("courses"), self.count("job_positions"), self.count("government_policies")),
        before,
    )


def test_ordinary_admin_reads_user_context_only_from_redemption_or_fulfillment(self):
    self.assertEqual(self.admin.get("/api/admin/redemptions/1").status_code, 200)
    self.assertEqual(self.admin.get("/api/admin/fulfillments").status_code, 200)
    self.assertEqual(self.admin.get("/api/admin/accounts").status_code, 403)
    self.assertEqual(self.admin.get("/api/admin/accounts?keyword=x").status_code, 403)
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_admin_permissions -v`

Expected: FAIL for any route that has a missing or overly broad role check.

- [x] **Step 3: Apply exact role sets to routes**

```python
SUPER_ADMIN = {"super_admin"}
ADMIN_OPERATIONS = {"admin", "super_admin"}


@admin_console_bp.get("/accounts")
def list_accounts_route():
    actor = require_admin_session(roles=SUPER_ADMIN)
    return jsonify(success=True, accounts=list_accounts())
```

All routes that expose account management, points-policy writes, or system announcements use `SUPER_ADMIN`. Review, moderation, presets, rewards, fulfillment, and redemption context use `ADMIN_OPERATIONS`.

- [x] **Step 4: Run permission tests**

Run: `uv run --directory backend python -m unittest tests.test_admin_permissions -v`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add backend/app/admin_console/routes.py backend/tests/test_admin_permissions.py
git commit -m "验收 011 双角色权限矩阵"
```

### Task 29: 普管看板排除项与指标口径验收

**Files:**
- Modify: `backend/tests/test_admin_dashboard.py`
- Modify: `backend/app/admin_console/dashboard.py`

**Interfaces:**
- Consumes: Tasks 5, 18, 19, 21, 22, 24.
- Produces: recursive forbidden-key test, metric formula tests, unavailable-source tests.

- [x] **Step 1: Write failing exclusion and formula tests**

```python
def test_admin_dashboard_exact_allowed_metrics_and_no_forbidden_keys(self):
    dashboard = self.admin.get("/api/admin/content-dashboard").get_json()["dashboard"]
    self.assertEqual(
        set(walk_keys(dashboard)) & FORBIDDEN_ADMIN_DASHBOARD_KEYS,
        set(),
    )
    self.assertEqual(dashboard["published_course_count"], 2)
    self.assertEqual(dashboard["active_job_count"], 3)
    self.assertEqual(dashboard["pending_fulfillment_count"], 1)
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_admin_dashboard -v`

Expected: FAIL for any metric mismatch or forbidden key leak.

- [x] **Step 3: Correct dashboard aggregation**

```python
FORBIDDEN_ADMIN_DASHBOARD_KEYS = frozenset(
    {
        "total_users",
        "role_distribution",
        "student_total",
        "student_count",
        "user_details",
        "average_progress",
        "completion_rate",
        "quiz_attempt_count",
        "quiz_average_score",
        "training_progress",
        "learning_behavior_count",
    }
)
```

Every aggregation calls the owning table/provider and returns either a real integer or `{"available": False, "value": None}`. It never returns a fabricated zero on source failure.

- [x] **Step 4: Run dashboard tests**

Run: `uv run --directory backend python -m unittest tests.test_admin_dashboard tests.test_enterprise_employment_statistics -v`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add backend/app/admin_console/dashboard.py backend/tests/test_admin_dashboard.py
git commit -m "验收 011 普管看板排除项"
```

### Task 30: 前端权限、交互和响应式验收

**Files:**
- Create: `frontend/src/views/AdminConsoleAcceptance.test.ts`
- Modify: `frontend/src/views/AdminConsoleResponsive.test.ts`
- Modify: `frontend/src/stores/adminConsole.test.ts`
- Modify: admin views from Tasks 9, 13-15, 17, 20, 23, 25.

**Interfaces:**
- Consumes: all admin views and store actions.
- Produces: role-based navigation/route assertions, form validation, loading/error/empty states, and `clientWidth == scrollWidth` geometry tests at 320/375/1280.

- [x] **Step 1: Write failing acceptance tests**

```ts
it.each([320, 375, 1280])('admin console has no horizontal overflow at %spx', async width => {
  const wrapper = mountAdminAtWidth(AdminDashboardView, width)
  await flushPromises()
  const root = wrapper.get('[data-test="admin-console"]').element as HTMLElement
  expect(root.clientWidth).toBe(root.scrollWidth)
})


it('ordinary admin cannot see account or points-policy navigation', () => {
  const wrapper = mount(AdminConsoleNav, { props: { role: 'admin' } })
  expect(wrapper.find('[data-test="admin-nav-accounts"]').exists()).toBe(false)
  expect(wrapper.find('[data-test="admin-nav-points-policy"]').exists()).toBe(false)
})
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd frontend; npm test -- --run src/views/AdminConsoleAcceptance.test.ts src/views/AdminConsoleResponsive.test.ts`

Expected: FAIL for missing selectors, route visibility, or overflow.

- [x] **Step 3: Fix UI states and responsive constraints**

```css
.admin-console {
  min-width: 0;
  overflow-x: clip;
}

.admin-console__content {
  width: min(100%, 1320px);
  min-width: 0;
}
```

Tables use horizontal scroll containers only inside the table region. Forms use stable grid tracks and `minmax(0, 1fr)`. Long Chinese text uses `line-break: strict`, `word-break: keep-all`, and `overflow-wrap: anywhere`. Icon buttons have accessible labels and tooltips.

- [x] **Step 4: Run frontend acceptance tests**

Run: `cd frontend; npm test -- --run src/views/AdminConsoleAcceptance.test.ts src/views/AdminConsoleResponsive.test.ts src/stores/adminConsole.test.ts`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add frontend/src/views/AdminConsoleAcceptance.test.ts frontend/src/views/AdminConsoleResponsive.test.ts frontend/src/stores/adminConsole.test.ts frontend/src/views/AdminDashboardView.vue frontend/src/views/AdminAccountsView.vue frontend/src/views/AdminPointsPolicyView.vue frontend/src/views/AdminReviewView.vue frontend/src/views/AdminModerationView.vue frontend/src/views/AdminPresetsView.vue frontend/src/views/AdminRewardsView.vue frontend/src/views/AdminRedemptionsView.vue frontend/src/views/AdminContentManagementView.vue frontend/src/views/AdminAnnouncementsView.vue
git commit -m "验收 011 前端权限与响应式"
```

### Task 31: 跨模块端到端集成验收

**Files:**
- Create: `backend/tests/test_admin_integration.py`
- Modify: `backend/app/admin_console/__init__.py`
- Modify: `backend/app/__init__.py`

**Interfaces:**
- Consumes: all backend tasks and existing 01/02/03/05/06/08/09/10.
- Produces: one real `create_app()` integration test proving the installed admin providers replace placeholders without changing consumers.

- [x] **Step 1: Write failing integration test**

```python
def test_real_app_uses_admin_providers_for_all_consumer_paths(self):
    app = create_app({"TESTING": True, "DATABASE": self.db_path})
    with app.app_context():
        self.assertIsInstance(
            get_content_review_provider(),
            CompositeContentReviewProvider,
        )
        self.assertIsInstance(
            get_points_policy_provider(),
            DatabasePointsPolicyProvider,
        )
        self.assertIsInstance(
            get_reward_catalog_provider(),
            DatabaseRewardCatalogProvider,
        )
        self.assertIsInstance(
            get_preset_provider(),
            DatabaseAgriPresetContentProvider,
        )
```

- [x] **Step 2: Run test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_admin_integration -v`

Expected: FAIL until `create_app()` installs the real defaults in the correct order.

- [x] **Step 3: Correct app initialization order**

```python
install_default_handcraft_services(app)
install_default_enterprise_services(app)
install_default_agri_services(app)
install_default_local_resource_services(app)
install_default_admin_services(app)
register_messaging_source_provider(app, ...)
```

`install_default_admin_services()` replaces placeholder slots only after all consumer defaults are installed. It never replaces a provider explicitly configured by tests before app initialization.

- [x] **Step 4: Run backend integration tests**

Run: `uv run --directory backend python -m unittest tests.test_admin_integration tests.test_admin_provider_acceptance tests.test_teacher_console_integration tests.test_local_resources_integration tests.test_enterprise_employment_statistics -v`

Expected: PASS.

- [x] **Step 5: Commit**

```powershell
git add backend/app/admin_console/__init__.py backend/app/__init__.py backend/tests/test_admin_integration.py
git commit -m "集成 011 后台 provider 与现有模块"
```

### Task 32: 全量回归与浏览器验收

**Files:**
- Modify: `backend/tests/test_admin_integration.py`
- Modify: `frontend/src/views/AdminConsoleAcceptance.test.ts`
- Create locally only: `.superpowers/sdd/2026-09-20-011-admin-console/browser-report.md`
- Create locally only: `.superpowers/sdd/2026-09-20-011-admin-console/screenshots/`

**Interfaces:**
- Consumes: all implementation tasks.
- Produces: backend/frontend full regression evidence and browser geometry evidence for desktop/mobile.

- [x] **Step 1: Write failing final acceptance assertions**

```python
def test_all_nine_admin_areas_are_covered(self):
    self.assertEqual(
        {
            "dashboard", "accounts", "review", "moderation",
            "presets", "rewards", "redemptions", "points_policy",
            "content_management",
        },
        self.admin_section_names(),
    )
```

- [x] **Step 2: Run full backend and frontend suites**

Run: `uv run --directory backend python -m unittest discover -s tests -v`

Run: `cd frontend; npm test`

Run: `cd frontend; npx tsc -b --noEmit`

Run: `cd frontend; npm run build`

Expected: all suites and build PASS.

- [x] **Step 3: Run browser geometry and interaction checks**

Use the project browser runbook to start the app and verify `/admin`, `/admin/review`, `/admin/moderation`, `/admin/presets`, `/admin/rewards`, `/admin/redemptions`, `/admin/accounts`, `/admin/points-policy`, `/admin/content`, `/admin/announcements` at `320`, `375`, and `1280` pixels.

Expected: every route has `clientWidth == scrollWidth`; critical actions remain reachable; role-hidden routes are absent for ordinary admin; no console errors.

- [x] **Step 4: Record verification evidence**

Write command outputs, screenshot paths, route/width matrix, and any residual visual risk to `.superpowers/sdd/2026-09-20-011-admin-console/browser-report.md`. `.superpowers/` is local-only and MUST NOT be staged or committed.

- [x] **Step 5: Commit**

```powershell
git add backend/tests/test_admin_integration.py frontend/src/views/AdminConsoleAcceptance.test.ts
git commit -m "验收 011 全量与浏览器回归"
```

### Task 33: 规格收敛与 provider 契约复核

**Files:**
- Modify: `.agents/memories/NOW.md`
- Modify: `.agents/memories/DECISIONS.md`
- Modify: `.agents/memories/guides/provider-contract.md`
- Modify: `specs/011-admin-console/checklists/requirements.md`

**Interfaces:**
- Consumes: final implementation and verification evidence.
- Produces: `$speckit-converge` result against `specs/011-admin-console/spec.md`; provider contract updates only for differences discovered during implementation.

- [x] **Step 1: Run convergence comparison**

Run: `$speckit-converge` against `specs/011-admin-console/spec.md`.

Expected: zero untracked gaps, or each gap has a concrete remediation task.

- [x] **Step 2: Reconcile the provider contract with the frozen 011 result**

```markdown
## 011 Provider Additions

- `assistant_feature_knowledge_provider`: Protocol and consumer 12 contract.
- `feedback_intake_provider`: Protocol and consumer 07/12 intake contract.
- Replace the stale `11 -> 10/11 全平台统计读取` row with:
  `11 -> 11 内部全平台统计；010 当前无 11 统计 provider 槽；若未来 010
  需要，先修订 010 consumer spec 再新增槽。`
```

Do not create a second requirements source. `spec.md` remains authoritative.

- [x] **Step 3: Update project memory**

Update `NOW.md` with implementation status, commits, tests, and retained worktree. Update `DECISIONS.md` with any durable provider decisions.

- [x] **Step 4: Re-run checklist validation**

Run: `rg -n "NEEDS CLARIFICATION|待定未决|未决占位" specs/011-admin-console/spec.md`

Expected: no matches in `spec.md`.

- [x] **Step 5: Commit**

```powershell
git add .agents/memories/NOW.md .agents/memories/DECISIONS.md .agents/memories/guides/provider-contract.md specs/011-admin-console/checklists/requirements.md
git commit -m "收敛 011 规格与跨模块契约"
```

### Task 34: 计划执行交接与工作树清理建议

**Files:**
- Modify: `.agents/memories/plans/2026-09-20-011-admin-console.md`
- Modify: `.agents/memories/NOW.md`

**Interfaces:**
- Consumes: Task 33 convergence result and final test evidence.
- Produces: execution handoff with task completion state, retained worktree path, commit range, and deferred items.

- [x] **Step 1: Record final handoff**

Append a handoff section with:

```markdown
## Execution Handoff

- Branch: `v2/lixKRT/011-admin-console`
- Worktree: `.worktrees/011-admin-console`
- Base spec commit: `1a62cf9`
- Verification: backend full suite, frontend full suite, TypeScript, build, browser matrix.
- Deferred: exact unresolved items from convergence.
```

- [x] **Step 2: Run worktree hygiene checks**

Run: `git status --short --branch`

Run: `git diff --check`

Expected: no unclassified source changes; only intentional plan/handoff edits remain.

- [x] **Step 3: Check task checklist completion**

Run: `rg -n "^- \[ \]" .agents/memories/plans/2026-09-20-011-admin-console.md`

Expected: no unchecked implementation steps for completed work; unfinished tasks are explicitly marked in handoff.

- [x] **Step 4: Commit final handoff**

```powershell
git add .agents/memories/plans/2026-09-20-011-admin-console.md .agents/memories/NOW.md
git commit -m "交接 011 实现计划执行状态"
```

- [x] **Step 5: Stop before merge**

Do not merge, push, clean worktrees, or enter SDD execution without explicit authorization. Report branch, worktree, commit range, verification, and remaining work.

## Execution Handoff

- Branch: `v2/lixKRT/011-admin-console`
- Worktree: `.worktrees/011-admin-console`（位于主仓库目录内；提示词写的同级
  路径 `粤乡智匠项目.worktrees\011-admin-console` 不存在，按 `git worktree list` 解析）
- Base spec commit: `1a62cf9`
- Session 6 commit range: `356e187..cd3a93c`
  - Task 29: `0461dca`, `ef26a19`（任务级审查 PASS）
  - Task 30: `159a0d9`, `e407aa5`, `9841f37`, `e04cb18`, `f5c7e1a`（任务级审查 PASS）
  - Task 31: `10791eb`（任务级审查 PASS，生产代码零改动）
  - Task 33: `e83c778`（规格与跨模块契约收敛）
  - 收尾修复: `cd3a93c`（移除 Task 20 遗留的未使用类型导入，修复 `npm run build`）
- Session 7 commit range: `ac2dea9..12e59b4`
  - Task 32: `12e59b4`（9 管理区验收断言 + 全量四件套回归 + 真实浏览器 10x3 回归；
    最终全分支审查 APPROVE，0 Critical / 0 Important / 4 Minor）
- Verification:
  - backend full `unittest discover` at `10791eb`: `Ran 1277 tests ... OK`；
    closing re-run at `cd3a93c`: `Ran 1277 tests in 2825.341s ... OK`。
  - frontend `npx vitest run`: `113 files / 806 tests` passed（改动前后各一遍）。
  - frontend `npx tsc -b --noEmit`: exit 0。
  - frontend `npm run build`: success at `cd3a93c`（`cd3a93c` 之前失败于
    `vue-tsc` TS6196 未使用导入，属 `tsc -b` 与 build 校验范围差异）。
  - browser matrix at 320/375/1280: PRODUCED in Task 32. Super-admin 10 routes x 3
    widths = 30/30 no horizontal overflow, console nav rendered; ordinary-admin 7
    routes x 3 = 21/21; the 3 super-admin-only routes redirect ordinary admins at
    the guard; console errors empty for both roles; 22 screenshots reviewed by the
    image agent (OVERALL PASS, 2 cosmetic MINOR). Evidence:
    `.superpowers/sdd/2026-09-20-011-admin-console/browser-report.md` (local only).
- Remaining work (Task-32 verification numbers):
  - backend full at `12e59b4`: `Ran 1279 tests in 2881.807s ... OK` (1277 + 2 new).
  - frontend `vitest run`: `113 files / 809 tests` passed (806 + 3 new);
    `tsc -b --noEmit` exit 0; `npm run build` success.
- Status: Task 1-32、33、34 全部完成。
- 最终全分支审查（`1a62cf9..12e59b4`）: APPROVE — 0 Critical / 0 Important / 4 Minor:
  - `routes.py:846` GET `/points-policy` 超管专属；注释归因写"权限矩阵"实为 FR-005（行为正确）。
  - `providers.py:199` `content_review_provider` 为唯一条件装配（仅当槽空或 Unavailable 时替换；默认装配下 011 provider 生效，安全）。
  - `AdminPortalView.vue` 全量重写但未列入计划前端共享清单（属 /admin 父布局必需，PortalShell 未动，无跨模块回归）。
  - `db.py` +324 行纯新增（0 删除），落在 Task 1/24 schema 边界内。
- 4 Minor 处置（2026-09-22，`v2/lixKRT/dev` 修复提交，行为均不变）:
  - O1 `routes.py` GET `/points-policy` 注释归因已由"权限矩阵"改为 FR-005
    （普通管理员 MUST NOT 访问积分规则配置；spec 中公告面的权限矩阵归因不受影响）。
  - O2 `providers.py` `install_default_admin_services` 的条件装配已补注释登记:
    该槽是唯一条件项，测试或后续 feature 自装的非占位 review provider 保持权威，
    与 DECISIONS.md 已登记的决策一致；其余七槽仍无条件替换。
  - O3 `AdminPortalView.vue` 已补登"共享文件改动"清单（`/admin` 父布局容器，
    `PortalShell` 未动）。
  - O4 `db.py` +324 行纯新增已核实全部落在 T001/T024 声明的 schema 边界内
    （见"共享文件改动" db.py 条：T001 建表、T006/T010/T012/T016/T019/T021/T022
    只增索引/约束/seed、T022/T024 增加迁移列），0 删除、幂等迁移。
- Remaining work: 将 `v2/lixKRT/011-admin-console` 合并进 `v2/lixKRT/dev`
  （需用户明确授权；未授权则停在审查后，不 merge、不 push、不清 worktree）。
  合并须整包取 011 的 `backend/app/admin_console/`（19 文件；dev 当前为 012 的 13 文件快照），
  回收计划见 `DECISIONS.md`；`.agents/memories/{NOW,DECISIONS}.md` 需内容合并，
  `backend/app/__init__.py` 与前端共享文件需保留双方增量。
- Deferred（Task 33 收敛登记，共 27 项 minor/Info，26 开放 + 1 核实免改）:
  Task 19 (3)、Task 20 (1，h1 移动端核实免改；另 2 项已在 Task 30 修复)、
  Task 25 (2 Info；3 项 minor 已在 Task 30 修复)、Task 26 (2)、Task 27 (4)、
  Task 28 (4)、Task 29 (4)、Task 30 (3)、Task 31 (4)。明细见
  `.superpowers/sdd/2026-09-20-011-admin-console/progress.md` 各审查段（本地文件）。
  结构性登记：06/010 共享 `government_employment_statistics_provider` 槽键；
  handcraft `set_video_review_provider` 为扇出装配器；
  `handcraft_teaching_video` 看板计数恒 0（Task 8 割裂）；
  跨控制台 401/403 语义分裂有意不统一。
- Task 32 新增 deferred minor（图片 agent MINOR，cosmetic）：预置/奖品视图 "新建奖品"
  标题在 320px 下 3+1 换行；桌面端及其余视图无缺陷。
- Deviations recorded: Task 33 由主代理以记账身份完成（派单阻塞；纯文档工件）；
  收尾回归发现的 build 阻塞修复 `cd3a93c` 由主代理执行（一行删除未使用导入）。
- Stop before merge: 最终全分支审查已跑并 APPROVE；未 merge、未 push、未清理 worktree（等待合并授权）。
