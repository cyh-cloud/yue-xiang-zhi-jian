# 贡献指南

本文规定代码结构、编码规范、提交要求与评审门槛。目标是让「改对了没有」可以被机械检查判定，而不是依赖 review 时的记忆力。

---

## 1. 开发流程

| 环节 | 做法 |
| --- | --- |
| 分支 | `main` 保持可运行；功能开发在 `feature/<简述>` 或 `fix/<简述>` 上进行 |
| 同步 | 开工前从当前开发分支拉取最新代码，避免长周期分叉 |
| 提交 | 小而完整：一次提交只做一件事，可独立运行、可独立回滚 |
| 合并 | 合并前跑完第 5 节的全部检查；合并提交保留，不压缩历史 |
| 发布 | 合并到 `main` 后打标签，标签名使用 `v<主>.<次>.<修订>` |

前端重构期的活动分支为 `frontend/vue-rebuild`，历史决策见 [`docs/adr/0003-frontend-vue-spa.md`](docs/adr/0003-frontend-vue-spa.md)。

## 2. 提交信息

采用 Conventional Commits，允许中文摘要：

```text
<type>(<scope>): <摘要>

<可选正文：说明动机、影响面、验证方式>
```

| type | 用途 |
| --- | --- |
| `feat` | 新功能 |
| `fix` | 缺陷修复 |
| `refactor` | 不改变外部行为的重构 |
| `test` | 测试新增或修正 |
| `docs` | 文档 |
| `chore` | 构建、依赖、脚本、配置 |
| `style` | 仅格式调整 |

规则：

- 摘要不超过 50 字，动词开头，说明「做了什么」。
- 正文说明「为什么」以及行为影响，尤其是接口契约、数据库结构、权限边界的变化。
- 一次提交不混入无关的格式化改动。
- 不提交密钥、真实用户数据、`data/*.db` 的本地改动、`node_modules`、构建产物。

示例：

```text
fix(pest): 用药剂量正则漏匹配「稀释 1500 倍」

原正则只接受「1500倍」连写，农户常写成「1500 倍」，导致免责声明
不触发。补一个可选空格。影响面：仅免责声明判定，不改接口返回结构。

验证：python -m unittest tests.test_permissions
```

## 3. 代码规范

### 3.1 Python

- 遵循 PEP 8，4 空格缩进，行宽 100 以内。
- 缩进、编码与行尾由仓库根的 `.editorconfig` 统一（当前为 UTF-8 + CRLF，与既有源码一致）。
- 一个模块一个职责；模块顶部写 docstring，说明职责与边界。
- 函数 docstring 说明「为什么这样」与副作用，不复述函数名。
- 注释解释取舍与坑，不写「给变量赋值」这类无信息注释。
- 异常处理要具体：禁止裸 `except:`；捕获后要么恢复，要么带上下文抛出。
- 路径一律从 `backend/repo_paths.py` 的 `REPO_ROOT` 推导，不写相对当前工作目录的路径。
- 不引入未在 `requirements.txt` 声明的第三方依赖；能用标准库就用标准库。

### 3.2 Vue / TypeScript

- 单文件组件使用 `<script setup lang="ts">` 与组合式 API。
- 视图放 `src/views/<页面域>/`，可复用组件放 `src/components/<业务域>/`，不把业务逻辑塞进通用组件。
- 请求统一走 `src/api/` 的封装，不在组件里直接拼 URL。
- 样式使用 `src/styles/tokens.css` 的语义变量，不硬编码颜色与间距；页面私有样式随视图存放。
- 组件 props 与接口返回都要有类型；避免 `any`，确需使用时写注释说明原因。
- 交互状态三态齐全：加载中、空结果、错误，且错误文案可执行（告诉用户下一步做什么）。

### 3.3 后端边界（硬约束）

| 约束 | 判定方式 |
| --- | --- |
| 领域路由之间不得互相 import | `python tools/check_architecture.py` |
| 共享层不得 import 领域模块 | 同上 |
| 路由鉴权必须走能力表，不比较角色名 | 同上 + 代码评审 |
| 跨领域取数走窄接口或只读视图 | 代码评审 |
| 内容数据只读库，不在代码里留副本 | 代码评审 + ADR 0002 |

新增领域时同步更新：`backend/domains/__init__.py` 的蓝图导出、`core/app_factory.py` 的注册、`docs/ARCHITECTURE.md` 的领域表。

### 3.4 权限

角色与能力的唯一真相源是 `backend/core/permissions.py` 的 `CAPABILITIES`。新增能力时：

1. 在表里加一行，写明持有角色；
2. 路由用 `@require_capability('<域>.<动作>')`；
3. 在 `tests/test_permissions.py` 的矩阵里补断言；
4. 需要前端按能力显隐时，确认 `capabilities_for_role()` 的下发结果符合预期。

### 3.5 数据库

- 建表与补列只在 `backend/db_schema.py` 定义，启动时由 `apply_schema()` 幂等执行。
- 结构变更必须兼容既有库：只加列、加表、加索引，不删列、不改列类型。
- 一次性数据迁移放 `migrations/`，脚本必须幂等，并在 `schema_migrations` 留记录。
- 内容数据不进代码、不进种子脚本，只经运营后台或迁移脚本写入。

## 4. 测试要求

| 改动类型 | 必须补充 |
| --- | --- |
| 新增或修改 API | 至少一条单测，覆盖成功路径与一个失败路径 |
| 修改权限边界 | `tests/test_permissions.py` 的能力矩阵断言 |
| 修改上传、限流、错误码 | 对应的契约测试 |
| 修改前端主流程 | 对应的 Playwright 规格；视觉变更同步更新快照 |
| 纯文档、注释 | 无需测试 |

测试命名说明「在什么条件下、期望什么」，不写 `test_1`、`test_ok`。

## 5. 提交前检查

```bash
# 1. 后端单测
python -m unittest discover -s . -p "test_*.py" -t .

# 2. 架构边界
python tools/check_architecture.py

# 3. Python 静态检查
python tools/check_python.py

# 4. 前端
cd frontend
npm run typecheck
npm run test:unit
npm run build
```

涉及样式改动时追加：

```bash
python tools/check_frontend_styles.py
cd frontend && npm run test:visual:matrix
```

任何一项失败都不提交。不要用跳过测试、放宽断言、删除用例的方式让检查变绿。

## 6. 文档要求

| 变化 | 需要更新的文档 |
| --- | --- |
| 架构边界、分层职责 | `docs/adr/` 新增 ADR，并更新 `docs/ARCHITECTURE.md` |
| 环境变量、依赖、启动方式 | `.env.example`、`ENVIRONMENT.md` |
| 领域术语的新增或改名 | `GLOSSARY.md` |
| 目录职责变化 | `PROJECT_STRUCTURE.md` |
| 提交规范、评审门槛 | 本文 |

ADR 一旦定稿不再改写结论；被推翻时新增一份 ADR，并在旧文件标注「被 ADR-xxxx 取代」。

## 7. 评审清单

提交合并请求前，逐条自查：

- [ ] 改动范围与标题一致，没有夹带无关修改
- [ ] 新增的公开接口有鉴权、有限流、有错误码
- [ ] 数据库变更对既有库兼容，且幂等
- [ ] 没有把密钥、真实用户数据、本机绝对路径写进代码或文档
- [ ] 新增的领域或能力已同步到架构文档与权限矩阵
- [ ] 第 5 节的检查全部通过
- [ ] 提交信息说明了「为什么」，而不只是「改了什么」
