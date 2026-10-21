# 外研非遗网非遗资讯与项目文章

共享契约: 见 `sources/CONTRACT.md`。通用字段、访问等级、状态和详情 URL 规则不在本文重复。

来源 ID: `feiyiw`

状态: `approved-with-gaps`

验证时间: `2026-10-19 01:10 Asia/Shanghai`

权利状态: `attribution-required`

## 来源概况

- 名称: 外研非遗网，非遗网-非遗商城-非物质文化遗产交易平台
- 域名: `www.feiyiw.cn`
- 主管机构: 页面页脚显示外研传媒有限公司，具体主管和备案主体未进一步核验
- 内容域: 非遗资讯、项目文章、传承人文章、技艺补充资料
- 优先级: P2
- 访问等级: `public`
- `license_or_usage`: 页脚显示 `Copyright © 2016-2022 外研传媒有限公司 版权所有`。免责声明说明站内文字、图片、音频、视频和页面设计来自传承人、爱好者供稿或互联网公开信息搜集整理，不代表站方立场，并允许权利人通知删除。未找到允许批量再分发全文的许可。
- `confidence`: 高，列表、分页、文章详情和字段选择器均由真实页面验证；中，站点更新节奏和全量内容类型未验证；低，转载授权和长期引用许可未确认。

本来源定位为非遗资讯和技艺补充来源，不是国家级非遗名录的权威来源。项目编号、级别、批次、保护单位等事实必须回到 `ihchina.cn` 或相应政府公告核验。

## 入口

| 用途 | URL | 方法 | 说明 |
| --- | --- | --- | --- |
| 首页 | `https://www.feiyiw.cn/` | GET | 站点首页 |
| 重点列表页 | `https://www.feiyiw.cn/index.php?app=article&cate_id=4` | GET | 列表标题“非遗大数据”，文章区每页 25 条 |
| 非遗动态补充列表 | `https://www.feiyiw.cn/index.php?app=article&cate_id=2` | GET | 标题“非遗动态”，本次只验证入口和分页，不把它当项目权威名录 |
| 项目文章补充列表 | `https://www.feiyiw.cn/index.php?app=article&cate_id=5` | GET | 标题“中国非遗项目名录”，存在项目名称文章，但仍是站内整理 |
| 列表分页模式 | `https://www.feiyiw.cn/index.php?app=article&cate_id=4&page={n}` | GET | `n` 从 1 开始，第 1 页可省略 `page` |
| 详情页模式 | `https://www.feiyiw.cn/index.php?app=article&act=view&article_id={id}` | GET | `id` 为整数文章 ID，是稳定详情定位键 |

详情页 URL 使用查询参数，不使用路径式 slug。`article_id` 可直接打开文章，不依赖列表页会话或 POST 请求。

## 请求与分页

- 请求方式: HTTP GET，服务端渲染 HTML，页面编码为 UTF-8。
- 查询参数:
  - 列表: `app=article`、`cate_id=4`、可选 `page={n}`
  - 详情: `app=article`、`act=view`、`article_id={id}`
- 分页字段: `page`，从 1 开始。
- 每页数量: 25 条。
- 总数字段: `.page .total`，格式为“共 1176 页”。`page_number` 输入框的 `max` 为 `1176`。
- 末页数量: 第 1176 页有 16 条，因此重点分类总量约为 `1175 × 25 + 16 = 29391` 条。
- 筛选字段: 列表页没有额外查询筛选。文章分类由 `cate_id` 区分，文章自身可用标题前缀和正文标签区分传统美术、传统技艺、传统医药等类别。
- 列表排序: 实测按发布日期倒序，第一页首条为 `2026-10-16`，第二页继续向前。
- 其他分类实测: `cate_id=2` 共 115 页，`cate_id=5` 共 1439 页，`cate_id=16` 共 4 页。除重点分类 4 外，这些只作为入口证据，不扩大采集范围。

## 字段定位

### JSON API

未发现公开 JSON 列表或详情接口。页面由服务端直接渲染 HTML，本来源按 HTML DOM 采集。

| 来源字段 | 含义 | 样本 |
| --- | --- | --- |
| 不存在 | 无公开 JSON 契约 | 无 |

### HTML DOM

列表页选择器：

| 字段 | 选择器 | 说明 |
| --- | --- | --- |
| 列表区域 | `#page-article div.col-main ul.content` | 重点分类主列表 |
| 列表项 | `#page-article div.col-main ul.content > li` | 每项包含链接、标题和日期 |
| 详情链接 | `#page-article div.col-main ul.content > li a.lebioa[href*="article_id="]` | `href` 可能是相对 URL |
| 列表标题 | `#page-article div.col-main ul.content > li a.lebioa` | 文本通常以 `【类别】` 开头 |
| 列表日期 | `#page-article div.col-main ul.content > li > span` | 格式 `YYYY.MM.DD` |
| 当前页 | `.page .items a.item.active` | 第 1 页文本为 `1` |
| 下一页 | `.page .items a.item.next` | `href` 指向 `page+1` |
| 总页数 | `.page .total` | 文本“共1176页” |
| 页码上限 | `#page_number[max]` | 值 `1176` |

详情页选择器：

| 字段 | 选择器 | 说明 |
| --- | --- | --- |
| 详情标题 | `.article-info h1` | 文章标题，包含 `【类别】` 前缀和可能的传承人姓名 |
| 发布时间 | `.article-info h2` | 格式 `YYYY-MM-DD HH:mm` |
| 面包屑分类 | `#page-article div.col-main > div.title .location` | 可用于确认 `cate_id` 对应的分类名称 |
| 正文 | `.article-detail` | 富文本 HTML，含段落、加粗、换行和行内样式 |
| 正文纯文本 | `.article-detail` 的 `get_text("\n")` | 清洗后保留标签字段 |
| 正文内项目名称 | `.article-detail` 文本中的 `【项目名称】` | 部分项目文章存在 |
| 正文内项目类别 | `.article-detail` 文本中的 `【项目类别】` | 如 `传统美术` |
| 正文内项目地区 | `.article-detail` 文本中的 `【项目地区】` | 如 `辽宁省朝阳市朝阳县` |
| 正文内项目级别 | `.article-detail` 文本中的 `【项目级别】` | 如 `市级`、`省级` |
| 正文内保护单位 | `.article-detail` 文本中的 `【项目保护单位】` | 并非每篇都有 |
| 正文内批准时间 | `.article-detail` 文本中的 `【项目批准时间】` | 常为自然语言，不是标准日期字段 |
| 正文内传承人简介 | `.article-detail` 文本中的 `【传承人简介】` | 需要保留人物信息，不得推断缺失信息 |
| 上一篇、下一篇 | 详情页 `h3` 文本 | 可辅助发现关联文章，不应作为主分页 |

正文标签没有独立 DOM 节点，很多字段写在同一个 `<p>` 或 `<strong>` 中，因此 parser 需要先转纯文本，再按 `【标签】` 边界切分。不要依赖行内 `style` 属性。

### 文件附件

重点分类列表和已抽查详情页没有发现必须下载的附件。正文图片是页面资源，不纳入首批采集。

| 文件名 | URL | 类型 | 大小 | 结构 |
| --- | --- | --- | --- | --- |
| 无 | 无 | 无 | 无 | 本次未下载附件 |

## 真实样本

三条样本均来自 `cate_id=4` 第一页，详情页 HTTP 200，标题、发布时间和正文可复现。

### 样本 1

- 详情 URL: `https://www.feiyiw.cn/index.php?app=article&act=view&article_id=70177`
- 抓取时间: `2026-10-19 01:10 Asia/Shanghai`
- 标题: `【传统美术】朝阳县烙画（朝阳市）传承人：闫海秋`
- 发布时间: `2026-10-16 15:56`
- 列表分类: `非遗大数据`，列表日期 `2026.10.16`
- 正文关键字段:
  - 项目名称: `朝阳县烙画`
  - 项目类别: `传统美术`
  - 项目地区: `辽宁省朝阳市朝阳县`
  - 项目级别: `市级`
  - 项目批准时间: `2021年`，正文写明第七批市级非物质文化遗产名录，项目序号 `63`，项目编号 `VII -26`
  - 传承人: `闫海秋`
  - 正文含传承人简介和从艺经历
- 目标映射: `std_ich_articles` 保存资讯文章；抽取后的项目资料作为 `ihchina` 的补充证据，不直接发布到 `crafts`

### 样本 2

- 详情 URL: `https://www.feiyiw.cn/index.php?app=article&act=view&article_id=70123`
- 抓取时间: `2026-10-19 01:10 Asia/Shanghai`
- 标题: `【传统美术】铁岭指画（铁岭市）传承人：关兴号桃园居`
- 发布时间: `2026-01-11 15:36`
- 列表分类: `非遗大数据`，列表日期 `2026.01.11`
- 正文关键字段:
  - 项目名称: `铁岭指画`
  - 项目类别: `传统美术`
  - 项目地区: `辽宁省铁岭市`
  - 项目级别: `省级`
  - 项目保护单位: `铁岭市文学艺术界联合会`
  - 项目批准时间: `2006年`，正文写明列入辽宁省级第一批非物质文化遗产项目名录
  - 传承人: `关兴号桃园居`
- 目标映射: 项目资料先进入 `stage_feiyiw_articles` 和 `std_ich_articles`，级别和保护单位需回到官方名录核对

### 样本 3

- 详情 URL: `https://www.feiyiw.cn/index.php?app=article&act=view&article_id=69998`
- 抓取时间: `2026-10-19 01:10 Asia/Shanghai`
- 标题: `【传统技艺】北派李氏花灯（营口市）传承人：李林田`
- 发布时间: `2025-02-06 10:53`
- 列表分类: `非遗大数据`，列表日期 `2025.02.06`
- 正文关键字段:
  - 项目名称: `北派李氏花灯`
  - 项目类别: `传统技艺`
  - 项目地区: `辽宁省营口市`
  - 项目级别: `市级`
  - 项目批准时间: `2020年12月21日`，正文写明营口市第六批非物质文化遗产代表性项目名录
  - 传承人: `李林田`
  - 正文含第十二代传承人和技艺传承说明
- 目标映射: 可作为手工技艺补充资料，抽取项目名、地区、级别和历史叙述，不抽取不存在的教学步骤

## 字段映射

### crawler 层

| 来源字段 | crawler 表.字段 | 粤乡智匠建议表.字段 | 转换说明 |
| --- | --- | --- | --- |
| `article_id` | `stage_feiyiw_articles.source_item_id` | 建议新增 `crafts.extra.source_item_id` | 本站自然键，优先于标题 |
| 详情 URL | `stage_feiyiw_articles.source_url` | 建议新增 `crafts.source_url` | 规范化为绝对 URL |
| `cate_id` | `stage_feiyiw_articles.category_id` | 建议新增 `crafts.source_category_id` | 来源分类 ID |
| 面包屑分类 | `stage_feiyiw_articles.category_name` | 建议新增 `crafts.source_category` | 如“非遗大数据” |
| `.article-info h1` | `stage_feiyiw_articles.title` | `crafts.name` 的候选依据 | 先剥离 `【类别】` 和 `传承人：` |
| `.article-info h2` | `stage_feiyiw_articles.published_at` | 建议新增 `crafts.source_published_at` | 解析 `YYYY-MM-DD HH:mm`，保留原字符串 |
| `【项目名称】` | `stage_feiyiw_articles.project_name` | `crafts.name` | 需要和官方项目名称核对 |
| 标题前缀类别 | `stage_feiyiw_articles.ich_category_title` | 建议新增 `crafts.ich_category` | 如 `传统技艺` |
| `【项目类别】` | `stage_feiyiw_articles.ich_category_body` | 建议新增 `crafts.ich_category` | 与标题前缀不一致时进入冲突记录 |
| `【项目地区】` | `stage_feiyiw_articles.region_text` | `crafts.origin` | 保留原文，后续按行政区划拆分 |
| `【项目级别】` | `stage_feiyiw_articles.level_text` | `crafts.level` | 统一为“国家级 / 省级 / 市级 / 县级”前必须人工核对 |
| `【项目保护单位】` | `stage_feiyiw_articles.protection_unit` | 建议新增 `crafts.protection_unit` | 可为空 |
| `【项目批准时间】` | `stage_feiyiw_articles.approval_text` | 建议新增 `crafts.approval_text` | 自然语言保留原文，不强行伪造日期 |
| `【传承人简介】` | `stage_feiyiw_articles.inheritor_text` | 建议新增 `crafts.inheritor_text` | 人物信息只保留公开正文内容 |
| `.article-detail` 纯文本 | `stage_feiyiw_articles.body_text` | `crafts.history` 的候选来源 | 不自动全文公开转载 |
| `.article-detail` HTML | `raw.page.content` | 不适用 | 采集库 raw 层保留用于回溯 |
| 正文内容哈希 | `raw.page.sha256` | 建议新增 `crafts.content_hash` | 用于变更检测 |

### std 层

使用以下已冻结标准实体：

- `std_ich_articles`：字段定义见 `schema/std-entities.md#std_ich_articles`，本文只记录来源差异。
- `std_ich_projects`: 只有从正文抽出并经过官方核验的项目事实才写入。字段包括项目名称、类别、地区、级别、批准时间原文、保护单位、项目编号和来源 URL。
- `craft_evidence`: 用于把补充文章挂到经过人工确认的技艺实体，保留 `confidence`、`review_status` 和 `source_url`，避免补充来源直接覆盖官方事实。

### 粤乡智匠表

- `crafts`: 可承接经审核的项目名称、地区、级别、历史概述和来源 URL。现有表缺少外部 ID、来源、项目编号、内容哈希等列，建议在目标库变更设计中补列。
- `craft_steps`: 该来源正文没有结构化教学步骤，不映射。不能把“传承人简介”或“项目介绍”拆成步骤。
- `craft_videos`: 本次未采集视频，不映射。
- `craft_purchase_*` 和 `craft_budgets`: 本次未采集采购内容，不映射。
- 如需展示资讯，建议新增 `ich_articles` 或等价资讯表，不要让资讯正文污染 `crafts.history`。

## 数据量与更新

- 当前数量估算: 重点分类 `cate_id=4` 共 1176 页，每页 25 条，末页 16 条，约 29391 条文章。该数字由分页推导，页面没有直接公布总条数。
- 更新频率: 页面未公开。实测最新条目为 `2026-10-16`，列表按日期倒序，说明站点仍在更新。
- 变更检测: 以 `article_id` 为主键，比较标题、发布时间、正文纯文本和正文哈希。列表发现新 ID 时抓详情；旧 ID 标题或正文哈希变化时记录修订。
- 建议采集频率: 每周一次增量检查第一页，必要时补查第二页；首次全量约 1176 次列表请求。实施时限速并缓存，避免重复请求未变化页面。
- 历史数据保留: raw HTML 按文章保留，正文哈希变化时保留新版本或版本表。业务库只保留审核后的字段和必要摘要。
- 更新风险: 列表可能有补录或重新发布，不能只依赖 ID 递增。按发布时间和内容哈希复核。

## 风险与限制

- 登录: 列表和文章详情无需登录即可查看。会员、购买、订单、收藏等需登录内容不在采集范围。
- robots: `https://www.feiyiw.cn/robots.txt` 返回 HTTP 404，记录为 `not-found`。允许采集并写 `deferred` 候选，404 不等于授权，仍需保留核查记录并遵守合理限速。
- 版权: 免责声明说明内容由用户供稿或互联网公开信息整理，站方不保证权属。记录使用 `attribution-required`，并在 `extra.rights_risk` 保留权属风险；不得默认拥有全文再发布权，业务库只保存审核后的必要字段或短摘要。
- 结构稳定性: 老式商城模板，HTML 较冗长，正文含大量内联样式。依赖文本标签和稳定 `class`，不依赖样式属性。
- 缺失字段: 没有官方项目编号作为独立字段，部分编号只写在自然语言中；没有统一分类字段；没有结构化批准日期；不同文章模板可能缺字段。
- 权威性: 站内“中国非遗项目名录”不是政府原始名录。项目级别、批次、编号和保护单位需和 `ihchina.cn` 或政府公告比对。
- 内容类型混杂: 同一正文可能混合项目介绍、传承人简介、新闻和个人叙述，抽取时需要置信度和人工复核。
- 人物信息: 传承人姓名和简介属于公开文章内容，但不应扩展采集联系方式、住址或其他隐私字段。

## 验证记录

- 验证方式: Python `requests` 请求列表页、分页页、末页、补充分类页和 3 个详情页；BeautifulSoup 实际执行列表项、标题、日期、正文和分页选择器；读取 `robots.txt`、`sitemap.xml` 和免责声明页。
- 验证结果: 重点列表页 HTTP 200，25 条/页，共 1176 页，末页 16 条；第二页首条可打开；3 个详情页 HTTP 200，标题、发布时间和 `.article-detail` 正文均存在；“共 1176 页”和 `page_number[max=1176]` 一致。
- robots 结果: `https://www.feiyiw.cn/robots.txt` HTTP 404，响应为 nginx 404 HTML。
- sitemap 结果: `https://www.feiyiw.cn/sitemap.xml` HTTP 200，可作为补充发现入口，但不能替代分页契约。
- 版权证据: `https://www.feiyiw.cn/index.php?app=article&act=view&article_id=38990` 可打开免责声明，页脚版权和备案信息在列表页可读。
- 未验证项: 全量文章模板覆盖率、不同 `cate_id` 的字段差异、图片和视频版权、站点更新频率、是否存在隐藏接口、历史文章删除率、转载许可。
- 下载: 无。没有保存页面、图片、音频、视频或其他文件。

## 实现验证

- 解析入口: `crawler/pipeline/sources/feiyiw.py` 提供列表发现、详情解析和 `article_id` 规范化；不依赖共享运行入口。
- 已测行为: 公开列表按 `article_id` 去重；详情必须来自有效 `article_id` 且包含公开标题和正文；会员、购买、登录页拒绝生成文章记录。
- 记录边界: 每条记录保留 `source_url`、`long_term_url`、`detail_url`、署名和 `rights_status`；正文标签进入 `extra.supplementary`，文章元数据写入已冻结的 `std_ich_articles`，不直接投射到 `std_ich_projects`。
- 测试: `python -m unittest crawler.tests.test_feiyiw -v`。
- 未接入项: 共享 `run_source` 已接入 fixture 的 raw、stage 和 `std_ich_articles` 写入；真实网络全量运行和业务库发布仍未完成。

## 审核要求

- 入口可打开: 是
- 样本可复现: 是，3 条样本均可直达
- 字段映射完整: 公开文章字段已映射；官方事实核验和业务发布规则仍有缺口
- 详情 URL 可直达: 是
- 合规结论: `approved-with-gaps`，仅采公开页面和必要摘要，不采会员内容，不作为国家级名录权威来源

## Runner 闭环

- `run_source('feiyiw','fixture',config)` 已写 raw、stage 和已冻结的 `std_ich_articles`。
- 真实网络全量运行尚未完成；转换器只把 `std_ich_articles` 当作补充资讯输入，不覆盖非遗项目事实。
