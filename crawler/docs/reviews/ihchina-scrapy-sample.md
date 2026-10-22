# ihchina Scrapy 小样本验证

日期: 2026-10-21

验收结论: blocked（本次重跑 HTTP 504）

运行结果: failed

## 实际重跑

- run_id: `ihchina-703ba5dd90304355b31576e508452d21`
- 归档位置: `../crawler-live-evidence/issue-133-20261021/ihchina/`
- 列表 URL: `https://www.ihchina.cn/getProject.html?category_id=16&limit=10&p=1`
- 取得时间: `2026-10-21 23:26:50 Asia/Shanghai`
- HTTP: `504`
- Content-Type: `text/html`
- robots: `https://www.ihchina.cn/robots.txt` 返回 `404`，结论为 `not-found`

本次按新 robots 口径重跑时，列表入口返回 HTTP 504，Spider 没有取得可用列表和详情，因此没有产生候选。`not-found` 仍只是访问事实，不是发布授权。

## 计数

- raw: 1
- stage: 0
- candidate: 0
- deferred: 0
- blocked: 0
- failed/failure_count: 1
- skipped: 0
- failure_reason: `HTTP 504: https://www.ihchina.cn/getProject.html?category_id=16&limit=10&p=1`

## 证据

- 公开索引: `crawler/docs/operations/live-evidence-index.json`
- 运行报告: `ihchina/reports/ihchina-703ba5dd90304355b31576e508452d21.json`
- 原始响应正文留在归档目录，不进入公开仓库。

## 解除条件

- 列表入口恢复稳定响应后重新运行列表和至少 5 条详情。
- 重跑确认 raw、stage、候选状态、`robots:not-found` 原因和失败计数。
- 不把 HTTP 200、robots 404 或 fixture 回放写成 live 成功。
