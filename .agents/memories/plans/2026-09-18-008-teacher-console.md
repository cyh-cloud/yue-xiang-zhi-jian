# 008-教师工作台 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付教师工作台，包括课程视频生产与审核状态机、AI 课后测验配置、教学公告、课程/非遗视频答疑、教师聚合看板和 AI 学情报告，同时以既有 `CourseProvider` 向 03/04/05 供课。

**Architecture:** 后端新增 `backend/app/teacher_console/` 领域包，课程内容保存在现有 `courses`/`course_quizzes` 体系，审核状态只通过通用 `ContentReviewProvider` 读取和变更。新增 `backend/app/content_review/` 作为 11 的 facade 契约与完整占位槽；11 落地时替换 provider，08 消费代码不变。前端在现有教师门户壳层下新增 Pinia store、课程管理、公告互动、看板报告四组路由和视图。

**Tech Stack:** Python 3.12、Flask、sqlite3、httpx、uv、unittest、Vue 3、Vite、Pinia、Vue Router、Vitest、Vue Test Utils、lucide-vue-next。

**Spec:** `specs/008-teacher-console/spec.md`

**Branch:** `v2/lixKRT/008-teacher-console`

**Worktree:** `.worktrees/008-teacher-console`

## Global Constraints

- 只允许 `active` 会话中的 `teacher` 角色访问 `/api/teacher/*`；身份、提交者和审核者字段由 01 会话覆盖。
- 课程必须经审核，不提供直接发布接口；所有课程可见性由统一状态解析函数决定。
- 08 实现既有 `CourseProvider`，只使用 `agri_course_provider` 注册槽，不创建第二张课程或测验注册表。
- 08 只调用 11 的通用 `ContentReviewProvider` 五方法，不读取、导入或复制 05 的 `apply(action)` 视频审核分支。
- 新增跨模块内容 ID 使用非空字符串；课程 provider 继续使用正整数 `int`，适配器负责 `str(course_id)` / `int(content_id)` 转换。
- 新 provider 时间字段使用带时区 ISO 8601；持久化规范值为 `+08:00`，排序前解析时间。
- 新 08/审核边界错误使用 `ProviderError` 层级；03/04/05/02 现有错误类型不回改。
- 本地视频支持 MP4/WebM、最大 500 MiB；外链支持可访问的 HTTP(S) 地址；两者由教师二选一。
- 课程标签为自由文本多选；`content_tags` 保存原文，`tag_ids` 只保存与 01 活跃 crop/skill 标签的精确匹配，允许为空。
- 已上架课程编辑或题库修改必须重新进入待审核，期间课程与测验同时不可见。
- AI 只通过 `get_ai_client()`、`build_ai_messages()` 和 allowlist 调用；008 新增两个调用点且均无降级。
- 通知只走 02；08 不发送审核结果通知，审核通知归 11。
- 看板只返回聚合数据，不返回姓名、联系方式、档案或可下钻个人记录。
- 旧系统根目录 `app.py`、`database.py` 和旧 HTML 页面禁止读取、导入、复制或迁移。
- 每个任务先写失败测试，再最小实现，再运行定向测试；每个任务单独提交。

## No Placeholders Rule

- 每个任务必须列出具体 Files、Interfaces、测试和实现步骤，不允许 `TODO`、`TBD`、空实现或“实现时再决定”。
- 11 未落地时只允许使用本计划定义的 `UnavailableContentReviewProvider` 完整占位实现；它必须实现五个 Protocol 方法，写入动作统一抛出 `ProviderUnavailableError`。
- 11 落地后只调用一次 `set_content_review_provider()` 替换注册槽；08 不判断“是否占位”而分叉业务路径。
- 03/04/05 现有课程消费方不修改调用签名；若行为测试失败，只修 08 provider 或共享适配器。

## AI 调用点与降级矩阵

| 调用点 | 输入 | 输出校验 | 失败表现 | 降级行为 | 提示文案 |
| --- | --- | --- | --- | --- | --- |
| `teacher_quiz_generate` | `course_summary`、`course_direction` | 3～5 道题；仅 `single_choice` / `true_false`；题干、选项、答案合法且唯一 | 网络失败、超时、JSON 非法、重复键、题量/题型/答案非法 | 无降级；不保存残缺题库，课程手动字段和关闭测验路径仍可保存 | `AI 服务暂时不可用` |
| `teacher_learning_report_generate` | 聚合统计、方向对比、风险计数；不含用户 ID、姓名或联系方式 | 三个非空部分：`progress_analysis`、`direction_comparison`、`risk_warning` | 网络失败、超时、JSON 非法、缺段或空段 | 无降级；不保存残缺报告，统计卡片继续返回 | `AI 服务暂时不可用` |

既有 `course_quiz_grade` 不在 08 新增调用点内；它继续由 03/04/05 学员作答链路使用。08 只生产题库并统计既有作答记录。

## 课程状态机与可见性矩阵

| 教师可见状态 | 本地 `courses.status` | 审核 provider 状态 | 学员方向课程区块 | 学员课程聚合页 | 推荐池 | 允许动作 |
| --- | --- | --- | --- | --- | --- | --- |
| 草稿 | `draft` | 无记录 | 否 | 否 | 否 | 编辑；首次提交 |
| 待审核 | `pending` | `pending` | 否 | 否 | 否 | 编辑全部内容；保持待审核 |
| 已上架 | `pending` 或 legacy `published` | `approved` | 是 | 是 | 是 | 下架；编辑后重审 |
| 已驳回 | `pending` | `rejected` | 否 | 否 | 否 | 编辑；重新提交 |
| 已下架 | `offline` | `approved` | 否 | 否 | 否 | 重新上架审核；编辑后重审 |

统一状态解析规则：

```python
def resolve_teacher_visible_status(course: dict, review_status: str | None) -> str:
    if course.get("teacher_id") is None and course.get("status") == "published":
        return "published"
    if course.get("status") == "draft":
        return "draft"
    if course.get("status") == "offline":
        return "offline"
    if review_status == "approved":
        return "published"
    if review_status == "rejected":
        return "rejected"
    return "pending"
```

只有 `resolve_teacher_visible_status(...) == "published"` 才可进入三处学员可见列表。`pending`、`rejected`、`offline`、`draft` 均不可见。

## CourseProvider 实现说明

既有签名保持不动：

```python
class CourseProvider(Protocol):
    def list_published_courses(
        self,
        student_id: int,
        direction: str,
    ) -> list[dict]: ...

    def get_course(self, course_id: int) -> dict | None: ...

    def get_quiz(self, course_id: int) -> dict | None: ...
```

- 真实现为 `backend/app/teacher_console/providers.py:DatabaseTeacherCourseProvider`。
- 注册槽继续为 `app.extensions["agri_course_provider"]`，继续使用 `set_course_provider()` / `get_course_provider()`。
- `install_default_teacher_console_services(app)` 在 `install_default_agri_services(app)` 之前执行；teacher provider 先占用槽，03 的默认 provider 不再覆盖。
- 03 经 `app.agri_skills.course_learning.list_courses()` 和 `list_recommendations()` 消费；04/05 继续调用同一方向包装器。
- 学员课程聚合页的 `/api/student/courses` 改由同一 `list_courses()` 读取，避免它绕过审核状态直读 `courses.status`。
- 返回课程包含整数 `id`、`status="published"`、非空 `published_at`、正整数 `duration_seconds`、`tag_ids: list[int]`，并新增 `content_tags: list[str]`。
- legacy 无 `teacher_id` 且 `status="published"` 的种子课程继续可见；新课程必须由通用审核 provider 返回 `approved`。

## ContentReviewProvider 接入说明

08 只依赖以下 facade：

```python
class ContentReviewProvider(Protocol):
    def submit_for_review(
        self, *, content_type: str, content_id: str, submitter_id: int,
        expected_version: int, payload: dict,
    ) -> dict: ...
    def get_review_status(
        self, *, content_type: str, content_id: str,
    ) -> dict | None: ...
    def approve(
        self, *, content_type: str, content_id: str, submitter_id: int,
        reviewer_id: int, reviewer_role: str, expected_version: int,
    ) -> dict: ...
    def reject(
        self, *, content_type: str, content_id: str, submitter_id: int,
        reviewer_id: int, reviewer_role: str, expected_version: int,
        opinion: str,
    ) -> dict: ...
    def edit(
        self, *, content_type: str, content_id: str, submitter_id: int,
        expected_version: int, payload: dict,
    ) -> dict: ...
```

- 注册槽为 `app.extensions["content_review_provider"]`，入口为 `set_content_review_provider()` / `get_content_review_provider()`。
- `UnavailableContentReviewProvider.get_review_status()` 返回 `None`；四个写入方法抛 `ProviderUnavailableError`。
- `CourseReviewAdapter` 使用 `content_type="course_video"`，并转换 `int course_id <-> str content_id`。
- 08 不调用 `approve` / `reject` 管理动作；管理员审核由 11 或测试替身驱动。08 只调用 `submit_for_review`、`edit`、`get_review_status`。
- 审核结果通知由 11 provider 在状态转换事务中触发；08 不调用 `emit_review_result()`。
- `approve` / `reject` 的审核者、意见、版本和更新时间由 11 的审核记录作为权威审计源；08 不重复写入这些动作，只读取并展示 `review_status`、`rejection_opinion`、`version`、`updated_at`。

## 与 001-05 的复用点

| 复用点 | 既有实现 | 08 使用方式 | 禁止事项 |
| --- | --- | --- | --- |
| 会话与角色 | `backend/app/session_manager.py`、01 用户表 | `load_session()` + `role="teacher"` 覆盖身份 | 不新增教师账号或第二套角色判断 |
| 兴趣标签 | `interest_tags`、`student_interest_tags` | 自由标签精确匹配 crop/skill 活跃标签得到 `tag_ids` | 不创建课程标签目录或改写 01 标签 |
| 课程学习 | `agri_skills.course_learning`、`CourseLearningPanel` | 保持 provider 和方向包装器供 03/04/05 | 不复制进度、完成或测验作答逻辑 |
| 测验作答 | `agri_course_quiz_attempts`、`course_quiz_grade` | 看板读取既有作答记录 | 不新建学员测验提交接口 |
| 通知与消息 | `messaging.broadcasts.emit_teaching_announcement()`、私信 API | 公告群发、审核通知和私信均走 02 | 不新增消息中心或通知表 |
| AI gateway | `get_ai_client()`、`build_ai_messages()` | 新增两个 allowlist 调用点 | 不绕过敏感字段过滤和错误映射 |
| 非遗视频评论目标 | `heritage_videos.video_id` | 统一评论表使用 `content_type=handcraft_teaching_video` | 不导入 05 私有表实现，仅存稳定 ID |
| 非遗审核兼容 | 05 视频专用 action | 仅作为 11 适配器输入；08 不调用 | 不复制 `apply(action)` 分支 |

## 共享文件改动

| Shared file | Change | Why it cannot be bypassed |
| --- | --- | --- |
| `backend/app/db.py` | 增加教师课程列、公告、评论、报告表及迁移函数 | 项目只有一个 SQLite schema/init 入口 |
| `backend/app/__init__.py` | 安装 008 provider、注册 blueprint 和受保护前缀 | `create_app()` 是唯一应用装配点 |
| `backend/app/agri_skills/ai_context.py` | 增加两个 AI allowlist 与 domain 映射 | AI 安全审计只认这张注册表 |
| `backend/app/agri_skills/course_learning.py` | 保持签名，仅兼容 `content_tags` 透传 | 03/04/05 共用消费入口 |
| `backend/app/courses/routes.py` | 学员课程聚合页改走共享 provider | 否则会绕过审核状态直读 `courses.status` |
| `backend/app/config.py` | 增加 `MAX_VIDEO_UPLOAD_BYTES` | 视频上传限制必须由配置层集中定义 |
| `backend/.env.example` | 增加视频上传限制示例 | 本地与部署配置可复现 |
| `frontend/src/api/client.ts` | FormData 请求不强制 JSON Content-Type | 视频上传必须发送 multipart/form-data |
| `frontend/src/api/types.ts` | 增加教师工作台 DTO | 前端类型集中维护 |
| `frontend/src/router/index.ts` | 注册教师子路由 | Vue Router 是页面可达性的唯一入口 |
| `frontend/src/views/TeacherPortalView.vue` | 从占位门户改为教师工作台壳层 | 教师默认路径保持 `/teacher` |

## File Structure

| Path | Responsibility |
| --- | --- |
| `backend/app/content_review/__init__.py` | 通用审核 provider 导出 |
| `backend/app/content_review/providers.py` | `ContentReviewProvider`、占位实现、set/get 注册槽 |
| `backend/app/teacher_console/__init__.py` | 008 默认服务安装与领域导出 |
| `backend/app/teacher_console/errors.py` | `ProviderError` 目标层级 |
| `backend/app/teacher_console/course_service.py` | 课程 CRUD、校验、状态解析和状态转换 |
| `backend/app/teacher_console/review_adapter.py` | 课程 ID 与通用审核 facade 的适配 |
| `backend/app/teacher_console/providers.py` | 真 `DatabaseTeacherCourseProvider` |
| `backend/app/teacher_console/media.py` | 本地视频保存、校验和读取 |
| `backend/app/teacher_console/quiz.py` | AI 出题、校验、保存和重审触发 |
| `backend/app/teacher_console/announcements.py` | 教学公告持久化与 02 群发 |
| `backend/app/teacher_console/comments.py` | 统一内容评论读取、教师回复和授权 |
| `backend/app/teacher_console/dashboard.py` | 聚合统计公式和方向分组 |
| `backend/app/teacher_console/reports.py` | AI 学情报告生成、保存和回看 |
| `backend/app/teacher_console/routes.py` | `/api/teacher/*` 与 `/media/teacher-courses/*` |
| `backend/tests/test_teacher_console_*.py` | 后端基础、状态机、provider、AI、公告、评论、看板和 API 测试 |
| `frontend/src/stores/teacherConsole.ts` | 教师工作台 Pinia store |
| `frontend/src/components/TeacherConsoleNav.vue` | 教师工作台导航 |
| `frontend/src/components/TeacherQuizEditor.vue` | 3～5 题预览编辑组件 |
| `frontend/src/components/TeacherCourseManager.vue` | 课程列表、表单、状态动作和媒体输入 |
| `frontend/src/views/TeacherCoursesView.vue` | 课程管理路由页 |
| `frontend/src/views/TeacherAnnouncementsView.vue` | 公告发布与历史页 |
| `frontend/src/views/TeacherInteractionsView.vue` | 课程/非遗视频评论回复页 |
| `frontend/src/views/TeacherDashboardView.vue` | 统计卡片、方向分组和学情报告页 |
| `frontend/src/stores/teacherConsole.test.ts` | store 请求、错误和状态测试 |
| `frontend/src/views/TeacherConsole*.test.ts` | 路由、壳层、交互和响应式测试 |

---

### Task 1: Teacher Console Schema and Migration

**Files:**
- Modify: `backend/app/db.py`
- Create: `backend/app/teacher_console/time_utils.py`
- Create: `backend/tests/test_teacher_console_foundation.py`

**Interfaces:**
- Consumes: `SCHEMA_SQL`, `get_db()`, `init_db()`, existing `courses`, `course_quizzes`, `interest_tags`.
- Produces course columns: `teacher_id INTEGER`, `version INTEGER NOT NULL DEFAULT 1`, `media_source_type TEXT`, `content_tags_json TEXT NOT NULL DEFAULT '[]'`, `rejection_opinion TEXT`, `submitted_at TEXT`.
- Produces tables: `teacher_announcements`, `teacher_announcement_delivery_events`, `teacher_course_status_history`, `content_comments`, `teacher_learning_reports`.
- Produces `now_shanghai_iso() -> str` and `parse_provider_time(value: object) -> datetime`; all 008 time writes use `now_shanghai_iso()`.

**Work:**

- [ ] **Step 1: Write the failing schema test**

```python
def test_teacher_console_schema_and_columns(self):
    with self.app.app_context():
        columns = {
            row["name"]
            for row in get_db().execute("PRAGMA table_info(courses)")
        }
        tables = {
            row["name"]
            for row in get_db().execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    self.assertTrue({
        "teacher_id", "version", "media_source_type",
        "content_tags_json", "rejection_opinion", "submitted_at",
    }.issubset(columns))
    self.assertTrue({
        "teacher_announcements", "teacher_announcement_delivery_events",
        "teacher_course_status_history", "content_comments",
        "teacher_learning_reports",
    }.issubset(tables))

def test_time_helpers_are_timezone_aware(self):
    value = now_shanghai_iso()
    self.assertTrue(value.endswith("+08:00"))
    self.assertEqual(
        parse_provider_time("2026-09-18T10:00:00Z").utcoffset(),
        timedelta(hours=8),
    )
```

- [ ] **Step 2: Run it and verify failure**

Run: `uv run --directory backend python -m unittest tests.test_teacher_console_foundation -v`

Expected: FAIL because the columns and tables do not exist.

- [ ] **Step 3: Add schema and migration**

Add `CREATE TABLE IF NOT EXISTS` blocks to `SCHEMA_SQL` and an idempotent migration. `teacher_announcements` stores `delivery_status` and `delivery_result_json`; `teacher_course_status_history` stores `course_id`, `from_status`, `to_status`, `actor_id`, `opinion`, `version`, `created_at`; `teacher_announcement_delivery_events` stores `announcement_id`, `status`, `result_json`, `created_at`. Implement the time helpers as:

```python
def now_shanghai_iso() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")

def parse_provider_time(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("时间字段必须包含时区")
    return parsed.astimezone(ZoneInfo("Asia/Shanghai"))
```

Task 4 catches `ValueError` from `parse_provider_time()` and maps it to `ProviderValidationError`.

```python
def _ensure_teacher_console_columns(db: sqlite3.Connection) -> None:
    columns = {row["name"] for row in db.execute("PRAGMA table_info(courses)")}
    additions = {
        "teacher_id": "INTEGER REFERENCES users(id)",
        "version": "INTEGER NOT NULL DEFAULT 1",
        "media_source_type": "TEXT",
        "content_tags_json": "TEXT NOT NULL DEFAULT '[]'",
        "rejection_opinion": "TEXT",
        "submitted_at": "TEXT",
    }
    for name, definition in additions.items():
        if name not in columns:
            db.execute(f"ALTER TABLE courses ADD COLUMN {name} {definition}")
```

Call `_ensure_teacher_console_columns(db)` from `init_db()` before seeding.

- [ ] **Step 4: Verify and commit**

Run: `uv run --directory backend python -m unittest tests.test_teacher_console_foundation -v`

Expected: PASS.

```bash
git add backend/app/db.py backend/app/teacher_console/time_utils.py backend/tests/test_teacher_console_foundation.py
git commit -m "feat(008): 增加教师工作台数据基础"
```

### Task 2: Provider Errors and Content Review Facade

**Files:**
- Create: `backend/app/teacher_console/errors.py`
- Create: `backend/app/content_review/__init__.py`
- Create: `backend/app/content_review/providers.py`
- Create: `backend/tests/test_content_review_provider_contract.py`

**Interfaces:**
- Consumes: Flask `app.extensions`.
- Produces `ProviderError` with explicit `code: str`, `message: str`, `details: dict`, plus `ProviderValidationError`, `ProviderNotFoundError`, `ProviderConflictError`, `ProviderUnavailableError`, `ProviderAccessDeniedError`.
- Produces `ContentReviewProvider`, `UnavailableContentReviewProvider`, `set_content_review_provider(app, provider)`, `get_content_review_provider()`.

**Work:**

- [ ] **Step 1: Write the failing contract tests**

```python
def test_placeholder_implements_complete_protocol(self):
    provider = get_content_review_provider()
    self.assertIsNone(provider.get_review_status(
        content_type="course_video", content_id="1"
    ))
    with self.assertRaises(ProviderUnavailableError):
        provider.submit_for_review(
            content_type="course_video", content_id="1",
            submitter_id=7, expected_version=1, payload={},
        )
    with self.assertRaises(ProviderUnavailableError):
        provider.approve(
            content_type="course_video", content_id="1",
            submitter_id=7, reviewer_id=1, reviewer_role="admin",
            expected_version=1,
        )
    with self.assertRaises(ProviderUnavailableError):
        provider.reject(
            content_type="course_video", content_id="1",
            submitter_id=7, reviewer_id=1, reviewer_role="admin",
            expected_version=1, opinion="不通过",
        )
    with self.assertRaises(ProviderUnavailableError):
        provider.edit(
            content_type="course_video", content_id="1",
            submitter_id=7, expected_version=1, payload={},
        )

def test_provider_slot_is_replaceable(self):
    replacement = FakeReviewProvider()
    set_content_review_provider(self.app, replacement)
    self.assertIs(get_content_review_provider(), replacement)
```

- [ ] **Step 2: Run it and verify failure**

Run: `uv run --directory backend python -m unittest tests.test_content_review_provider_contract -v`

Expected: FAIL because the package and provider slot do not exist.

- [ ] **Step 3: Implement the protocol and placeholder**

```python
class ProviderError(RuntimeError):
    def __init__(self, message: str, *, code: str, details: dict):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


class UnavailableContentReviewProvider:
    def submit_for_review(
        self, *, content_type: str, content_id: str, submitter_id: int,
        expected_version: int, payload: dict,
    ) -> dict:
        self._unavailable()

    def get_review_status(
        self, *, content_type: str, content_id: str,
    ) -> dict | None:
        return None

    def approve(
        self, *, content_type: str, content_id: str, submitter_id: int,
        reviewer_id: int, reviewer_role: str, expected_version: int,
    ) -> dict:
        self._unavailable()

    def reject(
        self, *, content_type: str, content_id: str, submitter_id: int,
        reviewer_id: int, reviewer_role: str, expected_version: int,
        opinion: str,
    ) -> dict:
        self._unavailable()

    def edit(
        self, *, content_type: str, content_id: str, submitter_id: int,
        expected_version: int, payload: dict,
    ) -> dict:
        self._unavailable()

    def _unavailable(self):
        raise ProviderUnavailableError(
            "内容审核服务暂不可用",
            code="review_unavailable",
            details={},
        )


def set_content_review_provider(app: Flask, provider: ContentReviewProvider) -> None:
    app.extensions["content_review_provider"] = provider


def get_content_review_provider() -> ContentReviewProvider:
    return current_app.extensions.get(
        "content_review_provider",
        UnavailableContentReviewProvider(),
    )
```

- [ ] **Step 4: Verify and commit**

Run: `uv run --directory backend python -m unittest tests.test_content_review_provider_contract -v`

Expected: PASS.

```bash
git add backend/app/teacher_console/errors.py backend/app/content_review backend/tests/test_content_review_provider_contract.py
git commit -m "feat(008): 冻结通用内容审核接口"
```

### Task 3: Course Persistence, Validation, and Ownership

**Files:**
- Create: `backend/app/teacher_console/course_service.py`
- Create: `backend/app/teacher_console/media.py`
- Create: `backend/tests/test_teacher_course_service.py`

**Interfaces:**
- Consumes: `get_db()`, 01 session user ID, `interest_tags`.
- Produces `create_teacher_course(teacher_id, payload) -> dict`, `update_teacher_course_draft(teacher_id, course_id, expected_version, payload) -> dict`, `get_teacher_course(teacher_id, course_id) -> dict`, `list_teacher_courses(teacher_id, direction=None, status=None) -> list[dict]`.
- Produces validation for direction, summary, tags, duration, media source, ownership and optimistic version.
- Produces `validate_media_reference(media_source_type, media_url, *, transport=None, check_remote=False) -> str` so drafts validate format and Task 4 submission validates reachability before review.

**Work:**

- [ ] **Step 1: Write failing CRUD and validation tests**

```python
def test_create_and_list_owned_course(self):
    course = create_teacher_course(7, {
        "title": "荔枝保果", "direction": "agriculture",
        "summary": "花期与果期管理要点", "content_tags": ["荔枝", "保果"],
        "duration_seconds": 300, "media_source_type": "external_url",
        "media_url": "https://media.example.test/lychee.mp4",
    })
    self.assertEqual(course["teacher_id"], 7)
    self.assertEqual(course["status"], "draft")
    self.assertEqual(course["content_tags"], ["荔枝", "保果"])
    self.assertEqual(course["tag_ids"], [self.interest_tag_id])

def test_other_teacher_cannot_read_course(self):
    with self.assertRaises(ProviderAccessDeniedError):
        get_teacher_course(8, self.course_id)
```

- [ ] **Step 2: Run it and verify failure**

Run: `uv run --directory backend python -m unittest tests.test_teacher_course_service -v`

Expected: FAIL because the service functions do not exist.

- [ ] **Step 3: Implement persistence and validation**

```python
def create_teacher_course(teacher_id: int, payload: dict) -> dict:
    values = _validate_course_payload(payload, partial=False)
    now = now_shanghai_iso()
    db = get_db()
    with db:
        cursor = db.execute(
            """
            INSERT INTO courses (
                title, direction, status, duration_seconds, media_url,
                published_at, summary, teacher_name, teacher_id,
                media_source_type, content_tags_json, version,
                rejection_opinion, submitted_at, created_at, updated_at
            )
            SELECT ?, ?, 'draft', ?, ?, NULL, ?, name, ?, ?, ?, 1,
                   NULL, NULL, ?, ?
            FROM users WHERE id = ? AND role = 'teacher' AND is_enabled = 1
            """,
            (
                values["title"], values["direction"],
                values["duration_seconds"], values["media_url"],
                values["summary"], teacher_id, values["media_source_type"],
                json.dumps(values["content_tags"], ensure_ascii=False),
                now, now, teacher_id,
            ),
        )
        if cursor.rowcount != 1:
            raise ProviderAccessDeniedError("教师身份无效")
    return get_teacher_course(teacher_id, int(cursor.lastrowid))
```

`_validate_course_payload()` trims text, rejects empty summary/title, accepts only `agriculture/ecommerce/handcraft`, de-duplicates free-text tags, requires positive duration and valid `local_upload|external_url` media source. `_sync_catalog_tag_ids()` writes exact matches against active crop/skill `interest_tags` into `course_interest_tags`; unmatched free-text tags remain only in `content_tags_json`. Implement `validate_media_reference()` here; Task 6 adds file storage around it.

- [ ] **Step 4: Verify and commit**

Run: `uv run --directory backend python -m unittest tests.test_teacher_course_service -v`

Expected: PASS.

```bash
git add backend/app/teacher_console/course_service.py backend/app/teacher_console/media.py backend/tests/test_teacher_course_service.py
git commit -m "feat(008): 实现教师课程草稿与校验"
```

### Task 4: Review Adapter and Course State Machine

**Files:**
- Create: `backend/app/teacher_console/review_adapter.py`
- Modify: `backend/app/teacher_console/course_service.py`
- Create: `backend/tests/test_teacher_course_state_machine.py`

**Interfaces:**
- Consumes: `get_content_review_provider()`, course persistence from Task 3.
- Produces `CourseReviewAdapter.submit(course, payload)`, `.read(course_id)`, `.edit(course, payload)`.
- Produces `resolve_teacher_visible_status(course, review_status)`, `submit_course_for_review(teacher_id, course_id, expected_version) -> dict`, `edit_course(teacher_id, course_id, expected_version, payload, *, quiz_override=None) -> dict`, `set_course_offline(teacher_id, course_id, expected_version) -> dict`, `request_course_relist(teacher_id, course_id, expected_version) -> dict`.
- Produces `review_payload(course) -> dict` with contract fields `title`, `direction`, `summary`, `tag_ids`, `duration_seconds`, `media_url`, `quiz_config`.

**Work:**

- [ ] **Step 1: Write failing state transition tests**

```python
def test_edit_published_course_hides_it_until_reapproval(self):
    self.review.set_status("course_video", str(self.course_id), "approved")
    self.assertEqual(self.visible_status(), "published")

    edit_course(
        self.teacher_id, self.course_id, expected_version=1,
        payload={"title": "修订标题"},
    )

    self.assertEqual(self.visible_status(), "pending")
    self.assertEqual(self.visible_course_ids("agriculture"), [])
    self.review.set_status("course_video", str(self.course_id), "approved")
    self.assertEqual(self.visible_status(), "published")

def test_rejected_course_returns_to_pending_on_edit(self):
    self.review.set_status("course_video", str(self.course_id), "rejected")
    edit_course(
        self.teacher_id, self.course_id, expected_version=1,
        payload={"summary": "补充后的知识点"},
    )
    self.assertEqual(self.review.calls[-1]["method"], "edit")

def test_offline_relist_starts_new_review_round(self):
    self.review.set_status("course_video", str(self.course_id), "approved")
    set_course_offline(self.teacher_id, self.course_id, expected_version=1)
    self.review.return_pending = True
    relisted = request_course_relist(
        self.teacher_id, self.course_id, expected_version=1
    )
    self.assertEqual(relisted["status"], "pending")
    self.assertEqual(self.review.calls[-1]["method"], "submit_for_review")
    history = get_db().execute(
        """
        SELECT from_status, to_status, actor_id
        FROM teacher_course_status_history
        ORDER BY id DESC LIMIT 1
        """
    ).fetchone()
    self.assertEqual(
        (history["from_status"], history["to_status"], history["actor_id"]),
        ("offline", "pending", self.teacher_id),
    )
```

- [ ] **Step 2: Run it and verify failure**

Run: `uv run --directory backend python -m unittest tests.test_teacher_course_state_machine -v`

Expected: FAIL because adapter and transition functions do not exist.

- [ ] **Step 3: Implement the adapter and transitions**

```python
class CourseReviewAdapter:
    def submit(self, course: dict, payload: dict) -> dict:
        return get_content_review_provider().submit_for_review(
            content_type="course_video",
            content_id=str(course["id"]),
            submitter_id=int(course["teacher_id"]),
            expected_version=int(course["version"]),
            payload=payload,
        )

    def edit(self, course: dict, payload: dict) -> dict:
        return get_content_review_provider().edit(
            content_type="course_video",
            content_id=str(course["id"]),
            submitter_id=int(course["teacher_id"]),
            expected_version=int(course["version"]),
            payload=payload,
        )
```

`submit_course_for_review()` only accepts `draft|rejected`; `edit_course()` accepts `pending|published|rejected|offline`. Both use one order: validate and build the complete payload, validate media with `check_remote=True`, open one local `with get_db()` transaction, call the provider inside that transaction, then apply the provider-returned `version` and `review_status` with conditional updates. The 11 provider MUST use the caller's active SQLite connection and not commit independently, matching the contract's single business-commit boundary. Provider or local failure rolls back both sides. If the provider returns the same version and status, no local version increment occurs. If it returns `pending`, persist the validated course fields and optional `quiz_override`, clear `rejection_opinion`, set `submitted_at`, clear local `published_at`, and set local `status="pending"`. `set_course_offline()` accepts only resolved published with matching expected version and sets `offline`. `request_course_relist()` calls `submit_for_review()` as a new review round, then applies the same returned version/status synchronization as submit: `pending` sets `submitted_at`, clears `rejection_opinion`/`published_at`, and sets local `status="pending"`; any other provider result raises `ProviderConflictError` and leaves the course `offline`.

Every local update uses `WHERE id = ? AND version = ? AND status = ?`; zero affected rows raises `ProviderConflictError`. Every transition writes one row to `teacher_course_status_history` inside the same transaction as the local status update. The history row records `from_status`, `to_status`, `actor_id`, `opinion`, `version`, and `created_at`.

08 requires `submit_for_review()` on an approved/offline course to create a fresh pending review round. This is the only relist path; the plan adds a contract test so 11 cannot implement relist as a no-op `edit()`.

- [ ] **Step 4: Verify and commit**

Run: `uv run --directory backend python -m unittest tests.test_teacher_course_state_machine -v`

Expected: PASS, including pending/rejected/offline invisibility and stale-version conflicts.

```bash
git add backend/app/teacher_console/review_adapter.py backend/app/teacher_console/course_service.py backend/tests/test_teacher_course_state_machine.py
git commit -m "feat(008): 实现课程审核状态机"
```

### Task 5: Database CourseProvider and Student Visibility Integration

**Files:**
- Create: `backend/app/teacher_console/providers.py`
- Create: `backend/app/teacher_console/__init__.py`
- Modify: `backend/app/__init__.py`
- Modify: `backend/app/agri_skills/course_learning.py`
- Modify: `backend/app/courses/routes.py`
- Create: `backend/tests/test_teacher_course_provider.py`
- Modify: `backend/tests/test_shared_course_provider.py`
- Modify: `backend/tests/test_course_catalog.py`

**Interfaces:**
- Consumes: Task 4 state resolver, existing `CourseProvider`, `set_course_provider()`, `list_courses()`.
- Produces `DatabaseTeacherCourseProvider.list_published_courses(student_id, direction)`, `.get_course(course_id)`, `.get_quiz(course_id)`.
- Produces `install_default_teacher_console_services(app)`.

**Work:**

- [ ] **Step 1: Write failing provider and three-surface tests**

```python
def test_approved_course_is_visible_in_catalog_and_recommendations(self):
    self.review.set_status("course_video", str(self.course_id), "approved")
    self.assertEqual(
        [item["id"] for item in list_courses(self.student_id, "agriculture")],
        [self.course_id],
    )
    self.assertEqual(
        [item["id"] for item in list_recommendations(
            self.student_id, "agriculture"
        )],
        [self.course_id],
    )
    response = self.client.get("/api/student/courses?direction=agriculture")
    self.assertIn(self.course_id, [
        item["id"] for item in response.get_json()["courses"]
    ])

def test_pending_course_is_hidden_from_all_three_surfaces(self):
    self.review.set_status("course_video", str(self.course_id), "pending")
    self.assertEqual(list_courses(self.student_id, "agriculture"), [])
    self.assertEqual(list_recommendations(self.student_id, "agriculture"), [])
    response = self.client.get("/api/student/courses?direction=agriculture")
    self.assertNotIn(self.course_id, [
        item["id"] for item in response.get_json()["courses"]
    ])
```

- [ ] **Step 2: Run it and verify failure**

Run: `uv run --directory backend python -m unittest tests.test_teacher_course_provider tests.test_shared_course_provider tests.test_course_catalog -v`

Expected: FAIL because teacher provider and aggregation-route integration do not exist.

- [ ] **Step 3: Implement provider and registration**

```python
class DatabaseTeacherCourseProvider:
    def list_published_courses(self, student_id: int, direction: str) -> list[dict]:
        return [
            course
            for course in self._list_direction(direction)
            if course["status"] == "published"
        ]

    def get_course(self, course_id: int) -> dict | None:
        row = get_db().execute(
            "SELECT * FROM courses WHERE id = ?", (course_id,)
        ).fetchone()
        if row is None:
            return None
        course = self._hydrate(dict(row))
        return course if course["status"] == "published" else None

    def get_quiz(self, course_id: int) -> dict | None:
        if self.get_course(course_id) is None:
            return None
        row = get_db().execute(
            "SELECT * FROM course_quizzes WHERE course_id = ?", (course_id,)
        ).fetchone()
        return _quiz_payload(row) if row is not None else None
```

`_hydrate()` adds `content_tags`, reads exact-match `tag_ids`, uses the review record's `published_at` when approved, clears the returned `published_at` for pending/rejected/offline, and computes `status` with `resolve_teacher_visible_status()` before any return. `_list_direction()` hydrates every row first and filters only resolved `published` rows. `install_default_teacher_console_services()` registers the provider only when `agri_course_provider` is absent; call it before `install_default_agri_services()` in `create_app()`.

Modify `agri_skills.course_learning._list_provider_recommendations()` so its `published_at` ordering uses a parsed aware datetime key:

```python
def _course_time(value: object) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))

recommendations.sort(
    key=lambda item: _course_time(item.get("published_at")),
    reverse=True,
)
```

Remove the agriculture-only direct SQL fallback in `list_recommendations()`. All three directions must use `_list_provider_recommendations()` so approved new courses with local `status="pending"` are included and pending/rejected/offline courses are excluded by provider status resolution. Preserve the existing recommendation order keys after replacing string timestamps with `_course_time()`.

- [ ] **Step 4: Verify and commit**

Run: `uv run --directory backend python -m unittest tests.test_teacher_course_provider tests.test_shared_course_provider tests.test_course_catalog tests.test_agri_course_api tests.test_ecommerce_course_learning tests.test_handcraft_course -v`

Expected: PASS.

```bash
git add backend/app/teacher_console/providers.py backend/app/teacher_console/__init__.py backend/app/__init__.py backend/app/agri_skills/course_learning.py backend/app/courses/routes.py backend/tests/test_teacher_course_provider.py backend/tests/test_shared_course_provider.py backend/tests/test_course_catalog.py
git commit -m "feat(008): 接入方向课程 provider"
```

### Task 6: Local Video Upload and Media Serving

**Files:**
- Modify: `backend/app/teacher_console/media.py`
- Modify: `backend/app/config.py`
- Modify: `backend/.env.example`
- Create: `backend/tests/test_teacher_media.py`

**Interfaces:**
- Consumes: Flask `FileStorage`, config `MAX_VIDEO_UPLOAD_BYTES`, `uploads/`.
- Produces `save_course_video(file_storage, teacher_id) -> dict`, `course_media_path(filename) -> Path`, `validate_media_reference(media_source_type, media_url, *, transport=None, check_remote=False) -> str`.
- Produces uploaded media URL `/media/teacher-courses/<uuid>.<ext>`.

**Work:**

- [ ] **Step 1: Write failing media tests**

```python
def test_local_upload_rejects_oversize_and_non_video(self):
    with self.assertRaises(ProviderValidationError):
        save_course_video(
            FileStorage(stream=io.BytesIO(b"x" * 10), filename="bad.txt"),
            self.teacher_id,
        )
    self.app.config["MAX_VIDEO_UPLOAD_BYTES"] = 4
    with self.assertRaisesRegex(ProviderValidationError, "大小超出限制"):
        save_course_video(
            FileStorage(stream=io.BytesIO(b"12345"), filename="large.mp4"),
            self.teacher_id,
        )

def test_external_url_requires_http_scheme_and_reachable_head(self):
    self.assertEqual(
        validate_media_reference(
            "external_url", "https://media.example.test/a.mp4",
            transport=reachable_transport, check_remote=True,
        ),
        "https://media.example.test/a.mp4",
    )
    with self.assertRaises(ProviderValidationError):
        validate_media_reference("external_url", "javascript:alert(1)")

def test_unreachable_external_url_is_rejected_without_network(self):
    with self.assertRaisesRegex(ProviderValidationError, "媒体地址不可访问"):
        validate_media_reference(
            "external_url", "https://media.example.test/missing.mp4",
            transport=unreachable_transport, check_remote=True,
        )
```

- [ ] **Step 2: Run it and verify failure**

Run: `uv run --directory backend python -m unittest tests.test_teacher_media -v`

Expected: FAIL because `save_course_video()` and `course_media_path()` do not exist.

- [ ] **Step 3: Implement validated storage**

```python
ALLOWED_VIDEO_EXTENSIONS = {".mp4": "video/mp4", ".webm": "video/webm"}
MAX_VIDEO_UPLOAD_BYTES = 500 * 1024 * 1024

def save_course_video(file_storage, teacher_id: int) -> dict:
    filename = str(file_storage.filename or "")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_VIDEO_EXTENSIONS:
        raise ProviderValidationError("视频仅支持 MP4 或 WebM")
    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size <= 0 or size > current_app.config["MAX_VIDEO_UPLOAD_BYTES"]:
        raise ProviderValidationError("视频文件大小超出限制")
    stored_name = f"{teacher_id}-{uuid4().hex}{suffix}"
    destination = course_media_path(stored_name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    file_storage.save(destination)
    return {
        "media_source_type": "local_upload",
        "media_url": f"/media/teacher-courses/{stored_name}",
        "size_bytes": size,
    }
```

Add `MAX_VIDEO_UPLOAD_BYTES=524288000` to config and `.env.example`. `validate_media_reference()` requires a local file to exist and be readable; when `check_remote=True`, it performs an HTTP `HEAD` with a 5-second timeout and accepts only 2xx/3xx, otherwise it raises `ProviderValidationError("媒体地址不可访问")`. Tests always inject an `httpx.MockTransport`, so no test depends on external network. The upload route sets `request.max_content_length = current_app.config["MAX_VIDEO_UPLOAD_BYTES"]`; Task 4 submission calls `validate_media_reference(..., check_remote=True)` before the review provider mutation.

- [ ] **Step 4: Verify and commit**

Run: `uv run --directory backend python -m unittest tests.test_teacher_media -v`

Expected: PASS.

```bash
git add backend/app/teacher_console/media.py backend/app/config.py backend/.env.example backend/tests/test_teacher_media.py
git commit -m "feat(008): 增加课程视频媒体处理"
```

### Task 7: AI Quiz Generation and Review Trigger

**Files:**
- Create: `backend/app/teacher_console/quiz.py`
- Modify: `backend/app/agri_skills/ai_context.py`
- Create: `backend/tests/test_teacher_quiz.py`
- Modify: `backend/tests/test_agri_ai_context.py`

**Interfaces:**
- Consumes: `get_ai_client()`, `build_ai_messages()`, `AiUnavailableError`, Task 4 `edit_course()`.
- Produces `generate_course_quiz(teacher_id, course_id, *, summary, direction) -> dict`, `save_course_quiz(teacher_id, course_id, expected_version, enabled, questions, scoring_rule="all_correct") -> dict`, `get_teacher_course_quiz(teacher_id, course_id) -> dict`.
- Produces AI call point `teacher_quiz_generate`.

**Work:**

- [ ] **Step 1: Write failing generation and re-review tests**

```python
def test_generate_quiz_uses_only_summary_and_direction(self):
    self.ai.complete_json.return_value = {
        "questions": [
            {"id": "q1", "type": "single_choice", "prompt": "?",
             "options": ["A", "B"], "answer": "A"},
            {"id": "q2", "type": "true_false", "prompt": "?",
             "options": ["正确", "错误"], "answer": "正确"},
            {"id": "q3", "type": "true_false", "prompt": "?",
             "options": ["正确", "错误"], "answer": "错误"},
        ]
    }
    quiz = generate_course_quiz(
        self.teacher_id, self.course_id,
        summary="课程简介", direction="agriculture",
    )
    self.assertEqual(len(quiz["questions"]), 3)
    call = self.ai.complete_json.call_args
    self.assertEqual(call.kwargs["call_point"], "teacher_quiz_generate")
    self.assertIn("课程简介", call.args[0][1]["content"])
    self.assertNotIn("video", call.args[0][1]["content"].lower())

def test_quiz_ai_failure_is_provider_error(self):
    self.ai.complete_json.side_effect = AiUnavailableError("down")
    with self.assertRaisesRegex(
        ProviderUnavailableError, "AI 服务暂时不可用"
    ):
        generate_course_quiz(
            self.teacher_id, self.course_id,
            summary="课程简介", direction="agriculture",
        )

def test_invalid_ai_questions_are_provider_errors(self):
    self.ai.complete_json.return_value = {"questions": [{"id": "q1"}]}
    with self.assertRaisesRegex(
        ProviderUnavailableError, "AI 服务暂时不可用"
    ):
        generate_course_quiz(
            self.teacher_id, self.course_id,
            summary="课程简介", direction="agriculture",
        )

def test_published_quiz_change_reenters_review(self):
    self.review.set_status("course_video", str(self.course_id), "approved")
    save_course_quiz(
        self.teacher_id, self.course_id, expected_version=1,
        enabled=True, questions=self.valid_questions,
        scoring_rule="all_correct",
    )
    self.assertEqual(self.review.calls[-1]["method"], "edit")

def test_provider_failure_does_not_write_quiz(self):
    self.review.fail_next = ProviderUnavailableError(
        "审核不可用", code="review_unavailable", details={}
    )
    with self.assertRaises(ProviderUnavailableError):
        save_course_quiz(
            self.teacher_id, self.course_id, expected_version=1,
            enabled=True, questions=self.valid_questions,
            scoring_rule="all_correct",
        )
    self.assertIsNone(get_teacher_course_quiz(self.teacher_id, self.course_id))
```

- [ ] **Step 2: Run it and verify failure**

Run: `uv run --directory backend python -m unittest tests.test_teacher_quiz tests.test_agri_ai_context -v`

Expected: FAIL because the call point and quiz service do not exist.

- [ ] **Step 3: Implement generation and validation**

Add to `AI_FIELD_ALLOWLISTS`:

```python
"teacher_quiz_generate": {"course_summary", "course_direction"},
```

Add the call point to the agriculture domain fallback and implement:

```python
def generate_course_quiz(teacher_id, course_id, *, summary, direction):
    try:
        payload = get_ai_client().complete_json(
            build_ai_messages(
                "teacher_quiz_generate",
                {
                    "course_summary": summary,
                    "course_direction": direction,
                },
            ),
            call_point="teacher_quiz_generate",
        )
    except AiUnavailableError as error:
        raise ProviderUnavailableError(
            "AI 服务暂时不可用",
            code="ai_unavailable",
            details={},
        ) from error
    return {"questions": _validate_questions(payload.get("questions"))}
```

`_validate_questions()` enforces 3～5 items, unique non-empty IDs, allowed types, non-empty prompts/options, and answers present in options. Invalid AI output raises `ProviderUnavailableError("AI 服务暂时不可用")`, not a raw validation exception. `save_course_quiz()` requires non-empty `scoring_rule`, builds the complete course payload including quiz config, and calls Task 4 `edit_course(..., quiz_override=quiz)` for every changed quiz on a non-draft course. Task 4 owns the provider call and the single local transaction for course, quiz, status/version and history; tests assert a provider edit failure does not update `course_quizzes`.

- [ ] **Step 4: Verify and commit**

Run: `uv run --directory backend python -m unittest tests.test_teacher_quiz tests.test_agri_ai_context tests.test_agri_course_quiz -v`

Expected: PASS, including AI failure preserving the previous quiz.

```bash
git add backend/app/teacher_console/quiz.py backend/app/agri_skills/ai_context.py backend/tests/test_teacher_quiz.py backend/tests/test_agri_ai_context.py
git commit -m "feat(008): 实现 AI 课后测验配置"
```

### Task 8: Teaching Announcement Publishing

**Files:**
- Create: `backend/app/teacher_console/announcements.py`
- Create: `backend/tests/test_teacher_announcements.py`

**Interfaces:**
- Consumes: `emit_teaching_announcement()`, `teacher_announcements` table.
- Produces `publish_teaching_announcement(teacher_id, title, body) -> dict`, `list_teaching_announcements(teacher_id) -> list[dict]`, `update_teaching_announcement(teacher_id, announcement_id, title, body) -> dict`.
- Announcement IDs are non-empty UUID strings; published announcements are immutable.

**Work:**

- [ ] **Step 1: Write failing announcement tests**

```python
def test_publish_sends_exactly_one_notification_per_student(self):
    announcement = publish_teaching_announcement(
        self.teacher_id, "课程安排", "本周课程调整"
    )
    self.assertEqual(
        {row["recipient_id"] for row in self.notifications()},
        self.student_ids,
    )
    self.assertEqual(announcement["delivery_status"], "sent")

def test_published_announcement_is_immutable(self):
    announcement = publish_teaching_announcement(
        self.teacher_id, "标题", "正文"
    )
    with self.assertRaises(ProviderConflictError):
        update_teaching_announcement(
            self.teacher_id, announcement["announcement_id"], "新标题", "新正文"
        )

def test_broadcast_failure_is_recorded_and_not_reported_as_success(self):
    with patch(
        "app.teacher_console.announcements.emit_teaching_announcement",
        side_effect=RuntimeError("delivery failed"),
    ):
        with self.assertRaises(RuntimeError):
            publish_teaching_announcement(
                self.teacher_id, "标题", "正文"
            )
    row = get_db().execute(
        "SELECT delivery_status FROM teacher_announcements"
    ).fetchone()
    events = get_db().execute(
        """
        SELECT status FROM teacher_announcement_delivery_events
        ORDER BY id
        """
    ).fetchall()
    self.assertEqual(row["delivery_status"], "failed")
    self.assertEqual([event["status"] for event in events], ["failed"])
```

- [ ] **Step 2: Run it and verify failure**

Run: `uv run --directory backend python -m unittest tests.test_teacher_announcements -v`

Expected: FAIL because announcement service does not exist.

- [ ] **Step 3: Implement idempotent delivery state**

```python
def publish_teaching_announcement(teacher_id: int, title: object, body: object) -> dict:
    normalized_title = _required_text(title, "标题")
    normalized_body = _required_text(body, "正文")
    announcement_id = f"teaching-{uuid4().hex}"
    event_id = f"{announcement_id}:v1"
    now = now_shanghai_iso()
    db = get_db()
    with db:
        db.execute(
            """
            INSERT INTO teacher_announcements (
                announcement_id, teacher_id, title, body, event_id,
                delivery_status, delivery_result_json, created_at
            ) VALUES (?, ?, ?, ?, ?, 'pending', '{}', ?)
            """,
            (announcement_id, teacher_id, normalized_title,
             normalized_body, event_id, now),
        )
    try:
        result = emit_teaching_announcement(
            event_id=event_id,
            teacher_id=teacher_id,
            announcement_id=announcement_id,
            title=normalized_title,
            body=normalized_body,
        )
    except Exception:
        _record_delivery_event(announcement_id, "failed", {})
        raise
    _record_delivery_event(announcement_id, "sent", result)
    return _announcement_payload(announcement_id, delivery_result=result)
```

Each publish writes `pending`, `sent` or `failed` rows to `teacher_announcement_delivery_events` with the 02 result. `update_teaching_announcement()` always raises `ProviderConflictError("已群发公告不可修改")`; no delete function is exported.

- [ ] **Step 4: Verify and commit**

Run: `uv run --directory backend python -m unittest tests.test_teacher_announcements tests.test_notification_broadcasts -v`

Expected: PASS.

```bash
git add backend/app/teacher_console/announcements.py backend/tests/test_teacher_announcements.py
git commit -m "feat(008): 实现教学公告群发"
```

### Task 9: Unified Course and Heritage Video Comments

**Files:**
- Create: `backend/app/teacher_console/comments.py`
- Create: `backend/tests/test_teacher_comments.py`

**Interfaces:**
- Consumes: Task 5 `DatabaseTeacherCourseProvider`, `content_comments`, `courses.teacher_id`, `heritage_videos.video_id`.
- Produces `list_teacher_comments(teacher_id, content_type=None, content_id=None) -> list[dict]`, `reply_to_comment(teacher_id, comment_id, body) -> dict`.
- Content types are `course_video` and `handcraft_teaching_video`; course IDs are converted to non-empty strings.

**Work:**

- [ ] **Step 1: Write failing ownership and reply tests**

```python
def test_teacher_replies_to_own_course_and_heritage_video(self):
    reply = reply_to_comment(self.teacher_id, self.course_comment_id, "按以下步骤复习")
    self.assertTrue(reply["is_teacher_reply"])
    self.assertEqual(reply["parent_comment_id"], self.course_comment_id)

    heritage_reply = reply_to_comment(
        self.teacher_id, self.heritage_comment_id, "先固定绣线再起针"
    )
    self.assertTrue(heritage_reply["is_teacher_reply"])

def test_teacher_cannot_reply_to_another_teachers_course(self):
    with self.assertRaises(ProviderAccessDeniedError):
        reply_to_comment(self.other_teacher_id, self.course_comment_id, "越权")
```

- [ ] **Step 2: Run it and verify failure**

Run: `uv run --directory backend python -m unittest tests.test_teacher_comments -v`

Expected: FAIL because comment service does not exist.

- [ ] **Step 3: Implement unified comment authorization**

```python
def reply_to_comment(teacher_id: int, comment_id: str, body: object) -> dict:
    normalized_body = _required_text(body, "回复内容")
    parent = _load_comment(comment_id)
    if parent is None:
        raise ProviderNotFoundError("评论不存在")
    if not bool(parent["is_visible"]):
        raise ProviderNotFoundError("评论不存在")
    if parent["content_type"] == "course_video":
        owner = get_db().execute(
            """
            SELECT c.teacher_id, c.status, c.version
            FROM courses AS c
            WHERE c.id = ?
            """,
            (int(parent["content_id"]),),
        ).fetchone()
        if owner is None or int(owner["teacher_id"] or 0) != teacher_id:
            raise ProviderAccessDeniedError("只能回复本人课程的评论")
        if get_course_provider().get_course(int(parent["content_id"])) is None:
            raise ProviderConflictError("目标课程当前不可回复")
    elif parent["content_type"] == "handcraft_teaching_video":
        video = get_db().execute(
            """
            SELECT review_status, source_available
            FROM heritage_videos
            WHERE video_id = ?
            """,
            (parent["content_id"],),
        ).fetchone()
        if (
            video is None
            or video["review_status"] != "approved"
            or not bool(video["source_available"])
        ):
            raise ProviderConflictError("目标非遗视频当前不可回复")
    now = now_shanghai_iso()
    reply_id = f"reply-{uuid4().hex}"
    with get_db():
        get_db().execute(
            """
            INSERT INTO content_comments (
                comment_id, content_type, content_id, author_id,
                parent_comment_id, body, is_teacher_reply,
                is_visible, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?, ?)
            """,
            (reply_id, parent["content_type"], parent["content_id"],
             teacher_id, comment_id, normalized_body, now, now),
        )
    return _comment_payload(reply_id)
```

- [ ] **Step 4: Verify and commit**

Run: `uv run --directory backend python -m unittest tests.test_teacher_comments -v`

Expected: PASS.

```bash
git add backend/app/teacher_console/comments.py backend/tests/test_teacher_comments.py
git commit -m "feat(008): 实现教师答疑回复"
```

### Task 10: Teacher Dashboard Aggregation

**Files:**
- Create: `backend/app/teacher_console/dashboard.py`
- Create: `backend/tests/test_teacher_dashboard.py`

**Interfaces:**
- Consumes: `users`, `student_profiles`, `courses`, `agri_course_progress`, `agri_course_quiz_attempts`, `DatabaseTeacherCourseProvider`.
- Produces `build_teacher_dashboard(teacher_id) -> dict` with `student_total`, `average_progress`, `completion_rate`, `quiz_attempt_count`, `quiz_average_score`, `directions`.
- Uses `progress_percent >= 80` as completion; `completed_at` is audit metadata only.

**Work:**

- [ ] **Step 1: Write failing formula tests**

```python
def test_dashboard_uses_self_selected_direction_and_80_percent_completion(self):
    dashboard = build_teacher_dashboard(self.teacher_id)
    self.assertEqual(dashboard["student_total"], 3)
    self.assertEqual(dashboard["average_progress"], 50.0)
    self.assertEqual(dashboard["completion_rate"], 33.33)
    self.assertEqual(dashboard["quiz_attempt_count"], 2)
    self.assertEqual(dashboard["quiz_average_score"], 85.0)
    self.assertEqual(
        dashboard["directions"]["comprehensive"]["student_count"], 1
    )

def test_dashboard_does_not_expose_student_details(self):
    payload = build_teacher_dashboard(self.teacher_id)
    serialized = json.dumps(payload, ensure_ascii=False)
    self.assertNotIn("姓名", serialized)
    self.assertNotIn("contact", serialized)
    self.assertNotIn("student_id", serialized)

def test_zero_published_courses_uses_zero_progress_and_no_division_error(self):
    dashboard = build_teacher_dashboard(self.teacher_id)
    self.assertEqual(dashboard["average_progress"], 0.0)
    self.assertEqual(dashboard["completion_rate"], 0.0)
```

- [ ] **Step 2: Run it and verify failure**

Run: `uv run --directory backend python -m unittest tests.test_teacher_dashboard -v`

Expected: FAIL because dashboard service does not exist.

- [ ] **Step 3: Implement exact formulas**

```python
def _student_progress(student_id: int, direction: str) -> float:
    directions = (
        ("agriculture", "ecommerce", "handcraft")
        if direction == "comprehensive"
        else (direction,)
    )
    ratios = []
    for item in directions:
        published_ids = {
            course["id"]
            for course in get_course_provider().list_published_courses(
                student_id, item
            )
        }
        if not published_ids:
            ratios.append(0.0)
            continue
        completed = get_db().execute(
            f"""
            SELECT COUNT(*) AS count
            FROM agri_course_progress
            WHERE user_id = ? AND progress_percent >= 80
              AND course_id IN ({",".join("?" for _ in published_ids)})
            """,
            (student_id, *sorted(published_ids)),
        ).fetchone()["count"]
        ratios.append(int(completed) / len(published_ids))
    return sum(ratios) / len(ratios)
```

`student_total` counts enabled users with `role='student'` and an existing `student_profiles` row. `average_progress = sum(student_progress) / student_count`; `completion_rate` counts ratios equal to `1.0`; quiz stats resolve the teacher's visible course IDs through `DatabaseTeacherCourseProvider` and count attempts for those IDs only, never by raw `courses.status='published'`.

For `directions`, group enabled students by `student_profiles.learning_direction`:

```python
directions[group]["student_count"] = len(group_students)
directions[group]["average_progress"] = (
    sum(_student_progress(student_id, group) for student_id in group_students)
    / len(group_students)
    if group_students else 0.0
)
```

The four groups are always present: `agriculture`, `ecommerce`, `handcraft`, `comprehensive`. `comprehensive` uses each member's three-direction ratio average, not a pooled course denominator. Tests assert `student_count` and `average_progress` for all four groups against fixed fixtures.

- [ ] **Step 4: Verify and commit**

Run: `uv run --directory backend python -m unittest tests.test_teacher_dashboard -v`

Expected: PASS.

```bash
git add backend/app/teacher_console/dashboard.py backend/tests/test_teacher_dashboard.py
git commit -m "feat(008): 实现教师聚合看板"
```

### Task 11: AI Learning Report

**Files:**
- Create: `backend/app/teacher_console/reports.py`
- Modify: `backend/app/agri_skills/ai_context.py`
- Create: `backend/tests/test_teacher_reports.py`
- Modify: `backend/tests/test_agri_ai_context.py`

**Interfaces:**
- Consumes: Task 10 `build_teacher_dashboard()`, `get_ai_client()`, `build_ai_messages()`, `teacher_learning_reports`.
- Produces `generate_teacher_report(teacher_id) -> dict`, `list_teacher_reports(teacher_id) -> list[dict]`, `get_teacher_report(teacher_id, report_id) -> dict`.
- Produces AI call point `teacher_learning_report_generate`.

**Work:**

- [ ] **Step 1: Write failing report and AI-failure tests**

```python
def test_report_contains_three_sections_and_persists(self):
    self.ai.complete_json.return_value = {
        "progress_analysis": "整体进度稳定",
        "direction_comparison": "农业方向领先",
        "risk_warning": "2 名学员连续 30 天零进度",
    }
    report = generate_teacher_report(self.teacher_id)
    self.assertEqual(
        set(report["sections"]),
        {"progress_analysis", "direction_comparison", "risk_warning"},
    )
    self.assertEqual(get_teacher_report(
        self.teacher_id, report["report_id"]
    )["report_id"], report["report_id"])

def test_ai_failure_does_not_break_dashboard(self):
    self.ai.complete_json.side_effect = AiUnavailableError("down")
    with self.assertRaisesRegex(
        ProviderUnavailableError, "AI 服务暂时不可用"
    ):
        generate_teacher_report(self.teacher_id)
    self.assertEqual(build_teacher_dashboard(self.teacher_id)["student_total"], 3)

def test_invalid_report_sections_are_provider_errors(self):
    self.ai.complete_json.return_value = {"progress_analysis": "only one"}
    with self.assertRaisesRegex(
        ProviderUnavailableError, "AI 服务暂时不可用"
    ):
        generate_teacher_report(self.teacher_id)
```

- [ ] **Step 2: Run it and verify failure**

Run: `uv run --directory backend python -m unittest tests.test_teacher_reports tests.test_agri_ai_context -v`

Expected: FAIL because report service and call point do not exist.

- [ ] **Step 3: Implement aggregate-only report generation**

Add `"teacher_learning_report_generate": {"aggregate_stats", "direction_comparison", "risk_summary"}` to `AI_FIELD_ALLOWLISTS`.

```python
def generate_teacher_report(teacher_id: int) -> dict:
    dashboard = build_teacher_dashboard(teacher_id)
    context = {
        "aggregate_stats": _report_stats(dashboard),
        "direction_comparison": dashboard["directions"],
        "risk_summary": _risk_summary(teacher_id),
    }
    try:
        payload = get_ai_client().complete_json(
            build_ai_messages(
                "teacher_learning_report_generate", context
            ),
            call_point="teacher_learning_report_generate",
        )
    except AiUnavailableError as error:
        raise ProviderUnavailableError(
            "AI 服务暂时不可用",
            code="ai_unavailable",
            details={},
        ) from error
    sections = _validate_sections(payload)
    report_id = f"report-{uuid4().hex}"
    with get_db():
        get_db().execute(
            """
            INSERT INTO teacher_learning_reports (
                report_id, teacher_id, sections_json,
                stats_snapshot_json, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (report_id, teacher_id, json.dumps(sections, ensure_ascii=False),
             json.dumps(context, ensure_ascii=False), now_shanghai_iso()),
        )
    return _report_payload(report_id)
```

`_risk_summary()` computes each student's latest activity as the maximum parsed `+08:00` time across course progress `updated_at`, quiz attempt `created_at`, agriculture/handcraft learning outcomes, ecommerce live-script versions, completed simulation/copy/customer sessions, and store-plan creation times. A student is at risk when the latest activity is older than 30 days or absent and no course has `progress_percent >= 80`. Invalid or incomplete AI report output raises `ProviderUnavailableError("AI 服务暂时不可用")`. It returns only count, ratio and direction grouping. `_report_stats()` strips all identity fields.

- [ ] **Step 4: Verify and commit**

Run: `uv run --directory backend python -m unittest tests.test_teacher_reports tests.test_agri_ai_context -v`

Expected: PASS.

```bash
git add backend/app/teacher_console/reports.py backend/app/agri_skills/ai_context.py backend/tests/test_teacher_reports.py backend/tests/test_agri_ai_context.py
git commit -m "feat(008): 实现 AI 学情报告"
```

### Task 12: Teacher HTTP API and Application Wiring

**Files:**
- Create: `backend/app/teacher_console/routes.py`
- Modify: `backend/app/teacher_console/__init__.py`
- Modify: `backend/app/__init__.py`
- Create: `backend/tests/test_teacher_console_api.py`

**Interfaces:**
- Consumes: Tasks 3-11 services, 01 `load_session()`, Flask error handlers.
- Produces routes:
  `GET/POST /api/teacher/courses`,
  `GET/PUT /api/teacher/courses/<int:course_id>`,
  `POST /api/teacher/courses/<int:course_id>/submit`,
  `POST /api/teacher/courses/<int:course_id>/offline`,
  `POST /api/teacher/courses/<int:course_id>/relist`,
  `POST /api/teacher/uploads/video`,
  `GET/POST /api/teacher/courses/<int:course_id>/quiz`,
  `POST /api/teacher/courses/<int:course_id>/quiz/generate`,
  `GET/POST /api/teacher/announcements`,
  `GET /api/teacher/comments`,
  `POST /api/teacher/comments/<comment_id>/replies`,
  `GET /api/teacher/dashboard`,
  `GET/POST /api/teacher/reports`,
  `GET /api/teacher/reports/<report_id>`,
  `GET /media/teacher-courses/<path:filename>` via a separate no-prefix media blueprint.

**Work:**

- [ ] **Step 1: Write failing route authorization and payload tests**

```python
def test_teacher_routes_require_teacher_role(self):
    self.login_student()
    response = self.client.get("/api/teacher/courses")
    self.assertEqual(response.status_code, 401)

def test_course_create_uses_session_identity(self):
    self.login_teacher()
    response = self.client.post("/api/teacher/courses", json={
        "title": "课程", "direction": "agriculture",
        "summary": "简介", "content_tags": ["荔枝"],
        "duration_seconds": 300, "media_source_type": "external_url",
        "media_url": "https://media.example.test/course.mp4",
        "teacher_id": 999,
    })
    self.assertEqual(response.status_code, 201)
    self.assertEqual(response.get_json()["course"]["teacher_id"], self.teacher_id)
```

- [ ] **Step 2: Run it and verify failure**

Run: `uv run --directory backend python -m unittest tests.test_teacher_console_api -v`

Expected: FAIL because the blueprint is not registered.

- [ ] **Step 3: Implement the blueprint and error mapping**

```python
teacher_console_bp = Blueprint(
    "teacher_console", __name__, url_prefix="/api/teacher"
)

def _teacher_session() -> dict:
    session = load_session(required=True, allowed_states={"active"})
    if session["role"] != "teacher":
        abort_session_required()
    return session

@teacher_console_bp.post("/courses")
def create_course_route():
    session = _teacher_session()
    payload = _json_object_payload()
    payload.pop("teacher_id", None)
    return jsonify(
        success=True,
        course=create_teacher_course(int(session["id"]), payload),
    ), 201
```

Register handlers mapping validation/not found/conflict/access/unavailable errors to 400/404/409/403/503. The upload route sets `request.max_content_length` and accepts `multipart/form-data`. Register `teacher_console_bp` and a separate no-prefix `teacher_media_bp`; add `/api/teacher` to protected prefixes, and expose the media route at `/media/teacher-courses/<path:filename>` without requiring a teacher session so learners can play approved local files. Add a route test asserting `url_map` contains `/media/teacher-courses/<path:filename>` and not `/api/teacher/media/...`.

- [ ] **Step 4: Verify and commit**

Run: `uv run --directory backend python -m unittest tests.test_teacher_console_api -v`

Expected: PASS.

```bash
git add backend/app/teacher_console/routes.py backend/app/teacher_console/__init__.py backend/app/__init__.py backend/tests/test_teacher_console_api.py
git commit -m "feat(008): 注册教师工作台 API"
```

### Task 13: Frontend Types, API Adapter, and Pinia Store

**Files:**
- Modify: `frontend/src/api/types.ts`
- Modify: `frontend/src/api/client.ts`
- Create: `frontend/src/stores/teacherConsole.ts`
- Create: `frontend/src/stores/teacherConsole.test.ts`

**Interfaces:**
- Consumes: all `/api/teacher/*` routes.
- Produces `TeacherCourse`, `TeacherQuiz`, `TeacherAnnouncement`, `TeacherComment`, `TeacherDashboard`, `TeacherReport`.
- Produces `useTeacherConsoleStore()` actions:
  `loadCourses`, `createCourse`, `saveCourse`, `submitCourse`, `offlineCourse`, `relistCourse`, `uploadVideo`, `generateQuiz`, `saveQuiz`, `loadAnnouncements`, `publishAnnouncement`, `loadComments`, `replyComment`, `loadDashboard`, `loadReports`, `generateReport`.

**Work:**

- [ ] **Step 1: Write failing store tests**

```typescript
it('keeps FormData multipart and does not force JSON', async () => {
  mockedApiFetch.mockResolvedValue({
    success: true,
    media: {
      media_source_type: 'local_upload',
      media_url: '/media/teacher-courses/a.mp4',
      size_bytes: 12
    }
  } as never)
  const store = useTeacherConsoleStore()
  const file = new File(['video'], 'a.mp4', { type: 'video/mp4' })
  await store.uploadVideo(file)
  const options = mockedApiFetch.mock.calls[0][1]
  expect(options?.body).toBeInstanceOf(FormData)
  expect(new Headers(options?.headers).has('Content-Type')).toBe(false)
})

it('generates quiz then stores editable draft', async () => {
  mockedApiFetch.mockResolvedValue({
    success: true,
    quiz: { questions: [
      { id: 'q1', type: 'true_false',
        prompt: '?', options: ['正确', '错误'], answer: '正确' },
      { id: 'q2', type: 'single_choice',
        prompt: '?', options: ['A', 'B'], answer: 'A' },
      { id: 'q3', type: 'true_false',
        prompt: '?', options: ['正确', '错误'], answer: '错误' }
    ] }
  } as never)
  const store = useTeacherConsoleStore()
  await store.generateQuiz(1, { summary: '简介', direction: 'agriculture' })
  expect(store.quizDraft?.questions[0].id).toBe('q1')
})

it('creates a course through the collection endpoint', async () => {
  mockedApiFetch.mockResolvedValue({
    success: true,
    course: { id: 1, status: 'draft', teacher_id: 7 }
  } as never)
  const store = useTeacherConsoleStore()
  await store.createCourse({
    title: '课程', direction: 'agriculture', summary: '简介',
    content_tags: [], duration_seconds: 300,
    media_source_type: 'external_url',
    media_url: 'https://media.example.test/a.mp4'
  })
  expect(mockedApiFetch).toHaveBeenCalledWith(
    '/api/teacher/courses',
    expect.objectContaining({ method: 'POST' })
  )
})
```

- [ ] **Step 2: Run it and verify failure**

Run: `cd frontend && npm test -- teacherConsole.test.ts`

Expected: FAIL because the store and types do not exist.

- [ ] **Step 3: Implement the store and multipart client behavior**

In `apiFetch()`, only default to JSON for string bodies:

```typescript
if (
  typeof options.body === 'string' &&
  !headers.has('Content-Type')
) {
  headers.set('Content-Type', 'application/json')
}
```

Create the store with explicit request/response types and no optimistic review transitions:

```typescript
async saveCourse(courseId: number, payload: TeacherCoursePayload) {
  this.loading = true
  this.error = ''
  try {
    const response = await apiFetch<TeacherCourseResponse>(
      `/api/teacher/courses/${courseId}`,
      { method: 'PUT', body: JSON.stringify(payload) }
    )
    this.replaceCourse(response.course)
    return response.course
  } catch (error) {
    this.captureError(error, '课程保存失败')
    throw error
  } finally {
    this.loading = false
  }
}
```

- [ ] **Step 4: Verify and commit**

Run: `cd frontend && npm test -- teacherConsole.test.ts api/clientStream.test.ts api/types.test.ts`

Expected: PASS.

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/stores/teacherConsole.ts frontend/src/stores/teacherConsole.test.ts
git commit -m "feat(008): 增加教师工作台前端状态层"
```

### Task 14: Course Management UI

**Files:**
- Create: `frontend/src/components/TeacherCourseManager.vue`
- Create: `frontend/src/views/TeacherCoursesView.vue`
- Create: `frontend/src/views/TeacherCoursesView.test.ts`

**Interfaces:**
- Consumes: `useTeacherConsoleStore()` from Task 13.
- Produces course list filters, create/edit form, local upload/external URL toggle, submit/offline/relist actions, required summary validation and status labels.

**Work:**

- [ ] **Step 1: Write failing course UI tests**

```typescript
it('blocks submit when summary is blank', async () => {
  const wrapper = mount(TeacherCourseManager, { global: { plugins: [pinia] } })
  await wrapper.get('[data-test="course-title"]').setValue('课程')
  await wrapper.get('[data-test="course-summary"]').setValue('   ')
  await wrapper.get('[data-test="save-course"]').trigger('click')
  expect(wrapper.text()).toContain('课程简介/知识点要点不能为空')
  expect(apiFetch).not.toHaveBeenCalled()
})

it('shows all five teacher states and only valid actions', () => {
  const wrapper = mount(TeacherCourseManager, {
    props: {
      courses: [
        draftCourse, pendingCourse, publishedCourse,
        rejectedCourse, offlineCourse
      ]
    },
    global: { plugins: [pinia] }
  })
  expect(wrapper.text()).toContain('草稿')
  expect(wrapper.text()).toContain('待审核')
  expect(wrapper.text()).toContain('已上架')
  expect(wrapper.text()).toContain('已驳回')
  expect(wrapper.text()).toContain('已下架')
  expect(wrapper.find('[data-test="publish-pending"]').exists()).toBe(false)
  expect(wrapper.find('[data-test="offline-published"]').exists()).toBe(true)
  expect(wrapper.find('[data-test="relist-offline"]').exists()).toBe(true)
})
```

- [ ] **Step 2: Run it and verify failure**

Run: `cd frontend && npm test -- TeacherCoursesView.test.ts`

Expected: FAIL because the components do not exist.

- [ ] **Step 3: Implement course management**

Use a form with:

- title, direction select, required summary textarea, free-tag input, duration.
- segmented local upload / external URL control.
- `input[type=file]` with MP4/WebM accept and client-side 500 MiB validation.
- table/list filters for direction and status.
- action buttons rendered from the state matrix.

```vue
<select v-model="form.direction" data-test="course-direction">
  <option value="agriculture">农业</option>
  <option value="ecommerce">电商</option>
  <option value="handcraft">手工</option>
</select>
<textarea
  v-model="form.summary"
  data-test="course-summary"
  required
  placeholder="课程简介/知识点要点"
/>
```

Status badges must render `draft/pending/published/rejected/offline` as `草稿/待审核/已上架/已驳回/已下架`. Published cards show down/edit actions; pending/rejected/offline cards never show direct publish.

- [ ] **Step 4: Verify and commit**

Run: `cd frontend && npm test -- TeacherCoursesView.test.ts teacherConsole.test.ts`

Expected: PASS.

```bash
git add frontend/src/components/TeacherCourseManager.vue frontend/src/views/TeacherCoursesView.vue frontend/src/views/TeacherCoursesView.test.ts
git commit -m "feat(008): 实现课程管理界面"
```

### Task 15: Quiz Editor UI

**Files:**
- Create: `frontend/src/components/TeacherQuizEditor.vue`
- Create: `frontend/src/components/TeacherQuizEditor.test.ts`
- Modify: `frontend/src/components/TeacherCourseManager.vue`

**Interfaces:**
- Consumes: Task 13 `generateQuiz()` / `saveQuiz()`, Task 14 course form.
- Produces toggle, 3～5 question preview, prompt/option editing, deletion, save and AI-unavailable state.

**Work:**

- [ ] **Step 1: Write failing quiz editor tests**

```typescript
it('edits and deletes preview questions before save', async () => {
  const wrapper = mount(TeacherQuizEditor, {
    props: { courseId: 1, initialQuestions: fourQuestions },
    global: { plugins: [pinia] }
  })
  await wrapper.get('[data-test="question-q1-prompt"]').setValue('新题干')
  await wrapper.get('[data-test="question-q1-option-0"]').setValue('新选项')
  await wrapper.get('[data-test="delete-q2"]').trigger('click')
  await wrapper.get('[data-test="save-quiz"]').trigger('click')
  const request = JSON.parse(mockedApiFetch.mock.calls[0][1]?.body as string)
  expect(request.questions).toHaveLength(3)
  expect(request.questions[0].options[0]).toBe('新选项')
})

it('blocks save when deletion leaves fewer than three questions', async () => {
  const wrapper = mount(TeacherQuizEditor, {
    props: { courseId: 1, initialQuestions: threeQuestions },
    global: { plugins: [pinia] }
  })
  await wrapper.get('[data-test="delete-q2"]').trigger('click')
  await wrapper.get('[data-test="save-quiz"]').trigger('click')
  expect(wrapper.text()).toContain('测验至少需要 3 道题')
  expect(mockedApiFetch).not.toHaveBeenCalled()
})

it('shows exact AI unavailable copy and keeps manual form usable', async () => {
  mockedApiFetch.mockRejectedValue(new ApiError('AI 服务暂时不可用', 503))
  const wrapper = mount(TeacherQuizEditor, {
    props: { courseId: 1, initialQuestions: [] },
    global: { plugins: [pinia] }
  })
  await wrapper.get('[data-test="generate-quiz"]').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('AI 服务暂时不可用')
  expect(wrapper.get('[data-test="close-quiz"]').exists()).toBe(true)
})
```

- [ ] **Step 2: Run it and verify failure**

Run: `cd frontend && npm test -- TeacherQuizEditor.test.ts`

Expected: FAIL because the editor does not exist.

- [ ] **Step 3: Implement the editor**

```vue
<button type="button" data-test="generate-quiz" @click="generate">
  生成课后测验
</button>
<label>
  <input v-model="enabled" type="checkbox" data-test="quiz-enabled" />
  开启 AI 课后测验
</label>
<article v-for="question in questions" :key="question.id">
  <textarea
    v-model="question.prompt"
    :data-test="`question-${question.id}-prompt`"
  />
  <input
    v-for="(option, index) in question.options"
    :key="`${question.id}-${index}`"
    v-model="question.options[index]"
    :data-test="`question-${question.id}-option-${index}`"
  />
  <button
    type="button"
    :data-test="`delete-${question.id}`"
    @click="removeQuestion(question.id)"
  >
    删除题目
  </button>
</article>
```

Prevent saving enabled quizzes with fewer than 3 or more than 5 questions. Closing the quiz sends `enabled=false` and clears the learner-visible question set.

- [ ] **Step 4: Verify and commit**

Run: `cd frontend && npm test -- TeacherQuizEditor.test.ts TeacherCoursesView.test.ts`

Expected: PASS.

```bash
git add frontend/src/components/TeacherQuizEditor.vue frontend/src/components/TeacherQuizEditor.test.ts frontend/src/components/TeacherCourseManager.vue
git commit -m "feat(008): 实现测验预览编辑器"
```

### Task 16: Announcements and Interaction UI

**Files:**
- Create: `frontend/src/views/TeacherAnnouncementsView.vue`
- Create: `frontend/src/views/TeacherInteractionsView.vue`
- Create: `frontend/src/views/TeacherAnnouncementsView.test.ts`
- Create: `frontend/src/views/TeacherInteractionsView.test.ts`

**Interfaces:**
- Consumes: Task 13 announcement/comment actions.
- Produces announcement form/history, sent-announcement immutable state, course/heritage comment tabs and teacher replies.

**Work:**

- [ ] **Step 1: Write failing interaction tests**

```typescript
it('publishes an announcement and moves it into history', async () => {
  mockedApiFetch.mockResolvedValue({
    success: true,
    announcement: {
      announcement_id: 'teaching-1', title: '课程安排',
      body: '本周调整', delivery_status: 'sent',
      created_at: '2026-09-18T10:00:00+08:00'
    }
  } as never)
  const wrapper = mount(TeacherAnnouncementsView, {
    global: { plugins: [pinia] }
  })
  await wrapper.get('[data-test="announcement-title"]').setValue('课程安排')
  await wrapper.get('[data-test="announcement-body"]').setValue('本周调整')
  await wrapper.get('[data-test="publish-announcement"]').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('已群发')
  expect(wrapper.find('[data-test="edit-announcement"]').exists()).toBe(false)
})

it('labels teacher replies and supports heritage comments', async () => {
  const wrapper = mount(TeacherInteractionsView, {
    global: { plugins: [pinia] }
  })
  await wrapper.get('[data-test="tab-handcraft_teaching_video"]').trigger('click')
  expect(wrapper.text()).toContain('非遗视频评论')
  await wrapper.get('[data-test="reply-body"]').setValue('先固定绣线再起针')
  await wrapper.get('[data-test="submit-reply"]').trigger('click')
  await flushPromises()
  expect(wrapper.find('[data-test="teacher-reply-label"]').exists()).toBe(true)
})
```

- [ ] **Step 2: Run it and verify failure**

Run: `cd frontend && npm test -- TeacherAnnouncementsView.test.ts TeacherInteractionsView.test.ts`

Expected: FAIL because the views do not exist.

- [ ] **Step 3: Implement both views**

Announcement history displays `pending/sent/failed` and never offers edit/delete for `sent`. Interaction view uses `content_type` tabs, a target filter, chronological comments and reply forms; replies receive the visible label `教师回复`.

```vue
<button
  data-test="tab-handcraft_teaching_video"
  @click="activeContentType = 'handcraft_teaching_video'"
>
  非遗视频评论
</button>
<span
  v-if="comment.is_teacher_reply"
  data-test="teacher-reply-label"
>
  教师回复
</span>
```

- [ ] **Step 4: Verify and commit**

Run: `cd frontend && npm test -- TeacherAnnouncementsView.test.ts TeacherInteractionsView.test.ts`

Expected: PASS.

```bash
git add frontend/src/views/TeacherAnnouncementsView.vue frontend/src/views/TeacherInteractionsView.vue frontend/src/views/TeacherAnnouncementsView.test.ts frontend/src/views/TeacherInteractionsView.test.ts
git commit -m "feat(008): 实现公告与答疑界面"
```

### Task 17: Dashboard and Learning Report UI

**Files:**
- Create: `frontend/src/views/TeacherDashboardView.vue`
- Create: `frontend/src/views/TeacherDashboardView.test.ts`

**Interfaces:**
- Consumes: Task 13 dashboard/report actions.
- Produces five statistic cards, direction grouping, report generation/history/detail and AI-unavailable state.

**Work:**

- [ ] **Step 1: Write failing dashboard tests**

```typescript
it('renders exact aggregate cards without student details', async () => {
  mockedApiFetch.mockResolvedValue({
    success: true,
    dashboard: {
      student_total: 12,
      average_progress: 62.5,
      completion_rate: 25,
      quiz_attempt_count: 30,
      quiz_average_score: 84.2,
      directions: {
        agriculture: { student_count: 4, average_progress: 75 },
        ecommerce: { student_count: 4, average_progress: 50 },
        handcraft: { student_count: 2, average_progress: 60 },
        comprehensive: { student_count: 2, average_progress: 55 }
      }
    }
  } as never)
  const wrapper = mount(TeacherDashboardView, {
    global: { plugins: [pinia] }
  })
  await flushPromises()
  expect(wrapper.text()).toContain('62.5%')
  expect(wrapper.text()).toContain('25%')
  expect(wrapper.text()).not.toContain('姓名')
})

it('keeps cards visible when report AI is unavailable', async () => {
  mockedApiFetch
    .mockResolvedValueOnce({ success: true, dashboard: dashboardFixture } as never)
    .mockRejectedValueOnce(new ApiError('AI 服务暂时不可用', 503))
  const wrapper = mount(TeacherDashboardView, {
    global: { plugins: [pinia] }
  })
  await flushPromises()
  await wrapper.get('[data-test="generate-report"]').trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('AI 服务暂时不可用')
  expect(wrapper.get('[data-test="student-total"]').exists()).toBe(true)
})
```

- [ ] **Step 2: Run it and verify failure**

Run: `cd frontend && npm test -- TeacherDashboardView.test.ts`

Expected: FAIL because the dashboard view does not exist.

- [ ] **Step 3: Implement cards, direction table and reports**

Render stable cards with `data-test` IDs:

```vue
<article data-test="student-total">
  <span>学员总数</span>
  <strong>{{ dashboard.student_total }}</strong>
</article>
<article data-test="average-progress">
  <span>平均进度</span>
  <strong>{{ dashboard.average_progress.toFixed(1) }}%</strong>
</article>
<button
  type="button"
  data-test="generate-report"
  :disabled="reportLoading"
  @click="generateReport"
>
  生成学情报告
</button>
```

Report detail renders the three sections and creation time. No student identity fields are rendered or stored in frontend state.

- [ ] **Step 4: Verify and commit**

Run: `cd frontend && npm test -- TeacherDashboardView.test.ts teacherConsole.test.ts`

Expected: PASS.

```bash
git add frontend/src/views/TeacherDashboardView.vue frontend/src/views/TeacherDashboardView.test.ts
git commit -m "feat(008): 实现教师看板与学情报告界面"
```

### Task 18: Teacher Shell, Navigation, and Route Registration

**Files:**
- Create: `frontend/src/components/TeacherConsoleNav.vue`
- Modify: `frontend/src/views/TeacherPortalView.vue`
- Modify: `frontend/src/router/index.ts`
- Create: `frontend/src/router/teacherConsoleRoutes.test.ts`
- Modify: `frontend/src/components/PortalShell.test.ts`

**Interfaces:**
- Consumes: Task 13 store and Tasks 14-17 views, existing auth guard.
- Produces `/teacher` default redirect, `/teacher/courses`, `/teacher/announcements`, `/teacher/interactions`, `/teacher/dashboard`.

**Work:**

- [ ] **Step 1: Write failing route and shell tests**

```typescript
it('registers teacher console children under teacher role guard', () => {
  expect(router.resolve('/teacher/courses').meta.roles).toEqual(['teacher'])
  expect(router.resolve('/teacher/announcements').meta.roles).toEqual(['teacher'])
  expect(router.resolve('/teacher/interactions').meta.roles).toEqual(['teacher'])
  expect(router.resolve('/teacher/dashboard').meta.roles).toEqual(['teacher'])
})
```

- [ ] **Step 2: Run it and verify failure**

Run: `cd frontend && npm test -- teacherConsoleRoutes.test.ts PortalShell.test.ts`

Expected: FAIL because child routes and navigation do not exist.

- [ ] **Step 3: Implement shell and routes**

`TeacherPortalView.vue` renders `AppHeader`, `TeacherConsoleNav`, `RouterView`, and keeps the existing onboarding request. The nav uses Lucide icons and links to the four child routes. Router configuration:

```typescript
const teacherMeta = { requiresAuth: true, roles: ['teacher'] as const }

{
  path: '/teacher',
  component: TeacherPortalView,
  meta: teacherMeta,
  children: [
    { path: '', redirect: '/teacher/dashboard' },
    { path: 'courses', component: TeacherCoursesView, meta: teacherMeta },
    { path: 'announcements', component: TeacherAnnouncementsView, meta: teacherMeta },
    { path: 'interactions', component: TeacherInteractionsView, meta: teacherMeta },
    { path: 'dashboard', component: TeacherDashboardView, meta: teacherMeta }
  ]
}
```

- [ ] **Step 4: Verify and commit**

Run: `cd frontend && npm test -- teacherConsoleRoutes.test.ts roleRoutes.test.ts PortalShell.test.ts`

Expected: PASS.

```bash
git add frontend/src/components/TeacherConsoleNav.vue frontend/src/views/TeacherPortalView.vue frontend/src/router/index.ts frontend/src/router/teacherConsoleRoutes.test.ts frontend/src/components/PortalShell.test.ts
git commit -m "feat(008): 建立教师工作台壳层"
```

### Task 19: Cross-Module Acceptance and Full Regression

**Files:**
- Create: `backend/tests/test_teacher_console_integration.py`
- Create: `backend/tests/test_teacher_console_provider_replacement.py`
- Create: `frontend/src/views/TeacherConsoleResponsive.test.ts`
- Modify: `.agents/memories/NOW.md`

**Interfaces:**
- Consumes: all previous tasks, 01 session, 02 notifications, 03/04/05 course consumers, fake and placeholder review providers.
- Produces end-to-end evidence for FR-001..FR-050 and SC-001..SC-010.

**Work:**

- [ ] **Step 1: Add cross-module integration tests**

```python
def test_approved_course_serves_03_04_05_without_consumer_changes(self):
    for direction in ("agriculture", "ecommerce", "handcraft"):
        with self.subTest(direction=direction):
            course = self.create_course(direction)
            self.review.set_status("course_video", str(course["id"]), "approved")
            self.assertEqual(
                [item["id"] for item in list_courses(1, direction)],
                [course["id"]],
            )

def test_replacement_review_provider_requires_no_consumer_change(self):
    replacement = FakeReviewProvider()
    set_content_review_provider(self.app, replacement)
    self.assertIs(get_content_review_provider(), replacement)
    submit_course_for_review(
        self.teacher_id, self.course_id, expected_version=1
    )
    self.assertEqual(replacement.calls[-1]["method"], "submit_for_review")

def test_all_course_states_have_the_same_visibility_in_three_surfaces(self):
    for review_status in ("pending", "approved", "rejected", None):
        for local_status in ("pending", "offline"):
            with self.subTest(
                review_status=review_status, local_status=local_status
            ):
                expected = (
                    review_status == "approved"
                    and local_status != "offline"
                )
                self.assertEqual(
                    bool(self.provider_course_ids("agriculture")),
                    expected,
                )
                self.assertEqual(
                    bool(self.catalog_course_ids("agriculture")),
                    expected,
                )
                self.assertEqual(
                    bool(self.recommendation_course_ids("agriculture")),
                    expected,
                )

def test_legacy_published_course_remains_visible_in_all_three_surfaces(self):
    course_id = self.seed_legacy_published_course("agriculture")
    self.assertIn(course_id, self.provider_course_ids("agriculture"))
    self.assertIn(course_id, self.catalog_course_ids("agriculture"))
    self.assertIn(course_id, self.recommendation_course_ids("agriculture"))

def test_review_history_is_read_from_provider_authority(self):
    self.review.set_status(
        "course_video", str(self.course_id), "rejected",
        opinion="补充课程简介", updated_at="2026-09-18T12:00:00+08:00",
    )
    course = get_teacher_course(self.teacher_id, self.course_id)
    self.assertEqual(course["status"], "rejected")
    self.assertEqual(course["rejection_opinion"], "补充课程简介")
    self.assertEqual(course["review_updated_at"], "2026-09-18T12:00:00+08:00")
```

- [ ] **Step 2: Add responsive and accessibility checks**

```typescript
it('keeps teacher navigation and cards within 320/375/1280 layouts', () => {
  const source = readFileSync(
    'src/components/TeacherConsoleNav.vue',
    'utf8'
  )
  expect(source).toContain('@media (max-width: 760px)')
  expect(source).toContain('overflow-x: clip')
})
```

Use Playwright for mandatory final browser evidence at 320, 375 and 1280 widths after the code tests pass. Capture screenshots for the teacher shell, course editor, quiz editor, announcement/comment view and dashboard; the source-string test is only a guard and does not count as responsive acceptance.

- [ ] **Step 3: Run full verification**

```bash
uv run --directory backend python -m unittest discover -s tests -v
cd frontend
npm test
npx tsc -b --noEmit
npm run build
```

Expected:

- Backend: all tests pass.
- Frontend: all tests pass.
- TypeScript: no errors.
- Production build: succeeds.

- [ ] **Step 4: Record handoff and commit**

Update `.agents/memories/NOW.md` with verified commands, commit hashes, review status, provider replacement status and residual risks. Do not modify the frozen spec.

```bash
git add backend/tests/test_teacher_console_integration.py backend/tests/test_teacher_console_provider_replacement.py frontend/src/views/TeacherConsoleResponsive.test.ts .agents/memories/NOW.md
git commit -m "test(008): 完成教师工作台验收"
```

## Task Dependency Order

1. Task 1 must precede all backend work.
2. Task 2 must precede Tasks 3, 4, 5, 8-12 and 19.
3. Task 3 must precede Task 4.
4. Task 4 must precede Tasks 5, 7, 12 and 19.
5. Task 5 must precede Tasks 9, 10, 12 and 19.
6. Task 3 must precede Task 6; Task 6 must precede Task 12 and Task 14 upload UI.
7. Task 7 must precede Tasks 10, 12 and 15.
8. Tasks 8-11 may run after Tasks 1 and 3; Task 10 depends on Tasks 5 and 7 and must precede Task 11.
9. Task 12 must follow Tasks 3-11.
10. Task 13 must follow Task 12.
11. Tasks 14-17 must follow Task 13.
12. Task 15 must follow Task 14 because the quiz editor is embedded in the course form.
13. Task 18 must follow Tasks 14-17 because route registration imports the completed views.
14. Task 19 must follow every prior task.

No consumer appears before its producer:

- 03/04/05 consume `DatabaseTeacherCourseProvider` only after Task 5.
- Quiz UI consumes quiz API only after Task 12.
- Dashboard consumes course visibility only after Task 5 and quiz attempts after Task 7.
- AI report consumes dashboard aggregation only after Task 10.
- All frontend views consume the store only after Task 13, and route registration consumes the views only after Tasks 14-17.

## Suggested Session Split

1. **Session A: Tasks 1-5** - Schema, provider contracts, course persistence, state machine, CourseProvider and three student surfaces.
2. **Session B: Tasks 6-12** - Media, quiz, announcements, comments, dashboard, report and HTTP API.
3. **Session C: Tasks 13-19** - Frontend store, four views, shell/route registration, responsive checks and full regression.

## Plan Self-Review

- Every spec functional requirement maps to at least one implementation task:
  FR-001..005 -> Tasks 3, 4, 12; FR-006..018 -> Tasks 1, 3-6, 12, 14;
  FR-019..025 -> Tasks 7, 15; FR-026..031 -> Tasks 8, 9, 16;
  FR-032..038 -> Tasks 10, 17; FR-039..042 -> Tasks 11, 17;
  FR-043..050 -> Tasks 2, 4, 5, 19.
- The state matrix, three learner visibility surfaces, 80% completion, comprehensive averaging, 30-day risk threshold, free tags and dual media sources are all expressed as testable behavior.
- No task references a function or table not defined by an earlier task or an existing repository file.
- Shared files are limited to schema, app wiring, AI allowlist, course provider integration, config, API client, types and router.
- The plan does not create `tasks.md`; `specs/008-teacher-console/spec.md` remains the sole requirement authority.
