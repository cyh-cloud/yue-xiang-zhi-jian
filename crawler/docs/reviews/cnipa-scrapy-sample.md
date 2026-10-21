# cnipa Scrapy 文件小样本验证

日期: 2026-10-21

验收结论: approved-with-gaps

运行结果: partial

## 真实请求

- 公告页: `https://www.cnipa.gov.cn/art/2026/8/12/art_1400_207705.html`
- 公告页 HTTP: `200`，`text/html; charset=UTF-8`，10,285 bytes
- 公告页 SHA-256: `90b29f7f4acc8186592d67a0d8b01d5a1286fd0a55535019ad987826bd3def06`
- 公告页取得时间: `2026-10-21 23:05:15 Asia/Shanghai`
- 附件 URL: `https://www.cnipa.gov.cn/module/download/downfile.jsp?classid=0&showname=1.%20%E4%B8%B4%E6%99%8B%E6%B1%9F%E7%9F%B3%E6%A6%B4%E7%AD%8958%E4%B8%AA%E5%9C%B0%E7%90%86%E6%A0%87%E5%BF%97%E4%BA%A7%E5%93%81%E5%85%AC%E5%91%8A%E4%BF%A1%E6%81%AF.pdf&filename=3cfd39dcf464453fb750f6101910585d.pdf`
- 附件 HTTP: `200`，`application/pdf;charset=UTF-8`，428,298 bytes
- 附件文件名: `1. 临晋江石榴等58个地理标志产品公告信息.pdf`
- 附件 SHA-256: `1f6c48cddda9acb3b5da658097beb23557c413ceb67029cc9ecb877c68d66c39`
- 附件取得时间: `2026-10-21 23:05:16 Asia/Shanghai`
- PDF 页数: 28
- robots: `https://www.cnipa.gov.cn/robots.txt` 返回 `404`，结论 `not-found`
- `https://ggfw.cnipa.gov.cn/robots.txt` 返回 200 HTML 壳页，结论 `unknown`，本样本没有使用该域

公告页是长期承载页。附件 URL 是稳定下载入口，不含 `X-Amz-*` 临时签名参数。

## 计数

- raw: 2
- raw PDF 文件: 1
- stage: 58
- 候选标准实体: 58
- candidate: 0
- deferred: 58
- blocked: 0
- failed/failure_count: 0
- candidate_reason: `robots:not-found`

58 条产品行均保留 `pdf=<文件名>; page=<n>; row=<n>; seq=<n>` locator，`detail_url=null`，`detail_url_status=missing`。公告页写入 `long_term_url`，附件 URL 写入 `source_url` 和 `fetch_url`。

## Fixture 回放

公开合成 PDF 通过真实 Spider、robots middleware、raw middleware、Pipeline 和采集运行时回放：

- raw: 3
- PDF 附件: 1
- stage: 2
- deferred 候选: 2
- locator 覆盖 `page=1; row=1; seq=1` 和 `page=2; row=1; seq=2`
- 临时签名 URL 不进入 stage 或候选长期字段

证据位置：`C:\Users\lixKR\AppData\Local\Temp\crawler-live-cnipa-c7a51b28e5234207918a50973292bdc8\download`。

## 剩余风险

- `ggfw.cnipa.gov.cn` 的 robots 仍是 `unknown`，需要签名 PDF 的路径不得写成允许采集。
- 当前样本只验证 `www.cnipa.gov.cn` 公告页的第一份产品信息 PDF，未覆盖第二份保护要求 PDF。
- PDF 文字层和表格列顺序可能随公告变化，候选仍需发布审核。
- robots 404 只表示没有取得允许规则，不构成发布授权。
