# AGENTS.md

> 遵循 Matt Pocock《A Complete Guide To AGENTS.md》与 `/retro` 的定位：本文件会被推进每个 agent 的上下文窗口，应极其克制，通常只放导航指针。目标 ≤80 行。

> 适用 mattpocock-skills v1.3.1。

## Project

基于 AI 实训的农村本土人才赋能平台：Flask 单体后端 + 多页面前端，服务学员、教师、企业、政府与管理员五类角色。后端已按领域拆分，改代码前先读下面的「后端结构」。

## Commands

只写非标准命令，标准命令 agent 自己找得到。

- 安装依赖：`pip install -r requirements.txt`
- 单测：`python -m unittest discover -s . -p "test_*.py" -t .`
- 端到端：`cd e2e; npx playwright test`
- 架构机械检查：`python tools/check_architecture.py`
- Python 静态检查：`python tools/check_python.py`
- 启动：`python backend/run.py`
- 用一份可弃数据库跑 e2e：由 `e2e/serve.py` 自动处理，`YUEXIANG_DB` 指向临时库

## 后端结构

后端代码全部在 `backend/` 下，前端文件与 `data/`、`uploads/`、`.env`、`requirements.txt` 留在仓库根。一个领域一个蓝图，领域之间不互相 import，共享层不感知任何具体领域。改后端前先读 `docs/adr/0001-backend-domain-split.md`（边界与裁决），再看 `GLOSSARY.md` 的「后端结构」一节（术语）。

- `backend/app.py`：入口。创建应用 + 健康检查探针 + 启动。业务路由不在这里。
- `backend/core/`：应用工厂、会话与角色鉴权、限流、统一错误响应。
- `backend/ai/`：上游模型调用的唯一出口。
- `backend/shared/`：零领域状态的纯函数与纯配置（节气、朗读评分、文案评分、作物白名单、实训状态标签等）。
- `backend/db_domains/`：按领域切分的数据访问层，一个领域一个模块。
- `backend/db_connection.py` / `db_schema.py` / `db_seed_*.py`：数据层基础设施与播种。
- `backend/domain_data/`：按领域归置的内容数据模块（不落库、import 即用）。
- `backend/domains/`：领域路由蓝图，一个领域一个目录。
- `backend/database.py`：对外的数据层契约层，`import database` + `database.xxx()` 的调用面保持不变。
- `backend/repo_paths.py`：路径唯一基准，`REPO_ROOT` 指向**仓库根**（不是 backend/），因为 `data/`、`uploads/`、`.env` 都在仓库根。

新增可审核内容类型、新增领域、或需要跨领域取数时，先读 ADR 0001 的裁决，不要凭空发明放法。

## Rules

1. **本文件保持最小。** 每条规则写前先问：它对**每一个**任务都成立吗？否，就推到 `docs/` 或技能里。一行加进来，每次请求都要付一遍。
2. **机械性违规做成检查，不要写成规则。** 固定句法、禁用 API、导入形状、文件位置，做成 lint 规则、pre-commit 钩子或 CI job。`CODING_STANDARDS.md` 只留真正的判断题。
3. **描述能力，别钉死路径。** 文件会改名搬家，写死 `src/auth/handlers.ts` 会在文件搬走后让 agent 自信地找错地方。
4. **正面表述。** 写目标行为，别写禁令；禁令会把被禁的行为拉进上下文。
5. **单一真相源。** 每个事实一个指针，不做副本。领域词汇只在 `GLOSSARY.md`，历史决策只在 `docs/adr/`。
6. **不用 em-dash。** 用逗号、冒号、句号、括号或连词。
7. **`GLOSSARY.md` 与 `docs/adr/` 不存在时静默继续。** 不提示缺失，不建议预先创建，`/domain-modeling` 会在术语或决策真正落地时惰性创建。
8. **判断某技能做什么，先读它的 `SKILL.md`。** `/ask-matt` 的摘要只作定位用，不能作为行动依据。

## 技能流程

首次进入工程流程前跑一次 `/setup-matt-pocock-skills`；不知道用哪个技能敲 `/ask-matt`；想改进这套环境跑 `/retro`。技能之间靠显式点名 Skill 工具，不丢裸 `/name`。

tracker 与标签词汇见 `docs/agents/`；grilling 的提问纪律与阶段边界处理见 mattpocock-skills 自带的 `ask-matt` / `grilling` 说明，本文件不复述。

## 位置索引

| 找什么 | 去哪 |
| --- | --- |
| 领域词汇 | `GLOSSARY.md`（多上下文先读 `GLOSSARY-MAP.md`） |
| 历史决策 | `docs/adr/` |
| tracker / 标签 / 领域文档配置 | `docs/agents/` |
| 编码规范（审查期读取） | `CODING_STANDARDS.md` |
| 被拒绝的需求 | `.out-of-scope/` |
| 本地 tracker 的 spec 与票据 | `.scratch/<feature>/` |
| 架构巡检报告 | `<OS-TMP>/architecture-review-<ts>.html`（不在仓库） |
| 原型 | `prototype/<name>` 分支（不在工作树） |

<!--
拆坏了的 AGENTS.md 怎么修？如果您开始担心仓库中 AGENTS.md 文件的重组，需按 progressive disclosure：

I want you to refactor my AGENTS.md file to follow progressive disclosure principles.

Follow these steps:

1. **Find contradictions**: Identify any instructions that conflict with each other, and for each conflict ask me which version to keep.
2. **Identify the essentials**: Extract only what belongs in AGENTS.md:
   - One-sentence project description
   - Package manager (if not npm)
   - Non-standard build/typecheck commands
   - Anything truly relevant to every task
3. **Group the rest**: Arrange the remaining instructions into logical categories (TypeScript conventions, testing patterns, API design, Git workflow), each in its own file.
4. **Create the file structure**: a minimal AGENTS.md with links; one file per group; a suggested docs/ tree.
5. **Flag for deletion**: instructions that are redundant, too vague, or obvious to the agent.
-->
