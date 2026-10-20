# Scrapy 迁移集成验收

日期: 2026-10-21

结果: blocked

## 项目清单

- `ihchina`
- `nzrc`
- `nongmuhr`
- `dialect-org`
- `cass-linguistics`
- `feiyiw`
- `aqsc-moa`
- `cnipa`

## 验证结果

| 项目 | fixture/骨架 | 联网小样本 | 运行结果 | 验收结论 |
| --- | --- | --- | --- | --- |
| ihchina | 通过 | 2 页列表 + 20 详情，robots 404，候选 0，blocked 20 | partial | blocked |
| nzrc | 通过 | 19 详情，robots 404，候选 0，blocked 19 | partial | blocked |
| nongmuhr | 通过 | 10 详情 HTTP 200，但详情解析 10 次失败，候选 0 | failed（failure_count 10） | blocked |
| dialect-org | 通过 | 15 详情，robots 404，候选 0，blocked 15 | partial | blocked |
| cass-linguistics | 通过 | 9 详情，其中 4 条 404；robots 404，候选 0，blocked 5 | partial（failure_count 4） | blocked |
| feiyiw | 通过 | 17 详情，robots 404，候选 0，blocked 17 | partial | blocked |
| aqsc-moa | 通过 | 不执行 | 不适用 | approved-with-gaps |
| cnipa | 通过 | 不执行 | 不适用 | approved-with-gaps |

## 边界核对

- Scrapy 仅写采集库，共享包没有导入业务库或转换器。
- 天气不在 Scrapy 项目中；`open-meteo` 和 `qweather` 没有 Spider。
- `5ajob`、`zhongguoyuyan`、`cnopendata` 没有新项目。
- `aqsc-moa` 和 `cnipa` 没有 live 请求或真实文件采集。
- 全量 crawler 测试通过，共 187 项。
- 每个项目都有独立 fixture 回放入口；连续两次回放时 raw 追加，stage 和候选按来源自然键幂等。
- 8 个项目的 fixture 回放均经过各自项目入口，并断言候选数量、状态和连续两次幂等。
- `aqsc-moa` 和 `cnipa` 的 fixture 回放把真实 XLSX/PDF 写入 `raw_files`，不是只回放 `discover.json`。
- 候选标准实体保留站点标准字段、`run_id` 和实际内容哈希。
- live crawl 生成结构化运行报告，包含请求、raw、stage、候选状态和错误摘要。
- 运行报告的 `failed` 与 `failure_count` 使用同一计数，记录解析异常、HTTP 4xx/5xx 和下载异常；`blocked` 统计 robots disallowed 请求及采集侧准入阻断，同一请求不重复计数。`failure_reason` 同时保留 robots 拒绝和失败摘要；`blocked` 是计数，不是 `RunReport.status` 的枚举。
- robots 结论覆盖 allowed、disallowed、not-found 和 unknown，拒绝请求保留 raw 证据。
- 8 个项目统一使用 `crawler/download/` 和 `crawler/data/crawler.db`。

## 未关闭问题

- `ihchina`、`nzrc`、`dialect-org`、`cass-linguistics`、`feiyiw` 的 robots.txt 返回 `404`，共享准入按 `robots:not-found` 阻断全部候选。站点页面返回 200 不等于采集候选成功。
- `nongmuhr` 详情页当前 HTML 不再匹配已登记字段结构，10 次详情解析均触发 `AttributeError`，raw 已保留但没有 stage 和候选。解除条件是重新定位详情字段并重跑 5 条详情。
- `cass-linguistics` 另有 4 条详情返回 404，未写成成功样本。

本次 fixture、项目入口、文件证据和采集边界已完成；实时候选门被 robots 和站点结构阻断，因此总体验收为 `blocked`，不是完全通过。
