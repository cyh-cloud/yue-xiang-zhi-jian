# cass-linguistics Scrapy 小样本验证

日期: 2026-10-21

验收结论: blocked（当前代码尚未按新口径重跑）

运行结果: partial

## 列表

- URL: `http://ling.cass.cn/news/bensuo/`
- 取得时间: `2026-10-21T05:12:53+08:00`
- HTTP: `200`
- 详情请求: 9 条
- 样本 ID: `6049078`、`6052571`、`6054128`、`6055725`、`6055732`

## 详情

| source_item_id | HTTP | 结果 |
| --- | ---: | --- |
| 6049078 | 200 | 可读取 |
| 6052571 | 200 | 可读取 |
| 6054128 | 404 | 失效链接 |
| 6055725 | 200 | 可读取 |
| 6055732 | 200 | 可读取 |

## 计数

- raw: 10
- stage: 5
- 候选标准实体: 0
- 当前代码 blocked: 5
- 目标口径 deferred: 5
- failed/failure_count: 4
- failure_reason: 4 条详情返回 HTTP 404

## 失败摘要

`http://ling.cass.cn/robots.txt` 返回 `404`，共享 robots 事实为 `not-found`。按最新裁决，`robots:not-found` 不阻断采集和采集库写入；raw、stage 保留，这 5 条候选应写为 `deferred`，原因 `robots:not-found`。当前分支的 blocked 5 是现有代码按旧 robots 策略产生的计数，尚未按新口径重跑。另有 4 条详情返回 HTTP 404，计入 `failure_count`，所以运行结果是 `partial`。404 仍不表示获得授权。只访问 `ling.cass.cn` 公开页面，没有请求登录后语料资源。

证据位置：`C:\Users\lixKR\AppData\Local\Temp\crawler-live-cass-783a606ae8334c5db6d8077f477abc6b\download`。

## 重试条件

项目负责人已裁决 `not-found` 不阻断采集。解除条件改为：按新口径重跑 5 条列表加 5 条详情，确认候选状态为 `deferred`，并保留 `robots:not-found` 原因。
