# nzrc Scrapy 小样本验证

日期: 2026-10-21

验收结论: blocked（当前代码尚未按新口径重跑）

运行结果: partial

## 列表

- URL: `http://www.nzrc.com.cn/career_seek.html`
- 取得时间: `2026-10-21T05:11:23+08:00`
- HTTP: `200`
- 详情请求: 19 条
- 样本 ID: `8235894`、`8235893`、`8235892`、`8235891`、`8235890`

## 详情

前 5 条详情 URL 均返回 `200`：

- `http://www.nzrc.com.cn/company/jobs/8235894.html`
- `http://www.nzrc.com.cn/company/jobs/8235893.html`
- `http://www.nzrc.com.cn/company/jobs/8235892.html`
- `http://www.nzrc.com.cn/company/jobs/8235891.html`
- `http://www.nzrc.com.cn/company/jobs/8235890.html`

## 计数

- raw: 20
- stage: 19
- 候选标准实体: 0
- 当前代码 blocked: 19
- 目标口径 deferred: 19
- failed: 0

## 失败摘要

`http://www.nzrc.com.cn/robots.txt` 返回 `404`，共享 robots 事实为 `not-found`。按最新裁决，`robots:not-found` 不阻断采集和采集库写入；raw、stage 保留，候选应写为 `deferred`，原因 `robots:not-found`。当前分支的 blocked 19 是现有代码按旧 robots 策略产生的计数，尚未按新口径重跑。404 仍不表示获得授权。联系方式区域未提取，公开岗位字段边界不变。

证据位置：`C:\Users\lixKR\AppData\Local\Temp\crawler-live-nzrc-aefad5969770471a8b77307d35d616d5\download`。

## 重试条件

项目负责人已裁决 `not-found` 不阻断采集。解除条件改为：按新口径重跑 5 条列表加 5 条详情，确认候选状态为 `deferred`，并保留 `robots:not-found` 原因。
