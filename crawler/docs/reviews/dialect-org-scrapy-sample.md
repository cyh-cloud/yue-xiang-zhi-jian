# dialect-org Scrapy 小样本验证

日期: 2026-10-21

结果: blocked

## 列表

- URL: `https://dialect.org.cn/`
- 取得时间: `2026-10-21T05:12:24+08:00`
- HTTP: `200`
- 详情请求: 15 条
- 样本 ID: `14`、`9`、`7`、`13`、`2`

## 详情

前 5 条详情 URL 均返回 `200`：

- `https://dialect.org.cn/dialect/14`
- `https://dialect.org.cn/dialect/9`
- `https://dialect.org.cn/dialect/7`
- `https://dialect.org.cn/dialect/13`
- `https://dialect.org.cn/dialect/2`

## 计数

- raw: 16
- stage: 15
- 候选标准实体: 0
- blocked: 15
- failed: 0

## 失败摘要

`https://dialect.org.cn/robots.txt` 返回 `404`，共享 robots 事实为 `not-found`。采集侧准入按保守策略阻断全部 15 条候选，失败原因统一为 `robots:not-found`。音频未下载，缺失与非法音频源仍分开记录。

证据位置：`C:\Users\lixKR\AppData\Local\Temp\crawler-live-dialect-31f84c7464164cbd9e0f292d1d776233\download`。

## 重试条件

站点提供可确认的 robots 允许规则，或项目负责人对 `not-found` 作出明确书面策略裁决后，重跑 5 条列表加 5 条详情。
