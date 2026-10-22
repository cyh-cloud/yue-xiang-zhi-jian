# aqsc-moa Scrapy 文件小样本验证

日期: 2026-10-21

run_id: `crawler-132-aqsc-live-20261021`

验收结论: blocked

运行结果: partial

## 真实请求

- 发现页: `https://jgs.moa.gov.cn/rzde/202509/t20250908_6477077.htm`
- 发现页 HTTP: `200`，`text/html`，50,830 bytes
- 发现页 SHA-256: `74466176dc5730b9c95c2845c25af2401cd65270ac9dbce3e82aab65e9385929`
- 发现页取得时间: `2026-10-21 23:05:32 Asia/Shanghai`
- robots: `https://jgs.moa.gov.cn/robots.txt` 返回 `404`，结论 `not-found`
- 公告页: `http://www.aqsc.agri.cn/tzgg/202508/t20250806_463294.htm`
- 公告页 HTTP: `200`，`text/html`，14,288 bytes
- 公告页 SHA-256: `42ed9a89451479a2bc0784809d70d9072274432e07cf748fa47517323459d0b3`
- 公告页取得时间: `2026-10-21 23:05:33 Asia/Shanghai`
- 附件 URL: `http://www.aqsc.agri.cn/tzgg/202508/P020250821548932446299.xlsx`
- 附件 HTTP: `403`，`text/html`，15,781 bytes
- 附件 SHA-256: `217778d44932469520ef613e78fcad75fad6f3b780f88d01f481981ab36d78c5`
- 附件取得时间: `2026-10-21 23:05:34 Asia/Shanghai`
- robots: `http://www.aqsc.agri.cn/robots.txt` 返回 `403`，结论 `unknown`

公告页发现和附件链接解析成功，XLSX 下载被 WAF 403 阻断。当前运行保留了 403 响应的错误诊断，但不会把它保存为有效附件正文：`raw_fetches` 记录 403 状态和错误信息，附件对应的 `raw_files` 仅记录 `download_status=http_error` 的文件级元数据，`file_path` 和 `sha256` 为空，MIME 仍如实记录为 `text/html`。真实 Spider 将记录写成 blocked 证据，没有把 403 页面当作 XLSX，也没有尝试绕过访问限制。

## 计数

- raw: 3
- raw_files 错误诊断: 1 条 `download_status=http_error`，不是有效 XLSX
- stage: 1
- 候选标准实体: 0
- blocked: 1
- deferred: 0
- failed/failure_count: 1
- failure_reason: `HTTP 403: http://www.aqsc.agri.cn/tzgg/202508/P020250821548932446299.xlsx`

## Fixture 回放

公开 fixture 通过真实 Spider、robots middleware、raw middleware、Pipeline 和采集运行时回放：

- raw: 5
- XLSX 附件: 2
- stage: 8
- deferred 候选: 8
- 每个候选保留 `sheet=Sheet1; row=<n>; seq=<n>` locator
- `detail_url=null`，`detail_url_status=missing`
- 公告页作为 `long_term_url`，附件 URL 作为 `source_url`

100MB 上限使用声明大小 `104857601` bytes 的 fixture 响应验证，`raw_files.download_status=oversize`，只写 `OVERSIZE.md`，不保存响应正文。

证据位置：`../crawler-live-evidence/issue-133-20261021/aqsc-moa/`。公开索引为 `crawler/docs/operations/live-evidence-index.json`。

## 解除条件

- `www.aqsc.agri.cn/robots.txt` 不再返回 403，或项目负责人给出可复核的访问裁决。
- 公告详情和 XLSX 附件在不绕过访问控制的前提下返回 200。
- 重跑后确认 raw、stage、XLSX 文件大小与 SHA-256、工作表行 locator 和 deferred 候选计数。

在这些条件满足前，aqsc-moa 的真实文件解析保持 blocked，fixture 结果不写成 live 成功。
