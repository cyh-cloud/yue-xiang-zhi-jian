# feiyiw Scrapy 小样本验证

日期: 2026-10-21

结果: blocked

## 列表

- URL: `https://www.feiyiw.cn/index.php?app=article&cate_id=4`
- 取得时间: `2026-10-21T05:13:23+08:00`
- HTTP: `200`
- 详情请求: 17 条
- 样本 ID: `69998`、`69999`、`70001`、`70004`、`70005`

## 详情

前 5 条详情 URL 均返回 `200`：

- `https://www.feiyiw.cn/index.php?app=article&act=view&article_id=69998`
- `https://www.feiyiw.cn/index.php?app=article&act=view&article_id=69999`
- `https://www.feiyiw.cn/index.php?app=article&act=view&article_id=70001`
- `https://www.feiyiw.cn/index.php?app=article&act=view&article_id=70004`
- `https://www.feiyiw.cn/index.php?app=article&act=view&article_id=70005`

## 计数

- raw: 20
- stage: 17
- 候选标准实体: 0
- blocked: 17
- failed: 0

## 失败摘要

`https://www.feiyiw.cn/robots.txt` 返回 `404`，共享 robots 事实为 `not-found`。采集侧准入按保守策略阻断全部 17 条候选，失败原因统一为 `robots:not-found`。会员、商城和购买链接继续排除，站点版权保留，业务发布前仍需审核。

证据位置：`C:\Users\lixKR\AppData\Local\Temp\crawler-live-feiyiw-8d6c32a525d14b609cde84046394d4b4\download`。

## 重试条件

站点提供可确认的 robots 允许规则，或项目负责人对 `not-found` 作出明确书面策略裁决后，重跑 5 条列表加 5 条详情。
