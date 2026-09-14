# 粤乡智匠 Constitution

## Core Principles

### I. 技术栈与重写边界

- v2 是全面重写：后端 MUST 位于 `backend/`，使用 Flask + SQLite，依赖由 uv 管理。
- `backend/pyproject.toml` 与 `backend/uv.lock` MUST 作为后端依赖的唯一权威；不得让生成的导出文件接管依赖状态。
- 前端 MUST 位于 `frontend/`，使用 Vue 3 + Vite + Pinia。
- 旧系统（根目录 `app.py`、`database.py` 和旧 HTML 页面）MUST NOT 被参考、导入或迁移；行为证据 MUST 来自需求文档或现行 spec。

### II. 需求基准与活规格

- 功能范围 MUST 以 `docs/粤乡智匠——需求输入.md`（v3）为唯一总基准。
- 每个子系统 MUST 使用 `specs/<NNN>/spec.md` 作为唯一需求契约。
- spec 是 living specification：需求变更 MUST 先修改对应 spec，再同步实现和测试。
- 实现 MUST NOT 与需求文档或对应 spec 的声明、边界、验收标准相冲突。

### III. AI 外部依赖边界

- AI 大模型服务是外部云依赖，平台 MUST NOT 将核心手动功能建立在 AI 可用性之上。
- 仅农业问答 MUST 允许降级到本地病虫害知识库。
- 其余 AI 功能不可用时 MUST 返回统一提示“AI 服务暂时不可用”。
- AI 功能不可用 MUST NOT 阻塞对应功能的手动操作路径。

### IV. TDD 与模块收敛

- TDD 的红、绿、重构循环 MUST 作为功能与缺陷修复的默认开发方式；行为变更 MUST 先有失败测试。
- 每个任务 MUST 完成双维审查：规格合规审查和代码质量审查。
- 每个模块合并后 MUST 运行 `$speckit-converge`，按项目约定的弱化版本对照对应 `spec.md`。
- 收敛发现缺口时 MUST 回填任务或记录后续行动，不得静默跳过。

### V. Git 分支治理

- feature 分支 MUST 位于 `v2/lixKRT/` 下。
- spec-kit 生成 `NNN-<slug>` 后 MUST 立即将分支改名为 `v2/lixKRT/NNN-<slug>`。
- 分支名 MUST 使用 ASCII kebab-case。
- 合并、推送、远端状态变更和发布 MUST 按全局 git-rules 获得对应授权。

### VI. 安全边界

- `.env`、API 密钥、密码、令牌和私有凭证 MUST NOT 进入版本库。
- 非演示环境的 `SECRET_KEY` 与 `AI_API_KEY` MUST 更换为独立受控值。
- 密码找回 MUST 采用超管重置为初始密码模式；MUST NOT 提供自助找回流程。
- 安全边界变更 MUST 先更新 spec 和测试，再进入实现。

### VII. 命名与提交规范

- 路由路径 MUST 使用 kebab-case。
- Python 函数 MUST 使用 snake_case。
- 前端函数与变量 MUST 使用 camelCase。
- Git 提交信息 MUST 使用中文短句，并聚焦单个变更意图。

## Repository Authority

- 本 Constitution 约束所有 spec、计划、实现、审查和验证活动。
- `docs/粤乡智匠——需求输入.md`（v3）是产品功能的总需求基准。
- `specs/<NNN>/spec.md` 是对应子系统的唯一需求契约；其他文档只能提供解释，不能替代或修改契约。
- 动态执行状态属于 `.agents/memories/`；该目录 MUST NOT 用来建立第二份需求契约。

## Quality and Review Gates

- 功能实现 MUST 先建立可表达需求行为的失败测试，再实现到测试通过。
- 重构 MUST 保持既有测试绿色，并不得改变未修改的需求契约。
- 任务完成前 MUST 分别检查规格合规与代码质量；任一维度未通过 MUST 返工。
- 模块合并后 MUST 执行收敛检查并对照 spec；发现缺口 MUST 生成可追踪任务。

## Governance

- 本 Constitution 优先于项目内其他工作流程与约定；冲突时 MUST 以本文件为准。
- 修订 MUST 更新本文件、顶部同步影响报告和语义化版本号。
- 新增或实质性扩展原则使用 MINOR 版本；删除、重定义或造成不兼容治理变化使用 MAJOR 版本；澄清和措辞修正使用 PATCH 版本。
- 所有实现审查 MUST 验证技术边界、需求基准、AI 降级、质量门禁、分支、安全与命名原则。
- 无法证明符合本 Constitution 的变更 MUST 返工或在进入实现前获得明确的治理修订。

**Version**: 1.0.0 | **Ratified**: 2026-09-14 | **Last Amended**: 2026-09-14
