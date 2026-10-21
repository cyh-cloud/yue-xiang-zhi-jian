# Scrapy 迁移集成验收

日期: 2026-10-21

结果: blocked（当前分支尚未按新口径重跑，保留历史阻断结论）

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
| ihchina | 通过 | 2 页列表 + 20 详情，robots `not-found`；历史 live 写 blocked 20，代码口径已改为 deferred 20，尚未重跑 | partial | blocked |
| nzrc | 通过 | 19 详情，robots `not-found`；历史 live 写 blocked 19，代码口径已改为 deferred 19，尚未重跑 | partial | blocked |
| nongmuhr | 通过 | 10 详情 HTTP 200，但详情解析 10 次失败，候选 0 | failed（failure_count 10） | blocked |
| dialect-org | 通过 | 15 详情，robots `not-found`；历史 live 写 blocked 15，代码口径已改为 deferred 15，尚未重跑 | partial | blocked |
| cass-linguistics | 通过 | 9 详情，其中 4 条 404；robots `not-found`；历史 live 写 blocked 5，代码口径已改为 deferred 5，尚未重跑 | partial（failure_count 4） | blocked |
| feiyiw | 通过 | 17 详情，robots `not-found`；历史 live 写 blocked 17，代码口径已改为 deferred 17，尚未重跑 | partial | blocked |
| aqsc-moa | 通过 | 发现页和公告页 200，附件和 robots 403；raw 3、stage 1 blocked、候选 0、failure_count 1 | partial | blocked |
| cnipa | 通过 | 公告页 200、PDF 200；raw 2、PDF 1、stage 58、deferred 58、failure_count 0 | partial | approved-with-gaps |

## 边界核对

- Scrapy 仅写采集库，共享包没有导入业务库或转换器。
- 天气不在 Scrapy 项目中；`open-meteo` 和 `qweather` 没有 Spider。
- `5ajob`、`zhongguoyuyan`、`cnopendata` 没有新项目。
- `aqsc-moa` live 已发现 aqsc 公告页和 XLSX 链接，但附件下载被 `www.aqsc.agri.cn` 403 阻断；`cnipa` live 已取得 28 页、428298 bytes 的 PDF，并解析 58 条 deferred 候选。
- 全量 crawler 测试共 216 项；本轮实现环境 215 项通过，证据账本用例仍受 Windows CRLF 与既有账本记录不一致影响，未计入 #132 的文件样本改动。
- 每个项目都有独立 fixture 回放入口；连续两次回放时 raw 追加，stage 和候选按来源自然键幂等。
- 8 个项目的 fixture 回放均经过各自项目入口，并断言候选数量、状态和连续两次幂等。
- `aqsc-moa` 和 `cnipa` 的 fixture 回放经过真实 Scrapy process，把合成 XLSX/PDF 写入 `raw_files`，不是只回放 `discover.json`。
- 候选标准实体保留站点标准字段、`run_id` 和实际内容哈希。
- live crawl 生成结构化运行报告，包含请求、raw、stage、候选状态和错误摘要。
- 运行报告的 `failed` 与 `failure_count` 使用同一计数，记录解析异常、HTTP 4xx/5xx 和下载异常；`blocked` 只统计真实阻断，`deferred` 单独计数。`failure_reason` 保留真实阻断和失败摘要；`blocked` 和 `deferred` 是计数，不是 `RunReport.status` 的枚举。
- robots 结论覆盖 allowed、disallowed、not-found 和 unknown。`not-found` 请求保留 raw 证据并写 `deferred` 候选；明确拒绝请求保留 raw 证据并写 `blocked`。
- 8 个项目统一使用 `crawler/download/` 和 `crawler/data/crawler.db`。

## 未关闭问题

- 上方 live 计数是代码口径修订前的实际运行结果。`ihchina`、`nzrc`、`dialect-org`、`cass-linguistics`、`feiyiw` 的 robots 404 现在按代码契约保留 raw 和 stage，并把候选写为 `deferred`，原因 `robots:not-found`。这 5 个来源尚未重跑 live，因此验收结论仍保留为 `blocked`，不能宣称新口径已完成联网验证。
- `nongmuhr` 详情页当前 HTML 不再匹配已登记字段结构，10 次详情解析均触发 `AttributeError`，raw 已保留但没有 stage 和候选。这是解析真实失败，应保持 `blocked`。解除条件是重新定位详情字段并重跑 5 条详情。
- `cass-linguistics` 另有 4 条详情返回 404，未写成成功样本。
- `aqsc-moa` 的 live 小样本仍被 WAF 403 阻断，解除条件是 robots、公告页和附件入口恢复可采集响应。`cnipa` 已完成 www 公告页加第一份 PDF 的 live 小样本；`ggfw` 签名 PDF 路径仍保持 `unknown` robots 约束。

本次 fixture、项目入口、文件证据和采集边界已完成。按新 robots 口径，5 个来源的 deferred 候选仍需重跑验证；`nongmuhr` 的真实解析失败仍未解除。总体验收保持 `blocked`，不是完全通过。
