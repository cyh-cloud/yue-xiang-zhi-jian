# CnOpenData 方言与非遗数据 审核记录

来源 ID: `cnopendata`

审核时间: `2026-10-19 01:45 Asia/Shanghai`

审核结论: `approved-with-gaps`

## 审核范围

- 待审文档: `crawler/docs/sources/cnopendata.md`
- 审核者: 来源审核 agent
- 复核方式: 独立 `requests` HTTP 与 Playwright Chromium；重开方言数据集、非遗数据集、API 商店、API 产品详情、登录页和下载配置，直接读取 robots、sitemap 与 `llms.txt`，核对公开数据集级样本、无行级样本、付费与登录边界

## 逐项结论

| 项目 | 结论 | 证据 |
| --- | --- | --- |
| 入口 URL | 通过 | 方言页、非遗页、API 商店及登录页均返回 200。Canonical 数据集路径是 `/data/m/culture/{slug}.html`，文档采用正确；不带 `/data/m` 的旧路径返回 404 |
| 列表页与分页 | 通过（有口径问题） | 数据集页不是列表页，无分页。API 商店页面正文显示 29 个已上架接口、5 个可见主题分类；RSC 载荷含 29 个产品、14 个分类键，其中两个键都叫“港股数据”，不能把 14 个键直接写成 14 个不同主题。文档写“13 个主题分类”与当前载荷不一致 |
| 详情页 URL | 通过 | 两个数据集级 URL 可直接打开；API 产品详情 `/api-store/ashare-daily-indicator` 返回 200。来源仍无行级方言点或非遗记录详情 URL |
| JSON 字段或 DOM 选择器 | 通过 | 两个数据集页均为 3 张字段表，字段名、类型和顺序可复现；方言页 3 个样本区均显示“暂无样本数据”。`h1`、字段表与页面文本可定位。RSC 中的 `hasSamples=true` 与页面样本区为空同时存在，文档已正确地把前者降级为非证据 |
| 样本记录 | 通过（仅数据集级） | 方言页标题“中国各地区方言信息数据”、时间区间“1986版与2012版”、3 张表及 9/8/10 字段结构可复现；非遗页标题、3 张表及 11/9/7 字段结构可复现。两页仍无可验证的行级样本 |
| 字段映射 | 有缺口 | 公开字段映射本身有页面依据，但文档使用 `std_dialect_points`、`std_ich_projects` 和 `stage_cnopendata_dataset` 等点分名称，与冻结 schema 的 `std_dialect_points`、`std_ich_projects` 以及现有 `stage_*` 命名不一致。文档也未说明这些 stage 表是建议新增还是已冻结 |
| 访问限制 | 通过（表述需修正） | 两类下载配置均返回 `hasPermission:false`、`requiresLogin:true`、`files:[]`；登录页要求邮箱/密码或微信扫码。公开页面正文可读，完整数据、订阅、下载和 API 受登录或购买约束。非遗页还显示可见的“OPEN”标签，不能据此推出完整数据可自由获取 |
| 版权与用途 | 通过（有缺口） | 页脚为“All rights reserved”；`llms.txt` 明确写明“名称不意味着所有数据免费、可自由再分发”，完整数据须遵守订阅、机构授权及使用协议。文档的“授权前不采集完整数据”结论成立，但对“OPEN”标签及学术版、商业版、企业定制版三种购买方案的边界写得不完整 |
| 下载记录 | 通过 | 本次未下载公开数据文件。两个数据集的下载配置均为空且要求登录，公开页未提供可下载样本；没有绕过付费墙、验证码或用户中心 |

## 发现的问题

- 文档“API 商店公开 13 个主题分类”与当前 RSC 载荷中的 14 个分类键不一致；可见侧栏只展示 5 个主题，且“港股数据”在分类键中重复。应区分“产品条目数”“分类键数”“页面可见主题数”，不能混用。
- 非遗数据集页实际显示“OPEN”标签，同时样本区为“暂无样本数据”、下载配置要求登录。文档没有记录这一表面的开放性标签与真实付费、登录边界之间的差异，容易让后续实现把“OPEN”误解为开放许可。
- 两个数据集页都提供“商业分析版 / 学术研究版 / 企业定制版”三类购买方案，分别出现“商业使用授权”“学术引用授权”“全量数据本地部署”等文字。文档概括为“需要登录、购买或联系销售”方向正确，但没有把授权类型写进访问边界，授权范围仍需合同确认。
- 文档中的点分表名 `std_dialect_points`、`std_ich_projects`、`stage_cnopendata_dataset` 无法直接对应冻结 schema。当前 schema 使用 `std_dialect_points`、`std_ich_projects` 等下划线表名，且没有明确列出 CnOpenData 专用 stage 表。
- 文档把方言页“更新时间”写成“不定时更新”，页面实际显示“不定时更新”；这本身成立，但 RSC 的 `dataScale` 为空，页面也未公布行数。文档已写明“无行数”，审核确认该判断成立，后续不应从 3 张表推导记录总量。
- 文档把 API 商店写成“公开完整产品集合，未观察到可见分页控件”，本次复核成立；但页面通过客户端渲染加载产品，普通 HTTP 只能看到加载占位和 RSC 载荷，不能把静态 HTML 的 22 张产品卡当作全量 29 个产品。
- 文档未记录 `llms.txt` 和 sitemap 的可用性。两者当前均返回 200，且 `llms.txt` 直接确认了“未经授权不应再分发完整数据、绕过访问限制”的平台口径，应作为版权边界证据补充。
- 本次未登录、未购买，故无法验证授权后文件清单、价格、字段空值率、实际行数、API 配额和返回结构；这些仍是明确缺口，不应写成已通过。

## 必须补齐

- 将 API 商店的数量口径改为可复现的三层表述：页面正文“29 个已上架接口”、RSC“29 个产品”、可见主题“5 个”、分类键“14 个且含重复名称”。如果继续写“13 个主题分类”，必须给出旧版或另一种统计口径的依据。
- 在非遗页访问限制中记录可见“OPEN”标签，并明确它只描述平台展示状态，不代表开放许可、免费下载或允许再分发；完整数据仍受登录、授权和合同约束。
- 把三类购买方案及“商业使用授权 / 学术引用授权 / 全量数据本地部署”写入授权风险，明确获得合同前不得采集、缓存或发布实际行级数据。
- 将映射中的 `crawler 的 std 命名 *`、`crawler.stage.*` 和点分表名统一到冻结 schema 的 `std_*`、`stage_*` 命名；若 CnOpenData 需要专用 stage 表，应在 schema 或映射文档中明确“建议新增”及其自然键。
- 把 `llms.txt` 中“未经授权不应再分发完整数据、绕过访问限制”的原文作为版权证据，并补充 robots 的 sitemap 声明。
- 保留“无公开行级样本、无行级详情 URL、无公开行数”的结论，不因页面有字段表或 `hasSamples=true` 就补充伪造样本。

## 可后续处理

- 登录并购买后再验证文件格式、字段空值率、实际行数、API 配额、API 返回结构和合同中的缓存、派生、公开展示权利。
- API 产品详情目前显示“注册后可获取 API Key”，请求参数和数据字段在未登录、未获取凭证时部分为加载占位；这不影响本次公开元数据审核，但影响后续 API 接入设计。
- 历史文化目录页面在浏览器中会跳到首个数据页，不能当作稳定列表契约；实现时继续使用具体数据集 URL。

## 验证记录

- 已打开并核对: `https://www.cnopendata.com/robots.txt`、`https://www.cnopendata.com/data/m/culture/zgfyxx.html`、`https://www.cnopendata.com/data/m/culture/intangible-cultural-heritage.html`、`https://www.cnopendata.com/api-store`、`https://www.cnopendata.com/api-store/ashare-daily-indicator`、`https://www.cnopendata.com/data/m/culture/`、`https://sso.cnopendata.com/user/login`、`https://www.cnopendata.com/api/v3/download/configs?seriesKey=zgfyxx`、`https://www.cnopendata.com/api/v3/download/configs?seriesKey=intangible-cultural-heritage`、`https://www.cnopendata.com/llms.txt`、`https://www.cnopendata.com/sitemap.xml`，共 11 个 URL。
- robots 结果: HTTP 200，正文为 `User-Agent: *`、`Allow: /`，禁止 `/api/`、`/myip`、`/user-center`、`/verify`、`/search`、`/userAuth`、`/users/`、`/iframeHTML`，并声明 sitemap。
- 数据集页结果: 方言页 330172 字节、SHA-256 `3e94de23952119b74dcef8351ae70948718355bb9ef10579be786fedbd3214a9`；非遗页 326184 字节、SHA-256 `cce83eb63cdb263d2a5bdf65c7cda1fdb9e297ef39a7129786d92ebc1f0f1e61`。两页均 HTTP 200，3 张字段表齐全，3 个样本区均显示“暂无样本数据”。
- API 商店结果: HTTP 200，228847 字节，SHA-256 `b25f02c430375dd9344410e966bf1885ee9512083d46de6bb44edec7e417605e`；RSC 解析出 29 个产品、29 个 `pricing:"contact"`、14 个分类键、2 个 featured 产品。
- API 产品详情: HTTP 200，220896 字节，SHA-256 `2a6dadfa8d71f4c3aba54a9035bf880566e8d85c944697d9e7f48042f33f9edf`；页面显示“注册后可获取 API Key”“API Key”授权方式及“需求机构级方案”提示。
- 下载边界: 两个 `download/configs` 均返回 200，`files` 为空数组，`hasPermission=false`，`requiresLogin=true`；未登录无法查看下载方案。
- 登录边界: 登录页 HTTP 200，Playwright 渲染后显示“登录账户”“使用微信扫码登录”“或使用邮箱登录”及“登录”按钮。
- 未验证项: 登录后的文件、价格、合同授权类型、行级样本、实际记录数、空值率、API 配额、API 返回结构、是否为完整数据提供 CSV/Stata/Excel 文件。
- 下载: 无。没有保存页面、文件、登录后数据或 API 响应数据。
