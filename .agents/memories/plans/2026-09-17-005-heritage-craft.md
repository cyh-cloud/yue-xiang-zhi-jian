# 05-手工传承 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付 05-手工传承子系统，包括四大非遗技艺学习、材料采购指南、教学视频可见性与播放、AR 分步指引、平台级积分、兑换商城和履约闭环，并复用 001-004 的账户、通知、课程、AI 注册与成果边界。

**Architecture:** 后端新增 `backend/app/handcraft_inheritance/` 领域包。平台积分账户、积分批次、流水和规则求值实现在该包的 `points.py`，其他模块只通过事件 inbox 和积分服务接口写入，不直接改余额。兑换和履约使用同一 SQLite 事务及条件更新处理并发。课程学习复用 003/004 的单一方向感知 provider，方向固定为 `handcraft`。前端新增手工传承 Pinia store 和 Vue views，课程页复用 `CourseLearningPanel`，其余共享入口只扩展类型、路由和门户目录。

**Tech Stack:** Python 3.12、Flask、sqlite3、httpx、uv、unittest、Vue 3、Vite、Pinia、Vue Router、Vitest、Vue Test Utils、lucide-vue-next。

**Spec:** `specs/005-heritage-craft/spec.md`

**Branch:** `v2/lixKRT/005-heritage-craft`

**Worktree:** `.worktrees/005-heritage-craft`

## Global Constraints

- 只允许 `active` 会话的学员访问学员接口；管理员履约视图使用独立的 role-authorized service contract，复用 01 的 `super_admin` / `admin` 角色。
- 兴趣标签只读复用 01 的目录和学员偏好；技能档案统一写入仍由 07 负责。
- 通知只走 02 的 `emit_*` / `emit_notification` 通道，不新增消息中心、未读状态或公告表。
- 手工课程只使用 03/004 的单一 `agri_course_provider` 注册槽和共享课程学习函数，direction 固定为 `handcraft`。
- AI 调用只通过现有 `get_ai_client()`、`build_ai_messages()` 和调用点 allowlist；005 只有两个调用点，均无降级。
- 积分账户、积分批次、流水和兑换履约使用同一 SQLite 数据库；其他模块不得直接更新积分余额。
- 规则由 11 权威配置；005 只读 provider。配置源不可用时优先使用最后有效只读规则，无规则时暂停积分变更并保留学习进度。
- 兑换、取消、发放和核销必须定义明确事务边界；积分、库存、状态和流水不能出现部分提交。
- 08 未实现时只使用只读教学视频 provider；005 不实现教师上传、审核动作、评论举报或第二套评论存储。
- 旧系统 `app.py`、`database.py` 与根目录旧 HTML 页面禁止读取、导入、复制或迁移。
- 路由 kebab-case，Python snake_case，前端 camelCase；每个任务先写失败测试，再最小实现，最后运行定向验证并提交。

## No Placeholders Rule

- 每个任务必须列出具体 Files 和 Interfaces，不允许 `TODO`、`TBD`、空实现或“实现时再决定”。
- 08/11 未实现部分只能通过本计划明确命名的 provider / adapter 替代，不允许页面直接查种子、直接改状态或绕过服务边界。
- 共享文件改动必须说明原因；不得复制既有课程、会话、通知、标签或 AI gateway 能力来绕开共享文件。
- 每个任务完成后至少运行该任务列出的定向测试；最终任务运行全套后端、前端和构建验证。

## AI 调用点与降级矩阵

| 调用点 | 失败表现 | 降级行为 | 前端提示文案 |
| --- | --- | --- | --- |
| `handcraft_ar_guidance_generate` | 网络失败、超时、空内容、重复字段、缺少工具准备/操作要点/常见错误/步骤，或步骤结构非法 | 必须无降级；保留 `craft_key` 和当前页面选择，不保存残缺指引，不调用 003 本地知识库 | `AI 服务暂时不可用` |
| `course_quiz_grade` | 网络失败、超时、分数无效、逐题结果缺失或不一致 | 必须无降级；保留答案，不生成新成绩，不覆盖正式成绩，不使用本地答案或规则判分 | `AI 服务暂时不可用` |

005 共 2 个 AI 调用点，全部无降级。`course_quiz_grade` 复用既有稳定 key，并新增 `course_direction` 到 allowlist；`handcraft_ar_guidance_generate` 为 005 新调用点。

## 积分服务设计

### 责任边界

- 005 负责账户余额、积分批次、不可变流水、规则求值、每日封顶、过期结算、消费、回退和余额查询。
- 11 负责规则配置的权威存储和配置入口；005 只读 provider，不提供学员侧配置。
- 003、004、005 的学习行为通过 `points_event_inbox` 写入事件；积分服务负责幂等、安全校验、封顶和记账。
- 07 只消费学习成果交接引用，不直接管理积分账户。

### 账户与流水模型

| Table | Key fields | Purpose |
| --- | --- | --- |
| `points_accounts` | `user_id`, `balance`, `updated_at` | 每个学员唯一余额账户 |
| `points_lots` | `id`, `user_id`, `award_transaction_id`, `original_points`, `remaining_points`, `expires_at`, `created_at` | 支持永久和自然年过期，消费时 FIFO 扣减 |
| `points_transactions` | `id`, `user_id`, `transaction_type`, `source_module`, `source_event_id`, `delta`, `balance_after`, `created_at`, `metadata_json` | 不可变获取、消费、回退、过期流水 |
| `points_allocations` | `transaction_id`, `lot_id`, `points` | 记录一次消费/回退涉及的积分批次 |
| `points_event_inbox` | `id`, `user_id`, `source_module`, `event_type`, `source_event_id`, `occurred_at`, `duration_seconds`, `status`, `error`, `created_at` | 跨模块幂等写入和失败重处理 |
| `points_learning_accruals` | `user_id`, `source_module`, `source_key`, `accumulated_seconds`, `awarded_units`, `updated_at` | 支持不足 10 分钟的碎片累计和重复上报去重 |
| `points_policy_snapshots` | `id`, `version`, `policy_json`, `observed_at` | 持久保存最后一次有效只读规则，供规则源短暂不可用时恢复 |

### 对外写入接口

```python
enqueue_learning_event(
    user_id: int,
    source_module: str,
    event_type: str,
    source_event_id: str,
    occurred_at: str,
    duration_seconds: int | None = None,
) -> int

process_pending_events(user_id: int, limit: int = 100) -> list[dict]
```

- `source_event_id` 在 `(user_id, source_module, event_type)` 上唯一。
- 时长为负、未来、超过单段 7200 秒或事件反复上报时不增加积分。
- 离散训练事件不要求 duration；按有效规则中的训练权重发分。
- 事件先持久化再处理；处理失败保留在 inbox，后续访问积分页或后台重试时继续处理。

### 规则读取

- `PointsPolicyProvider.get_policy() -> PointsPolicy` 返回 `seconds_per_point`、`training_weights`、`daily_limit`、`expiry_mode`、`version`、`source_available`。
- 占位值固定为 600 秒/分、每类唯一成功训练 10 分、每日 60 分、默认永久。
- `get_effective_policy()` 每次优先读取 provider；读取成功后写入新的只读 snapshot。provider 失败时使用最新 snapshot；没有 snapshot 时积分累计、消费、兑换和过期暂停，并提示 `积分规则暂不可用，请稍后重试`。

### 过期与跨模块接入

- 每次获取积分时创建 lot；永久模式写 `expires_at=NULL`，自然年模式写平台时区自然年边界。
- `run_expiry_settlement(now, batch_size)` 按 lot 到期时间幂等清零，逐人写过期流水并调用 `emit_points_expired()`。
- 学员访问积分账户前先执行 `process_pending_events()` 和 `settle_user_expiry()`。
- 本期写入：手工步骤、AR、手工课程，以及 004 四类新成功训练。
- 本期不回填：003 农业课程、004 电商课程及既有 004 训练记录。

## 未实现依赖的占位与替换点

| 依赖 | 本期占位形态 | 替换钩子 |
| --- | --- | --- |
| 08 上传教学视频 | `TeachingVideoSourceProvider` 提供四个技艺的已审核演示视频、审核状态和演示播放地址；没有上传 API | `set_teaching_video_provider(app, provider)`；未来 08 实现同一只读协议 |
| 11 非遗视频审核 | `TeachingVideoReviewActionProvider` 接受 `approve` / `reject` / 版本号及审核意见，测试 adapter 可驱动状态 | `set_video_review_action_provider(app, provider)`；生产由 11 调用同一服务契约 |
| 11 奖品库 | `RewardCatalogProvider` 提供名称、积分、库存、上下架状态，并提供幂等 `reserve_stock()` / `release_stock()` | `set_reward_catalog_provider(app, provider)`；11 的替换实现必须提供同一写入契约 |
| 11 履约管理 | `FulfillmentAdminActionProvider` 接受 `issue`、`cancel_pending`、`manual_verify`；005 服务仍校验角色和状态 | `set_fulfillment_action_provider(app, provider)`；生产 overlay 由 11 调用 |
| 11 预置内容 | `CraftPresetProvider` 提供四个技艺、介绍、六步骤和材料指南 | `set_craft_preset_provider(app, provider)`；11 更新内容后保持稳定 key |
| 11 积分规则 | `PointsPolicyProvider` 提供折算、训练权重、每日上限和有效期 | `set_points_policy_provider(app, provider)`；配置入口仍在 11 |

## 与 001-004 的复用点

| 复用点 | 既有接口/组件/机制 | 005 使用方式 | 不新建的理由 |
| --- | --- | --- | --- |
| 角色与会话 | `backend/app/session_manager.py` 的 `load_session()`、`abort_session_required()`；`frontend/src/router/roleRoutes.ts` | 学员路由和授权的履约服务复用现有会话状态与角色 | 01 是认证和禁用账户的唯一边界 |
| 兴趣标签 | `interest_tags`、`student_interest_tags`、`course_interest_tags` | 手工课程推荐只读稳定 tag ID | 标签目录和偏好由 01 唯一拥有 |
| 技能档案边界 | `agri_skills.outcomes.list_learning_outcomes()`；004 `archive_written=False` 参考模式 | 005 只生成 `LearningOutcomeHandoff` 引用，等待 07 接口 | 07 尚未定义写入契约，不能建立竞争存档 |
| 通知 | `backend/app/messaging/events.py` 的 review/redemption/fulfillment/points expiry 函数 | 005 只调用既有事件函数 | 02 已拥有投递、未读和去重 |
| 课程 provider | `backend/app/agri_skills/providers.py` | 使用 `set_course_provider()` 和方向参数 `handcraft` | 新增 registry 会制造两个课程权威源 |
| 课程学习 | `backend/app/agri_skills/course_learning.py` | 复用推荐、进度、完成、测验和正式成绩规则 | 复制行为会导致课程统计分叉 |
| AI gateway | `get_ai_client()`、`complete_json()`、`AiUnavailableError` | AR 和课程测验统一走现有客户端和错误映射 | 不新建第二 AI 客户端或超时机制 |
| AI allowlist | `backend/app/agri_skills/ai_context.py` | AR 相关调用、课程测验 `course_direction` 和敏感字段过滤 | 统一调用点注册是安全审计边界 |
| 课程前端 | `CourseLearningPanel.vue`、`courseLearning.ts` | direction 联合类型增加 `handcraft`，复用同一面板 | 页面复制会继续分散课程行为 |

## 共享文件改动

| Shared file | Change | Why it cannot be bypassed |
| --- | --- | --- |
| `backend/app/__init__.py` | 安装 005 默认 provider，注册 `handcraft_inheritance_bp` 和受保护前缀 | `create_app()` 是 blueprint、provider 和保护前缀的唯一装配点 |
| `backend/app/config.py` | 增加 `POINTS_EXPIRY_TOKEN` 和 `POINTS_EXPIRY_BATCH_SIZE` | 定时入口和 batch 参数必须在应用构造前读取 |
| `backend/.env.example` | 增加过期任务 token 和 batch size 示例 | 本地和部署配置必须可复现 |
| `backend/app/db.py` | 新增积分、兑换、履约、手工艺进度、视频状态和事件 inbox 表，初始化 005 seed | 项目只有一个 SQLite schema 和初始化入口 |
| `backend/app/agri_skills/providers.py` | 将 `is_eligible_course()` 的发布、tag、duration 校验泛化到所有方向 | handcraft 不能绕过 03/004 的共享课程资格边界 |
| `backend/app/agri_skills/course_learning.py` | provider recommendation 泛化到 `handcraft`，保持 `agriculture`/`ecommerce` 兼容 | 005 必须复用同一推荐和进度算法 |
| `backend/app/agri_skills/ai_context.py` | 增加 `handcraft_ar_guidance_generate`、`course_direction` allowlist 和 handcraft domain 分类 | AI 安全审计只认这一张注册表 |
| `frontend/src/api/types.ts` | 增加手工传承、积分、兑换履约、AR、视频和成果 DTO | API 类型集中维护 |
| `frontend/src/stores/courseLearning.ts` | 方向类型扩展为 `handcraft` | 共享课程 store 不能复制 |
| `frontend/src/components/CourseLearningPanel.vue` | direction prop 支持 `handcraft` | 共享面板必须承载第三方向课程 |
| `frontend/src/router/index.ts` | 注册 005 首页、技艺、积分、兑换、课程路由 | Vue Router 是页面可达性的唯一入口 |
| `frontend/src/views/StudentPortalView.vue` | 增加手工传承快捷入口 | 学员门户入口由现有页面承载 |
| `frontend/src/data/portal-guides.ts` | 增加手工传承 portal entry 和引导步骤 | 01 首次使用引导只读取该目录 |

不修改 `frontend/src/api/client.ts`、`frontend/src/stores/auth.ts`、`frontend/src/components/AppHeader.vue`、`frontend/src/styles/tokens.css`：现有请求封装、会话 store、头部和设计 token 已能满足 005。

## File Structure

| Path | Responsibility |
| --- | --- |
| `backend/app/handcraft_inheritance/__init__.py` | 默认 provider 安装与领域导出 |
| `backend/app/handcraft_inheritance/providers.py` | 预置内容、视频、奖品、规则和管理动作 provider contracts |
| `backend/app/handcraft_inheritance/presets.py` | 08/11 缺失时四个技艺、六步骤、材料、视频、奖品和规则占位数据 |
| `backend/app/handcraft_inheritance/points.py` | 积分账户、lot、流水、事件 inbox、封顶和过期结算 |
| `backend/app/handcraft_inheritance/crafts.py` | 技艺目录、步骤进度、材料指南 |
| `backend/app/handcraft_inheritance/videos.py` | 教学视频可见性、状态契约和评论入口边界 |
| `backend/app/handcraft_inheritance/ar_guidance.py` | AR 指引生成、结构校验和无降级行为 |
| `backend/app/handcraft_inheritance/rewards.py` | 奖品、原子兑换和并发处理 |
| `backend/app/handcraft_inheritance/fulfillment.py` | 履约状态机、取消回退、发放与手工核销 |
| `backend/app/handcraft_inheritance/admin_actions.py` | 视频审核与履约管理 adapter 的受权限服务契约 |
| `backend/app/handcraft_inheritance/course_learning.py` | 手工方向课程薄封装及成果投影 |
| `backend/app/handcraft_inheritance/outcomes.py` | 07 handoff reference |
| `backend/app/handcraft_inheritance/routes.py` | `/api/handcraft-inheritance/*` 学员 API 与定时结算入口 |
| `backend/app/handcraft_inheritance/seed.py` | 005 固定占位数据和初始化幂等写入 |
| `backend/tests/test_handcraft_*.py` | 后端 foundation、积分、兑换、履约、视频、AR、课程和 API 测试 |
| `frontend/src/stores/handcraftInheritance.ts` | 技艺目录、步骤、材料、视频与 AR 状态 |
| `frontend/src/stores/handcraftPoints.ts` | 余额、流水、规则不可用状态 |
| `frontend/src/stores/handcraftRewards.ts` | 奖品、兑换和履约状态 |
| `frontend/src/components/HandcraftInheritanceNav.vue` | 005 模块导航 |
| `frontend/src/components/HandcraftCraftLearning.vue` | 六步骤、材料、视频和 AR 组合界面 |
| `frontend/src/components/HandcraftPointsPanel.vue` | 积分余额和流水 |
| `frontend/src/components/HandcraftRewardsPanel.vue` | 奖品、兑换和“我的兑换” |
| `frontend/src/views/HandcraftInheritanceHomeView.vue` | 005 首页 |
| `frontend/src/views/HandcraftCraftView.vue` | 技艺学习页 |
| `frontend/src/views/HandcraftPointsView.vue` | 积分页 |
| `frontend/src/views/HandcraftRewardsView.vue` | 商城与履约页 |
| `frontend/src/views/HandcraftCoursesView.vue` | 手工课程共享面板包装 |
| `frontend/src/api/types.ts` | 005 DTO 联合类型 |
| `frontend/src/router/index.ts` | 005 routes |
| `frontend/src/views/StudentPortalView.vue` | 学员门户入口 |
| `frontend/src/data/portal-guides.ts` | 门户引导目录 |

---

### Task 1: Backend Foundation, Schema, and Provider Registration

**Files:**
- Create: `backend/app/handcraft_inheritance/__init__.py`
- Create: `backend/app/handcraft_inheritance/providers.py`
- Create: `backend/tests/test_handcraft_foundation.py`
- Modify: `backend/app/db.py`
- Modify: `backend/app/__init__.py`

**Interfaces:**
- Consumes: `get_db()`, `init_db()`, Flask `app.extensions`, existing session manager and error classes.
- Produces: `install_default_handcraft_services(app)`, `set_craft_preset_provider(app, provider)`, `get_craft_preset_provider()`, `set_teaching_video_provider(app, provider)`, `get_teaching_video_provider()`, `set_reward_catalog_provider(app, provider)`, `get_reward_catalog_provider()`, `set_points_policy_provider(app, provider)`, `get_points_policy_provider()`.
- Produces Protocols: `TeachingVideoProvider.list_videos()`, `get_video()`, `get_review_status()`; `RewardCatalogProvider.list_rewards()`, `reserve_stock()`, `release_stock()`.
- Produces tables: `heritage_craft_progress`, `heritage_videos`, `points_accounts`, `points_lots`, `points_transactions`, `points_allocations`, `points_event_inbox`, `points_learning_accruals`, `points_policy_snapshots`, `reward_stock_reservations`, `redemptions`, `fulfillments`.

**Work:**
- [ ] Write failing table/provider/default-install tests.
- [ ] Add the schema in the shared `SCHEMA_SQL` block with foreign keys, uniqueness and state checks.
- [ ] Add provider protocols and app extension registration hooks.
- [ ] Install only default providers in `create_app()`; blueprint creation and protected-prefix registration remain in Task 14.
- [ ] Run `uv run --directory backend python -m unittest tests.test_handcraft_foundation -v`.

### Task 2: Shared AI Registry and Handcraft Course Provider Generalization

**Files:**
- Modify: `backend/app/agri_skills/ai_context.py`
- Modify: `backend/app/agri_skills/providers.py`
- Modify: `backend/app/agri_skills/course_learning.py`
- Modify: `backend/tests/test_agri_ai_context.py`
- Modify: `backend/tests/test_shared_course_provider.py`
- Modify: `backend/tests/test_agri_course_api.py`
- Modify: `backend/tests/test_agri_course_progress.py`
- Modify: `backend/tests/test_ecommerce_course_learning.py`

**Interfaces:**
- Consumes: existing `AI_FIELD_ALLOWLISTS`, `allowed_context()`, `build_ai_messages()`, `CourseProvider`, `set_course_provider()`, `list_courses()`, `list_recommendations()`.
- Produces: `handcraft_ar_guidance_generate` allowlist; `course_direction` allowlist for `course_quiz_grade`; direction-aware eligibility for `handcraft`; provider-backed recommendation for every supported direction.

**Work:**
- [ ] Add failing allowlist and sensitive-field tests for AR and handcraft quiz.
- [ ] Add failing provider test proving a handcraft course uses `list_published_courses(..., "handcraft")`.
- [ ] Generalize course validation and recommendation to provider-backed handcraft while preserving agriculture/ecommerce wrappers.
- [ ] Add handcraft domain classification without changing 003 fallback semantics.
- [ ] Run `uv run --directory backend python -m unittest tests.test_agri_ai_context tests.test_shared_course_provider tests.test_agri_course_api tests.test_agri_course_progress tests.test_ecommerce_course_learning -v`.

### Task 3: Placeholder Presets, Seed, and Rule Provider

**Files:**
- Create: `backend/app/handcraft_inheritance/presets.py`
- Create: `backend/app/handcraft_inheritance/seed.py`
- Modify: `backend/app/handcraft_inheritance/__init__.py`
- Modify: `backend/app/db.py`
- Create: `backend/tests/test_handcraft_presets.py`

**Interfaces:**
- Consumes: Task 1 provider contracts and shared app initialization.
- Produces: `PlaceholderCraftPresetProvider`, `PlaceholderTeachingVideoProvider`, `PlaceholderRewardCatalogProvider` with list/reserve/release methods, `PlaceholderPointsPolicyProvider`; fixed four-craft/six-step/material/video/reward/rule fixture; `seed_handcraft_fixtures(connection)`.

**Work:**
- [ ] Write failing assertions for four crafts, exactly six steps, material guide fields, video status, reward fields and demo point values.
- [ ] Implement stable `craft_key` / step keys / reward IDs and explicit `source_available` values.
- [ ] Install default providers in `install_default_handcraft_services(app)` and call the idempotent seed from `init_db()`.
- [ ] Test replacement by swapping each provider in `app.extensions`.
- [ ] Run `uv run --directory backend python -m unittest tests.test_handcraft_presets -v`.

### Task 4: Management Action Adapters and 02 Notification Bridge

**Files:**
- Create: `backend/app/handcraft_inheritance/admin_actions.py`
- Create: `backend/tests/test_handcraft_admin_actions.py`
- Modify: `backend/app/handcraft_inheritance/providers.py`
- Modify: `backend/app/handcraft_inheritance/__init__.py`

**Interfaces:**
- Consumes: `emit_review_result()`, `emit_fulfillment_issued()`, `emit_fulfillment_cancelled()`, role checks from 01.
- Produces: `TeachingVideoReviewActionProvider`, `FulfillmentAdminActionProvider`; `apply_video_review(action)`, `apply_fulfillment_admin_action(action)`; event payloads with stable IDs for 02 idempotency.

**Work:**
- [ ] Write failing tests for approve, reject with opinion, edit-keeps-pending, issue, cancel pending, manual verify and invalid transitions.
- [ ] Implement role-authorized action records with no direct UI dependency.
- [ ] Connect successful actions to the existing 02 event functions after transaction commit.
- [ ] Assert no new notification table or message center is created.
- [ ] Run `uv run --directory backend python -m unittest tests.test_handcraft_admin_actions -v`.

### Task 5: Points Account, Lots, Ledger, and Policy Reading

**Files:**
- Create: `backend/app/handcraft_inheritance/points.py`
- Create: `backend/tests/test_handcraft_points.py`
- Modify: `backend/app/handcraft_inheritance/__init__.py`

**Interfaces:**
- Consumes: points tables from Task 1; `PointsPolicyProvider`.
- Produces: `get_effective_policy()`, `get_points_account(user_id)`, `get_points_ledger(user_id)`, `enqueue_learning_event(...)`, `process_pending_events(user_id, limit=100)`, `record_duration_points(...)`, `record_training_points(...)`, `spend_points(...)`, `refund_points(...)`, `settle_user_expiry(...)`.

**Work:**
- [ ] Write failing ledger tests for award, spend, refund, expiry, idempotent event IDs and balance non-negativity.
- [ ] Implement account/lot/transaction writes in one transaction per event.
- [ ] Implement daily cap by natural day and segment cap by server-validated duration.
- [ ] Persist each successful provider read into `points_policy_snapshots`; implement latest-snapshot fallback and no-rule pause behavior.
- [ ] Run `uv run --directory backend python -m unittest tests.test_handcraft_points -v`.

### Task 6: Atomic Reward Redemption and Concurrency

**Files:**
- Create: `backend/app/handcraft_inheritance/rewards.py`
- Create: `backend/tests/test_handcraft_rewards.py`
- Modify: `backend/app/handcraft_inheritance/presets.py`

**Interfaces:**
- Consumes: `get_points_account()`, `spend_points()`, `emit_redemption_succeeded()`, and `RewardCatalogProvider.list_rewards()`, `reserve_stock()`, `release_stock()`.
- Produces: `list_rewards(user_id)`, `redeem_reward(user_id, reward_id, request_id)`, `list_redemptions(user_id)`.

**Work:**
- [ ] Write failing tests for insufficient points, offline reward, zero stock, concurrent requests, duplicate request IDs and provider reservation conflicts.
- [ ] Implement one `BEGIN IMMEDIATE` domain transaction. The placeholder provider participates in the same SQLite transaction through idempotent `reserve_stock()`; a future 11 provider must provide transactional reserve or idempotent compensation.
- [ ] Create redemption + spending ledger + stock reservation atomically; no auto-retry on conflict.
- [ ] After commit, emit one idempotent `emit_redemption_succeeded()` event; notification failure is retried without repeating the transaction.
- [ ] Return exact messages for insufficient points, offline, exhausted stock and retryable conflict.
- [ ] Run `uv run --directory backend python -m unittest tests.test_handcraft_rewards -v`.

### Task 7: Expiry Scheduler and Lazy Settlement

**Files:**
- Modify: `backend/app/handcraft_inheritance/points.py`
- Modify: `backend/app/config.py`
- Modify: `backend/.env.example`
- Create: `backend/tests/test_handcraft_points_expiry.py`

**Interfaces:**
- Consumes: `POINTS_EXPIRY_TOKEN`, `POINTS_EXPIRY_BATCH_SIZE`, `emit_points_expired()`.
- Produces: `run_expiry_settlement(now, batch_size)` and lazy settlement in `get_points_account()`. The protected HTTP trigger is added later by Task 14.

**Work:**
- [ ] Write failing tests for permanent mode, natural-year expiry, repeated batch execution, lazy fallback and no-rule pause.
- [ ] Implement lot FIFO expiry, one expiration transaction per learner and one notification event.
- [ ] Return idempotent settlement counts that Task 14 can expose through the protected scheduler endpoint.
- [ ] Ensure timer failure leaves pending lots for the next access or scheduled run.
- [ ] Run `uv run --directory backend python -m unittest tests.test_handcraft_points_expiry -v`.

### Task 8: Points Integration for 005 and 004 Successful Training

**Files:**
- Modify: `backend/app/handcraft_inheritance/crafts.py`
- Modify: `backend/app/handcraft_inheritance/ar_guidance.py`
- Modify: `backend/app/handcraft_inheritance/course_learning.py`
- Modify: `backend/app/ecommerce_training/live_script.py`
- Modify: `backend/app/ecommerce_training/simulation.py`
- Modify: `backend/app/ecommerce_training/copy_training.py`
- Modify: `backend/app/ecommerce_training/customer_service.py`
- Create: `backend/tests/test_handcraft_points_integration.py`

**Interfaces:**
- Consumes: Task 5 `enqueue_learning_event()` / `process_pending_events()` and the services produced by Tasks 10-13.
- Produces: points event enqueue for craft steps, AR use, handcraft course view, live-script version, completed simulation, completed copy training and completed customer-service session; no direct balance writes from 004.

**Work:**
- [ ] Write failing tests proving each unique successful source record creates one inbox event.
- [ ] Add enqueue calls inside each source transaction or immediately after the source record is committed, using a stable source event ID.
- [ ] Process pending events after commit without blocking training success on transient points failures.
- [ ] Verify existing 003/004 historical records receive zero points.
- [ ] Run affected `test_ecommerce_*` and `test_handcraft_points_integration` suites.

### Task 9: Fulfillment State Machine, Cancellation, and Role Boundaries

**Files:**
- Create: `backend/app/handcraft_inheritance/fulfillment.py`
- Create: `backend/tests/test_handcraft_fulfillment.py`
- Modify: `backend/app/handcraft_inheritance/admin_actions.py`

**Interfaces:**
- Consumes: `refund_points()`, `emit_fulfillment_issued()`, `emit_fulfillment_cancelled()`, `role` from active session, `FulfillmentAdminActionProvider`.
- Produces: `cancel_pending_fulfillment()`, `issue_fulfillment()`, `manual_verify_fulfillment()`, `student_verify_fulfillment()`, `list_student_fulfillments()`, `list_admin_fulfillments(role)`.

**Work:**
- [ ] Write failing tests for all legal and illegal transitions, duplicate requests, student ownership and admin role access.
- [ ] Implement cancellation with points, allocation reversal, stock rollback and status in one domain transaction.
- [ ] Emit one idempotent 02 notification after commit; retries do not repeat rollback.
- [ ] Apply single-click student verification with no auto-verification and preserve admin manual verify.
- [ ] Run `uv run --directory backend python -m unittest tests.test_handcraft_fulfillment -v`.

### Task 10: Craft Learning, Resume, and Material Guide Service

**Files:**
- Create: `backend/app/handcraft_inheritance/crafts.py`
- Create: `backend/tests/test_handcraft_crafts.py`
- Modify: `backend/app/handcraft_inheritance/presets.py`

**Interfaces:**
- Consumes: `CraftPresetProvider`, `enqueue_learning_event()`, `get_db()`.
- Produces: `list_crafts()`, `get_craft(craft_key)`, `get_craft_progress(user_id, craft_key)`, `complete_craft_step(user_id, craft_key, step_no, active_seconds, event_id)`, `get_material_guide(craft_key)`.

**Work:**
- [ ] Write failing tests for four crafts, six ordered steps, resume point, out-of-order submission and material fields.
- [ ] Implement monotonic progress and invalid duration rejection.
- [ ] Enqueue one points event per valid step/learning period.
- [ ] Return explicit unavailable states for malformed or missing provider content.
- [ ] Run `uv run --directory backend python -m unittest tests.test_handcraft_crafts -v`.

### Task 11: Teaching Video Visibility and Pending-Edit Contract

**Files:**
- Create: `backend/app/handcraft_inheritance/videos.py`
- Create: `backend/tests/test_handcraft_videos.py`
- Modify: `backend/app/handcraft_inheritance/providers.py`

**Interfaces:**
- Consumes: `TeachingVideoProvider`, `TeachingVideoReviewActionProvider`.
- Produces: `list_student_videos(craft_key)`, `get_video_playback(video_id)`, `list_video_reviews()`, `update_pending_video_contract(...)`, `set_video_review_provider(...)`.

**Work:**
- [ ] Write failing tests for approved visibility, pending/rejected/offline invisibility, pending edit, approved edit re-review and demo playback availability.
- [ ] Implement read-only display and status transitions through the management adapter.
- [ ] Ensure no upload, comment-report queue or comment store is created.
- [ ] Run `uv run --directory backend python -m unittest tests.test_handcraft_videos -v`.

### Task 12: AR Guidance with No Fallback

**Files:**
- Create: `backend/app/handcraft_inheritance/ar_guidance.py`
- Create: `backend/tests/test_handcraft_ar_guidance.py`
- Modify: `backend/app/agri_skills/ai_context.py`

**Interfaces:**
- Consumes: `get_ai_client()`, `complete_json()`, `build_ai_messages("handcraft_ar_guidance_generate", ...)`, `AiUnavailableError`.
- Produces: `generate_ar_guidance(user_id, craft_key, project_label)` returning the FR-077 object; exact failure message `AI 服务暂时不可用`.

**Work:**
- [ ] Write failing tests for success schema, missing sections, duplicate fields, invalid steps, timeout and no local fallback.
- [ ] Validate response before persistence or display.
- [ ] Enqueue valid AR active-use time as a points event; failed generations enqueue nothing.
- [ ] Run `uv run --directory backend python -m unittest tests.test_handcraft_ar_guidance -v`.

### Task 13: Handcraft Course Wrapper and Outcome Handoff

**Files:**
- Create: `backend/app/handcraft_inheritance/course_learning.py`
- Create: `backend/app/handcraft_inheritance/outcomes.py`
- Create: `backend/tests/test_handcraft_course.py`
- Modify: `backend/app/agri_skills/course_learning.py`

**Interfaces:**
- Consumes: `list_courses(..., "handcraft")`, `list_recommendations(..., "handcraft")`, generic progress/quiz functions.
- Produces: `list_handcraft_courses()`, `list_handcraft_recommendations()`, `get_handcraft_course_progress()`, `update_handcraft_course_progress()`, `submit_handcraft_course_quiz()`, `list_handcraft_learning_outcomes()`.

**Work:**
- [ ] Write failing tests for published handcraft filtering, recommendation order, 80% completion, lower progress regression and quiz result history.
- [ ] Implement thin wrappers over shared course functions with no duplicate SQL or scoring rules.
- [ ] Emit course-view and quiz-result learning outcomes with FR-093 fields.
- [ ] Run `uv run --directory backend python -m unittest tests.test_handcraft_course -v`.

### Task 14: Handcraft Inheritance JSON Routes and Error Handling

**Files:**
- Create: `backend/app/handcraft_inheritance/routes.py`
- Create: `backend/tests/test_handcraft_api.py`
- Modify: `backend/app/handcraft_inheritance/__init__.py`
- Modify: `backend/app/__init__.py`

**Interfaces:**
- Consumes: Task 7 `run_expiry_settlement()`, all Task 10-13 services, `load_session()`, `abort_session_required()`, existing error classes.
- Produces routes: `/api/handcraft-inheritance/crafts`, `/crafts/<key>`, `/crafts/<key>/progress`, `/crafts/<key>/steps/<n>/complete`, `/videos`, `/ar-guidance`, `/points`, `/points/ledger`, `/rewards`, `/redemptions`, `/redemptions/<id>/cancel`, `/courses`, `/recommendations`, `/courses/<id>/progress`, `/courses/<id>/quiz`, and protected `POST /api/handcraft-inheritance/internal/points-expiry/run`.

**Work:**
- [ ] Write failing API tests for learner authorization, cross-student access, validation errors, AI 503 and route payloads.
- [ ] Implement JSON-only handlers and map domain errors to stable status codes.
- [ ] Register the blueprint and protected prefix in `create_app()`.
- [ ] Add the internal expiry route using constant-time `POINTS_EXPIRY_TOKEN` comparison and idempotent settlement counts.
- [ ] Run `uv run --directory backend python -m unittest tests.test_handcraft_api -v`.

### Task 15: Shared Frontend Types and Handcraft Course Store Support

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/stores/courseLearning.ts`
- Modify: `frontend/src/components/CourseLearningPanel.vue`
- Create: `frontend/src/stores/handcraftInheritance.ts`
- Create: `frontend/src/stores/handcraftPoints.ts`
- Create: `frontend/src/stores/handcraftRewards.ts`

**Interfaces:**
- Consumes: `apiFetch()`, existing `CourseLearningStore`, existing `CourseProgress`/`CourseQuiz` types.
- Produces: `HandcraftCraft`, `HandcraftStep`, `HandcraftProgress`, `HandcraftVideo`, `HandcraftPointsAccount`, `HandcraftLedgerEntry`, `HandcraftReward`, `HandcraftRedemption`, `HandcraftFulfillment`, `HandcraftLearningOutcome`; `CourseDirection` includes `handcraft`.

**Work:**
- [ ] Write failing type/store tests for handcraft filtering, points/ledger and redemption payloads.
- [ ] Add DTOs with `source_available`, `archive_written`, `is_formal`, `return_to` and `comment_url` where applicable.
- [ ] Extend shared course store/panel direction without changing agriculture/ecommerce behavior.
- [ ] Run `cd frontend && npm test -- courseLearning handcraft`.

### Task 16: Handcraft Home and Craft Learning Frontend

**Files:**
- Create: `frontend/src/components/HandcraftInheritanceNav.vue`
- Create: `frontend/src/components/HandcraftCraftLearning.vue`
- Create: `frontend/src/views/HandcraftInheritanceHomeView.vue`
- Create: `frontend/src/views/HandcraftCraftView.vue`
- Create: `frontend/src/views/HandcraftCoursesView.vue`

**Interfaces:**
- Consumes: `handcraftInheritance` store, shared `CourseLearningPanel`, `apiFetch`, existing `AppHeader` and auth store.
- Produces: craft cards, six-step progress UI, material guide, video state, AR request entry and embedded handcraft course panel.

**Work:**
- [ ] Write failing Vue tests for 4 crafts, six steps, resume, unavailable content, video playback states and AR error message.
- [ ] Implement responsive layouts without changing global tokens.
- [ ] Wire course panel with `direction="handcraft"` and `/api/handcraft-inheritance` prefix.
- [ ] Run `cd frontend && npm test -- Handcraft`.

### Task 17: Points, Rewards, and Fulfillment Frontend

**Files:**
- Create: `frontend/src/components/HandcraftPointsPanel.vue`
- Create: `frontend/src/components/HandcraftRewardsPanel.vue`
- Create: `frontend/src/views/HandcraftPointsView.vue`
- Create: `frontend/src/views/HandcraftRewardsView.vue`

**Interfaces:**
- Consumes: `handcraftPoints` and `handcraftRewards` stores.
- Produces: balance, newest-first ledger, daily-cap notice, reward grid, redemption confirmations, fulfillment states and cancellation action.

**Work:**
- [ ] Write failing tests for insufficient points, offline reward, exhausted stock, success, pending, issued, verified and canceled states.
- [ ] Show the exact daily-limit notice and conflict retry message.
- [ ] Keep user detail and full redemption records available in admin-facing types without adding a 005 admin view.
- [ ] Run `cd frontend && npm test -- HandcraftPoints HandcraftRewards`.

### Task 18: Video, AR, and Handcraft Course Integration UI

**Files:**
- Modify: `frontend/src/components/HandcraftCraftLearning.vue`
- Modify: `frontend/src/views/HandcraftCraftView.vue`
- Modify: `frontend/src/views/HandcraftCoursesView.vue`
- Create: `frontend/src/views/HandcraftInheritanceResponsive.test.ts`

**Interfaces:**
- Consumes: Task 15-17 stores and shared course DTOs.
- Produces: complete craft-page composition, AR loading/error/retry states, approved video playback, no comment/report controls when shared comments are unavailable, and course progress/quiz behavior.

**Work:**
- [ ] Write failing UI tests for AI failure, video hidden states, course progress and 320/375/1280 overflow.
- [ ] Verify `AI 服务暂时不可用` appears exactly for AR and quiz failures.
- [ ] Keep all existing 003/004 course behavior unchanged.
- [ ] Run `cd frontend && npm test -- HandcraftInheritanceResponsive`.

### Task 19: Router, Portal, Navigation, and Guide Integration

**Files:**
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/views/StudentPortalView.vue`
- Modify: `frontend/src/data/portal-guides.ts`

**Interfaces:**
- Consumes: all Task 16-18 views.
- Produces routes `/student/handcraft-inheritance`, `/student/handcraft-inheritance/crafts/:craftKey`, `/points`, `/rewards`, `/courses`; portal quick links and onboarding guidance entries.

**Work:**
- [ ] Write failing route tests and portal-guide tests.
- [ ] Register routes under the existing student auth guard.
- [ ] Add the handcraft entry to the student portal and guide definitions.
- [ ] Leave `frontend/src/components/AppHeader.vue` unchanged; the existing home anchor is outside this feature contract.
- [ ] Run `cd frontend && npm test -- handcraftRoutes roleRoutes Portal` and `npx tsc -b --noEmit`.

### Task 20: Cross-Service Acceptance, Replacement, and Regression

**Files:**
- Create: `backend/tests/test_handcraft_integration.py`
- Create: `backend/tests/test_handcraft_placeholders.py`
- Create: `frontend/src/views/HandcraftInheritanceSession.test.ts`
- Modify: `frontend/src/views/HandcraftInheritanceResponsive.test.ts`

**Interfaces:**
- Consumes: all previous tasks, existing session expiry, notification, course-provider and AI gateway tests.
- Produces: end-to-end evidence for FR-001..FR-102 and SC-001..SC-018; provider replacement evidence for 08/11 seams; browser-visible verification evidence.

**Work:**
- [ ] Add integration tests for session expiry, cross-student denial, provider replacement, notification idempotency, points rollback and handoff fields.
- [ ] Run backend suite, frontend suite, type check and production build.
- [ ] Run browser checks at 320/375/1280 for horizontal overflow, AR error copy, points flow and reward flow.
- [ ] Record any residual visual risk in `.agents/memories/NOW.md`; do not change the frozen spec silently.

## Task Dependency Order

1. Task 1 must precede all backend work.
2. Task 2 must precede Task 13 and any handcraft course view.
3. Tasks 3-4 must precede Tasks 5-12.
4. Task 5 must precede Tasks 6-9.
5. Task 6 must precede Task 9.
6. Task 7 must precede the internal scheduler route in Task 14.
7. Task 8 must follow Tasks 10-13 because it wires those source records into points.
8. Tasks 10-13 must precede Task 14 routes.
9. Task 14 must precede Tasks 15-20.
10. Task 15 must precede Tasks 16-18.
11. Task 19 must follow all views and precede Task 20 browser verification.

## Suggested Session Split

1. **当前会话：Tasks 1-7** - Foundation, shared provider/AI contracts, placeholders, management actions, points core, atomic redemption and expiry service. These tasks are ordered to run without depending on later learning-service files.
2. **下一会话：Tasks 8-20** - Finish source integrations, fulfillment, learning services, JSON routes, frontend, route integration and final verification.

## Plan Self-Review

- Spec sections pending provider replacement, manual data preservation and no-fallback AI behavior are represented by Tasks 3, 4, 12 and 20.
- Each task has explicit Files and Interfaces blocks and a concrete verification command.
- The plan does not create `tasks.md` and does not replace the spec as feature authority.
