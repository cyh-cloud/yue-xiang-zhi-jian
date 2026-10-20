# ihchina Scrapy 小样本验证

日期: 2026-10-21

结果: blocked

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
- blocked: 20
- failed: 0

## 失败摘要

`https://www.ihchina.cn/robots.txt` 返回 `404`，共享 robots 事实为 `not-found`。采集侧准入按保守策略阻断全部 20 条候选，失败原因统一为 `robots:not-found`。详情页本身可访问，不能把本次结果写成候选成功。

证据位置：`C:\Users\lixKR\AppData\Local\Temp\crawler-live-ihchina-736f27ec38934feab384df46eca528b0\download`。

## 重试条件

站点提供可确认的 robots 允许规则，或项目负责人对 `not-found` 作出明确书面策略裁决后，重跑 5 条列表加 5 条详情。重跑前不得绕过 robots 或把 `not-found` 改成 `allowed`。
