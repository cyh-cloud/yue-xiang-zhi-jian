# nongmuhr Scrapy 小样本验证

日期: 2026-10-21

验收结论: blocked

运行结果: failed

## 列表

- URL: `http://nongmuhr.com/Employ.aspx`
- 取得时间: `2026-10-21T05:12:00+08:00`
- HTTP: `200`
- robots: `http://nongmuhr.com/robots.txt` 返回 `200`，结论为 `allowed`
- 详情请求: 10 条
- 样本 ID: `13545`、`13546`、`13540`、`13541`、`13542`

## 详情

前 5 条详情 URL 均返回 `200`：

- `http://nongmuhr.com/EmployView.aspx?Id=13545`
- `http://nongmuhr.com/EmployView.aspx?Id=13546`
- `http://nongmuhr.com/EmployView.aspx?Id=13540`
- `http://nongmuhr.com/EmployView.aspx?Id=13541`
- `http://nongmuhr.com/EmployView.aspx?Id=13542`

取得时间：`2026-10-21T05:12:02+08:00` 至 `2026-10-21T05:12:13+08:00`。

## 计数

- raw: 11
- stage: 0
- 候选标准实体: 0
- blocked: 0
- failed/failure_count: 10
- failure_reason: `AttributeError: 'NoneType' object has no attribute 'select'`（10 次）

## 失败摘要

10 条详情均返回 `200`，但实现使用的 `#project_L` 容器不存在，`parse_job_detail` 访问字段容器时触发 `AttributeError: 'NoneType' object has no attribute 'select'`。这是代码和文档沿用了未经验证的旧结构，属于真实解析失败。运行报告状态是 `failed`，因为 10 次解析异常都计入 `failure_count`；候选状态是 `blocked`，因为数据不完整。这不是 robots 合规阻断，也不能把导航菜单的 `li` 当作岗位字段。

证据位置：`C:\Users\lixKR\AppData\Local\Temp\crawler-live-nongmuhr-2907e74ff22a4579bd820034a29d05e0\download`。

## 解除条件

- 先重新抓取真实列表页和至少 5 条详情页，记录实际 DOM、HTTP 状态和取得时间。
- 用真实结构更新 `crawler/docs/sources/nongmuhr.md`，在验证前不得把 `#project_L` 继续写成权威选择器。
- 根据更新后的文档修改 parser 和 fixture，再重跑 5 条列表加 5 条详情，确认至少标题、地点、有效期、招聘人数和发布日期可读。
- 在此之前只保留离线 fixture 和接口测试结论，不报告 live 成功。
