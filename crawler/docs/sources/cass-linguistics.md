# 中国社会科学院语言研究所

共享契约: 见 `sources/CONTRACT.md`。通用字段、访问等级、状态和详情 URL 规则不在本文重复。

来源 ID: `cass-linguistics`

状态: `approved-with-gaps`

权利状态: `noncommercial-permitted`

验证时间: `2026-10-19 01:08 Asia/Shanghai`

## 来源概况

- 名称: 中国社会科学院语言研究所
- 域名: `ling.cass.cn`
- 主管机构: 中国社会科学院语言研究所
- 内容域: 语言研究资料、数字资源目录、学术资讯；不是可直接消费的方言词条库
- 优先级: P2
- 访问等级: `public`（公开页面）；其中 `汉语方言语法特征语料库` 的研究数据访问需注册登录，属于 `login-required` 的受限子资源
- `license_or_usage`: 页面版权为“中国社会科学院语言研究所版权所有”；未发现开放许可，只登记公开内容和来源链接，不转载论文全文、出版物正文或需登录的数据
- `confidence`: `medium`（栏目、列表、详情和数字资源说明已验证；方言调查资料的结构化数据不可公开获取）

## 入口

| 用途 | URL | 方法 | 说明 |
| --- | --- | --- | --- |
| 首页 | `http://ling.cass.cn/index/` | GET | 200，栏目导航和新闻/成果聚合 |
| 数字资源列表 | `http://ling.cass.cn/keyan/xueshuchengguo/szzy/` | GET | 10+2 条数字资源条目 |
| 数字资源分页 | `http://ling.cass.cn/keyan/xueshuchengguo/szzy/index_1.html` | GET | 第 2 页；`index_2.html` 返回 404 |
| 新闻列表 | `http://ling.cass.cn/news/bensuo/` | GET | 10 条/页 |
| 新闻分页 | `http://ling.cass.cn/news/bensuo/index_1.html` | GET | 第 2 页，`index_2.html` 可访问 |
| 期刊栏目 | `http://ling.cass.cn/ziyuan/qikan/fangyan/` | GET | 《方言》期刊介绍、目录和动态 |
| 期刊分页 | `http://ling.cass.cn/ziyuan/qikan/fangyan/index_1.html` | GET | 10 条/页 |
| 详情页模式 | `http://ling.cass.cn/{栏目路径}/{YYYYMM}/t{YYYYMMDD}_{id}.html` | GET | 如 `/news/bensuo/202609/t20260904_6066095.html` |

## 请求与分页

- 请求方式: HTML `GET`，UTF-8
- 查询参数: 未发现列表查询参数；站点搜索是前端/门户搜索，不作为数据接口
- 分页字段: 栏目路径后 `index_{N}.html`，`N=1` 为第 2 页；首页为栏目根路径
- 每页数量: 列表 `.li_pgUl` 为 10 条/页
- 总数字段: 未发现
- 筛选字段: 按栏目路径筛选（本所新闻、数字资源、期刊、学术活动等），无字段级筛选

## 字段定位

### JSON API

未发现公开 JSON API。`汉语方言语法特征语料库` 页面指向外部站点 `http://www.dialectgrammar.com`，其数据需要注册登录；不把该站点的登录后数据当作本来源公开内容。

### HTML DOM

| 字段 | 选择器 | 说明 |
| --- | --- | --- |
| 列表项 | `.li_pgUl` | 每页 10 条 |
| 标题 | `.li_pgUl .li_bqListRight h2` | 如“追寻语言奥秘 回应时代需求” |
| 摘要 | `.li_pgUl .li_bqListRight p` | 列表摘要，详情页有完整正文 |
| 详情链接 | `.li_pgUl .li_bqListRight a[href]` | 相对路径或外部 `cssn.cn` 链接 |
| 来源/时间 | `.li_pgUl .li_bqListLt span` | 例如“来源：中国社会科学网”“时间：2026-09-04” |
| 缩略图 | `.li_pgUl .li_ulImg img[src]` | 可空 |
| 正文 | `.TRS_Editor` | 数字资源、新闻、期刊详情共用 |
| 详情来源/作者/时间 | `.TRS_Editor` 前面的标签行，或页面文本“来源：/作者：/时间：” | 选择器应优先匹配标签文本，避免依赖布局 |

### 文件附件

| 文件名 | URL | 类型 | 大小 | 结构 |
| --- | --- | --- | --- | --- |
| 未下载 | 未发现本任务所需的稳定结构化附件 | - | - | 公告页可见 PDF 链接，但不属于方言词条数据 |

## 真实样本

### 样本 1: 汉语方言语法特征语料库

- 详情 URL: `http://ling.cass.cn/keyan/xueshuchengguo/szzy/202308/t20230816_5679245.html`
- 抓取时间: `2026-10-19 01:08 Asia/Shanghai`
- 关键字段: 标题 `汉语方言语法特征语料库`；来源 `科研处`；时间 `2023-08-16`；正文说明截至 2023-07-10 收录 29 个方言点、22 个语法范畴、711 句语法例句；外部平台 `www.dialectgrammar.com`
- 数据性质: 研究资料/数字资源说明，不是词条明细；29 个方言点只在正文表格中出现，例句和方言说法需要注册登录后查询
- 目标映射: 文章级公开元数据映射到已冻结的 `std_research_articles`；资源目录映射到建议新增的 `std_research_resources`，不映射到 `dialect_lexemes`

### 样本 2: 多模态语言资源平台

- 详情 URL: `http://ling.cass.cn/keyan/xueshuchengguo/szzy/202511/t20251113_5949019.html`
- 抓取时间: `2026-10-19 01:08 Asia/Shanghai`
- 关键字段: 标题 `中国社会科学院多模态语言资源平台`；来源 `中国社会科学院（中国社会科学院大学）语言学重点实验室`；时间 `2025-11-13`；正文说明平台集资源管理、展示、规范说明、工具介绍与成果推荐于一体
- 数据性质: 资源目录说明，未提供可直接抓取的词条字段
- 目标映射: `std_research_resources`（建议新增，尚未冻结）

### 样本 3: 新闻正文

- 详情 URL: `http://ling.cass.cn/news/bensuo/202609/t20260904_6066095.html`
- 抓取时间: `2026-10-19 01:08 Asia/Shanghai`
- 关键字段: 标题 `追寻语言奥秘 回应时代需求`；来源 `中国社会科学网`；时间 `2026-09-04`；正文含儿童语音、成人语音老化数据库、方言与语音实验等研究介绍
- 数据性质: 资讯/研究报道，不是方言词条数据
- 目标映射: 已冻结的 `std_research_articles`；`std_research_sources` 仍为建议新增，当前不写入

### 样本 4: 《方言》目录

- 详情 URL: `http://ling.cass.cn/ziyuan/qikan/fangyan/202602/t20260225_5974130.html`
- 抓取时间: `2026-10-19 01:08 Asia/Shanghai`
- 关键字段: 标题 `《方言》2026年第1期目录`；作者 `《方言》编辑部`；来源 `今日语言学`；时间 `2026-02-25`
- 数据性质: 期刊目录/出版动态，不含论文全文
- 目标映射: 已冻结的 `std_research_articles`，只保存目录级元数据

## 字段映射

| 来源字段 | crawler 表.字段 | 粤乡智匠表.字段 | 转换说明 |
| --- | --- | --- | --- |
| 列表标题 | `std_research_articles.title` | `research_articles.title`（建议新增） | 原文标题 |
| 列表摘要 | `std_research_articles.summary` | `research_articles.summary` | 仅摘要，不替代正文 |
| 详情 URL | `std_research_articles.source_url` | `research_articles.source_url` | 直接可打开 |
| 来源标签 | `std_research_sources.media` | `research_article_sources.media` | 如“科研处”“中国社会科学网” |
| 时间标签 | `std_research_articles.published_at` | `research_articles.published_at` | 解析 `YYYY-MM-DD` |
| `.TRS_Editor` | `std_research_articles.body_text` | `research_articles.body_text` | 采集库保存公开正文；业务库只发布摘要或经授权内容 |
| 正文中“29 个方言点” | `std_research_resources.item_count` | `research_resources.item_count` | 仅作为研究资源说明，不生成词条 |
| 外部平台 URL | `std_research_resources.external_url` | `research_resources.external_url` | `www.dialectgrammar.com` 需登录，标记 `login-required` |

建议自然键: `(source_id='cass-linguistics', source_item_id)`，缺少来源 ID 时退回 `source_url`；研究文章和研究资源分表，不能把资讯标题映射成方言词条。`std_research_articles` 已冻结并允许 fixture 写入；`std_research_sources` 和 `std_research_resources` 仍为建议新增，不进入运行时写入或转换器输入。

## 数据量与更新

- 当前数量估算: 数字资源栏目约 12 条（首页 10 条 + `index_1.html` 2 条）；新闻栏目 10 条/页且可持续翻页；期刊栏目 10 条/页
- 更新频率: 新闻和活动不定期更新；数字资源更新较慢；期刊目录按出版周期更新
- 变更检测: 列表第一页标题集合、`.TRS_Editor` 正文哈希、栏目 `index_N.html` 是否出现新文章
- 建议采集频率: 数字资源与期刊每周 1 次；新闻每周 1 至 2 次；不采集登录后平台
- 历史数据保留: 采集库保存公开正文快照和抓取时间；业务库按发布策略保留摘要和链接

## 风险与限制

- 登录: 公开文章无需登录；`汉语方言语法特征语料库` 的检索与例句需要注册登录，属于 `login-required`
- robots: `http://ling.cass.cn/robots.txt` 返回 404，记录为 `not-found`；HTTPS robots 请求连接被重置，记录为 `unknown`。HTTP not-found 允许采集并写 `deferred` 候选；HTTPS unknown 按真实阻断处理。按公开页面、低频率、学术用途访问
- 版权: 页面明确写“中国社会科学院语言研究所版权所有”；论文、期刊和出版物正文不得全文转载到业务库
- 结构稳定性: 门户模板和 `TRS_Editor` 正文可定位，但列表相对路径跨栏目，需 `urljoin`；部分新闻链接指向 `cssn.cn` 或微信，需按来源域名分流
- 缺失字段: 无公开方言词条 API；无结构化 29 个方言点/711 句数据；无统一发布时间字段（需从标签行解析）
- 付费/全文: 期刊目录和文章页可能只公开目录或新闻，不采集付费论文全文

## 验证记录

- 验证方式: `requests` 实际 HTTP + Playwright（Playwright 对列表/详情选择器做了补充校验；超时项不再作为证明）
- 验证结果: 首页、数字资源、新闻、期刊、四个详情 URL 均返回 200；`.li_pgUl` 列表 10 条/页；`.TRS_Editor` 正文可读；数字资源分页 `index_1.html` 返回 200、`index_2.html` 返回 404
- 未验证项: 全部栏目历史页数、外部 `dialectgrammar.com` 的登录后字段、PDF/论文全文的可授权范围

## 审核要求

- 入口可打开: 是
- 样本可复现: 是（4 条详情样本）
- 字段映射完整: 是；仅研究资料/资讯字段，明确不映射到方言词条
- 详情 URL 可直达: 是

## 实现验证

- 公共入口: `crawler/collection/projects/cass-linguistics` 只读取已保存的公开研究详情 fixture。
- 写入: 每条公开详情生成一条 `std_research_articles`，保留 `source_url`、`long_term_url` 和正文哈希。
- 访问边界: `body_access=public` 才写入；`www.dialectgrammar.com` 只作为 `login-required` 子资源元数据保留，不请求、不写词条。
- 不生成 `std_dialect_lexemes`，研究资讯不会转换成方言词条。
