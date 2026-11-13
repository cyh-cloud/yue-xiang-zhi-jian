# 提交历史与开发过程

本文记录仓库的提交规模、阶段划分与分支策略，用于说明开发过程可追溯。所有数字取自 Git，可用文中命令复算。

---

## 1. 概览

| 指标 | 数值 |
| --- | --- |
| 提交总数 | 96 |
| 时间跨度 | 2026-08-02 至 2026-11-10（约 100 天） |
| 贡献者 | 3（`lixKRT` 89 次、`cyh` 5 次、`codex` 2 次） |
| 活动分支 | `frontend/vue-rebuild` |
| 标签 | 暂无 |

```bash
# 复算
git rev-list --count HEAD
git log --reverse --pretty=format:"%ad" --date=short | head -1
git shortlog -sne HEAD
```

## 2. 提交类型分布

| 类型 | 次数 | 说明 |
| --- | --- | --- |
| `feat` | 17 | 新功能 |
| `refactor` | 16 | 不改变外部行为的重构 |
| `fix` | 16 | 缺陷修复 |
| `chore` | 8 | 构建、依赖、脚本 |
| `merge` | 8 | 分支合并 |
| `test` | 7 | 测试补充与修正 |
| `docs` | 2 | 文档 |
| `dev` | 1 | 开发辅助 |
| 无前缀 | 21 | 早期提交与 CSS 迁移期的任务式提交 |

```bash
git log --pretty=format:"%s" | sed -E 's/^([a-zA-Z]+)(\(|:|!| ).*/\1/' | sort | uniq -c | sort -rn
```

早期提交未严格遵守 Conventional Commits，2026-10-12 之后逐步统一；`css-t*`、`css-*-integrate` 一类提交来自样式迁移期的任务编号，用于把大改动切成可独立回滚的小步。

## 3. 开发阶段

### 阶段一：项目初始化（2026-08-02 至 2026-10-10）

| 日期 | 关键提交 | 内容 |
| --- | --- | --- |
| 08-02 | `添加 vercel.json 修复 404 问题` | 首次部署尝试 |
| 10-07 | `同步完整项目源码` | 完整代码入库 |
| 10-09 | `fix:index.html拆分`、`fix:通知中心` | 页面结构拆分、通知中心修复 |
| 10-10 | `fix:超管 内容审核时间排序`、`test:内容审核测试数据` | 审核链路修复与测试数据 |

这一阶段是单文件应用形态：`app.py` 约 6000 行，`database.py` 约 3300 行，33 张表混在一个模块里，领域边界只靠注释横幅分隔。

### 阶段二：内容落库与后端领域化（2026-10-12 至 2026-10-16）

这是改动最集中的一周，两条主线并行：

**后端拆分**

- `04ae96d refactor: 后端按领域拆分，代码迁入 backend/`
- `f83ea28 refactor(core): 权限模型落地为能力表与 require_capability`
- `986bef0 refactor: 删除数据层转发层 database.py`
- `12e8b4a test(tools): 架构检查改为按能力表判权`

**内容落库**

- `ddd9b05 feat(db): 新增 20 张内容表、预留列、复核人字段与 5 个视图`
- `55e7369 refactor(pest): 病虫害内容切到读库`
- `addbf8a refactor(agriculture): 农时内容切到读库`
- `96a056e refactor(recruit,case,policy): 招募案例政策停止代码播种，改为读库`
- `f333602 feat(migrations): 一次性内容迁移脚本与基线库夹具`

同期建立了质量门禁：`b160f54 chore: 补齐 guardrail —— pre-commit、两个新检查`、`caac862 fix(backend): 补上静态检查抓出的三处运行时炸弹，清理 17 处死导入`。

### 阶段三：运营后台与页面完善（2026-10-13 至 2026-10-18）

- 运营后台四块内容维护：农时与病虫害（`22650a1`）、技艺方言招募案例（`464eebd`）
- 学员走查问题修复：农时日历加载态、农产品分类筛选、手工视频教学
- 后台外壳重做：`68db8ba feat(admin): 重做后台管理页外壳，后台角色继承普通用户权限`
- 消息中心抽成共享模块：`9acb186`

### 阶段四：Vue SPA 重构与样式体系（2026-10-19 至 2026-10-21）

- `d907fb6 feat(frontend): 完成 Vue SPA 重构`
- `ee48d1b feat(css): establish semantic tokens and base layer`
- `76374b9` 至 `9d39d2c` 共 27 个提交，按页面域迁移样式：公共外壳、就业、超管、技艺/资源/社区、教师/政府、企业/运营，最后做语义别名收敛与验收
- `57822a0 data: add current business database snapshot` 把业务库快照纳入版本库

> 数据库的入库状态变过两次：`2deb5e9` 先按计划把 `data/*.db` 移出版本库并写入 `.gitignore`，随后 `57822a0` 又把当时的业务库快照纳入，以便其他人拉下来就能看到完整演示内容。因此当前仓库内**有**一份 `data/yuexiang.db` 快照，而 `.gitignore` 里仍保留 `data/*.db` 规则。

这一阶段把多页面前端退役为 `legacy/reference/` 只读参照，活动前端统一为 `frontend/` 的 Vue 3 + TypeScript 单页应用。

### 阶段五：企业资质与社区治理（2026-11-10）

- 企业资质认证：营业执照提交、超管审核队列、未认证企业岗位数量门禁
- 企业岗位治理与社区敏感词审核：敏感词初筛转人工、待审内容断链、评论计数一致性
- 该阶段的功能集中在同一次提交入库：`2273d9b feat: 企业资质认证、企业岗位治理与社区敏感词审核`

## 4. 提交节奏

| 月份 | 提交数 | 说明 |
| --- | --- | --- |
| 2026-08 | 1 | 初始化 |
| 2026-09 | 0 | 无提交 |
| 2026-10 | 94 | 主体开发期 |
| 2026-11 | 1 | 收尾功能 |

```bash
git log --pretty=format:"%ad" --date=format:"%Y-%m" | sort | uniq -c
```

9 月无提交，10 月集中完成拆分、落库、重构与样式迁移，11 月补企业资质与社区治理。

## 5. 分支与历史保留

| 分支 | 用途 |
| --- | --- |
| `main` | 稳定分支 |
| `frontend/vue-rebuild` | Vue 重构期活动分支，当前 HEAD |

历史保留原则：

1. **不压缩、不改写已推送的历史**。评审需要看到真实的开发过程，`git rebase -i`、`squash`、`commit --amend` 只允许在本地未推送的提交上使用。
2. **合并提交保留**。`Merge branch 'codex/...'` 一类提交记录了并行任务的集成点，删除会丢失分支结构。
3. **不重新初始化仓库**。`rm -rf .git && git init` 会让 96 次提交与时间线全部消失，是最需要避免的操作。
4. **大文件只增不改**。历史中的数据库快照会让仓库体积偏大，但改写历史清理的代价高于收益，且会破坏已有克隆。

## 6. 查看历史

```bash
# 最近 30 条，带日期与作者
git log --pretty=format:"%h %ad %an %s" --date=short -30

# 按作者统计
git shortlog -sne HEAD

# 某个文件的变更历史（含重命名）
git log --follow --oneline -- backend/core/permissions.py

# 某次提交的完整改动
git show 2273d9b --stat

# 两次提交之间的差异
git diff 69aedaa..HEAD --stat
```

## 7. 提交规范

后续提交请遵循 [`CONTRIBUTING.md`](../CONTRIBUTING.md) 第 2 节：Conventional Commits、摘要说明「做了什么」、正文说明「为什么」与影响面。历史中不符合规范的提交不再追溯修改。
