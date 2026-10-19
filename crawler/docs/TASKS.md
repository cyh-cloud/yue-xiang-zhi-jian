# 本地任务图

本文件代替远程 tracker，不创建 issue 或 PR。任务只记录依赖、产出和当前状态，问题明细指向 `ISSUES.md`。

## 已完成

| 任务 | 产出 | 状态依据 |
| --- | --- | --- |
| `spec` | `SPEC.md` | 规格已冻结 |
| `implementation-spec` | `IMPLEMENTATION-SPEC.md` | 实现规格已冻结，供新会话执行 |
| `source-baseline` | 12 份来源文档 | 首轮实现已落盘 |
| `review-baseline` | 12 份独立审核记录 | 首轮审核已落盘 |
| `architecture-baseline` | `schema/`、`mapping/`、`operations/` | 设计文档已落盘 |
| `registry-contract` | `sources.json`、`sources/CONTRACT.md`、`README.md` | 来源注册表和共享契约已建立 |

## 待修复

| 任务 | 依赖 | 产出 |
| --- | --- | --- |
| `source-contract-alignment` | `registry-contract` | 来源文档按 `sources/CONTRACT.md` 补齐差异字段、详情 URL 资格、下载记录和验证时间 |
| `crawler-core` | `implementation-spec` | 采集库初始化、运行记录、来源适配器 interface 和测试骨架 |
| `p0-adapters` | `crawler-core` | `ihchina`、`aqsc-moa`、`cnipa` 三个来源适配器 |
| `std-projection` | `p0-adapters` | 第一版 std 投影和 dry-run 转换计划 |
| `review-alignment` | `source-contract-alignment` | 审核记录重新核对 `sources.json` 的状态、访问边界和来源证据 |
| `blockers-p0` | 无 | 按 `ISSUES.md` 的 P0 顺序关闭实现前决策门 |
| `blockers-p1-p2` | `blockers-p0` | 按 `ISSUES.md` 分级关闭后续修复和改进项 |

## 待复核

| 任务 | 依赖 | 产出 |
| --- | --- | --- |
| `registry-contract-review` | `registry-contract` | 复核 JSON 合法性、ID 唯一性、状态一致性、路径存在性和契约语义 |
| `source-detail-url-review` | `source-contract-alignment` | 复核每份来源的详情 URL 是否满足业务发布硬规则 |
| `final-review` | 全部待修复和待复核任务 | 最终交付验收记录 |

## 阻塞

| 阻塞门 | 依赖 | 说明 |
| --- | --- | --- |
| `p0-decisions` | 人工决策 | 未关闭前不进入来源实现和转换器实现，明细只看 `ISSUES.md` |
| `restricted-source-access` | 外部授权或人工核验 | 受限来源保持登记状态，满足契约后才可变更，明细只看 `ISSUES.md` |
