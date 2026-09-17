# 04-电商运营实训 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付 04-电商运营实训子系统，包括直播话术生成、文字直播间模拟训练与四维评分、文案提示词训练、店铺装修指导、客服模拟训练，以及电商方向课程学习、推荐、进度和 AI 课后测验。

**Architecture:** 后端在 `backend/app/ecommerce_training/` 内建立独立领域包，复用现有共享 AI gateway、错误类型和 03 的单一课程 provider 注册/替换机制；课程 provider 协议新增方向参数，同时保留 03 的农业兼容 wrapper。前端把 03 的课程 store/view 抽为方向参数化共享实现，再在同一套实现上注册电商课程页；其余实训页面使用独立 Pinia store 和 Vue view，复用 01 的会话、路由守卫和标签能力。

**Tech Stack:** Python 3.12、Flask、sqlite3、httpx、uv、unittest、Vue 3、Vite、Pinia、Vue Router、Vitest、Vue Test Utils、lucide-vue-next。

**Spec:** `specs/004-ecommerce-training/spec.md`

## Global Constraints

- 004 只允许已登录、会话状态为 `active` 的学员访问；账户、禁用状态、角色路由和会话过期复用 01。
- 兴趣标签只读复用 01 的 `interest_tags`、`student_interest_tags` 和课程标签关系；不得创建第二标签目录。
- 技能档案写入等待 07 的统一接口；004 只保存自身训练/学习源记录，不创建成果存储、可见范围或企业展示记录。
- 课程 provider 复用 03 的单一注册、默认占位机制和替换 hook；协议必须支持方向，不得新增电商专用 provider 注册表。
- 课程学习、推荐、进度、完成判定和测验语义必须与 03 一致，仅方向固定为 `ecommerce`。
- 004 全部 AI 调用均为无降级；不可用、超时、空响应或结构无效时统一提示“AI 服务暂时不可用”。
- 004 AI 调用全部为非流式完整响应；不得复用 03 问答的 SSE 或本地病虫害知识库降级。
- 达到 80% 有效进度才完成课程；已完成课程不进入推荐池；推荐顺序与 03 完全一致。
- 直播间模拟四维均为 0–100 整数分，等权 25%，总分取加权平均整数。
- 直播话术每个成功版本独立保留并作为未来技能档案成果；最新版本是模块当前结果。
- 文案训练一致性分和优化效果分均为 0–100 整数，且必须伴随理由或证据。
- 客服场景至少两条可观察目标；AI 判定目标并建议结束，学员确认后才结束，不设轮数上限。
- 08 未实现时使用固定数据库占位夹具；同一 provider hook 可透明替换为 08 权威数据。
- 所有后端代码位于 `backend/`，所有前端代码位于 `frontend/`。
- 旧系统 `app.py`、`database.py` 和根目录旧 HTML 页面禁止读取、导入、复制或迁移。
- 路由 kebab-case、Python snake_case、前端 camelCase；每个任务先失败测试、再最小实现、再验证、再提交。

## AI 调用点与降级矩阵

| 调用点 | 失败表现 | 降级行为 | 前端提示文案 |
| --- | --- | --- | --- |
| `live_script_generate` | 请求失败、超时、缺少四段结构 | 无降级；不创建成功版本，保留输入 | `AI 服务暂时不可用` |
| `simulation_score` | 请求失败、四维缺失、分数或建议无效 | 无降级；不生成评分、不完成训练，保留全部环节草稿 | `AI 服务暂时不可用` |
| `copy_case_generate` | 请求失败、少于两个有效缺陷类别 | 无降级；不发布残缺案例，保留选择 | `AI 服务暂时不可用` |
| `copy_reference_critique` | 请求失败、一致性分或理由无效 | 无降级；保留学员评判，不进入下一步 | `AI 服务暂时不可用` |
| `copy_revised_generate` | 请求失败、新版文案为空或结构无效 | 无降级；保留优化提示词，不生成新版 | `AI 服务暂时不可用` |
| `copy_optimization_critique` | 请求失败、优化分或证据无效 | 无降级；保留新旧文案，不完成训练 | `AI 服务暂时不可用` |
| `store_plan_generate` | 请求失败、四段方案缺失 | 无降级；不创建成功方案，保留输入 | `AI 服务暂时不可用` |
| `customer_message_generate` | 请求失败、空客户消息 | 无降级；保留已确认对话，不伪造下一句 | `AI 服务暂时不可用` |
| `customer_reply_analyze` | 请求失败、问题/证据/建议/目标状态缺失 | 无降级；当前回复保留为待处理，不进入下一轮 | `AI 服务暂时不可用` |
| `customer_summary` | 请求失败、四部分总结缺失 | 无降级；保留完整对话，不标记完成 | `AI 服务暂时不可用` |
| `course_quiz_grade` | 请求失败、分数或逐题讲解无效 | 无降级；不生成/覆盖成绩，保留答案 | `AI 服务暂时不可用` |

004 共 11 个 AI 调用点，全部为“无降级”。`course_quiz_grade` 复用共享 AI gateway 的既有调用点名称，新增十个调用点写入同一字段白名单。

## 与 001/003 的复用点

| 复用点 | 已存在接口/组件/机制 | 004 使用方式 | 为什么不需要新建 |
| --- | --- | --- | --- |
| 会话与角色 | `backend/app/session_manager.py`、`frontend/src/router/roleRoutes.ts`、`apiFetch` 401 处理 | 全部 004 路由使用现有学员会话与守卫 | 01 已定义会话有效期、禁用和重定向语义 |
| 兴趣标签 | `interest_tags`、`student_interest_tags`、`course_interest_tags` | 推荐和课程匹配只读取稳定 tag ID | 标签目录和学员偏好由 01 唯一拥有 |
| 课程 provider | `backend/app/agri_skills/providers.py` 的 `set_course_provider()` / `get_course_provider()` | 同一 `agri_course_provider` 扩展槽注入方向感知 provider | 新注册表会制造两个课程权威源 |
| 课程学习 | `backend/app/agri_skills/course_learning.py` 的推荐、进度和测验实现 | 泛化 direction 参数，农业 wrapper 保持原 API | 复制逻辑会违反“方向唯一差异”约束 |
| 课程进度/成绩表 | `agri_course_progress`、`agri_course_quiz_attempts` | 电商课程复用同一表和唯一正式成绩规则 | 两套表会破坏 08 学习统计与 07 档案消费 |
| AI gateway | `get_ai_client()`、`complete_json()`、`AiUnavailableError` | 004 全部调用走同一 gateway 和错误映射 | 不建立第二 AI 客户端、第二超时/脱敏机制 |
| AI 白名单 | `backend/app/agri_skills/ai_context.py` | 扩展 004 调用点并复用脱敏逻辑 | 防止账户/联系方式等字段外发 |
| 技能档案 | 07 尚未提供统一写接口 | 004 只保留源记录，等待 07 接口 | 当前 001 无写入契约，提前自建会成为错误权威源 |
| 课程前端 | `frontend/src/stores/agriCourses.ts`、`AgriCoursesView.vue` | 抽为方向参数化 store/view，农业与电商共同使用 | 复制组件会继续分散课程学习行为 |

## 共享文件改动

| Shared file | Change | Why it cannot be bypassed |
| --- | --- | --- |
| `backend/app/agri_skills/providers.py` | 增加方向感知 `CourseProvider` 契约和兼容调用 helper，保留旧扩展槽名 | provider 注册是 03 已建立的唯一替换点 |
| `backend/app/agri_skills/course_learning.py` | 推荐、进度、测验函数增加方向参数；农业旧函数作为 wrapper | 004 必须复用同一课程行为，不能复制 SQL/评分逻辑 |
| `backend/app/agri_skills/ai_context.py` | 增加 004 的 10 个新 AI 调用点白名单，并按调用域生成 system 文案 | AI 字段白名单和脱敏由共享 gateway 唯一控制 |
| `backend/app/db.py` | 增加 004 表、课程 `duration_seconds` 迁移和占位课程种子调用 | SQLite schema 与初始化只有一个共享入口 |
| `backend/app/__init__.py` | 注册 004 blueprint 与 `/api/ecommerce-training` 保护前缀 | `create_app()` 是 Flask 蓝图唯一装配点 |
| `frontend/src/api/types.ts` | 增加 004 DTO，复用现有 `CourseProgress` / `CourseQuiz` 类型 | API 类型集中维护，避免页面各自定义重复类型 |
| `frontend/src/stores/agriCourses.ts` | 改为薄兼容导出，实际指针到共享 course learning store | 农业旧导入和测试保持兼容，同时避免复制 store |
| `frontend/src/views/AgriCoursesView.vue` | 改为共享课程面板的农业参数包装 | 03 行为保持，页面逻辑不再与 004 分叉 |
| `frontend/src/router/index.ts` | 注册 004 首页和五个实训/课程页面 | Vue Router 是页面可达性的唯一注册点 |
| `frontend/src/views/StudentPortalView.vue` | 增加电商运营实训入口 | 学员门户快捷入口由现有页面唯一承载 |
| `frontend/src/data/portal-guides.ts` | 增加电商实训门户条目和引导步骤 | 01 首次使用引导只读取该目录 |

不修改 `backend/app/config.py`、`frontend/src/api/client.ts`、`AppHeader.vue`、`stores/auth.ts`、`styles/tokens.css`：现有 AI 配置、JSON 请求、头部组件、会话 store 和设计 token 已满足 004。

## File Structure

| Path | Responsibility |
| --- | --- |
| `backend/app/ecommerce_training/__init__.py` | 004 领域导出 |
| `backend/app/ecommerce_training/presets.py` | 风格、场景、缺陷类别、平台和客服目标目录 |
| `backend/app/ecommerce_training/seed.py` | 固定电商课程占位夹具 |
| `backend/app/ecommerce_training/live_script.py` | 直播话术生成、版本校验和历史 |
| `backend/app/ecommerce_training/simulation.py` | 场景环节、四维评分和总分 |
| `backend/app/ecommerce_training/copy_training.py` | 文案五步训练状态机 |
| `backend/app/ecommerce_training/store_guidance.py` | 店铺装修方案生成和历史 |
| `backend/app/ecommerce_training/customer_service.py` | 客服目标、逐轮分析和总结 |
| `backend/app/ecommerce_training/course_learning.py` | 电商课程 API 对共享课程机制的薄封装和成果投影 |
| `backend/app/ecommerce_training/routes.py` | `/api/ecommerce-training/*` JSON 路由 |
| `backend/tests/test_ecommerce_*.py` | 004 后端单元、API、持久化、无降级和夹具测试 |
| `frontend/src/stores/courseLearning.ts` | 方向参数化课程、推荐、进度和测验 store |
| `frontend/src/stores/ecommerceTraining.ts` | 电商模块首页与公共错误状态 |
| `frontend/src/stores/ecommerceLiveScript.ts` | 直播话术状态 |
| `frontend/src/stores/ecommerceSimulation.ts` | 模拟训练状态 |
| `frontend/src/stores/ecommerceCopyTraining.ts` | 文案训练状态 |
| `frontend/src/stores/ecommerceStoreGuidance.ts` | 店铺装修状态 |
| `frontend/src/stores/ecommerceCustomerService.ts` | 客服模拟状态 |
| `frontend/src/components/EcommerceTrainingNav.vue` | 004 子模块导航 |
| `frontend/src/components/CourseLearningPanel.vue` | 农业/电商共享课程学习面板 |
| `frontend/src/views/EcommerceTrainingHomeView.vue` | 004 首页 |
| `frontend/src/views/EcommerceLiveScriptView.vue` | 直播话术页面 |
| `frontend/src/views/EcommerceSimulationView.vue` | 模拟训练页面 |
| `frontend/src/views/EcommerceCopyTrainingView.vue` | 文案提示词训练页面 |
| `frontend/src/views/EcommerceStoreGuidanceView.vue` | 店铺装修页面 |
| `frontend/src/views/EcommerceCustomerServiceView.vue` | 客服模拟页面 |
| `frontend/src/views/EcommerceCoursesView.vue` | 电商课程页面 |
| `frontend/src/views/EcommerceTrainingResponsive.test.ts` | 004 响应式与无重叠验收 |

---

### Task 1: Direction-Aware Shared Course Provider

**Files:**
- Modify: `backend/app/agri_skills/providers.py`
- Modify: `backend/app/agri_skills/course_learning.py`
- Modify: `backend/tests/test_agri_course_progress.py`
- Create: `backend/tests/test_shared_course_provider.py`

**Interfaces:**
- Consumes: existing `set_course_provider(app, provider)`, `get_course_provider()`, `list_published_courses(user_id, direction)`, course progress and quiz tables.
- Produces: `CourseProvider.list_published_courses(student_id: int, direction: str) -> list[dict]`; legacy `list_published_agriculture_courses(student_id) -> list[dict]` compatibility; `list_provider_courses(student_id: int, direction: str) -> list[dict]`; `list_courses(student_id: int, direction: str) -> list[dict]`; `is_eligible_course(course: dict, direction: str) -> bool`; direction-aware `list_recommendations`, `get_course_progress`, `update_course_progress`, `get_course_quiz`, `submit_course_quiz`.

**Shared File Changes:** See Task ownership in “共享文件改动”. The same `agri_course_provider` extension remains the only provider registry.

- [ ] **Step 1: Write the failing provider compatibility test**

Create `backend/tests/test_shared_course_provider.py`:

```python
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.agri_skills.course_learning import (
    DatabaseAgriCourseProvider,
    list_courses,
)
from app.agri_skills.providers import list_provider_courses, set_course_provider
from app.db import get_db


class LegacyProvider:
    def list_published_agriculture_courses(self, student_id):
        return [{"id": 1, "direction": "agriculture"}]

    def get_course(self, course_id):
        return {"id": course_id, "direction": "agriculture"}

    def get_quiz(self, course_id):
        return None


class DirectionProvider:
    def list_published_courses(self, student_id, direction):
        return [{"id": 2, "direction": direction}]

    def get_course(self, course_id):
        return {"id": course_id, "direction": "ecommerce"}

    def get_quiz(self, course_id):
        return None


class TestSharedCourseProvider(unittest.TestCase):
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

    def test_legacy_agriculture_provider_still_works(self):
        with self.app.app_context():
            set_course_provider(self.app, LegacyProvider())
            self.assertEqual(
                list_provider_courses(1, "agriculture")[0]["id"],
                1,
            )

    def test_direction_provider_serves_ecommerce(self):
        with self.app.app_context():
            set_course_provider(self.app, DirectionProvider())
            self.assertEqual(
                list_courses(1, "ecommerce")[0]["direction"],
                "ecommerce",
            )

    def test_database_provider_keeps_legacy_agriculture_method(self):
        with self.app.app_context():
            provider = DatabaseAgriCourseProvider()
            self.assertEqual(
                provider.list_published_agriculture_courses(1),
                provider.list_published_courses(1, "agriculture"),
            )


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_shared_course_provider -v`

Expected: FAIL because `CourseProvider`, `list_provider_courses`, `list_courses`, and the direction-aware database method do not exist.

- [ ] **Step 3: Implement the shared direction-aware contract**

Replace the provider protocol block in `backend/app/agri_skills/providers.py` with:

```python
class CourseProvider(Protocol):
    def list_published_courses(
        self,
        student_id: int,
        direction: str,
    ) -> list[dict]: ...
    def get_course(self, course_id: int) -> dict | None: ...
    def get_quiz(self, course_id: int) -> dict | None: ...


AgriCourseProvider = CourseProvider


def list_provider_courses(student_id: int, direction: str) -> list[dict]:
    provider = get_course_provider()
    directional = getattr(provider, "list_published_courses", None)
    if callable(directional):
        return directional(student_id, direction)
    legacy = getattr(provider, "list_published_agriculture_courses", None)
    if direction == "agriculture" and callable(legacy):
        return legacy(student_id)
    raise ValueError("课程 provider 不支持该方向")
```

Filter every provider and recommendation result through one shared validator:

```python
REQUIRED_COURSE_TEXT_FIELDS = ("title", "summary", "teacher_name")

def is_eligible_course(course: dict, direction: str) -> bool:
    if not isinstance(course, dict) or course.get("direction") != direction:
        return False
    course_id = course.get("id")
    duration = course.get("duration_seconds")
    if (
        not isinstance(course_id, int)
        or isinstance(course_id, bool)
        or course_id <= 0
        or not isinstance(duration, int)
        or isinstance(duration, bool)
        or duration <= 0
    ):
        return False
    return all(
        isinstance(course.get(field), str) and bool(course[field].strip())
        for field in REQUIRED_COURSE_TEXT_FIELDS
    )
```

`list_courses()` returns only `is_eligible_course(item, direction)` rows. `list_recommendations()` uses the same validator after its SQL query and adds `AND c.duration_seconds > 0` to the query. `_require_course()` rejects a course that fails the validator.

In `backend/app/agri_skills/course_learning.py`, rename the provider method to:

```python
def list_published_courses(
    self,
    student_id: int,
    direction: str,
) -> list[dict]:
    courses = list_published_course_rows(student_id, direction)
    return [self._hydrate_course(course) for course in courses]

def list_published_agriculture_courses(self, student_id: int) -> list[dict]:
    return self.list_published_courses(student_id, "agriculture")
```

Import `list_provider_courses` and expose:

```python
def list_courses(student_id: int, direction: str) -> list[dict]:
    return list_provider_courses(student_id, direction)

def list_agriculture_courses(student_id: int) -> list[dict]:
    return list_courses(student_id, "agriculture")
```

Change recommendation and progress/quiz public functions to accept `direction: str = "agriculture"`, validate the course returned by the provider has the requested direction, and keep all existing call sites valid through the default. Use one shared private helper:

```python
def _require_course(course_id: int, direction: str) -> dict:
    course = get_course_provider().get_course(course_id)
    if course is None or course.get("direction") != direction:
        raise AgriNotFoundError("课程不存在")
    return course
```

- [ ] **Step 4: Run 003 and the new provider tests**

Run: `uv run --directory backend python -m unittest tests.test_shared_course_provider tests.test_agri_course_progress tests.test_agri_course_api tests.test_agri_course_quiz -v`

Expected: PASS; all existing 003 tests remain green through legacy wrappers.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/agri_skills/providers.py backend/app/agri_skills/course_learning.py backend/tests/test_agri_course_progress.py backend/tests/test_shared_course_provider.py
git commit -m "refactor(courses): 泛化共享课程 provider"
```

---

### Task 2: Backend Schema, Presets, Fixed Fixture, and AI Allowlist

**Files:**
- Create: `backend/app/ecommerce_training/__init__.py`
- Create: `backend/app/ecommerce_training/presets.py`
- Create: `backend/app/ecommerce_training/seed.py`
- Modify: `backend/app/db.py`
- Modify: `backend/app/agri_skills/ai_context.py`
- Create: `backend/tests/test_ecommerce_foundation.py`

**Interfaces:**
- Consumes: `get_db()`, `init_db()`, `seed_interest_tags()`, `AI_FIELD_ALLOWLISTS`.
- Produces: 004 tables `ecommerce_live_script_versions`, `ecommerce_simulation_trainings`, `ecommerce_copy_training_sessions`, `ecommerce_store_plans`, `ecommerce_customer_sessions`, `ecommerce_customer_turns`; `LIVE_SCRIPT_STYLES`, `SIMULATION_SCENES`, `COPY_DEFECT_CATEGORIES`, `STORE_PLATFORMS`, `CUSTOMER_SCENARIOS`; fixed placeholder fixtures; ten new AI allowlists.

**Shared File Changes:** `backend/app/db.py` and `backend/app/agri_skills/ai_context.py` are shared authorities; see the dedicated section above.

- [ ] **Step 1: Write the failing foundation test**

Create `backend/tests/test_ecommerce_foundation.py`:

```python
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.agri_skills.ai_context import AI_FIELD_ALLOWLISTS
from app.db import get_db


class TestEcommerceFoundation(unittest.TestCase):
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

    def test_tables_and_course_duration_column_exist(self):
        with self.app.app_context():
            db = get_db()
            names = {
                row["name"]
                for row in db.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            self.assertTrue(
                {
                    "ecommerce_live_script_versions",
                    "ecommerce_simulation_trainings",
                    "ecommerce_copy_training_sessions",
                    "ecommerce_store_plans",
                    "ecommerce_customer_sessions",
                    "ecommerce_customer_turns",
                }.issubset(names)
            )
            columns = {
                row["name"]
                for row in db.execute("PRAGMA table_info(courses)")
            }
            self.assertIn("duration_seconds", columns)

    def test_fixed_ecommerce_course_fixture(self):
        with self.app.app_context():
            rows = get_db().execute(
                """
                SELECT id, direction, status, duration_seconds
                FROM courses
                WHERE id BETWEEN 1001 AND 1005
                ORDER BY id
                """
            ).fetchall()
        self.assertEqual([row["id"] for row in rows], [1001, 1002, 1003, 1004, 1005])
        self.assertEqual(rows[0]["direction"], "ecommerce")
        self.assertEqual(rows[2]["status"], "pending")
        self.assertEqual(rows[3]["direction"], "agriculture")
        self.assertIsNone(rows[4]["duration_seconds"])

    def test_ai_allowlists_are_registered(self):
        expected = {
            "live_script_generate",
            "simulation_score",
            "copy_case_generate",
            "copy_reference_critique",
            "copy_revised_generate",
            "copy_optimization_critique",
            "store_plan_generate",
            "customer_message_generate",
            "customer_reply_analyze",
            "customer_summary",
        }
        self.assertTrue(expected.issubset(AI_FIELD_ALLOWLISTS))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_ecommerce_foundation -v`

Expected: FAIL with missing tables, `duration_seconds`, fixture rows and allowlists.

- [ ] **Step 3: Add the exact schema and fixture**

Append these tables to `SCHEMA_SQL` in `backend/app/db.py`:

```sql
CREATE TABLE IF NOT EXISTS ecommerce_live_script_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_name TEXT NOT NULL,
    selling_points_json TEXT NOT NULL,
    price_text TEXT NOT NULL DEFAULT '',
    style TEXT NOT NULL CHECK (style IN ('enthusiastic', 'professional', 'humorous')),
    script_json TEXT NOT NULL,
    is_current INTEGER NOT NULL DEFAULT 1 CHECK (is_current IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ecommerce_simulation_trainings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scene_key TEXT NOT NULL,
    segments_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('draft', 'completed')),
    scores_json TEXT,
    total_score INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS ecommerce_copy_training_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_type TEXT NOT NULL,
    scene_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN (
            'case_ready', 'critique_ready', 'copy_ready', 'completed'
        )
    ),
    case_json TEXT NOT NULL,
    learner_critique TEXT,
    reference_json TEXT,
    optimized_prompt TEXT,
    revised_copy TEXT,
    optimization_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS ecommerce_store_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    store_type TEXT NOT NULL,
    platform TEXT NOT NULL,
    style_preference TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ecommerce_customer_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scenario_key TEXT NOT NULL,
    goal_criteria_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK (
        status IN ('active', 'goal_reached', 'completed')
    ),
    end_suggested INTEGER NOT NULL DEFAULT 0 CHECK (end_suggested IN (0, 1)),
    confirmed_at TEXT,
    summary_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE IF NOT EXISTS ecommerce_customer_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL
        REFERENCES ecommerce_customer_sessions(id) ON DELETE CASCADE,
    turn_no INTEGER NOT NULL,
    customer_message TEXT NOT NULL,
    student_reply TEXT,
    analysis_json TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (session_id, turn_no)
);
```

Update `init_db()` in this exact order so existing databases gain the column before fixture inserts:

```python
def init_db(connection: sqlite3.Connection | None = None) -> None:
    db = connection or get_db()
    db.executescript(SCHEMA_SQL)
    _ensure_course_duration_column(db)
    seed_interest_tags(db)
    seed_ecommerce_course_fixtures(db)
    db.commit()
```

In the feature seed:

```python
FIXTURES = (
    (1001, "电商直播开场实战（占位）", "ecommerce", "published", 300, "电商直播"),
    (1002, "电商产品讲解与促单（占位）", "ecommerce", "published", 360, "电商运营"),
    (1003, "待审核电商课程（占位）", "ecommerce", "pending", 300, "电商运营"),
    (1004, "农业对照课程（占位）", "agriculture", "published", 300, None),
    (1005, "无效时长电商课程（占位）", "ecommerce", "published", None, "电商运营"),
)
```

Insert each course idempotently with `INSERT OR IGNORE`, then attach the named tag by querying `interest_tags.name`; never create a new tag.

- [ ] **Step 4: Add migrations and allowlists**

Implement:

```python
def _ensure_course_duration_column(db: sqlite3.Connection) -> None:
    columns = {row["name"] for row in db.execute("PRAGMA table_info(courses)")}
    if "duration_seconds" not in columns:
        db.execute("ALTER TABLE courses ADD COLUMN duration_seconds INTEGER")
```

Add `duration_seconds INTEGER` to the `CREATE TABLE courses` definition for fresh databases.

Extend `AI_FIELD_ALLOWLISTS` with:

```python
"live_script_generate": {"product_name", "selling_points", "price_text", "style"},
"simulation_score": {"scene_label", "segments"},
"copy_case_generate": {"product_type", "scene"},
"copy_reference_critique": {"case_text", "defect_categories", "learner_critique"},
"copy_revised_generate": {"optimized_prompt", "case_text"},
"copy_optimization_critique": {"original_copy", "revised_copy", "optimized_prompt"},
"store_plan_generate": {"store_type", "platform", "style_preference"},
"customer_message_generate": {"scenario", "goal_criteria", "prior_turns", "turn_no"},
"customer_reply_analyze": {"scenario", "goal_criteria", "customer_message", "student_reply"},
"customer_summary": {"scenario", "goal_criteria", "turns"},
```

Add `AI_CALL_DOMAINS` so 004 call points use `"电商运营实训任务：{call_point}"`; all 003 call points continue to use `"农业技能任务：{call_point}"`.

- [ ] **Step 5: Run foundation and 03 regression tests**

Run: `uv run --directory backend python -m unittest tests.test_ecommerce_foundation tests.test_agri_ai_context tests.test_foundation -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/ecommerce_training/__init__.py backend/app/ecommerce_training/presets.py backend/app/ecommerce_training/seed.py backend/app/db.py backend/app/agri_skills/ai_context.py backend/tests/test_ecommerce_foundation.py
git commit -m "feat(ecommerce): 建立实训基础与课程夹具"
```

---

### Task 3: Live Script Generation Backend

**Files:**
- Create: `backend/app/ecommerce_training/live_script.py`
- Create: `backend/tests/test_ecommerce_live_script.py`

**Interfaces:**
- Consumes: `get_db()`, `get_ai_client()`, `build_ai_messages()`, `AiUnavailableError`, `AgriValidationError`, `utc_now_iso()`, `LIVE_SCRIPT_STYLES`.
- Produces: `generate_live_script(user_id: int, payload: dict) -> dict`; `list_live_scripts(user_id: int) -> list[dict]`; `get_live_script(user_id: int, version_id: int) -> dict`; script object keys `opening`, `product_intro`, `interaction`, `closing`.

- [ ] **Step 1: Write the failing service tests**

Create `backend/tests/test_ecommerce_live_script.py` with tests for the exact four sections, version retention, latest current marker, input preservation on AI failure and ownership:

```python
self.ai.complete_json.return_value = {
    "opening": "欢迎来到直播间",
    "product_intro": "这款产品...",
    "interaction": "扣一告诉我...",
    "closing": "现在下单...",
}
first = generate_live_script(
    self.student_id,
    {
        "product_name": "荔枝干",
        "selling_points": "香甜、耐储存",
        "price_text": "39.9 元",
        "style": "enthusiastic",
    },
)
second = generate_live_script(self.student_id, {**payload, "style": "professional"})
self.assertEqual(second["id"], generated_new_version)
self.assertFalse(first["is_current"])
self.assertEqual(len(list_live_scripts(self.student_id)), 2)
self.ai.complete_json.side_effect = AiUnavailableError("raw")
with self.assertRaisesRegex(AiUnavailableError, "AI 服务暂时不可用"):
    generate_live_script(self.student_id, payload)
self.assertEqual(len(list_live_scripts(self.student_id)), 2)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_ecommerce_live_script -v`

Expected: FAIL because `app.ecommerce_training.live_script` does not exist.

- [ ] **Step 3: Implement validation and persistence**

Use exact keys and validators:

```python
SCRIPT_KEYS = ("opening", "product_intro", "interaction", "closing")

def _validate_payload(payload: dict) -> dict:
    product_name = str(payload.get("product_name", "")).strip()
    selling_points = [
        str(value).strip()
        for value in payload.get("selling_points", [])
        if str(value).strip()
    ]
    style = str(payload.get("style", "")).strip()
    if not product_name:
        raise AgriValidationError("商品名称不能为空")
    if not selling_points:
        raise AgriValidationError("至少填写一个卖点")
    if style not in LIVE_SCRIPT_STYLES:
        raise AgriValidationError("直播风格不正确")
    return {
        "product_name": product_name,
        "selling_points": selling_points,
        "price_text": str(payload.get("price_text", "")).strip(),
        "style": style,
    }

def _validate_script(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise AiUnavailableError("AI 服务暂时不可用")
    script = {key: str(payload.get(key, "")).strip() for key in SCRIPT_KEYS}
    if any(not value for value in script.values()):
        raise AiUnavailableError("AI 服务暂时不可用")
    return script
```

Call `get_ai_client().complete_json(build_ai_messages("live_script_generate", request), call_point="live_script_generate")`. In one transaction mark all prior user versions `is_current = 0`, insert the new version with `is_current = 1`, and return the serialized row.

- [ ] **Step 4: Run service tests**

Run: `uv run --directory backend python -m unittest tests.test_ecommerce_live_script -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/ecommerce_training/live_script.py backend/tests/test_ecommerce_live_script.py
git commit -m "feat(ecommerce): 实现直播话术生成"
```

---

### Task 4: Simulation Training and Four-Dimension Scoring Backend

**Files:**
- Create: `backend/app/ecommerce_training/simulation.py`
- Create: `backend/tests/test_ecommerce_simulation.py`

**Interfaces:**
- Consumes: `SIMULATION_SCENES`, AI gateway, `ecommerce_simulation_trainings`, `utc_now_iso()`.
- Produces: `list_simulation_scenes() -> list[dict]`; `start_simulation(user_id: int, scene_key: str) -> dict`; `save_simulation_segment(user_id: int, training_id: int, segment_key: str, text: str) -> dict`; `score_simulation(user_id: int, training_id: int) -> dict`; `list_simulations(user_id: int) -> list[dict]`; `get_simulation(user_id: int, training_id: int) -> dict`.
- Score dimensions: `pacing`, `emotion`, `interaction`, `selling_point`; each integer 0–100; `total_score = round(sum(scores) / 4)`.

- [ ] **Step 1: Write the failing simulation tests**

Create `backend/tests/test_ecommerce_simulation.py` with exact scenes and scoring:

```python
self.assertEqual(
    [scene["key"] for scene in list_simulation_scenes()],
    ["opening", "product_intro", "interaction", "closing", "objection"],
)
training = start_simulation(self.student_id, "opening")
for key, text in self.segments.items():
    save_simulation_segment(self.student_id, training["id"], key, text)
self.ai.complete_json.return_value = {
    "scores": {
        "pacing": 80,
        "emotion": 72,
        "interaction": 90,
        "selling_point": 66,
    },
    "suggestions": {
        "pacing": "缩短长句。",
        "emotion": "增加情绪词。",
        "interaction": "增加提问。",
        "selling_point": "先讲核心利益。",
    },
}
result = score_simulation(self.student_id, training["id"])
self.assertEqual(result["total_score"], 77)
self.assertEqual(result["status"], "completed")
```

Add cases for incomplete segments, invalid dimension, AI failure preserving draft, and another student receiving not-found.

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_ecommerce_simulation -v`

Expected: FAIL because the module and functions do not exist.

- [ ] **Step 3: Implement the exact scenes and validation**

Define:

```python
SIMULATION_SCENES = {
    "opening": {
        "label": "开场白",
        "segments": [
            {"key": "greeting", "label": "问候"},
            {"key": "hook", "label": "引题"},
            {"key": "audience_call", "label": "聚人"},
        ],
    },
    "product_intro": {
        "label": "产品介绍",
        "segments": [
            {"key": "core_value", "label": "核心卖点"},
            {"key": "use_case", "label": "使用场景"},
            {"key": "proof", "label": "信任证明"},
        ],
    },
    "interaction": {
        "label": "互动引导",
        "segments": [
            {"key": "question", "label": "提问"},
            {"key": "poll", "label": "投票"},
            {"key": "response_prompt", "label": "回应引导"},
        ],
    },
    "closing": {
        "label": "促单话术",
        "segments": [
            {"key": "offer", "label": "利益点"},
            {"key": "urgency", "label": "紧迫感"},
            {"key": "call_to_action", "label": "行动指令"},
        ],
    },
    "objection": {
        "label": "异议处理",
        "segments": [
            {"key": "acknowledge", "label": "承接异议"},
            {"key": "clarify", "label": "澄清问题"},
            {"key": "evidence", "label": "证据回应"},
            {"key": "close", "label": "再次促单"},
        ],
    },
}
```

Implement validation:

```python
def _validate_scores(payload: dict) -> tuple[dict, dict]:
    if not isinstance(payload, dict):
        raise AiUnavailableError("AI 服务暂时不可用")
    scores = payload.get("scores")
    suggestions = payload.get("suggestions")
    keys = set(DIMENSION_KEYS)
    if not isinstance(scores, dict) or set(scores) != keys:
        raise AiUnavailableError("AI 服务暂时不可用")
    if not isinstance(suggestions, dict) or set(suggestions) != keys:
        raise AiUnavailableError("AI 服务暂时不可用")
    normalized_scores = {}
    normalized_suggestions = {}
    for key in DIMENSION_KEYS:
        score = scores[key]
        suggestion = str(suggestions[key]).strip()
        if (
            not isinstance(score, int)
            or isinstance(score, bool)
            or not 0 <= score <= 100
            or not suggestion
        ):
            raise AiUnavailableError("AI 服务暂时不可用")
        normalized_scores[key] = score
        normalized_suggestions[key] = suggestion
    return normalized_scores, normalized_suggestions
```

Require every configured segment for the chosen scene before calling AI.

- [ ] **Step 4: Run tests**

Run: `uv run --directory backend python -m unittest tests.test_ecommerce_simulation -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/ecommerce_training/simulation.py backend/tests/test_ecommerce_simulation.py
git commit -m "feat(ecommerce): 实现直播模拟训练评分"
```

---

### Task 5: Copy Prompt Training Backend

**Files:**
- Create: `backend/app/ecommerce_training/copy_training.py`
- Create: `backend/tests/test_ecommerce_copy_training.py`

**Interfaces:**
- Consumes: `COPY_DEFECT_CATEGORIES`, AI gateway, `ecommerce_copy_training_sessions`.
- Produces: `create_copy_training(user_id: int, product_type: str, scene: str) -> dict`; `submit_copy_critique(user_id: int, session_id: int, critique: str) -> dict`; `generate_revised_copy(user_id: int, session_id: int, optimized_prompt: str) -> dict`; `generate_optimization_critique(user_id: int, session_id: int) -> dict`; history getters.
- Defect categories: `missing_key_information`, `unclear_value`, `unsupported_claim`, `missing_interaction`, `missing_action`.

- [ ] **Step 1: Write failing five-step tests**

Create `backend/tests/test_ecommerce_copy_training.py`:

```python
self.ai.complete_json.side_effect = [
    {
        "copy_text": "这款产品很好，赶紧买。",
        "defect_categories": ["missing_key_information", "missing_action"],
    },
    {
        "reference_critique": "缺少价格、规格和行动引导。",
        "consistency_score": 67,
        "reason": "命中两个问题，遗漏信任证据。",
    },
    {"revised_copy": "精选荔枝干，净含量 250g，限时 39.9 元，点击下单。"},
    {
        "differences": ["补充规格", "补充价格", "增加行动指令"],
        "optimization_score": 88,
        "evidence": "新版包含可验证信息并明确下一步。",
    },
]
session = create_copy_training(self.student_id, "food", "social_commerce")
critiqued = submit_copy_critique(self.student_id, session["id"], "没有规格和下单引导。")
copied = generate_revised_copy(self.student_id, session["id"], "写一段荔枝干短文案，包含规格、价格和行动指令")
completed = generate_optimization_critique(self.student_id, session["id"])
self.assertEqual(completed["status"], "completed")
self.assertEqual(completed["optimization"]["optimization_score"], 88)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_ecommerce_copy_training -v`

Expected: FAIL because the service is absent.

- [ ] **Step 3: Implement state validation and exact AI calls**

Allowed transitions:

```python
TRANSITIONS = {
    ("case_ready", "critique"): "critique_ready",
    ("critique_ready", "copy"): "copy_ready",
    ("copy_ready", "optimization"): "completed",
}
```

Validate case generation:

```python
def _validate_case(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise AiUnavailableError("AI 服务暂时不可用")
    text = str(payload.get("copy_text", "")).strip()
    categories = payload.get("defect_categories")
    if (
        not text
        or not isinstance(categories, list)
        or len(set(categories)) < 2
        or not set(categories).issubset(COPY_DEFECT_CATEGORIES)
    ):
        raise AiUnavailableError("AI 服务暂时不可用")
    return {"copy_text": text, "defect_categories": sorted(set(categories))}
```

Validate consistency and optimization scores as integers 0–100 with non-empty reason/evidence. Each method uses exactly:

```python
call_point = {
    "case": "copy_case_generate",
    "critique": "copy_reference_critique",
    "copy": "copy_revised_generate",
    "optimization": "copy_optimization_critique",
}[step]
```

On AI failure, roll back only the failed step and keep the previous completed fields.

- [ ] **Step 4: Run tests with all failure branches**

Run: `uv run --directory backend python -m unittest tests.test_ecommerce_copy_training -v`

Expected: PASS, including state skip rejection and AI failure preservation.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/ecommerce_training/copy_training.py backend/tests/test_ecommerce_copy_training.py
git commit -m "feat(ecommerce): 实现文案提示词训练"
```

---

### Task 6: Store Decoration Guidance Backend

**Files:**
- Create: `backend/app/ecommerce_training/store_guidance.py`
- Create: `backend/tests/test_ecommerce_store_guidance.py`

**Interfaces:**
- Consumes: `STORE_PLATFORMS`, AI gateway, `ecommerce_store_plans`.
- Produces: `generate_store_plan(user_id: int, payload: dict) -> dict`; `list_store_plans(user_id: int) -> list[dict]`; `get_store_plan(user_id: int, plan_id: int) -> dict`.
- Required plan keys: `home_layout`, `color_scheme`, `detail_structure`, `navigation`.

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_ecommerce_store_guidance.py`:

```python
self.ai.complete_json.return_value = {
    "home_layout": ["顶部活动区", "商品分组"],
    "color_scheme": {"primary": "#E43D30", "accent": "#F7C948"},
    "detail_structure": ["卖点", "参数", "售后"],
    "navigation": ["首页", "新品", "优惠", "客服"],
}
plan = generate_store_plan(
    self.student_id,
    {
        "store_type": "农产品旗舰店",
        "platform": "taobao",
        "style_preference": "温暖、可靠",
    },
)
self.assertEqual(set(plan["plan"]), {
    "home_layout", "color_scheme", "detail_structure", "navigation"
})
self.assertEqual(list_store_plans(self.student_id)[0]["id"], plan["id"])
```

Add one invalid platform test and one AI failure test asserting no row is created.

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_ecommerce_store_guidance -v`

Expected: FAIL because the service is absent.

- [ ] **Step 3: Implement exact validation**

Use:

```python
STORE_PLATFORM_KEYS = {"taobao", "pinduoduo", "douyin_shop"}
PLAN_KEYS = (
    "home_layout",
    "color_scheme",
    "detail_structure",
    "navigation",
)
```

Reject a missing/blank store type, style preference or unsupported platform with `AgriValidationError`. Reject any AI payload where any plan key is `None`, an empty string, an empty list or an empty dict with `AiUnavailableError("AI 服务暂时不可用")`. Insert a row only after all validations pass.

- [ ] **Step 4: Run tests**

Run: `uv run --directory backend python -m unittest tests.test_ecommerce_store_guidance -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/ecommerce_training/store_guidance.py backend/tests/test_ecommerce_store_guidance.py
git commit -m "feat(ecommerce): 实现店铺装修指导"
```

---

### Task 7: Customer Service Simulation Backend

**Files:**
- Create: `backend/app/ecommerce_training/customer_service.py`
- Create: `backend/tests/test_ecommerce_customer_service.py`

**Interfaces:**
- Consumes: `CUSTOMER_SCENARIOS`, AI gateway, `ecommerce_customer_sessions`, `ecommerce_customer_turns`.
- Produces: `list_customer_scenarios() -> list[dict]`; `start_customer_session(user_id: int, scenario_key: str) -> dict`; `submit_customer_reply(user_id: int, session_id: int, reply: str) -> dict`; `generate_next_customer_message(user_id: int, session_id: int) -> dict`; `end_customer_session(user_id: int, session_id: int) -> dict`; history getters.

- [ ] **Step 1: Write the failing multi-turn tests**

Create `backend/tests/test_ecommerce_customer_service.py` covering five scenarios, no maximum turn count, analysis before next message, goal suggestion, confirmation and summary:

```python
self.assertEqual(
    [item["key"] for item in list_customer_scenarios()],
    ["product_info", "price_promo", "shipping", "after_sales", "complaint"],
)
session = start_customer_session(self.student_id, "after_sales")
self.ai.complete_json.side_effect = [
    {
        "problem": "未先确认订单情况",
        "evidence": "学员直接说明退换政策",
        "suggestion": "先询问订单号和商品状态",
        "criteria": {
            "issue_identified": False,
            "policy_and_process_explained": True,
        },
        "goal_status": "not_reached",
    },
    {"customer_message": "商品已经拆封，还能退吗？"},
    {
        "problem": "回应完整",
        "evidence": "先确认拆封状态并说明流程",
        "suggestion": "补充时效",
        "criteria": {
            "issue_identified": True,
            "policy_and_process_explained": True,
        },
        "goal_status": "reached",
    },
    {
        "overall_performance": "能承接问题",
        "main_problems": ["首次未确认订单"],
        "prioritized_improvements": ["先确认事实", "补充时效"],
        "goal_completion": "两项目标均完成",
    },
]
after_reply = submit_customer_reply(self.student_id, session["id"], "请提供订单号")
self.assertEqual(after_reply["status"], "active")
next_turn = generate_next_customer_message(self.student_id, session["id"])
self.assertEqual(next_turn["turns"][-1]["customer_message"], "商品已经拆封，还能退吗？")
reached = submit_customer_reply(self.student_id, session["id"], "拆封后可按规定申请")
self.assertTrue(reached["end_suggested"])
completed = end_customer_session(self.student_id, session["id"])
self.assertEqual(completed["status"], "completed")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_ecommerce_customer_service -v`

Expected: FAIL because the service is absent.

- [ ] **Step 3: Define exact scenarios and goal criteria**

Use:

```python
CUSTOMER_SCENARIOS = {
    "product_info": {
        "label": "商品信息咨询",
        "criteria": ["product_need_identified", "accurate_info_and_next_step"],
    },
    "price_promo": {
        "label": "价格优惠咨询",
        "criteria": ["promotion_rule_explained", "eligibility_verified"],
    },
    "shipping": {
        "label": "物流时效咨询",
        "criteria": ["order_context_identified", "delivery_and_next_step"],
    },
    "after_sales": {
        "label": "售后退换咨询",
        "criteria": ["issue_identified", "policy_and_process_explained"],
    },
    "complaint": {
        "label": "投诉与情绪安抚",
        "criteria": ["emotion_acknowledged", "resolution_or_escalation"],
    },
}
```

- [ ] **Step 4: Implement strict call separation**

`submit_customer_reply` calls only `customer_reply_analyze`; it must return non-empty `problem`, `evidence`, `suggestion`, every criterion key and one of `reached` / `not_reached`. It sets `end_suggested = 1` only when all criteria are true and `goal_status == "reached"`.

`generate_next_customer_message` calls only `customer_message_generate` and refuses when the latest turn already has a customer message or when `end_suggested = 1`.

`end_customer_session` refuses unless `end_suggested = 1` and performs only `customer_summary`. Require these four non-empty keys:

```python
SUMMARY_KEYS = (
    "overall_performance",
    "main_problems",
    "prioritized_improvements",
    "goal_completion",
)
```

Do not impose a maximum `turn_no`; AI never changes session status automatically.

- [ ] **Step 5: Run tests**

Run: `uv run --directory backend python -m unittest tests.test_ecommerce_customer_service -v`

Expected: PASS, including failure preservation and no auto-end.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/ecommerce_training/customer_service.py backend/tests/test_ecommerce_customer_service.py
git commit -m "feat(ecommerce): 实现客服模拟训练"
```

---

### Task 8: E-commerce Course Learning API and Outcome Projection

**Files:**
- Create: `backend/app/ecommerce_training/course_learning.py`
- Create: `backend/tests/test_ecommerce_course_learning.py`

**Interfaces:**
- Consumes: generalized shared course functions from Task 1, `ecommerce_courses` direction providers, `agri_course_progress`, `agri_course_quiz_attempts`, `courses`.
- Produces: `list_ecommerce_courses(student_id: int) -> list[dict]`; `list_ecommerce_recommendations(student_id: int) -> list[dict]`; `get_ecommerce_course_progress(user_id: int, course_id: int) -> dict`; `update_ecommerce_course_progress(user_id: int, course_id: int, position_seconds: int, watched_delta_seconds: int) -> dict`; `get_ecommerce_course_quiz(user_id: int, course_id: int) -> dict | None`; `submit_ecommerce_course_quiz(user_id: int, course_id: int, answers: dict) -> dict`; `list_ecommerce_learning_outcomes(user_id: int) -> list[dict]` returning kinds `live_script`, `simulation_training`, `course_quiz`, `course_completion`.

- [ ] **Step 1: Write the failing course tests**

Create `backend/tests/test_ecommerce_course_learning.py` using a direction-aware fake provider and fixed fixture:

```python
courses = list_ecommerce_courses(self.student_id)
self.assertEqual([course["id"] for course in courses], [1002, 1001])
self.assertTrue(all(course["direction"] == "ecommerce" for course in courses))

progress = update_ecommerce_course_progress(self.student_id, 1001, 80, 80)
self.assertEqual(progress["progress_percent"], 80)
self.assertIsNotNone(progress["completed_at"])

recommendations = list_ecommerce_recommendations(self.student_id)
self.assertNotIn(1001, [course["id"] for course in recommendations])

self.ai.complete_json.return_value = {
    "score": 90,
    "questions": [{"id": "q1", "correct": True, "explanation": "正确"}],
}
attempt = submit_ecommerce_course_quiz(self.student_id, 1002, {"q1": "A"})
self.assertTrue(attempt["is_formal"])
outcomes = list_ecommerce_learning_outcomes(self.student_id)
self.assertEqual(
    {outcome["kind"] for outcome in outcomes},
    {"live_script", "simulation_training", "course_quiz", "course_completion"},
)
self.assertTrue(
    all(outcome["archive_written"] is False for outcome in outcomes)
)
```

Also assert 1003/1004/1005 are excluded and no second provider registry is created.

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_ecommerce_course_learning -v`

Expected: FAIL because the module is absent.

- [ ] **Step 3: Implement thin direction wrappers**

Use shared functions exactly:

```python
def list_ecommerce_courses(student_id: int) -> list[dict]:
    return list_courses(student_id, "ecommerce")

def list_ecommerce_recommendations(student_id: int) -> list[dict]:
    return list_recommendations(student_id, "ecommerce")

def update_ecommerce_course_progress(
    user_id: int,
    course_id: int,
    position_seconds: int,
    watched_delta_seconds: int,
) -> dict:
    return update_course_progress(
        user_id,
        course_id,
        position_seconds,
        watched_delta_seconds,
        direction="ecommerce",
    )
```

Implement the remaining wrappers with `direction="ecommerce"`. `list_ecommerce_learning_outcomes` returns one normalized source-record projection per completed or successful item:

```python
def list_ecommerce_learning_outcomes(user_id: int) -> list[dict]:
    outcomes = []
    outcomes.extend(_live_script_outcomes(user_id))
    outcomes.extend(_simulation_outcomes(user_id))
    outcomes.extend(_course_quiz_outcomes(user_id))
    outcomes.extend(_course_completion_outcomes(user_id))
    return sorted(
        outcomes,
        key=lambda item: (item["created_at"], item["kind"], item["source_id"]),
    )
```

Every row includes `kind`, `source_id`, `created_at`, `summary`, `score`, `is_formal`, `archive_written=False`. It never inserts into an archive table and never claims that 07 consumed the outcome.

- [ ] **Step 4: Run course and 03 contract tests**

Run: `uv run --directory backend python -m unittest tests.test_ecommerce_course_learning tests.test_shared_course_provider tests.test_agri_course_quiz -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/ecommerce_training/course_learning.py backend/tests/test_ecommerce_course_learning.py
git commit -m "feat(ecommerce): 复用电商课程学习机制"
```

---

### Task 9: E-commerce Training JSON Routes

**Files:**
- Create: `backend/app/ecommerce_training/routes.py`
- Modify: `backend/app/__init__.py`
- Create: `backend/tests/test_ecommerce_api.py`

**Interfaces:**
- Consumes: all Task 3–8 service functions, `load_session`, `abort_session_required`, shared error classes.
- Produces: `ecommerce_training_bp` with `/api/ecommerce-training/*`; `register_ecommerce_training_error_handlers(app)`; one student guard.

**Shared File Changes:** `backend/app/__init__.py` registers the blueprint and protects `/api/ecommerce-training`; see the dedicated section.

- [ ] **Step 1: Write the failing API contract test**

Create `backend/tests/test_ecommerce_api.py`:

```python
ROUTES = [
    ("POST", "/api/ecommerce-training/live-scripts", {}),
    ("GET", "/api/ecommerce-training/live-scripts", None),
    ("GET", "/api/ecommerce-training/simulations/scenes", None),
    ("POST", "/api/ecommerce-training/simulations", {"scene_key": "opening"}),
    ("GET", "/api/ecommerce-training/copy-training/catalog", None),
    ("POST", "/api/ecommerce-training/copy-training", {"product_type": "food", "scene": "social_commerce"}),
    ("GET", "/api/ecommerce-training/customer-service/scenarios", None),
    ("POST", "/api/ecommerce-training/customer-service/sessions", {"scenario_key": "after_sales"}),
    ("GET", "/api/ecommerce-training/courses", None),
    ("GET", "/api/ecommerce-training/recommendations", None),
]

for method, path, payload in ROUTES:
    anonymous = self.app.test_client().open(path, method=method, json=payload)
    teacher = self.teacher_client.open(path, method=method, json=payload)
    self.assertEqual(anonymous.status_code, 401)
    self.assertEqual(teacher.status_code, 401)
    self.assertEqual(anonymous.get_json()["message"], "未登录或会话已过期")
```

Add route tests for exact 201/200/400/404/503 mappings and never expose raw provider errors.

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run --directory backend python -m unittest tests.test_ecommerce_api -v`

Expected: FAIL with 404 because the blueprint is not registered.

- [ ] **Step 3: Implement the route table**

Register routes:

```text
POST /api/ecommerce-training/live-scripts
GET  /api/ecommerce-training/live-scripts
GET  /api/ecommerce-training/live-scripts/<int:version_id>

GET  /api/ecommerce-training/simulations/scenes
POST /api/ecommerce-training/simulations
GET  /api/ecommerce-training/simulations
GET  /api/ecommerce-training/simulations/<int:training_id>
PUT  /api/ecommerce-training/simulations/<int:training_id>/segments/<segment_key>
POST /api/ecommerce-training/simulations/<int:training_id>/score

GET  /api/ecommerce-training/copy-training/catalog
POST /api/ecommerce-training/copy-training
GET  /api/ecommerce-training/copy-training
GET  /api/ecommerce-training/copy-training/<int:session_id>
POST /api/ecommerce-training/copy-training/<int:session_id>/critique
POST /api/ecommerce-training/copy-training/<int:session_id>/copy
POST /api/ecommerce-training/copy-training/<int:session_id>/optimization

POST /api/ecommerce-training/store-plans
GET  /api/ecommerce-training/store-plans
GET  /api/ecommerce-training/store-plans/<int:plan_id>

GET  /api/ecommerce-training/customer-service/scenarios
POST /api/ecommerce-training/customer-service/sessions
GET  /api/ecommerce-training/customer-service/sessions
GET  /api/ecommerce-training/customer-service/sessions/<int:session_id>
POST /api/ecommerce-training/customer-service/sessions/<int:session_id>/replies
POST /api/ecommerce-training/customer-service/sessions/<int:session_id>/next-message
POST /api/ecommerce-training/customer-service/sessions/<int:session_id>/end

GET  /api/ecommerce-training/courses
GET  /api/ecommerce-training/recommendations
GET  /api/ecommerce-training/courses/<int:course_id>/progress
PUT  /api/ecommerce-training/courses/<int:course_id>/progress
GET  /api/ecommerce-training/courses/<int:course_id>/quiz
POST /api/ecommerce-training/courses/<int:course_id>/quiz
```

The guard is:

```python
def _student_session() -> dict:
    session = load_session(required=True, allowed_states={"active"})
    if session["role"] != "student":
        abort_session_required()
    return session
```

Map `AgriValidationError` to 400, `AgriNotFoundError`/`AgriAccessError` to 404, and `AiUnavailableError` to 503 with exact message `AI 服务暂时不可用`.

- [ ] **Step 4: Register the blueprint**

In `create_app()` add `/api/ecommerce-training` to `PROTECTED_API_PREFIXES`, import `ecommerce_training_bp`, and register it after `agri_skills_bp`.

- [ ] **Step 5: Run all backend tests**

Run: `uv run --directory backend python -m unittest discover -s tests -v`

Expected: PASS for all 01–04 backend tests.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/ecommerce_training/routes.py backend/app/__init__.py backend/tests/test_ecommerce_api.py
git commit -m "feat(ecommerce): 注册实训 API"
```

---

### Task 10: Shared Frontend Types and Direction-Aware Course Store

**Files:**
- Modify: `frontend/src/api/types.ts`
- Create: `frontend/src/stores/courseLearning.ts`
- Create: `frontend/src/stores/ecommerceTraining.ts`
- Modify: `frontend/src/stores/agriCourses.ts`
- Create: `frontend/src/components/EcommerceTrainingNav.vue`
- Create: `frontend/src/components/CourseLearningPanel.vue`
- Modify: `frontend/src/views/AgriCoursesView.vue`
- Create: `frontend/src/stores/courseLearning.test.ts`

**Interfaces:**
- Produces: `LiveScriptVersion`, `SimulationScene`, `SimulationTraining`, `CopyTrainingSession`, `StorePlan`, `CustomerScenario`, `CustomerSession`, `EcommerceCourse`.
- Produces: `useCourseLearningStore()` with `configure(apiPrefix: string, direction: 'agriculture' | 'ecommerce')`, `loadCourses()`, `loadRecommendations()`, `loadProgress(courseId)`, `saveProgress(...)`, `loadQuiz(courseId)`, `submitQuiz(courseId, answers)`.
- Produces: `useEcommerceTrainingStore()` for shared 004 module error/loading presentation.
- Produces: `EcommerceTrainingNav` with seven links and `CourseLearningPanel` props `{ direction, moduleCode, title, description, apiPrefix }` plus a `nav` slot.
- Keeps: `useAgriCoursesStore` as an alias to the shared store with agriculture defaults.

**Shared File Changes:** See “共享文件改动”; this task changes type authority and replaces duplicated course UI logic.

- [ ] **Step 1: Write the failing store-parameterization test**

Create `frontend/src/stores/courseLearning.test.ts`:

```ts
it('switches course endpoints and direction without creating another store', async () => {
  const store = useCourseLearningStore()
  store.configure('/api/ecommerce-training', 'ecommerce')
  apiFetch.mockResolvedValueOnce({ success: true, courses: [] })
  await store.loadCourses()
  expect(apiFetch).toHaveBeenCalledWith('/api/ecommerce-training/courses')
  expect(store.direction).toBe('ecommerce')
  expect(store.apiPrefix).toBe('/api/ecommerce-training')
})

it('keeps agriculture defaults for the legacy store', async () => {
  const store = useAgriCoursesStore()
  apiFetch.mockResolvedValueOnce({ success: true, courses: [] })
  await store.loadCourses()
  expect(apiFetch).toHaveBeenCalledWith('/api/agri-skills/courses')
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend; npx vitest run src/stores/courseLearning.test.ts`

Expected: FAIL because `courseLearning.ts` does not exist.

- [ ] **Step 3: Add exact DTOs and generic store**

Add the DTOs to `frontend/src/api/types.ts`. Define the generic course store with defaults:

```ts
const DEFAULT_API_PREFIX = '/api/agri-skills'
const DEFAULT_DIRECTION = 'agriculture' as const

export const useCourseLearningStore = defineStore('courseLearning', {
  state: () => ({
    apiPrefix: DEFAULT_API_PREFIX,
    direction: DEFAULT_DIRECTION,
    courses: [] as EcommerceCourse[],
    recommendations: [] as EcommerceCourse[],
    progressByCourse: {} as Record<number, CourseProgress>,
    progressErrorsByCourse: {} as Record<number, string>,
    activeQuiz: null as CourseQuiz | null,
    attempts: [] as CourseQuizAttempt[],
    loading: false,
    error: '',
    recommendationError: ''
  }),
  actions: {
    configure(apiPrefix: string, direction: 'agriculture' | 'ecommerce') {
      if (this.apiPrefix === apiPrefix && this.direction === direction) return
      this.apiPrefix = apiPrefix
      this.direction = direction
      this.courses = []
      this.recommendations = []
      this.progressByCourse = {}
      this.progressErrorsByCourse = {}
      this.activeQuiz = null
      this.attempts = []
    },
    async loadCourses() {
      const response = await apiFetch<{ success: true; courses: EcommerceCourse[] }>(
        `${this.apiPrefix}/courses`
      )
      this.courses = response.courses.filter(course => course.direction === this.direction)
    }
  }
})
```

Replace the body of `agriCourses.ts` with:

```ts
export { useCourseLearningStore } from './courseLearning'
export const useAgriCoursesStore = useCourseLearningStore
export type { CourseLearningCourse as AgriCourse } from './courseLearning'
```

All other actions follow the same `${this.apiPrefix}` pattern and preserve the existing error semantics.

- [ ] **Step 4: Extract the shared course panel**

Create `CourseLearningPanel.vue` from the existing `AgriCoursesView.vue` markup/behavior. Its script begins:

```ts
const props = defineProps<{
  direction: 'agriculture' | 'ecommerce'
  moduleCode: string
  title: string
  description: string
  apiPrefix: string
}>()
const coursesStore = useCourseLearningStore()
onMounted(() => {
  coursesStore.configure(props.apiPrefix, props.direction)
  void Promise.all([coursesStore.loadCourses(), coursesStore.loadRecommendations()])
})
```

The panel template replaces the hardcoded `AgriSkillsNav` with:

```vue
<slot name="nav" />
```

Create `EcommerceTrainingNav.vue` in this task so every later 004 view can import it before routes are registered:

```ts
const links = [
  { to: '/student/ecommerce-training', label: '模块首页', icon: Home },
  { to: '/student/ecommerce-training/live-script', label: '直播话术', icon: Radio },
  { to: '/student/ecommerce-training/simulation', label: '模拟训练', icon: Mic2 },
  { to: '/student/ecommerce-training/copy-training', label: '文案训练', icon: PenLine },
  { to: '/student/ecommerce-training/store-guidance', label: '店铺装修', icon: Store },
  { to: '/student/ecommerce-training/customer-service', label: '客服模拟', icon: MessagesSquare },
  { to: '/student/ecommerce-training/courses', label: '电商课程', icon: BookOpen }
] as const
```

Modify `AgriCoursesView.vue` to a wrapper:

```vue
<template>
  <CourseLearningPanel
    direction="agriculture"
    module-code="03"
    title="农业课程"
    description="浏览已上架农业课程，从断点继续学习，并在达到完成进度后参加课后测验。"
    api-prefix="/api/agri-skills"
  >
    <template #nav>
      <AgriSkillsNav />
    </template>
  </CourseLearningPanel>
</template>
```

The panel keeps `暂无课程`, `暂无推荐`, 80% quiz gating, progress retry, quiz results and responsive behavior exactly as existing 03 tests expect.

- [ ] **Step 5: Run existing 03 frontend tests and the new store test**

Run:

```powershell
cd frontend
npx vitest run src/stores/courseLearning.test.ts src/stores/agriCourses.test.ts src/views/AgriCoursesView.test.ts
npx tsc -b --noEmit
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add frontend/src/api/types.ts frontend/src/stores/courseLearning.ts frontend/src/stores/ecommerceTraining.ts frontend/src/stores/agriCourses.ts frontend/src/components/EcommerceTrainingNav.vue frontend/src/components/CourseLearningPanel.vue frontend/src/views/AgriCoursesView.vue frontend/src/stores/courseLearning.test.ts
git commit -m "refactor(courses): 参数化共享课程前端"
```

---

### Task 11: Live Script Frontend

**Files:**
- Create: `frontend/src/stores/ecommerceLiveScript.ts`
- Create: `frontend/src/views/EcommerceLiveScriptView.vue`
- Create: `frontend/src/stores/ecommerceLiveScript.test.ts`
- Create: `frontend/src/views/EcommerceLiveScriptView.test.ts`

**Interfaces:**
- Consumes: `apiFetch`, `AppHeader`, `EcommerceTrainingNav`, 004 DTOs.
- Produces: `useEcommerceLiveScriptStore()` with `generate(payload)`, `loadHistory()`, `openVersion(id)`, `resetForm()`.

- [ ] **Step 1: Write the failing store test**

Create `frontend/src/stores/ecommerceLiveScript.test.ts`:

```ts
it('keeps input and shows the exact AI failure message', async () => {
  const store = useEcommerceLiveScriptStore()
  store.form = {
    product_name: '荔枝干',
    selling_points: '香甜、耐储存',
    price_text: '39.9 元',
    style: 'enthusiastic'
  }
  apiFetch.mockRejectedValueOnce(new ApiError('AI 服务暂时不可用', 503))
  const result = await store.generate()
  expect(result).toBe(false)
  expect(store.form.product_name).toBe('荔枝干')
  expect(store.error).toBe('AI 服务暂时不可用')
  expect(store.current).toBeNull()
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend; npx vitest run src/stores/ecommerceLiveScript.test.ts`

Expected: FAIL because the store does not exist.

- [ ] **Step 3: Implement the store and view**

Store request:

```ts
const response = await apiFetch<{ success: true; version: LiveScriptVersion }>(
  '/api/ecommerce-training/live-scripts',
  { method: 'POST', body: JSON.stringify(this.form) }
)
this.current = response.version
this.history = [response.version, ...this.history].sort(
  (left, right) => right.id - left.id
)
```

The view renders:

- required product name and selling points fields;
- exactly three style radio buttons: 热情、专业、幽默;
- generate and regenerate buttons;
- four ordered output sections;
- module-local history list;
- an `aria-live` alert containing `store.error`.

No audio or streaming UI is added.

- [ ] **Step 4: Run store/view tests**

Run: `cd frontend; npx vitest run src/stores/ecommerceLiveScript.test.ts src/views/EcommerceLiveScriptView.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/stores/ecommerceLiveScript.ts frontend/src/views/EcommerceLiveScriptView.vue frontend/src/stores/ecommerceLiveScript.test.ts frontend/src/views/EcommerceLiveScriptView.test.ts
git commit -m "feat(ecommerce): 实现直播话术前端"
```

---

### Task 12: Simulation Frontend

**Files:**
- Create: `frontend/src/stores/ecommerceSimulation.ts`
- Create: `frontend/src/views/EcommerceSimulationView.vue`
- Create: `frontend/src/stores/ecommerceSimulation.test.ts`
- Create: `frontend/src/views/EcommerceSimulationView.test.ts`

**Interfaces:**
- Consumes: five scenario definitions, simulation endpoints and score DTOs.
- Produces: `useEcommerceSimulationStore()` with `loadScenes()`, `start(sceneKey)`, `saveSegment(segmentKey, text)`, `score()`, `loadHistory()`, `openTraining(id)`.

- [ ] **Step 1: Write the failing tests**

Test the one-scene/multiple-segment flow and score rendering:

```ts
await store.loadScenes()
await store.start('opening')
await store.saveSegment('greeting', '欢迎来到直播间')
await store.saveSegment('hook', '今天带来广东荔枝干')
await store.saveSegment('audience_call', '想要的扣一')
apiFetch.mockResolvedValueOnce({
  success: true,
  training: {
    id: 1,
    scene_key: 'opening',
    status: 'completed',
    scores: { pacing: 80, emotion: 70, interaction: 90, selling_point: 60 },
    total_score: 75
  }
})
await store.score()
expect(store.current?.total_score).toBe(75)
expect(wrapper.text()).toContain('75')
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend; npx vitest run src/stores/ecommerceSimulation.test.ts src/views/EcommerceSimulationView.test.ts`

Expected: FAIL because the store/view do not exist.

- [ ] **Step 3: Implement exact segment and score behavior**

The view renders one selected scene at a time, all returned segments in order, each textarea, save buttons and a score button disabled until all segments are saved. It renders the four dimension rows and total:

```ts
const dimensionLabels = {
  pacing: '语速节奏',
  emotion: '情绪感染力',
  interaction: '互动引导',
  selling_point: '卖点突出'
} as const
```

On AI failure, keep the current training and segment drafts, keep the score button available for retry, and show exactly `AI 服务暂时不可用`.

- [ ] **Step 4: Run tests**

Run: `cd frontend; npx vitest run src/stores/ecommerceSimulation.test.ts src/views/EcommerceSimulationView.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/stores/ecommerceSimulation.ts frontend/src/views/EcommerceSimulationView.vue frontend/src/stores/ecommerceSimulation.test.ts frontend/src/views/EcommerceSimulationView.test.ts
git commit -m "feat(ecommerce): 实现模拟训练前端"
```

---

### Task 13: Copy Prompt Training Frontend

**Files:**
- Create: `frontend/src/stores/ecommerceCopyTraining.ts`
- Create: `frontend/src/views/EcommerceCopyTrainingView.vue`
- Create: `frontend/src/stores/ecommerceCopyTraining.test.ts`
- Create: `frontend/src/views/EcommerceCopyTrainingView.test.ts`

**Interfaces:**
- Consumes: copy catalog and four-step endpoints.
- Produces: `useEcommerceCopyTrainingStore()` with `loadCatalog()`, `create(productType, scene)`, `submitCritique(text)`, `generateCopy(prompt)`, `generateOptimization()`, history getters.

- [ ] **Step 1: Write failing state-machine tests**

```ts
await store.create('food', 'social_commerce')
expect(store.current?.status).toBe('case_ready')
await store.submitCritique('缺少规格和行动指令')
expect(store.current?.consistency.score).toBe(67)
await store.generateCopy('补充规格、价格和行动指令')
expect(store.current?.revised_copy).toContain('250g')
await store.generateOptimization()
expect(store.current?.status).toBe('completed')
expect(store.current?.optimization.evidence).toContain('可验证')
```

Add a test that AI failure at each step leaves all earlier fields unchanged and exposes exact message.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend; npx vitest run src/stores/ecommerceCopyTraining.test.ts src/views/EcommerceCopyTrainingView.test.ts`

Expected: FAIL because the store/view do not exist.

- [ ] **Step 3: Implement the five visible stages**

The view must render:

1. product/scene selection;
2. generated case;
3. learner critique and its submit button;
4. side-by-side learner/reference critique with consistency score and reason;
5. optimized prompt, old/new copy, differences, optimization score and evidence.

There is no standalone “生成成品文案” button. The only revised-copy request is inside stage 5 after an optimized prompt exists.

All API failures set `error = 'AI 服务暂时不可用'` and do not advance `status`.

- [ ] **Step 4: Run tests**

Run: `cd frontend; npx vitest run src/stores/ecommerceCopyTraining.test.ts src/views/EcommerceCopyTrainingView.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/stores/ecommerceCopyTraining.ts frontend/src/views/EcommerceCopyTrainingView.vue frontend/src/stores/ecommerceCopyTraining.test.ts frontend/src/views/EcommerceCopyTrainingView.test.ts
git commit -m "feat(ecommerce): 实现文案训练前端"
```

---

### Task 14: Store Guidance Frontend

**Files:**
- Create: `frontend/src/stores/ecommerceStoreGuidance.ts`
- Create: `frontend/src/views/EcommerceStoreGuidanceView.vue`
- Create: `frontend/src/stores/ecommerceStoreGuidance.test.ts`
- Create: `frontend/src/views/EcommerceStoreGuidanceView.test.ts`

**Interfaces:**
- Consumes: store plan endpoints.
- Produces: `useEcommerceStoreGuidanceStore()` with `generate()`, `loadHistory()`, `openPlan(id)`.

- [ ] **Step 1: Write the failing tests**

```ts
store.form = {
  store_type: '农产品旗舰店',
  platform: 'taobao',
  style_preference: '温暖可靠'
}
apiFetch.mockResolvedValueOnce({ success: true, plan: planFixture })
expect(await store.generate()).toBe(true)
expect(store.current?.plan.home_layout.length).toBeGreaterThan(0)
```

Add invalid platform validation and AI failure/no-row behavior at the store/view boundary.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend; npx vitest run src/stores/ecommerceStoreGuidance.test.ts src/views/EcommerceStoreGuidanceView.test.ts`

Expected: FAIL because the store/view do not exist.

- [ ] **Step 3: Implement form and four-part rendering**

Use a select with exactly `taobao`, `pinduoduo`, `douyin_shop`; free-text store type and style preference. Always render four labeled sections:

```ts
const planLabels = {
  home_layout: '首页布局',
  color_scheme: '色彩方案',
  detail_structure: '详情页结构',
  navigation: '导航分类'
} as const
```

The history list displays generation time, platform and input summary.

- [ ] **Step 4: Run tests**

Run: `cd frontend; npx vitest run src/stores/ecommerceStoreGuidance.test.ts src/views/EcommerceStoreGuidanceView.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/stores/ecommerceStoreGuidance.ts frontend/src/views/EcommerceStoreGuidanceView.vue frontend/src/stores/ecommerceStoreGuidance.test.ts frontend/src/views/EcommerceStoreGuidanceView.test.ts
git commit -m "feat(ecommerce): 实现店铺装修前端"
```

---

### Task 15: Customer Service Frontend

**Files:**
- Create: `frontend/src/stores/ecommerceCustomerService.ts`
- Create: `frontend/src/views/EcommerceCustomerServiceView.vue`
- Create: `frontend/src/stores/ecommerceCustomerService.test.ts`
- Create: `frontend/src/views/EcommerceCustomerServiceView.test.ts`

**Interfaces:**
- Consumes: customer-service scenario/session endpoints.
- Produces: `useEcommerceCustomerServiceStore()` with `loadScenarios()`, `start(scenarioKey)`, `submitReply(text)`, `nextMessage()`, `confirmEnd()`, history getters.

- [ ] **Step 1: Write the failing multi-turn tests**

```ts
await store.start('after_sales')
expect(store.current?.turns[0].customer_message).toContain('退')
await store.submitReply('请提供订单号')
expect(store.current?.turns[0].analysis.problem).toBeTruthy()
expect(store.current?.turns[0].analysis.goal_status).toBe('not_reached')
await store.nextMessage()
expect(store.current?.turns[1].customer_message).toBeTruthy()
await store.submitReply('拆封后可按流程申请')
expect(store.current?.end_suggested).toBe(true)
await store.confirmEnd()
expect(store.current?.status).toBe('completed')
```

Add tests for AI failure preserving the transcript and no automatic end on goal reached.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend; npx vitest run src/stores/ecommerceCustomerService.test.ts src/views/EcommerceCustomerServiceView.test.ts`

Expected: FAIL because the store/view do not exist.

- [ ] **Step 3: Implement the turn-based UI**

The view renders:

- five scenario cards with labels and target criteria;
- ordered customer/student turns;
- per-turn problem, evidence, suggestion and criterion statuses;
- a reply textarea;
- a “继续客户消息” action only when analysis succeeded and goal not reached;
- an “结束训练” action only after `end_suggested` is true;
- no turn counter or forced end.

No SSE or token-streaming text area is created.

- [ ] **Step 4: Run tests**

Run: `cd frontend; npx vitest run src/stores/ecommerceCustomerService.test.ts src/views/EcommerceCustomerServiceView.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/stores/ecommerceCustomerService.ts frontend/src/views/EcommerceCustomerServiceView.vue frontend/src/stores/ecommerceCustomerService.test.ts frontend/src/views/EcommerceCustomerServiceView.test.ts
git commit -m "feat(ecommerce): 实现客服模拟前端"
```

---

### Task 16: E-commerce Courses Frontend

**Files:**
- Create: `frontend/src/views/EcommerceCoursesView.vue`
- Create: `frontend/src/views/EcommerceCoursesView.test.ts`

**Interfaces:**
- Consumes: `CourseLearningPanel`, `useCourseLearningStore`.
- Produces: `/student/ecommerce-training/courses` page using `direction="ecommerce"` and `api-prefix="/api/ecommerce-training"`.

- [ ] **Step 1: Write the failing wrapper test**

Create `frontend/src/views/EcommerceCoursesView.test.ts`:

```ts
it('uses the shared course panel for ecommerce only', () => {
  const panel = wrapper.getComponent(CourseLearningPanel)
  expect(panel.props('direction')).toBe('ecommerce')
  expect(panel.props('moduleCode')).toBe('04')
  expect(panel.props('apiPrefix')).toBe('/api/ecommerce-training')
  expect(panel.props('title')).toBe('电商课程')
})
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd frontend; npx vitest run src/views/EcommerceCoursesView.test.ts`

Expected: FAIL because the view does not exist.

- [ ] **Step 3: Implement the wrapper**

Use:

```vue
<script setup lang="ts">
import CourseLearningPanel from '@/components/CourseLearningPanel.vue'
import EcommerceTrainingNav from '@/components/EcommerceTrainingNav.vue'
</script>

<template>
  <CourseLearningPanel
    direction="ecommerce"
    module-code="04"
    title="电商课程"
    description="浏览电商方向已上架课程，按兴趣和学习行为获取推荐并完成 AI 课后测验。"
    api-prefix="/api/ecommerce-training"
  >
    <template #nav>
      <EcommerceTrainingNav />
    </template>
  </CourseLearningPanel>
</template>
```

Do not create a second ecommerce course store or copy quiz/progress markup.

- [ ] **Step 4: Run agriculture and ecommerce course tests**

Run: `cd frontend; npx vitest run src/views/EcommerceCoursesView.test.ts src/views/AgriCoursesView.test.ts src/stores/courseLearning.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/views/EcommerceCoursesView.vue frontend/src/views/EcommerceCoursesView.test.ts
git commit -m "feat(ecommerce): 接入共享电商课程页"
```

---

### Task 17: Module Shell, Routes, Portal, and Cross-Service Acceptance

**Files:**
- Create: `frontend/src/views/EcommerceTrainingHomeView.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/views/StudentPortalView.vue`
- Modify: `frontend/src/data/portal-guides.ts`
- Create: `frontend/src/router/ecommerceTrainingRoutes.test.ts`
- Create: `frontend/src/views/EcommerceTrainingResponsive.test.ts`

**Interfaces:**
- Produces routes: `/student/ecommerce-training`, `/live-script`, `/simulation`, `/copy-training`, `/store-guidance`, `/customer-service`, `/courses`.
- Consumes: `EcommerceTrainingNav` created in Task 10.
- Produces `EcommerceTrainingHomeView` with seven cards.
- Student portal and onboarding gain the `student-ecommerce-training` entry.

**Shared File Changes:** See “共享文件改动”; route and portal registration are the only ways to make the module reachable.

- [ ] **Step 1: Write failing route/portal/session tests**

Create `frontend/src/router/ecommerceTrainingRoutes.test.ts`:

```ts
const paths = [
  '/student/ecommerce-training',
  '/student/ecommerce-training/live-script',
  '/student/ecommerce-training/simulation',
  '/student/ecommerce-training/copy-training',
  '/student/ecommerce-training/store-guidance',
  '/student/ecommerce-training/customer-service',
  '/student/ecommerce-training/courses'
]

for (const path of paths) {
  expect(router.resolve(path).matched[0].meta).toMatchObject({
    requiresAuth: true,
    roles: ['student']
  })
}
```

Add a portal guide test asserting `student-ecommerce-training` has href `/student/ecommerce-training`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd frontend; npx vitest run src/router/ecommerceTrainingRoutes.test.ts src/views/PortalShell.test.ts`

Expected: FAIL because routes and portal entry are absent.

- [ ] **Step 3: Implement the shell and routes**

Add each view route with `meta: { requiresAuth: true, roles: ['student'] }`. Add the student portal entry and first-use guide step. No auth store modification is needed.

- [ ] **Step 4: Add cross-service and responsive tests**

Create `EcommerceTrainingResponsive.test.ts` that mounts all six AI-training views and `EcommerceCoursesView` at `1280`, `768` and `375` CSS widths with long Chinese content and asserts:

```ts
expect(wrapper.find('[data-test="horizontal-overflow"]').exists()).toBe(false)
expect(wrapper.text()).not.toContain('AI service unavailable')
```

Add one session-expiry test per data-loading view by mocking `ApiError(..., 401, {}, '/login')`; assert the page calls the existing session-expired handler and does not show a raw provider error.

- [ ] **Step 5: Run all frontend gates**

Run:

```powershell
cd frontend
npm test
npx tsc -b --noEmit
npm run build
```

Expected: all Vitest suites pass, type-check passes and production build succeeds.

- [ ] **Step 6: Run all backend gates**

Run: `uv run --directory backend python -m unittest discover -s tests -v`

Expected: all backend tests pass.

- [ ] **Step 7: Run browser acceptance**

Start:

```powershell
uv run --directory backend python run.py
cd frontend
npm run dev
```

Use `agent-browser` to verify:

1. All seven 004 routes resolve to the student shell.
2. Live script regeneration preserves every prior version and marks the latest current.
3. Simulation uses one scene with ordered segments and exact 0–100 four-dimension/equal-weight total.
4. Copy training requires all five stages and exposes both 0–100 scores with reasons/evidence.
5. Store guidance renders exactly four plan sections.
6. Customer service performs multi-turn AI goal checking with confirmation-only ending and no forced cap.
7. Course page shows only published ecommerce fixtures, excludes completed courses from recommendations, enables quiz at 80%, and uses no agri fallback.
8. All 11 AI failure states show exactly `AI 服务暂时不可用`.
9. Desktop and 375px screenshots have no overlap, clipped text or horizontal overflow.

- [ ] **Step 8: Commit**

```powershell
git add frontend/src/views/EcommerceTrainingHomeView.vue frontend/src/router/index.ts frontend/src/views/StudentPortalView.vue frontend/src/data/portal-guides.ts frontend/src/router/ecommerceTrainingRoutes.test.ts frontend/src/views/EcommerceTrainingResponsive.test.ts
git commit -m "test(ecommerce): 完成模块集成验收"
```

---

## Plan Self-Review

### Spec Coverage

| Spec area | Implementation tasks |
| --- | --- |
| FR-001..009 session, tags, provider, archive boundary and ownership | Tasks 1, 2, 8, 9, 10, 17 |
| FR-010..018 live-script input, structure, regeneration, history and no fallback | Tasks 3, 11 |
| FR-019..028 simulation scenes, ordered segments, four-dimension equal-weight scoring and no fallback | Tasks 2, 4, 12 |
| FR-029..039 copy case defects, consistency score, prompt optimization score and no standalone generator | Tasks 2, 5, 13 |
| FR-040..047 decoration inputs, four sections, history and no real platform API | Tasks 2, 6, 14 |
| FR-048..058 customer goals, turn analysis, confirmation-only ending, summary and no fallback | Tasks 2, 7, 15 |
| FR-059..082 ecommerce course source, recommendation, progress, quiz and fixed 08 placeholder | Tasks 1, 2, 8, 9, 10, 16, 17 |
| FR-083..088 all eleven no-fallback AI call points | Tasks 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17 |
| FR-089..091 non-streaming calls, turn boundaries and module-local history | Tasks 3, 7, 8, 11, 12, 13, 14, 15, 16 |
| SC-001..014 measurable outcomes | Tasks 2–17 |

### Interface Consistency

- `CourseProvider.list_published_courses(student_id, direction)` is the direction-aware contract; `list_published_agriculture_courses(student_id)` remains a Task 1 compatibility wrapper.
- `is_eligible_course()` is the single list/recommendation/progress filter for direction, stable ID, text fields and positive duration.
- All course progress uses `furthest_position_seconds`, `resume_position_seconds`, `progress_percent`, `watched_seconds` and `completed_at`.
- All 004 routes use `/api/ecommerce-training`; no second provider registry is introduced.
- AI call-point names match the matrix and `AI_FIELD_ALLOWLISTS`.
- Simulation score keys are consistently `pacing`, `emotion`, `interaction`, `selling_point`.
- Copy-training scores are consistently integers 0–100 and are stored with reason or evidence.
- Customer-service goals are criterion arrays; per-turn analysis stores criterion statuses and an overall `reached` / `not_reached` result.
- `CourseLearningPanel` is the only ecommerce/agriculture course view implementation; `AgriCoursesView` and `EcommerceCoursesView` are direction wrappers.
- `CourseLearningPanel` takes navigation through a slot, so 03 keeps `AgriSkillsNav` and 04 injects `EcommerceTrainingNav`.
- `list_ecommerce_learning_outcomes()` projects live scripts, simulations, course quizzes and course completion without writing a skill archive.
- `init_db()` migrates `duration_seconds` before seeding ecommerce fixtures.

### Incomplete-Work Scan

- No `TODO`, `TBD`, “implement later”, “fill in details” or “similar to Task N” instruction remains.
- Every task contains concrete Files and Interfaces blocks.
- Every code-changing task includes a failing test, exact failure command, implementation contract, passing command and commit boundary.
- Every shared file change is listed once in “共享文件改动” and assigned to a numbered task.
- The plan contains 17 tasks and 11 AI call points.
