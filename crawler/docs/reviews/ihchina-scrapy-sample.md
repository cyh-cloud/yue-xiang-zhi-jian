# ihchina Scrapy 小样本验证

日期: 2026-10-21

验收结论: blocked（当前代码尚未按新口径重跑）

运行结果: partial

## 列表

- URL: `https://www.ihchina.cn/getProject.html?category_id=16&limit=10&p=1`
- 取得时间: `2026-10-21T05:10:03+08:00`
- HTTP: `200`
- 列表请求: 2 页
- 详情请求: 20 条
- 样本 ID: `12185`、`12184`、`12183`、`12182`、`12181`

## 详情

前 5 条详情 URL 均返回 `200`：

- `https://www.ihchina.cn/project_details/12185.html`
- `https://www.ihchina.cn/project_details/12184.html`
- `https://www.ihchina.cn/project_details/12183.html`
- `https://www.ihchina.cn/project_details/12182.html`
- `https://www.ihchina.cn/project_details/12181.html`

## 计数

- raw: 23
- stage: 20
- 候选标准实体: 0
- 当前代码 blocked: 20
- 目标口径 deferred: 20
- failed: 0

## 失败摘要

`https://www.ihchina.cn/robots.txt` 返回 `404`，共享 robots 事实为 `not-found`。按最新裁决，`robots:not-found` 不阻断采集和采集库写入；raw、stage 保留，候选应写为 `deferred`，原因 `robots:not-found`。当前分支的 blocked 20 是现有代码按旧 robots 策略产生的计数，尚未按新口径重跑。404 仍不表示获得授权，也不自动获得业务发布资格。

证据位置：`C:\Users\lixKR\AppData\Local\Temp\crawler-live-ihchina-736f27ec38934feab384df46eca528b0\download`。

## 重试条件

项目负责人已裁决 `not-found` 不阻断采集。解除条件改为：按新口径重跑 5 条列表加 5 条详情，确认候选状态为 `deferred`，并保留 `robots:not-found` 原因。不得把 `not-found` 改写成 `allowed`。
