# feiyiw Scrapy 小样本验证

日期: 2026-10-21

验收结论: blocked（当前代码尚未按新口径重跑）

运行结果: partial

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
- 当前代码 blocked: 17
- 目标口径 deferred: 17
- failed: 0

## 失败摘要

`https://www.feiyiw.cn/robots.txt` 返回 `404`，共享 robots 事实为 `not-found`。按最新裁决，`robots:not-found` 不阻断采集和采集库写入；raw、stage 保留，候选应写为 `deferred`，原因 `robots:not-found`。当前分支的 blocked 17 是现有代码按旧 robots 策略产生的计数，尚未按新口径重跑。404 仍不表示获得授权。会员、商城和购买链接继续排除，站点版权保留，业务发布前仍需审核。

证据位置：`C:\Users\lixKR\AppData\Local\Temp\crawler-live-feiyiw-8d6c32a525d14b609cde84046394d4b4\download`。

## 重试条件

项目负责人已裁决 `not-found` 不阻断采集。解除条件改为：按新口径重跑 5 条列表加 5 条详情，确认候选状态为 `deferred`，并保留 `robots:not-found` 原因。
