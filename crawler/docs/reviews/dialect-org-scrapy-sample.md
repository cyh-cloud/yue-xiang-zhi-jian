# dialect-org Scrapy 小样本验证

日期: 2026-10-21

验收结论: blocked（当前代码尚未按新口径重跑）

运行结果: partial

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
- 当前代码 blocked: 15
- 目标口径 deferred: 15
- failed: 0

## 失败摘要

`https://dialect.org.cn/robots.txt` 返回 `404`，共享 robots 事实为 `not-found`。按最新裁决，`robots:not-found` 不阻断采集和采集库写入；raw、stage 保留，候选应写为 `deferred`，原因 `robots:not-found`。当前分支的 blocked 15 是现有代码按旧 robots 策略产生的计数，尚未按新口径重跑。404 仍不表示获得授权。音频未下载，缺失与非法音频源仍分开记录。

证据位置：`C:\Users\lixKR\AppData\Local\Temp\crawler-live-dialect-31f84c7464164cbd9e0f292d1d776233\download`。

## 重试条件

项目负责人已裁决 `not-found` 不阻断采集。解除条件改为：按新口径重跑 5 条列表加 5 条详情，确认候选状态为 `deferred`，并保留 `robots:not-found` 原因。
