# nzrc Scrapy 小样本验证

日期: 2026-10-21

结果: blocked

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
- blocked: 19
- failed: 0

## 失败摘要

`http://www.nzrc.com.cn/robots.txt` 返回 `404`，共享 robots 事实为 `not-found`。采集侧准入按保守策略阻断全部 19 条候选，失败原因统一为 `robots:not-found`。联系方式区域未提取，公开岗位字段边界不变。

证据位置：`C:\Users\lixKR\AppData\Local\Temp\crawler-live-nzrc-aefad5969770471a8b77307d35d616d5\download`。

## 重试条件

站点提供可确认的 robots 允许规则，或项目负责人对 `not-found` 作出明确书面策略裁决后，重跑 5 条列表加 5 条详情。
