# nongmuhr Scrapy 小样本验证

日期: 2026-10-21

验收结论: approved

运行结果: succeeded

## 列表

- URL: `http://nongmuhr.com/Employ.aspx`
- 取得时间: `2026-10-21T21:47:14+08:00`
- HTTP: `200`
- Content-Type: `text/html; charset=utf-8`
- robots: `http://nongmuhr.com/robots.txt` 返回 `200`，结论为 `allowed`
- 解析结果: 10 条岗位
- 关键选择器: `#joblist_table div.joblist_showlist`、`td.joblist_jobname a`、`td.joblist_a a[id^="rptList_hlCompany_"]`、`div.fontover_hide.width_105`

## 详情

以下 5 条详情均返回 `200`，Content-Type 为 `text/html; charset=utf-8`：

| 岗位 ID | URL | 取得时间 |
| --- | --- | --- |
| `13553` | `http://nongmuhr.com/EmployView.aspx?Id=13553` | `2026-10-21T21:48:02+08:00` |
| `13556` | `http://nongmuhr.com/EmployView.aspx?Id=13556` | `2026-10-21T21:48:02+08:00` |
| `13555` | `http://nongmuhr.com/EmployView.aspx?Id=13555` | `2026-10-21T21:48:02+08:00` |
| `13554` | `http://nongmuhr.com/EmployView.aspx?Id=13554` | `2026-10-21T21:48:02+08:00` |
| `13561` | `http://nongmuhr.com/EmployView.aspx?Id=13561` | `2026-10-21T21:48:03+08:00` |

关键选择器:

- 岗位名称: `#joblist .joblistonelf`
- 公司名称和公司链接: `#joblist #hlCompanyName`
- 字段表: 中文标签 `td` 的相邻 `td`
- 职位描述: `职位描述及具体要求：` 所在行之后的 `td[style*="word-break"]`
- 公司行业、规模和性质: `#joblist1 td.y12x`

5 条详情均成功读取标题、公司、地点、招聘人数、截止日期、发布时间和职位描述。旧 `#project_L` 不存在，实现已移除该依赖。

## 运行计数

- 运行模式: live
- run_id: `nongmuhr-aa6ff5a1c2d34d6b8940e34c2efd9b28`
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

- 运行报告: `C:\Users\lixKR\AppData\Local\Temp\crawler-130-scrapy-live-ddae9bc9078b4be8bd76387c0e736fa9\reports\nongmuhr-aa6ff5a1c2d34d6b8940e34c2efd9b28.json`
- 原始证据目录: `C:\Users\lixKR\AppData\Local\Temp\crawler-130-scrapy-live-ddae9bc9078b4be8bd76387c0e736fa9\download`
- 列表 SHA-256: `B0B9AF635BA338B992DA9875DD1E7845B319C551A92DC5A2D2CF6A76827144C5`
- 详情 SHA-256: `41BFEB30C5AB598EAAEFDEBD324F44C798351677025183A30578B6FC4B6798DD`、`91A31C7670D6EF94D813D0508217977F022D1D0A2A3F681CFABDF34D84F2010F`、`71D5B56E57FC0771B5D0518194629B889E621B3037385E5079D85ACDDB9422B5`、`144F75D5EDF99AC33385D27C08D8E2A0F8A91C95E52AF6751FDF5FCABE5DC753`、`3EF339AFDF69A481F836DD6DF11DFAB68CCF1A963F98B8035810523BDCE6EBCB`

原始 HTML 含公开联系方式和页面全文，不进入公开仓库。验收文档只保留 URL、时间、状态、选择器、计数、哈希和字段摘要。

## 剩余风险

- 5 个样本的截止日期均早于本次验证日期，列表仍展示这些岗位；过期岗位的业务展示规则不在本票据范围。
- 本轮只验证默认列表页和 5 条详情，未全量遍历约 903 个分页索引。
- 站点结构或编码变化后需要重新运行本样本。
