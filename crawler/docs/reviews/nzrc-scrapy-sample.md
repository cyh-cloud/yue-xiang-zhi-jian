# nzrc Scrapy 小样本验证

日期: 2026-10-21

验收结论: approved-with-gaps

运行结果: partial

## 实际重跑

- run_id: `nzrc-f13c8dae7ed74d278ca7807c9cc733ee`
- 归档位置: `../crawler-live-evidence/issue-133-20261021/nzrc/`
- 列表 URL: `http://www.nzrc.com.cn/career_seek.html`
- 取得时间: `2026-10-21 23:28:13 Asia/Shanghai`
- HTTP: `200`
- robots: `http://www.nzrc.com.cn/robots.txt` 返回 `404`，结论为 `not-found`
- 详情请求: 20 条，均返回 `200`
- 样本 ID: `8232893`、`8232892`、`8232581`、`8232580`、`8239681`

## 计数

- raw: 21
- stage: 20
- candidate: 0
- deferred: 20
- blocked: 0
- failed/failure_count: 0
- skipped: 0
- candidate_reason: `robots:not-found`

20 条完整候选按新口径写为 `deferred`，不再写成历史 `blocked`。robots 404 不表示获得授权，联系方式和个人简历边界不变。

## 证据

- 公开索引: `crawler/docs/operations/live-evidence-index.json`
- 运行报告: `nzrc/reports/nzrc-f13c8dae7ed74d278ca7807c9cc733ee.json`
- 原始响应正文留在归档目录，不进入公开仓库。

## 剩余风险

- 本轮只验证默认列表页和 20 条详情，没有全量遍历分页。
- 页面依赖 PostBack 和会话状态，后续全量运行需保持低频和幂等。
- robots 404 只表示没有取得允许规则，不构成发布授权。
