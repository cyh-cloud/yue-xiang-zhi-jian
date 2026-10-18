# 国家知识产权局地理标志 审核记录

来源 ID: `cnipa`

审核时间: `2026-10-19 01:53 Asia/Shanghai`

审核结论: `approved-with-gaps`

## 审核范围

- 待审文档: `crawler/docs/sources/cnipa.md`
- 审核者: 来源审核 agent
- 复核方式: 独立使用 `requests` 实际 HTTP GET 与 Playwright Chromium 重开栏目首页、`col1400`、`col1399`、公告详情、检索首页、`search/init`、`search/list`、`search/detail`、检索详情页和样本 PDF；用 Playwright 操作免责声明、关键词查询和结果详情，逐项核对字段、分页、附件的可访问性与哈希

## 逐项结论

| 项目 | 结论 | 证据 |
| --- | --- | --- |
| 入口 URL | 通过 | `col1388`、`col1400`、`col1399`、两个样本公告详情均返回 `200`；`dbQuery`、`search/init`、`search/list`、`search/detail` 和 `detail?id=...` 均返回 `200`，接口内容类型为 JSON |
| 列表页与分页 | 通过（有描述修正） | `search/list` 的 `type=1` 为 `495` 条，`type=2` 为 `42` 条，合计 `537`；`limit=100` 时 type 1 共 5 页、type 2 共 1 页，最后一页分别为 95 条和 42 条。`col1400` 页面实际显示“共 41 条、3 页、每页 15 条”，但必须通过浏览器执行分页脚本；纯 HTTP 的 `?uid=4536&pageNum=2` 仍返回第 1 页，文档把“分页参数”写得像服务端参数，需注明是前端脚本分页 |
| 详情页 URL | 通过 | 检索详情 URL 的 3 条样本均返回 `200`；查询 `黄骅` 能从 `dbQuery` 结果打开 `detail?id=513&name=...`，页面标题显示“黄骅梭子蟹…（第539号）.pdf”。`id=58`、`513`、`541` 的 `search/detail` 均返回 `success=true` |
| JSON 字段或 DOM 选择器 | 通过（有缺口） | `init.data` 的 `"1"`、`"2"` 各 5 条，字段 `id/name/announcement/coding/type/isDeleted` 可读；`list.data.count`、`list.data.data`、`detail.data` 可复现。Playwright 在 `dbQuery` 接受免责声明后确认 `input[placeholder="关键词搜索"]`、`.policyAnswersItem`、`.el-pagination` 均存在；`.policyAnswersItem` 的结果通过点击新建详情标签页。栏目 `.ulist li a`、`.ulist li span`、`.index_title`、`.index_time`、`.index_art_con` 在真实页有效。文档的 `.ulist li` 选择器会把分页数字 `li` 一并选中，应改用 `.ulist li a` 或限定带日期的行 |
| 样本记录 | 通过（有 1 处日期/字段需注意） | 样本 1 `id=58`：公告标题、`2009年第89号`、PDF 7 页、正文中的白蕉海鲈保护范围与“广东省珠海市斗门区”可复现，落款“二〇〇九年九月二十一日”可复现；样本 2 `id=513`：第539号、`2023-08-01` 落款、黄骅梭子蟹、申请机构和南排河镇保护范围可复现；样本 3 `id=541`：第687号、`2026-08-03`、临晋江石榴、山西省临猗县 6 个乡镇可复现，PDF 第 2 页表格和第 29 页保护要求可解析。样本 3 的 `栏目发布日期 2026-08-12` 与 PDF 落款日期分开保存，文档方向正确 |
| 字段映射 | 有缺口 | 业务表 `agri_certified_products`、`agri_product_sources` 与冻结 schema 一致；但 std 层文档使用 `agri_certified_products`、`agri_product_sources` 作为“来源字段 / std 字段”，而冻结 schema 是 `std_agri_products`、`std_agri_product_sources`。文档还写 `agri_product_sources.exclusion_reason` / `batch_label` / `attachment_url`，这些不是 `std_agri_product_sources` 的冻结字段（`source_title`、`source_product_name`、`source_region` 等才是），需要按 `crawler/docs/schema/crawler-db.md` 对齐 |
| 访问限制 | 通过（有边界） | `www.cnipa.gov.cn`、`ggfw.cnipa.gov.cn` 的检索与公告页面匿名可访问；`dbQuery` 首屏有免责声明弹窗，Playwright 接受后可查；接口本身未发现登录门槛。`/robots.txt` 在 `www` 返回 `404`，在 `ggfw` 返回 HTML 单页应用或壳页，不构成有效 robots 文件；文档已如实写出，但不能据此扩大为“无任何限制” |
| 版权与用途 | 通过（有边界） | `www` 公告页实际显示“版权所有：国家知识产权局”，检索系统页面显示“主办单位 : 国家知识产权局”“版权所有 : 国家知识产权局”；未见开放许可声明。文档只做结构化字段、短摘要和原文链接的发布策略可保留，原文快照与对外发布需分开审批 |
| 下载记录 | 通过（有缺口） | 三份本地 PDF 与远端重新获取的文件哈希一致：`2009年第89号.pdf` 为 `250,603` 字节 / `6535b57a...`、第687号 PDF 为 `1,174,529` 字节 / `1d1e5e10...`、`www-cnipa-539.pdf` 为 `484,164` 字节 / `6a6e42ca...`；目录 `crawler/download/ggfw.cnipa.gov.cn` 有 README 和样本，三份文件均小于 100MB。缺口是 `download/ggfw.cnipa.gov.cn/samples.json` 保存了约 5 小时有效的签名 URL，签名 URL 本身不应作为长期来源；README 已说明，但保存原始签名链接仍有泄露和误导风险，后续应只保留请求元数据、PDF 路径与哈希 |

## 发现的问题

- `col1400` 的实际分页不是服务端 `?uid=4536&pageNum=2` 直接返回第 2 页。Playwright 打开 `?uid=4536&pageNum=2` 后仍显示第 1 页数据，需点击页面分页器或执行 jpage 脚本才切换到第 2 页；文档应把“前端分页 + 脚本状态”作为契约，而不是只列 URL 参数。
- `.ulist li` 在 `col1400` 的第 2、3 页还会把分页数字 `1`、`2`、`3` 作为 `li` 返回；文档的“公告列表项 `.ulist li`”不是安全选择器。应改为 `.ulist li a` 取标题，并与 `.ulist li span` 的日期按行配对，或限定有锚点的 `li`。
- `https://www.cnipa.gov.cn/module/download/downfile.jsp?classid=0&showname={name}.pdf&filename={hash}.pdf` 只在 `showname` 和 `filename` 匹配真实附件时返回 PDF；任意占位名会返回 `text/html` 空响应。文档中的 URL 模板不能直接用于探测，必须从公告 `.index_art_con` 提取真实 `href`。
- `search/detail?id=513` 返回的临时 PDF 路径是 `/approval/old/%E7%AC%AC539%E5%8F%B7.pdf`，而不是文档附件表写的 `www-cnipa-539.pdf` 文件名；本地 `www-cnipa-539.pdf` 来自国家知识产权局 `down.jsp?i_ID=186731&colID=1400`，两组来源身份需要分开记录。
- 文档说 `col1400` 有 41 条、每页 15 条，但实际页面 DOM 第 1 页只有 15 个带标题的 `a`，`.ulist li` 总数还包含分页数字；抓取器若用 `li` 计数会把条数算错。实际“共 41 条 / 3 页”由分页区域文本确认，本次浏览器复核一致。
- `samples.json` 保存了 `X-Amz-Credential`、`X-Amz-Signature` 等临时签名参数。这些不是账号密码，但属于短期访问凭证；在文档中可保留“签名字段名”和有效期，不应把完整签名 URL 作为 samples 长期样例。
- 文档把 std 字段写成 `agri_*`，与冻结 schema 的 `std_agri_*` 不一致；`exclusion_reason` 在业务目标表存在，但不是 `std_agri_product_sources` 的字段，不能同时写成 std 字段和业务字段。
- 水产品覆盖在公告标题层面可复现：`type=1` 列表标题含鱼、虾、蟹、贝、藻、海参、鲍鱼等样本，`type=2` 可查到黄骅梭子蟹；但这只是“公告标题命中”，不是“产品级全量覆盖”。产品级完整目录必须解析 PDF 表格后才能证明，文档已将它列为限制，审核不把它当作已完成的覆盖率结论。
- PDF 签名验证成立：三条详情接口均返回 `X-Amz-Expires=18000`，签名参数齐全；去掉签名返回 `403 AccessDenied`，改成 1 秒返回 `403 ExpiredSignature`。文档可保留此结论，但 samples 文件不应继续公开完整签名 URL。
- `col1400` 的 HTML 纯 HTTP 首屏只包含 `ulist` 中的 15 条记录和分页占位，分页切换依赖 `dataproxy.jsp`/jpage 脚本；文档未写出这一层，后续调度器直接按 `pageNum` 请求会得到重复第 1 页。

## 必须补齐

- 将 `col1400` 的分页说明改为“前端 jpage 分页”，并写明可执行的初始化/翻页方式；至少补充 `dataproxy.jsp` 请求或 Playwright 点击 `.ui-pager` 的契约，以及每页 15 条、共 41 条、3 页的实测结果。
- 将所有列表选择器改为带锚点的 `.ulist li a` 或“包含 `a` 的 `li`”，并把日期与标题按同一行的 `span` 配对，避免分页数字进入记录集合。
- 把附件下载入口改为“先解析公告 `.index_art_con` 中的真实链接，不得拼接 `showname/filename` 探测”；对 `downfile.jsp` 的非 PDF 响应明确判失败。
- 将 `search/detail?id=513` 的临时 `/approval/old/第539号.pdf` 与 `www-cnipa-539.pdf` 的来源 URL 分列，说明后者来自 `down.jsp?i_ID=186731&colID=1400`，不能用同一文件名覆盖。
- 将 std 映射统一为 `std_agri_products`、`std_agri_product_sources`；把 `source_title`、`source_product_name`、`source_region`、`source_item_id` 等按冻结 schema 改名，业务侧再映射到 `agri_product_sources`。
- 从 `download/ggfw.cnipa.gov.cn/samples.json` 移除或替换完整签名 URL，只保留 ID、请求路径、`X-Amz-Expires`、获取时间、文件哈希和“需重新调用 detail 接口”的说明；若必须保留响应样本，应删去 `X-Amz-Credential` 与 `X-Amz-Signature`。
- 补充 `col1400` 和检索系统两套公告源的覆盖范围差异：栏目 41 条只覆盖产品认定公告栏目，检索 `type=1/2` 共 537 条包含旧公告与新公告，不能把 41 当作全量公告数。

## 可后续处理

- 解析全部 537 条公告 PDF 的产品行，统计真正的水产品数量、类别和地区覆盖率；当前只能确认公告标题层面存在鱼虾蟹贝藻等候选，以及 3 条样本可复现。
- 对 `col1400` 的 3 页逐页用浏览器点击核验 15+15+11 条与“共 41 条”的一致性，并把实际 href 和日期写入下载记录或样本说明。
- 为所有已下载 PDF 补充重下载校验、取得时间和 raw 层响应快照；当前三份文件的大小和 SHA-256 已一致，但 samples 中的临时签名需要脱敏。
- 评估检索系统免责声明弹窗的长期可自动化性；若站方调整弹窗或 SPA 路由，采集器应以 `search/init` 和 `search/list` 为主，不依赖弹窗状态。
