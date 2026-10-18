# 本地任务图

本文件代替远程 tracker，不创建 issue 或 PR。

## 已完成

- `spec`: 规格冻结，见 `SPEC.md`。
- `registry`: 来源 ID 和共享文件骨架冻结，见 `sources.json`。

## 第一波：来源契约

| 任务 | 依赖 | 产出 |
| --- | --- | --- |
| `source-ihchina` | `registry` | `sources/ihchina.md` |
| `source-aqsc-moa` | `registry` | `sources/aqsc-moa.md` |
| `source-cnipa` | `registry` | `sources/cnipa.md` |
| `source-weather` | `registry` | `sources/weather.md` |
| `source-nzrc` | `registry` | `sources/nzrc.md` |
| `source-nongmuhr` | `registry` | `sources/nongmuhr.md` |

## 第二波：来源契约

| 任务 | 依赖 | 产出 |
| --- | --- | --- |
| `source-5ajob` | `registry` | `sources/5ajob.md` |
| `source-dialect-org` | `registry` | `sources/dialect-org.md` |
| `source-cass-linguistics` | `registry` | `sources/cass-linguistics.md` |
| `source-cnopendata` | `registry` | `sources/cnopendata.md` |
| `source-zhongguoyuyan` | `registry` | `sources/zhongguoyuyan.md` |
| `source-feiyiw` | `registry` | `sources/feiyiw.md` |

## 第三波：架构与映射

| 任务 | 依赖 | 产出 |
| --- | --- | --- |
| `adr-crawler-db` | `spec` | `adr/0001-crawler-separate-database.md` |
| `adr-source-access` | `spec` | `adr/0002-source-rights-and-access.md` |
| `schema-crawler` | `spec` | `schema/crawler-db.md` |
| `schema-yuexiang` | `spec` | `schema/yuexiang-target-db.md` |
| `converter` | `schema-crawler` | `schema/converter.md` |
| `mapping-content` | `spec` | `mapping/agri-products.md`, `mapping/ich-crafts.md`, `mapping/jobs.md`, `mapping/dialects.md`, `mapping/weather.md` |

## 第四波：审核与汇总

| 任务 | 依赖 | 产出 |
| --- | --- | --- |
| `review-p0` | 第一波 | `reviews/ihchina.md`, `reviews/aqsc-moa.md`, `reviews/cnipa.md` |
| `review-p1` | 第一、二波 | 其余来源审核 |
| `operations` | `spec` | `operations/collection-rules.md`, `operations/validation.md`, `operations/rollout.md` |
| `final-review` | 全部 | 最终验收记录 |

## 当前状态

- 第一波和第二波的 12 个来源文档均已完成。
- 12 个来源均有独立审核记录。
- 架构、schema、映射和运维文档均已完成。
- 未决事项已汇总到 `BLOCKERS.md`，等待人工决策。

## 审核结论

除 `zhongguoyuyan` 为 `blocked` 外，其余来源均为 `approved-with-gaps`。缺口不阻止继续整理设计，但在实现前需先处理 `BLOCKERS.md` 中的 P0 项。
