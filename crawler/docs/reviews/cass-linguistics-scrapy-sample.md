# cass-linguistics Scrapy 小样本验证

日期: 2026-10-21

验收结论: approved-with-gaps

运行结果: partial

## 实际重跑

- run_id: `cass-linguistics-d97213dd2aca4465b630ef1b4abcecc9`
- 归档位置: `../crawler-live-evidence/issue-133-20261021/cass-linguistics/`
- 列表 URL: `http://ling.cass.cn/news/bensuo/`
- 取得时间: `2026-10-21 23:29:38 Asia/Shanghai`
- HTTP: `200`
- robots: `http://ling.cass.cn/robots.txt` 返回 `404`，结论为 `not-found`
- 详情请求: 9 条
- 样本 ID: `6049078`、`6052571`、`6054128`、`6055725`、`6055732`

## 详情结果

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
- candidate: 0
- deferred: 5
- blocked: 0
- failed/failure_count: 4
- skipped: 0
- candidate_reason: `robots:not-found`
- failure_reason: 4 条详情返回 HTTP 404

5 条完整候选按新口径写为 `deferred`，不再写成历史 `blocked`。4 条 404 详情计入失败，运行结果保持 `partial`。

## 证据

- 公开索引: `crawler/docs/operations/live-evidence-index.json`
- 运行报告: `cass-linguistics/reports/cass-linguistics-d97213dd2aca4465b630ef1b4abcecc9.json`
- 原始响应正文留在归档目录，不进入公开仓库。

## 剩余风险

- 失效链接和站点分页变化需要后续重跑。
- robots 404 只表示没有取得允许规则，不构成发布授权。
