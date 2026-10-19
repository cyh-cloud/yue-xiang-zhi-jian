# 中国非物质文化遗产网 审核记录

来源 ID: `ihchina`

审核时间: `2026-10-19 01:53 Asia/Shanghai`

审核结论: `approved-with-gaps`

权利状态: `attribution-required`

## 审核范围

- 待审文档: `crawler/docs/sources/ihchina.md`
- 审核者: 来源审核 agent
- 复核方式: 独立使用 `requests` 实际 HTTP GET 与 Playwright Chromium 重开首页、`/project`、列表 JSON、详情页、传承人页、资讯/学术页、版权声明和 robots；逐项执行文档中的 JSON 字段与 DOM 选择器检查。未采用实现 agent 的结论作为证据

## 逐项结论

| 项目 | 结论 | 证据 |
| --- | --- | --- |
| 入口 URL | 通过 | 2026-10-19 复核首页、`/project` 均返回 `200`；首页与列表页可正常渲染，列表页标题为“国家级非物质文化遗产代表性项目名录” |
| 列表页与分页 | 通过 | 默认接口 `category_id=16&limit=10&p=1` 返回 `total=3610`、`count=3610`、`links.total_pages=361`；第 1 页 10 条，第 361 页 10 条（`23622` 至 `23631`），第 362 页返回 `200` 且无 `list`。`limit=1/50/100` 分别返回 1/50/100 条，`links.total_pages` 随 limit 变化。广东筛选 `province=440000` 返回 `165` 条，关键词“粤剧”返回 `7` 条，省略 `category_id` 返回 `4234` 条 |
| 详情页 URL | 通过 | `12178`、`23632`、`ccr_detail/716`、`ccr_detail/29840` 均返回 `200`；`12178` 与 `23632` 的 8 个基本信息键值、标题和正文均可定位 |
| JSON 字段或 DOM 选择器 | 通过（有 1 个缺口） | 列表顶层 `total/count/p/more/links/show/list/pa` 与文档一致；`list[]` 的 `id/title/title2/auto_id/num/num_first/num_sec/project_num/type/cate/rx_time/address/province/city/area/unit/protect_unit/content/modified/status...` 均可读到。Playwright 确认 `.num-box .b[data-rn]` 第 4 项为 `3610`、`#table th` 9 列、`.tit .col` 为 `3610`、`.page-box` 和 `input[name="total_pages"]` 存在。详情 `.article-mod2 .t_head .h30`、`.article-mod2 .table .p`、`.article-mod2 .text .p`、`.inherit_xx2 .list` 可用；相关项目选择器 `.inherit_xx2 .x-tables table:nth-of-type(2)` 实测为空，实际第 2 个 `.x-tables` 内可直接取 `table`，但 `nth-of-type` 写法与真实 DOM 层级不匹配。资讯/学术详情页选择器在 `Article/Index/detail?id=28021` 上有效，编辑节点应写 `.article-nav`，不是 `.newsdetails2 .article-nav` |
| 样本记录 | 通过（有细节缺口） | 样本 1 `12178` 苗族古歌的全部关键字段、5 名传承人、3 个相关项目和 5 条资讯、5 条学术可复现；样本 2 `23632` 的标题、8 个基本信息、1 名传承人、3 个相关项目、无资讯/学术区块可复现。样本 2 正文实测纯文本为约 845 字（不同空白归一方式可得 848 字），文档写 `851`。辅助样本 `ccr_detail/716` 王安江的序号、性别、出生日期、民族、类别、项目编号、项目名称和申报地区均可复现 |
| 字段映射 | 通过 | 文档已统一使用 `std_ich_projects`、`std_ich_inheritors`、`std_ich_related_items`、`std_ich_media_links`；`project_serial`、`source_project_num` 与冻结 schema 对齐 |
| 访问限制 | 通过 | 列表接口、项目详情、传承人页、资讯/学术页和版权声明均匿名可访问；`/robots.txt` 实测返回 `404`，不能解释为授权；`/login` 返回 `404`，未发现登录门槛；本轮未使用账号、Cookie 或绕过访问控制 |
| 版权与用途 | 通过（有边界） | `about/206.html` 实际写明站内文字、图片、音视频的著作权归网站，未经事先书面授权不得用于商业用途，转载、引用、摘编、下载或其他复制使用时须注明作者并标明来源，未经授权不得修改。文档把“采集库保存公开内容和原始响应”与“业务库只发布基础字段和必要短摘要”分开，方向正确；但业务上线前仍应把“内部回溯保存”和“对外展示”分别审批 |
| 下载记录 | 有缺口 | 本次未发现必须依赖的列表或详情附件，文档写“无”与当前事实一致；但没有任何 raw 响应、详情 HTML、JSON 或 robots 响应的大小、SHA-256、取得时间和保存位置记录。审核只能确认来源没有公开附件，不能完成文档验收所需的下载与哈希核对 |

## 发现的问题

- 历史发现（已处理）：相关项目选择器 `.inherit_xx2 .x-tables table:nth-of-type(2)` 曾返回 0 条；现已按第 2 个 `.x-tables` 容器读取。
- 历史发现（已处理）：资讯/学术编辑字段曾写成 `.newsdetails2 .article-nav`；现统一使用 `.article-nav`。
- 历史发现（已处理）：样本 2 正文长度不再作为固定断言，解析器只保存归一后的纯文本和哈希。
- 字段映射已统一为 `std_ich_projects`、`std_ich_inheritors`、`std_ich_related_items` 和 `std_ich_media_links`，与冻结 schema 一致。
- 文档把 `/project` 描述为“前端壳页”，但真实静态 HTML 已包含表头、筛选选项和分页器骨架；数据行和统计值由 AJAX 填充。这个描述不影响实现，但会让 DOM 回退验证误判为“必须等前端渲染后才能取选择器”。
- 列表 JSON 的 `links.pages` 和 `links.down` 等 URL 使用 `/getProject/category_id/16/limit/10/p/...html` 形式，而文档入口表只列了查询串形式。采集器应把查询串作为请求契约，不要直接把 `links` 返回的路径当唯一入口。
- 相关资讯和相关学术每个详情页最多展示 5 条且没有区块分页；文档已承认这是“可见样本”而非全量，但清洗逻辑必须保留 `body_saved` / 可见性标记，不能把 5 条当成完整关联集合。
- 文档的“已实际返回 200”覆盖了入口和样本，但没有记录列表第 1 页、第 361 页之外的逐页全量拉取；本次也未能证明 361 页累计去重后严格等于 3610。该缺口不阻塞字段和样本审核，但阻塞“已全量可复现”的强声明。

## 必须补齐

- 已完成：相关项目解析按 `.inherit_xx2 .x-tables` 第 2 个容器读取，不再使用错误的 `nth-of-type(2)`。
- 已完成：资讯/学术编辑字段使用实际可命中的 `.article-nav`。
- 已完成：样本 2 正文长度改为归一规则描述，实现不使用固定字数断言。
- 已完成：四张 std 表统一为冻结的 `std_ich_*` 名称。
- 已完成离线 fixture：列表 JSON、项目详情、传承人详情和关联区块进入 raw/stage 测试。真实 3610 详情页的全量 raw 证据仍为 `deferred`，解除条件是完成真实全量详情运行并保存分层样本。
- 已完成：列表入口统一使用查询串，`links` 路径只作为分页参考。

## 可后续处理

- 对 361 页执行一次全量分页累计、ID 去重计数和 `modified` 分布检查，再决定是否把“3610 子项全量可复现”写成 `approved`。
- 抽查传承人独立列表与项目详情中的传承人集合差异，确认 `/art/representative.html` 是否有独立分页参数或页面脚本所需状态。
- 继续验证正文图片、视频、音频和 iframe 的可访问性；本次样本 `12178`、`23632` 未发现正文图片或有效媒体地址，不应把空媒体容器写成有资源。

## 2026-10-20 修复复核

- 已实现离线项目详情和传承人详情遍历：fixture 可提供 `details[id].html` 与 `details[id].inheritors`，运行入口会保存独立 raw 证据，并把传承人、相关项目、相关资讯和媒体链接写入 stage `extra.detail`。
- 真实网络模式也按项目详情和传承人链接逐条请求，失败保留 raw 证据并计入错误摘要。
- 真实 3610 详情全量运行、独立传承人列表完整性和媒体可播放性未在离线环境验证，保持 `deferred`，不声称已解决。
