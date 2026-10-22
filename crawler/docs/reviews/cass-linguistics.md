# 中国社会科学院语言研究所 审核记录

来源 ID: `cass-linguistics`

审核时间: `2026-10-19 01:29 Asia/Shanghai`

审核结论: `approved-with-gaps`

权利状态: `noncommercial-permitted`

## 审核范围

- 待审文档: `crawler/docs/sources/cass-linguistics.md`
- 审核者: 来源审核 agent
- 复核方式: 独立 `requests` HTTP 与 Playwright Chromium；重开数字资源页、新闻/期刊栏目、4 条详情和外部语料库登录边界

## 逐项结论

| 项目 | 结论 | 证据 |
| --- | --- | --- |
| 入口 URL | 通过 | 首页、数字资源、新闻、期刊栏目均返回 200；数字资源首页 10 条、`index_1.html` 2 条，`index_2.html` 404 |
| 列表页与分页 | 通过（有抽样缺口） | `.li_pgUl` 每页 10 条；新闻第 1、2、3 页均可访问；期刊第 1、2 页均 10 条。未穷举全部历史页 |
| 详情页 URL | 通过 | 4 条样本详情均返回 200，标题、来源、时间及 `.TRS_Editor` 正文可读 |
| JSON 字段或 DOM 选择器 | 通过 | 未发现公开 JSON API；`.li_pgUl`、`.li_bqListRight h2`、`.li_bqListRight p`、`.li_bqListRight a[href]`、`.li_bqListLt span`、`.TRS_Editor` 均有非空结果 |
| 样本记录 | 通过 | 样本 1 的正文明确写有 29 个方言点、22 个语法范畴、711 句语法例句；样本 2 多模态平台、样本 3 新闻正文、样本 4 《方言》目录均可复现 |
| 字段映射 | 通过（有边界） | `std_research_articles` 已冻结并列入 `crawler-db.md`，运行时只写公开文章；`std_research_sources`、`std_research_resources` 仍为建议新增，不进入转换器。业务库研究表未冻结，当前不写入 |
| 访问限制 | 通过（需区分来源等级） | `ling.cass.cn` 公开页面匿名可访问；`http://www.dialectgrammar.com` 首页公开显示“注册登录”，登录页有邮箱/手机号/密码/验证码，注册页要求邮箱和验证码。登录后的例句、国际音标和发音不应进入公开采集 |
| 版权与用途 | 通过（有用途边界） | 页面页脚明确写“COPYRIGHT © 2017-2026 中国社会科学院语言研究所版权所有”，样本 3 还写“本文转载自中国社会科学网”；文档明确只登记公开内容和来源链接，不转载论文、期刊或需登录数据，结论成立 |
| 下载记录 | 有缺口 | 未发现本任务所需的稳定结构化附件；样本详情中的 PNG/JPG 图片可访问（最大约 1MB），但它们不是本任务的附件下载项。文档仍未记录这些图片的大小、SHA-256、取得时间，也没有说明正文图片是否进入 raw 或仅保留 URL |

## 发现的问题

- 29 个方言点和 711 句说明在公开详情正文中可复现，但这是资源说明，不是可抓取的词条明细；文档对此判断正确，必须继续禁止把说明文字拆成 711 条伪造词条。
- 外部平台 `www.dialectgrammar.com` 是同一研究资源的登录后站点，文档把它挂在 `cass-linguistics` 的 `login-required` 子资源下；`sources.json` 仍只登记 `ling.cass.cn` 为 `public`，没有独立来源记录。若后续需要采集该站，必须新增来源 ID、robots/版权核验和 `login-required` 访问等级。
- 外部平台 HTTP 首页返回空壳，Playwright 才显示公开介绍；HTTPS 根地址证书握手失败，实际公开入口应写 `http://`，并明确浏览器渲染是必要条件。
- `std_research_articles` 已在 schema 冻结，允许 CASS fixture 写入公开文章；`std_research_sources`、`std_research_resources` 仍没有冻结 schema，保持不写入。
- 业务表 `research_articles`、`research_resources`、`research_article_sources` 在目标库文档中没有定义；文档把它们写成“建议新增”是诚实的，但需要把新增表、字段、自然键和回滚方式补到目标库或映射文档。
- 样本 3 的正文超过 3,000 字且明确“转载自中国社会科学网”，文档只写“业务库只发布摘要或经授权内容”，但未把转载来源和授权边界作为字段或审核条件。
- 数字资源列表第 1 页 10 条、第 2 页 2 条已复核，但没有验证全部历史页、外部站点的登录后字段，也没有验证 `.TRS_Editor` 在所有详情类型中的稳定性。
- 文档没有下载记录章节；虽然页面没有稳定附件，但 4 条样本的正文图片均返回 200，大小和哈希未记录。图片是否属于 raw 文件、是否只保存 URL，需要明确。

## 必须补齐

- 已完成 `std_research_articles` 的冻结和物理表定义；`std_research_sources`、`std_research_resources` 的解除条件是需要独立来源关系和资源目录字段评审，当前只保留建议，不写运行时。
- 在目标库文档中定义 `research_articles`、`research_resources`、`research_article_sources` 的字段、自然键、迁移顺序和回滚方式，或明确本期不建表。
- 明确 `ling.cass.cn` 与 `www.dialectgrammar.com` 是两个访问主体：前者 `public`，后者 `login-required`。如果只登记前者，必须在来源文档和 `sources.json` 中写明后者不是独立采集来源。
- 为样本 3 的转载来源、样本 1 的 29 个方言点说明和样本 4 的目录级内容分别写明发布边界，不得把说明正文当作词条或论文全文。
- 补充正文图片的下载元数据，或写入“只保存图片 URL、不保存文件”的明确例外说明；如有超限文件，再写 `OVERSIZE.md`。

## 可后续处理

- 外部平台登录后字段、用户手册、引用格式和音频/国际音标数据，需在获得明确授权并新增来源登记后再审核。
- 全部历史页、`cssn.cn` 外链和微信公众号跳转可留到实现阶段按域名分流验证。
- 研究资源目录是否独立成表仍为 deferred；解除条件是产品与转换器负责人确认资源目录字段、业务目标和回滚方式。
