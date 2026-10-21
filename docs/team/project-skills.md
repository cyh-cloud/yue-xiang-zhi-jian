# 项目技能入口

项目技能位于 `.agents/skills/`，每个技能以 `SKILL.md` 为说明。技能路由使用 `ask-matt`，例如 `/ask-matt`；判断技能内容时直接读对应的 `SKILL.md`。

## 常用入口

| 场景 | 技能 |
| --- | --- |
| 不确定用哪个技能 | `ask-matt` |
| 需求澄清与方案压力测试 | `grilling`、`grill-with-docs` |
| 形成规格与拆分票据 | `to-spec`、`to-tickets` |
| 实现功能 | `implement`、`implement-spec` |
| 测试驱动开发 | `tdd` |
| 代码审查 | `code-review` |
| 排查缺陷 | `diagnosing-bugs` |
| 前端设计 | `frontend-design`、`prototype` |
| 浏览器验证 | `playwright-cli` |
| 文档与代理配置 | `writing-for-agents` |
| 环境改进复盘 | `retro` |

## 使用约束

- 先读 `SKILL.md`，再按其中流程执行。不要只凭路由摘要行动。
- 技能产出的需求、规格和票据，以 GitHub issue 为准。
- 技能流程同样受 `docs/adr/` 和本目录的协作规则约束。
- 修改技能本身时，保持入口指针短小，具体流程留在技能文件内。
