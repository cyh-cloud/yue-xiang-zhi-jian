# nongmuhr Scrapy 小样本验证

日期: 2026-10-21

验收结论: approved

运行结果: succeeded

证据范围: live 外部证据，公开 fixture 仅覆盖 2 条详情

## 实际重跑

- run_id: `nongmuhr-3b01c369718c47d2a690284f939a5791`
- 归档位置: `../crawler-live-evidence/issue-133-20261021/nongmuhr/`
- 列表 URL: `http://nongmuhr.com/Employ.aspx`
- 列表取得时间: `2026-10-21 23:28:48 Asia/Shanghai`
- 列表 HTTP: `200`
- Content-Type: `text/html; charset=utf-8`
- robots: `http://nongmuhr.com/robots.txt` 返回 `200`，结论为 `allowed`
- 解析结果: 10 条岗位

关键选择器:

- `#joblist_table div.joblist_showlist`
- `td.joblist_jobname a`
- `td.joblist_a a[id^="rptList_hlCompany_"]`
- `div.fontover_hide.width_105`

## 详情

本节 10 条结论来自 2026-10-21 的 live 外部运行，不是公开 fixture 回放结论。仓库内 `crawler/tests/fixtures/evidence/nongmuhr/` 只覆盖 2 条脱敏详情；live 证据保留在仓库外的归档目录。

以下 10 条详情均返回 `200`，Content-Type 为 `text/html; charset=utf-8`：

| 岗位 ID | URL | 取得时间 |
| --- | --- | --- |
| `13563` | `http://nongmuhr.com/EmployView.aspx?Id=13563` | `2026-10-21 23:28:49 Asia/Shanghai` |
| `13564` | `http://nongmuhr.com/EmployView.aspx?Id=13564` | `2026-10-21 23:28:51 Asia/Shanghai` |
| `13565` | `http://nongmuhr.com/EmployView.aspx?Id=13565` | `2026-10-21 23:28:52 Asia/Shanghai` |
| `13557` | `http://nongmuhr.com/EmployView.aspx?Id=13557` | `2026-10-21 23:28:53 Asia/Shanghai` |
| `13560` | `http://nongmuhr.com/EmployView.aspx?Id=13560` | `2026-10-21 23:28:54 Asia/Shanghai` |
| `13561` | `http://nongmuhr.com/EmployView.aspx?Id=13561` | `2026-10-21 23:28:55 Asia/Shanghai` |
| `13554` | `http://nongmuhr.com/EmployView.aspx?Id=13554` | `2026-10-21 23:28:56 Asia/Shanghai` |
| `13555` | `http://nongmuhr.com/EmployView.aspx?Id=13555` | `2026-10-21 23:28:58 Asia/Shanghai` |
| `13556` | `http://nongmuhr.com/EmployView.aspx?Id=13556` | `2026-10-21 23:28:59 Asia/Shanghai` |
| `13553` | `http://nongmuhr.com/EmployView.aspx?Id=13553` | `2026-10-21 23:29:00 Asia/Shanghai` |

关键选择器:

- 岗位名称: `#joblist .joblistonelf`
- 公司名称和公司链接: `#joblist #hlCompanyName`
- 字段表: 中文标签 `td` 的相邻 `td`
- 职位描述: `职位描述及具体要求：` 所在行之后的 `td[style*="word-break"]`
- 公司行业、规模和性质: `#joblist1 td.y12x`

10 条详情均成功读取标题、公司、地点、招聘人数、截止日期、发布时间和职位描述。旧 `#project_L` 不存在，实现已移除该依赖。

## 运行计数

- 运行模式: live
- discovered: 10
- raw: 11
- stage: 10
- 候选标准实体: 10
- candidate: 10
- deferred: 0
- blocked: 0
- skipped: 0
- failed/failure_count: 0
- status: `succeeded`

## 证据

- 公开索引: `crawler/docs/operations/live-evidence-index.json`
- 运行报告: `nongmuhr/reports/nongmuhr-3b01c369718c47d2a690284f939a5791.json`
- 原始证据目录: `nongmuhr/download/`
- 原始 HTML 含公开联系方式和页面全文，不进入公开仓库。验收文档只保留 URL、时间、状态、选择器、计数、哈希和字段摘要。

## 剩余风险

- 样本截止日期早于本次验证日期，列表仍展示这些岗位；过期岗位的业务展示规则不在本票据范围。
- 本轮只验证默认列表页和 10 条详情，未全量遍历约 903 个分页索引。
- 站点结构或编码变化后需要重新运行本样本。
