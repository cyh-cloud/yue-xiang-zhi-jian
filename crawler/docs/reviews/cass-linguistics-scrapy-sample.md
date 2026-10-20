# cass-linguistics Scrapy 小样本验证

日期: 2026-10-21

结果: blocked

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
- blocked: 5
- failed: 0

## 失败摘要

`http://ling.cass.cn/robots.txt` 返回 `404`，共享 robots 事实为 `not-found`。采集侧准入按保守策略阻断 5 条候选，失败原因统一为 `robots:not-found`。另有 4 条详情返回 `404`，未写成成功样本。只访问 `ling.cass.cn` 公开页面，没有请求登录后语料资源。

证据位置：`C:\Users\lixKR\AppData\Local\Temp\crawler-live-cass-783a606ae8334c5db6d8077f477abc6b\download`。

## 重试条件

站点提供可确认的 robots 允许规则，或项目负责人对 `not-found` 作出明确书面策略裁决后，重跑 5 条列表加 5 条详情。
