# AGENTS.md

> 遵循 Matt Pocock《A Complete Guide To AGENTS.md》与 `/retro` 的定位：本文件会被推进每个 agent 的上下文窗口，应极其克制，通常只放导航指针。目标 ≤80 行。

> 适用 mattpocock-skills v1.3.1。

## Project
基于 AI 实训的农村本土人才赋能平台：Flask 单体后端 + 多页面前端，服务学员、教师、企业、政府与管理员五类角色。后端已按领域拆分，改代码前先读下面的「后端结构」。

团队协作：`backend/` 与数据库属于受保护范围；前端小功能可在当前分支提交，涉及后端接口或数据库结构时先读 `docs/team/README.md`。现有 ADR 只读，所有任务遵循，任何成员不得修改、重命名、移动或删除；实现与裁决冲突时停止并上报项目负责人。详见 `docs/team/adr-constitution.md`。

## Commands

只写非标准命令，标准命令 agent 自己找得到。

- 安装依赖：`pip install -r requirements.txt`
- 全仓单测（需应用基线数据库，不属于 crawler 验收）：`python -m unittest discover -s . -p "test_*.py" -t .`
- crawler 验收：`python -m unittest discover -s crawler/tests -p "test_*.py" -t .`
- 端到端：`cd e2e; npx playwright test`
- 架构机械检查：`python tools/check_architecture.py`
- Python 静态检查：`python tools/check_python.py`
- 启动：`python backend/run.py`（自托管单机部署：Flask 裸跑 + 多线程，静态文件由同一进程伺服）
- 用一份可弃数据库跑 e2e：由 `e2e/serve.py` 自动处理，`YUEXIANG_DB` 指向临时库

## 后端结构

后端代码全部在 `backend/` 下，前端文件与 `data/`、`uploads/`、`.env`、`requirements.txt` 留在仓库根。一个领域一个蓝图，共享层不感知任何具体领域。领域之间的数据访问按权限判定，不再以「不得 import」一禁了之（ADR 0002 修订了 ADR 0001 的这条）。改后端前先读 `docs/adr/0001-backend-domain-split.md`（边界与裁决）与 `docs/adr/0002-content-into-database.md`（内容落库），再看 `GLOSSARY.md` 的「后端结构」一节（术语）。

- `backend/app.py`：入口。创建应用 + 健康检查探针 + 启动。业务路由不在这里。
- `backend/core/`：应用工厂、会话与角色鉴权、限流、统一错误响应。
- `backend/ai/`：上游模型调用的唯一出口。
- `backend/shared/`：零领域状态的纯函数与纯配置（节气、朗读评分、文案评分、作物白名单、实训状态标签等）。
- `backend/db_domains/`：按领域切分的数据访问层，一个领域一个模块。
- `backend/db_connection.py` / `db_schema.py` / `db_seed_accounts.py`：数据层基础设施与演示账号播种。
- `backend/db_init.py`：启动编排（建表、补列、清废弃表、空库灌演示账号）。内容不在这里播种。
- `backend/domains/`：领域路由蓝图，一个领域一个目录。
- `backend/core/permissions.py`：全站唯一的「角色到能力」映射，路由鉴权走它，不写角色名比较。
- `backend/repo_paths.py`：路径唯一基准，`REPO_ROOT` 指向**仓库根**（不是 backend/），因为 `data/`、`uploads/`、`.env` 都在仓库根。

数据层转发层 `database.py` 已按 ADR 0002 删除，调用方一律 `from db_domains import <域>`。

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
9. **Git commit 使用英文类型前缀与中文描述。** 标题写成 `feat/fix/test/docs/refactor/chore(范围): 中文描述`；正文先写本次改动概要，再写验证结果，复杂改动补充原因与影响。

## 技能流程

项目技能在 `.agents/skills/`，入口见 `docs/team/project-skills.md`。首次进入工程流程前跑一次 `/setup-matt-pocock-skills`；不知道用哪个技能敲 `/ask-matt`；想改进这套环境跑 `/retro`。技能之间靠显式点名 Skill 工具，不丢裸 `/name`。

tracker 与标签词汇见 `docs/agents/`；grilling 的提问纪律与阶段边界处理见 mattpocock-skills 自带的 `ask-matt` / `grilling` 说明，本文件不复述。

## 位置索引

| 找什么 | 去哪 |
| --- | --- |
| 团队开发规范 | `docs/team/README.md` |
| 领域词汇 | `GLOSSARY.md`（多上下文先读 `GLOSSARY-MAP.md`） |
| 开发宪法（ADR，只读） | `docs/adr/` |
| tracker / 标签 / 领域文档配置 | `docs/agents/` |
| 项目技能 | `.agents/skills/`（入口：`docs/team/project-skills.md`） |
| 编码规范（审查期读取） | `CODING_STANDARDS.md` |
| 被拒绝的需求 | `.out-of-scope/` |
| 本地 tracker 的 spec 与票据 | `.scratch/<feature>/` |
| 架构巡检报告 | `<OS-TMP>/architecture-review-<ts>.html`（不在仓库） |
| 原型 | `prototype/<name>` 分支（不在工作树） |
