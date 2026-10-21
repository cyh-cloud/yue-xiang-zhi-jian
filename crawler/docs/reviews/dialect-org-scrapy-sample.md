# dialect-org Scrapy 小样本验证

日期: 2026-10-21

验收结论: approved-with-gaps

运行结果: partial

## 实际重跑

- run_id: `dialect-org-e7265be7d9d14059a9c086f13150c883`
- 归档位置: `../crawler-live-evidence/issue-133-20261021/dialect-org/`
- 列表 URL: `https://dialect.org.cn/`
- 取得时间: `2026-10-21 23:29:11 Asia/Shanghai`
- HTTP: `200`
- robots: `https://dialect.org.cn/robots.txt` 返回 `404`，结论为 `not-found`
- 详情请求: 15 条，均返回 `200`
- 样本 ID: `14`、`9`、`7`、`13`、`2`

## 计数

- raw: 16
- stage: 15
- candidate: 0
- deferred: 15
- blocked: 0
- failed/failure_count: 0
- skipped: 0
- candidate_reason: `robots:not-found`

15 条完整候选按新口径写为 `deferred`，不再写成历史 `blocked`。音频未下载，缺失与非法音频源仍分开记录。

## 证据

- 公开索引: `crawler/docs/operations/live-evidence-index.json`
- 运行报告: `dialect-org/reports/dialect-org-e7265be7d9d14059a9c086f13150c883.json`
- 原始响应正文留在归档目录，不进入公开仓库。

## 剩余风险

- 本轮只验证默认列表页和 15 条详情，没有全量遍历。
- robots 404 只表示没有取得允许规则，不构成发布授权。
