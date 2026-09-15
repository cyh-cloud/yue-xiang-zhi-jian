# superpowers 执行阶段操作指南

> 前置：《需求到功能模块操作指南》第 1-5 步已完成（宪法已立、specs/NNN/spec.md 已冻结提交）。
> 本指南覆盖：实现计划 → SDD 自动执行 → 收尾验收 的全部操作。
> 执行环境：同前——项目根目录的 Codex 会话；模型阶梯/防偷懒清单/worktree 规则已在项目 AGENTS.md 路由块声明，Codex 自动读取。

---

## 总览：一个子系统的完整执行循环

```
阶段 A  writing-plans 写实现计划        （你审查+批准，30 分钟）
阶段 B  SDD 自动执行全部任务            （几乎全自动，数小时）
阶段 C  终审 → 合并（需你授权） → converge → 更新 NOW.md（30 分钟）
```

每个子系统走一遍这个循环。可以串行（一个做完下一个），也可以 2-3 个 worktree 并行（见进阶节）。

---

## 前置确认（每次开工 2 分钟）

1. `git log --oneline -3` 确认目标 spec 已冻结提交
2. Codex 会话在项目根目录启动
3. `~/.codex/config.toml` 的 `[features] multi_agent = true` 在位（已配，改过需重启 Codex）

---

## 阶段 A：writing-plans 写实现计划（每子系统一次）

在 Codex 聊天框（自然语言即可，superpowers 会自动挂技能）：

```
基于 specs/001-user-portal/spec.md 编写实现计划。
```

想显式点名就说"使用 superpowers:writing-plans 技能…"。AI 会：

1. 通读 spec.md → 映出文件结构（哪些文件创建/修改）
2. 拆任务：每个任务 2-5 分钟粒度，含**真实测试代码**（写失败测试→跑→实现→跑→提交五步）
3. 每个任务标注 **Files**（精确路径）和 **Interfaces**（函数签名、Consumes/Produces）
4. 自查：spec 覆盖 / 无占位符（禁止 TBD）/ 类型一致
5. 保存到 `.agents/memories/plans/YYYY-MM-DD-<feature>.md`（项目路由块声明的位置），计划头 **Spec 字段指向 specs/NNN/spec.md**

**你做什么**：通读计划，重点审三处——
- 任务拆分是否覆盖 spec 全部验收标准（漏了 = 打回补）
- 接口签名是否互相一致（后面任务的输入 = 前面任务的输出）
- 有没有" TBD / 待实现 / 适当处理"这类占位符（有 = 打回）

批准后进入阶段 B。

---

## 阶段 B：SDD 自动执行（subagent-driven-development）

计划保存后 AI 会主动问"Subagent-Driven 还是 Inline Execution"——**选 Subagent-Driven**（推荐，除非想逐步盯）。

之后就是自动驾驶，你不需要逐任务确认：

```
SDD 自动做的事（你不用管）：
├─ 建 worktree（挂当前 v2/lixKRT/NNN-<slug> 分支，路由块已声明）
├─ 逐任务循环：
│   ├─ 派实现者子代理（deepseek-flash，任务简报含防偷懒"三实"要求）
│   ├─ 派审查员子代理（glm-5.3，双维审查 + 偷懒清单逐项核查）
│   ├─ 不合格 → 修复循环（1-3 轮原代理 → 4-5 轮升 glm-5.3）
│   └─ 通过 → 记账 → 下一任务（任务间不停顿问你）
└─ 全部完成 → 自动做最终全分支审查（最强档）
```

**只有四类情况会停下来找你**：不可逆操作 / 安全敏感 / 工作树外副作用（合并、推送）/ 计划破碎无法推进。回答它的决策问题，它继续跑。

**中断与恢复（重要）**：
- 会话断了 / 上下文压缩了 → 进度在 `.superpowers/sdd/<计划名>/progress.md`（账本，第一行是计划路径）
- 新会话里说：`继续执行 .agents/memories/plans/<计划文件> 的计划` → SDD 从账本恢复，不重做已完成任务
- 子代理跑得慢是正常的（每个任务 = 实现+审查两轮 AI 调用）；看 New API 消费记录可观察各档模型用量

**spawn 报模型不可用**：如果第一个任务派发就报模型不在允许列表，把路由块的实现档模型名换成 config.toml 主模型同款（glm-5.3-flash），先跑通再调阶梯。

---

## 阶段 C：收尾（每模块 30 分钟）

1. **最终审查结果处理**：SDD 的终审会汇总全部发现（含被递延的次要项）——你裁决哪些修、哪些留着
2. **合并**：AI 走 finishing-a-development-branch 流程给出选项（merge/保留/丢弃）——**合并到主干需要你明确授权**（你的 git-rules）
3. **converge 验收**：合并后跑 `$speckit-converge`（弱化版对照 spec.md）→ 发现的缺口回填 superpowers 计划或记 NOW.md
4. **记忆维护**：让 Codex 把本模块完成状态写进 `.agents/memories/NOW.md`，有新决策记 DECISIONS.md
5. **清理**：worktree 保留到该模块稳定后再删（删除需授权）

---

## 进阶：多模块并行（可选，不急于第一天用）

前提：涉及的 specs 都已冻结、共享契约（数据模型/API schema）不再交叉变动。

```
主 checkout 继续跑模块 A 的 SDD
+ 另开 1-2 个终端，各自 checkout 到 .worktrees/ 下已有的并行 worktree 跑模块 B/C 的 SDD
```

铁律：**合并回主干必须顺序化**（一个合完再下一个）；`.specify/feature.json` 合并冲突是预期行为，裁决到最新完成的 feature 即可。

---

## 常见坑

1. **不要在 SDD 运行中改 spec.md**——实现对照的是冻结版；真要改，停 SDD → 改 spec → 重跑 writing-plans
2. **不要替 SDD 手改代码**——主会话自己改代码会跳过审查（SDD 明令禁止的行为）；发现不对让它派修复
3. **worktree 里没有 `$speckit-*` 命令是正常的**——skills 不进 git（.gitignore 策略），speckit 命令只在主 checkout 用；worktree 里只做实现
4. **看到 SDD 停下来 ≠ 出错**——先看它说的是不是四类合法停机；是就回答决策，不是才是 bug
5. **token 消耗焦虑**——实现档已是最便宜档，大头在审查；真嫌贵可把任务审查 effort 从 high 降 medium，终审保持最高档不动
