# feiyiw Scrapy 小样本验证

日期: 2026-10-21

验收结论: approved-with-gaps

运行结果: partial

## 实际重跑

- run_id: `feiyiw-9f11f4195c654773ae362fbdda8de7b6`
- 归档位置: `../crawler-live-evidence/issue-133-20261021/feiyiw/`
- 列表 URL: `https://www.feiyiw.cn/index.php?app=article&cate_id=4`
- 取得时间: `2026-10-21 23:29:59 Asia/Shanghai`
- HTTP: `200`
- robots: `https://www.feiyiw.cn/robots.txt` 返回 `404`，结论为 `not-found`
- 列表页: 3 页
- 详情请求: 20 条，均返回 `200`
- 样本 ID: `69998`、`69999`、`70001`、`70004`、`70005`

## 计数

- raw: 23
- stage: 20
- candidate: 0
- deferred: 20
- blocked: 0
- failed/failure_count: 0
- skipped: 0
- candidate_reason: `robots:not-found`

20 条完整候选按新口径写为 `deferred`，不再写成历史 `blocked`。会员、商城和购买链接继续排除。

## 证据

- 公开索引: `crawler/docs/operations/live-evidence-index.json`
- 运行报告: `feiyiw/reports/feiyiw-9f11f4195c654773ae362fbdda8de7b6.json`
- 原始响应正文留在归档目录，不进入公开仓库。

## 剩余风险

- 本轮只验证 3 页列表和 20 条详情，没有全量遍历。
- 站点版权保留，业务发布前仍需审核。
- robots 404 只表示没有取得允许规则，不构成发布授权。
