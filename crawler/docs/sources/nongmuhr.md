# 农牧人才网

共享契约: 见 `sources/CONTRACT.md`。通用字段、访问等级、状态和详情 URL 规则不在本文重复。

来源 ID: `nongmuhr`

状态: `approved-with-gaps`

权利状态: `attribution-required`

验证时间: `2026-10-21 21:48 Asia/Shanghai`

结构校验状态: `verified`

> 2026-10-21 已重新抓取真实列表页和 5 条详情页。列表页返回 10 条岗位；5 条详情均返回 HTTP 200，标题、公司、地点、招聘人数、截止日期、发布时间和职位描述可读。旧 `#project_L` 选择器不存在，已从实现中移除。来源状态仍为 `approved-with-gaps`，与本次结构校验状态分开记录。

## 来源概况

- 名称: 农牧人才网，页面同时使用“中国农牧人才网”
- 域名: `nongmuhr.com`
- 主管机构: 页面主办单位为北京盈创智慧科技有限公司
- 内容域: `jobs`
- 优先级: P1
- 访问等级: `public`
- `license_or_usage`: 页脚明确“本网站所有招聘信息及作品，未经授权不得转载”。仅采集公开岗位索引和结构化摘要，不全文转载；展示时保留来源链接并取得授权后再扩大正文使用范围。
- `confidence`: 高。首页、`Employ.aspx` 列表、第二页、两个岗位详情页均已通过实际 HTTP GET 验证。
- 收录边界: 只收农业、畜牧、水产、种植、养殖、饲料、兽药、农资等岗位。`/P_ResumeView.aspx` 等 robots 禁止的个人简历路径不访问、不采集。

## 入口

| 用途 | URL | 方法 | 说明 |
| --- | --- | --- | --- |
| 首页 | `http://nongmuhr.com/` | GET | 返回 200 |
| 列表页 | `http://nongmuhr.com/Employ.aspx` | GET | 返回 200，每页 10 条 |
| 列表分页 | `http://nongmuhr.com/Employ.aspx?pubtime=-1&experience=-1&page={page}` | GET | `page` 从 0 开始；默认列表为 `page=0`，`page=1` 是第二页，均已实测 |
| 岗位详情模式 | `http://nongmuhr.com/EmployView.aspx?id={job_id}` | GET | 例如 `id=13520`、`id=13519`，均返回 200 |
| 企业详情模式 | `http://nongmuhr.com/CompanyView.aspx?Id={company_id}` | GET | 详情页公司链接，例如 `Id=2333` |
| robots | `http://nongmuhr.com/robots.txt` | GET | 返回 200 |

首页导航“企业招聘”、首页“最新招聘信息”和 `Employ.aspx` 都指向同一岗位列表。`EmployView.aspx` 大写 `Id` 和小写 `id` 均可工作，实现时统一使用小写 `id`。

## 请求与分页

- 请求方式: 列表和详情均可用 GET
- 列表筛选参数: `txtCompany`、`txtEmploy`、`ddlIndustry`、`ddlPubtime`、`ddlExperience`、`ddlJobclass`、`ddlSalary`、`ddlEducation`、`ddlCompanyclass`、`txtGzdd`、`selArea`、`txtKeyword`
- 页面分页参数: `pubtime=-1`、`experience=-1`、`page={page}`
- 每页数量: 10
- 总数字段: 2026-10-21 页面脚本 `$("#Pagination").pagination(9027, { items_per_page: 10 })`
- 总页数: 约 903 页，由总数除以每页数量得到
- 分页起点: 默认页是 `page=0`，`page=1` 是第二页
- 职位搜索参数示例: 职位名称输入框 `txtEmploy`，行业下拉 `ddlIndustry`
- 行业筛选值: `园林/园艺/花卉`、`种子/化肥/农药`、`养殖/宠物`、`兽药/动保/生物制品`、`饲料/添加剂/原料`、`水产/种苗`、`农牧机械`、`农业种植养殖`
- 发布时间筛选: `ddlPubtime` 可取 `3`、`7`、`30`
- 经验筛选: `ddlExperience` 可取 `0`、`1`、`2`、`3`、`5`、`8`、`10`
- 工作类型: `ddlJobclass` 可取 `全职`、`兼职`
- 学历: `ddlEducation` 可取 `不限`、`初中`、`高中`、`中技`、`中专`、`大专`、`本科`、`硕士`、`博士`
- 登录要求: 公开列表和详情无需登录

分页链接由 `jquery.pagination.js` 生成，模板为 `?pubtime=-1&experience=-1&page=__id__`。`page` 从 0 开始。后续采集只需保留筛选参数并替换 `page`，不需要处理 ASP.NET 的 `__VIEWSTATE`。

历史声明: 2026-10-19 前的文档曾写“`page` 从 1 开始”，该说法与页面实测不符，已废弃。当前事实以默认页 `page=0`、`page=1` 为第二页为准，审核记录保留这次修正过程。

## 字段定位

### HTML DOM

列表页:

| 字段 | 选择器 | 说明 |
| --- | --- | --- |
| 列表容器 | `#joblist_table table.joblist_b_border` | 每个岗位一个 `tr` |
| 岗位块 | `div.joblist_showlist` | 包含岗位名、公司、地点、刷新时间 |
| 岗位详情 URL | `td.joblist_jobname a[href^="EmployView.aspx?Id="]` | `href` 中的 `Id` 为岗位 ID |
| 岗位名称 | `td.joblist_jobname a` | 可能跨行，需清理空白 |
| 公司名称 | `td.joblist_a a[id^="rptList_hlCompany_"]` | 文本为公司名 |
| 公司详情 URL | `td.joblist_a a[id^="rptList_hlCompany_"]` | `href` 为 `CompanyView.aspx?Id={company_id}` |
| 招聘地点 | `td[colspan="2"] div.fontover_hide.width_105` | 可为多个地区，以 `|` 分隔 |
| 刷新时间 | 岗位行最后一个 `td[width="105"]` | 相对时间，例如 `3天前` |
| 列表招聘人数 | `div.job_list_zf` 中 `招聘人数：` | 数值在相邻 `b` |
| 列表月薪 | `div.job_list_zf` 中 `月薪：` | 例如 `面议` |
| 列表学历 | `div.job_list_zf` 中 `学历要求：` | 例如 `大专` |
| 列表公司规模 | `div.job_list_zf` 中 `公司规模：` | 例如 `100－499人` |
| 列表公司性质 | `div.job_list_zf` 中 `公司性质：` | 例如 `私营/民营企业` |
| 列表职位描述摘要 | 岗位块第二个 `td[height="48"]` | 带省略号，只作预览 |
| 分页容器 | `#Pagination` | 2026-10-21 由 `jquery.pagination.js` 接收总数 9027 |

详情页:

> 以下选择器来自 2026-10-21 的真实页面复验。`#project_L` 属于已废弃的历史结构，不得继续用于实现。

| 字段 | 选择器 | 说明 |
| --- | --- | --- |
| 岗位名称 | `#joblist .joblistonelf` | 文本为岗位名 |
| 公司名称 | `#joblist #hlCompanyName` | 文本为公司名 |
| 公司详情 URL | `#joblist #hlCompanyName[href]` | 相对 URL `CompanyView.aspx?Id={company_id}` |
| 工作性质 | 标签 `工作性质：` 的相邻 `td` | 例如 `全职` |
| 部门 | 标签 `部 门：` 的相邻 `td` | 例如 `设备部` |
| 招聘人数 | 标签 `招聘人数：` 的相邻 `td` | 纯数字 |
| 截止日期 | 标签 `截止日期：` 的相邻 `td` | 格式 `YYYY-MM-DD` |
| 工作经验 | 标签 `工作经验：` 的相邻 `td` | 例如 `3年以上` |
| 学历 | 标签 `学 历：` 的相邻 `td` | 例如 `高中` |
| 工作地点 | 标签 `工作地点：` 的相邻 `td` | 可为多地区，以 `|` 分隔 |
| 性别 | 标签 `性 别：` 的相邻 `td` | 例如 `不限` |
| 年龄 | 标签 `年 龄：` 的相邻 `td` | 例如 `30-45` |
| 邮箱 | 标签 `邮 件：` 的相邻 `td` | `{{EMAIL_*}}` 模板占位符不可用 |
| 联系人 | 标签 `联系人：` 的相邻 `td` | 公开可见时保留，不在文档转录 |
| 联系电话 | 标签 `联系电话：` 的相邻 `td` | 公开可见时保留，不在文档转录 |
| 职位描述 | 标签 `职位描述及具体要求：` 所在行之后的第一个 `td[style*="word-break"]` | 含岗位职责和任职条件 |
| 发布时间 | 标签 `发布时间：` 的相邻 `td` | 格式 `YYYY-MM-DD` |
| 公司行业 | `#joblist1 td.y12x` | 文本内混合行业、规模、性质、地区 |
| 公司介绍 | `#joblist1 td[colspan="2"]` | 公司简介 |

联系方式是公开页面字段，但仍属于企业联系人信息。采集库可保存公开值并限制访问，业务库默认只展示来源链接，不直接公开个人手机号或联系人姓名。

### 文件附件

本来源未发现岗位附件。

## 真实样本

2026-10-21 21:47 至 21:48 Asia/Shanghai 抓取列表页和 5 条详情。列表页返回 10 条岗位，以下 5 条详情均返回 `200`，内容类型为 `text/html; charset=utf-8`。

| 岗位 ID | 岗位名称 | 公司 | 地点 | 人数 | 截止日期 | 发布时间 |
| --- | --- | --- | --- | ---: | --- | --- |
| `13553` | 设备工程师 | 江西华裕家禽育种有限公司 | 宜春市 | 1 | 2026-07-30 | 2025-08-10 |
| `13556` | 管培生 | 河南浪之潮农业科技有限公司 | 不限地点 | 10 | 2025-10-13 | 2025-08-12 |
| `13555` | 推广经理 | 河南浪之潮农业科技有限公司 | 不限地点 | 10 | 2025-10-13 | 2025-08-12 |
| `13554` | 大区经理 | 河南浪之潮农业科技有限公司 | 不限地点 | 10 | 2025-10-13 | 2025-08-12 |
| `13561` | 出纳 | 巴里坤农牧业投资集团有限公司 | 新疆自治区 | 2 | 2025-09-30 | 2025-08-19 |

详情 URL 模式为 `http://nongmuhr.com/EmployView.aspx?Id={job_id}`。五个样本的职位描述均能从 `职位描述及具体要求：` 之后的 `td[style*="word-break"]` 取得；公司行业、规模和性质从 `#joblist1 td.y12x` 取得。

五个样本的截止日期均早于本次验证日期，列表仍展示这些岗位。实现以详情页日期为准，把列表相对刷新时间只作为发现信号。原始页面含公开联系人和联系电话，本文档和公开 fixture 不转录这些字段。

目标映射为 `recruitment_postings`。本轮只验证字段读取和采集库候选写入，不改变过期岗位的业务发布规则。

## 字段映射

### crawler std 层

目标标准实体为 `std_jobs`。raw 层保存列表和详情 HTML；stage 层保留 `nongmuhr_job` 原始字段；std 层统一岗位字段。

| 来源字段 | crawler 表.字段 | 粤乡智匠表.字段 | 转换说明 |
| --- | --- | --- | --- |
| `EmployView.aspx?id={id}` 中的 `id` | `std_jobs.source_item_id` | `recruitment_postings.source_item_id` | 保留字符串 |
| 详情 URL | `std_jobs.source_url` | `recruitment_postings.source_url` | 规范化为绝对 URL，作为来源内自然键 |
| `来源 ID = nongmuhr` | `std_jobs.source_id` | `recruitment_posting_sources.source_id` | 固定 `nongmuhr` |
| `#joblist .joblistonelf` | `std_jobs.title` | `recruitment_postings.title` | 清理空白 |
| `#joblist #hlCompanyName` | `std_jobs.company_name` | `recruitment_postings.company_name` | 直接映射 |
| `#joblist #hlCompanyName[href]` | `std_jobs.company_url` | `recruitment_postings.company_url` | 转绝对 URL |
| `工作性质` | `std_jobs.employment_type` | `recruitment_postings.employment_type` | 如 `全职` |
| `部 门` | `std_jobs.extra.department` | `recruitment_postings.department` | 直接映射 |
| `招聘人数` | `std_jobs.headcount` | `recruitment_postings.headcount` | 转整数 |
| `截止日期` | `std_jobs.deadline_at` | `recruitment_postings.deadline_at` | 解析为 ISO 日期 |
| `工作经验` | `std_jobs.experience_raw` | `recruitment_postings.experience_raw` | 保留原文，可派生 `experience_min_years` |
| `学 历` | `std_jobs.education_raw` | `recruitment_postings.education_raw` | 直接映射 |
| `工作地点` | `std_jobs.location_raw` | `recruitment_postings.location_raw` | 保留 `|` 分隔的原文，拆首个到 `region` |
| `性 别` | `std_jobs.gender_requirement` | `recruitment_postings.gender_requirement` | 直接映射 |
| `年 龄` | `std_jobs.age_requirement` | `recruitment_postings.age_requirement` | 保留区间原文 |
| `邮 件` | `std_jobs.extra.public_contact_email` | `recruitment_postings.contact_email` | 识别 `{{EMAIL_*}}` 为模板占位，置 null |
| `联系人` | `std_jobs.extra.public_contact_name` | `recruitment_postings.contact_name` | 公开值可入库，默认不公开展示 |
| `联系电话` | `std_jobs.extra.public_contact_phone` | `recruitment_postings.contact_phone` | 公开值可入库，默认不公开展示 |
| 职位描述标题之后的 `td[style*="word-break"]` | `std_jobs.description` | `recruitment_postings.description` | 清洗 HTML，保留职责和要求 |
| `发布时间` | `std_jobs.published_at` | `recruitment_postings.published_at` | 解析为 ISO 日期 |
| 公司行业/规模/性质/地区 | `std_jobs.company_industry` 等 | `recruitment_postings.company_industry` 等 | 从 `#joblist1 td.y12x` 分段解析 |
| 公司介绍 | `std_jobs.extra.company_description` | `recruitment_postings.company_description` | 可截断为摘要，避免全文转载 |
| 列表刷新时间 | `std_jobs.extra.listed_relative_time` | `recruitment_postings.listed_relative_time` | 只作发现信号，不用于精确日期 |
| 详情 HTML 正文 | `std_jobs.content_hash` | `recruitment_postings.content_hash` | 对规范化正文计算 SHA-256 |
| 抓取时间 | `std_jobs.retrieved_at` | `recruitment_postings.retrieved_at` | 每次采集更新 |

### 粤乡智匠建议表

只写入 `recruitment_postings` 和 `recruitment_posting_sources`，不写 `job_listings` 或 `recruitments`。

`recruitment_postings` 建议字段:

- `id`
- `source_id`
- `source_item_id`
- `source_url`
- `title`
- `company_name`
- `company_url`
- `company_address`
- `company_industry`
- `company_size`
- `company_type`
- `region`
- `location_raw`
- `department`
- `employment_type`
- `headcount`
- `salary_raw`
- `salary_min`
- `salary_max`
- `salary_period`
- `education_raw`
- `experience_raw`
- `experience_min_years`
- `gender_requirement`
- `age_requirement`
- `published_at`
- `deadline_at`
- `description`
- `requirements`
- `contact_name`
- `contact_phone`
- `contact_email`
- `is_agriculture_related`
- `is_expired`
- `content_hash`
- `fetched_at`
- `first_seen_at`
- `last_seen_at`
- `status`

`recruitment_posting_sources` 建议字段:

- `id`
- `posting_id`
- `source_id`
- `source_item_id`
- `source_url`
- `fetched_at`
- `http_status`
- `content_hash`
- `raw_snapshot_path`
- `is_primary`

自然键: `source_id + source_item_id`。详情 URL 必须保存，用于用户跳转到原招聘页。

农业相关性判定建议:

1. 行业字段属于 `园林/园艺/花卉`、`种子/化肥/农药`、`养殖/宠物`、`兽药/动保/生物制品`、`饲料/添加剂/原料`、`水产/种苗`、`农牧机械`、`农业种植养殖` 时直接通过。
2. 标题或正文命中种植、养殖、畜牧、水产、饲料、兽药、农资、农艺、植保等词时通过。
3. 纯行政、财务、销售但公司属于农业行业时，标记为 `农业相关企业岗位`，由运营决定是否展示。

## 数据量与更新

- 当前数量估算: 页面分页总数 9026 条，每页 10 条，约 903 页
- 更新频率: 列表有日更岗位，也存在旧岗位和日期不一致记录
- 变更检测: 使用 `source_item_id + content_hash`，并校验 `deadline_at`；截止日期早于采集日的记录标记过期
- 建议采集频率: 列表每日 1 次，按行业筛选的重点岗位每日 2 次；详情只在岗位新增或哈希变化时刷新
- 历史保留: 保留首次和最后发现时间、内容哈希、截止日期；过期岗位标记状态，不物理删除

## 风险与限制

- 登录: 公开岗位无需登录
- robots: `User-agent: * / Disallow:/P_ResumeView.aspx?*`，只禁止个人简历路径；岗位列表和详情未禁止
- 个人隐私: `/P_ResumeView.aspx`、人才求职和个人简历页面不采集
- 版权: 页面明确未经授权不得转载。业务库只保存摘要和来源链接，全文使用需授权
- 权利标记: 记录使用 `attribution-required`，并在 `extra.rights_risk` 保留未经授权不得转载的风险说明
- 结构稳定性: 老式 ASP.NET 表格布局，字段依赖中文标签和表格位置
- 缺失字段: 5 个样本均能读取发布时间；列表相对时间与详情日期可能不一致，不能把相对时间当成发布时间
- 过期风险: 5 个样本截止日期均早于本次验证日期，首页仍可打开，需显式标记过期
- 联系方式: 部分详情页显示真实电话和联系人，可能被模板占位符替换；不得绕过登录或反爬
- 数据质量: 列表和详情薪资、学历字段可能不一致，详情优先
- 未验证项: 全量 903 页可达性、所有筛选参数组合、公司详情页字段、岗位下架和归档规则
- 结构回归: 2026-10-21 已用真实列表和 5 条详情完成复验，`#project_L` 已移除；后续仍以本文的当前选择器为回归基线。

## 验证记录

- 验证方式: 2026-10-21 实际 HTTP GET `Employ.aspx`、5 条 `EmployView.aspx` 详情和 robots；列表页和详情页均返回 200
- 验证结果: 列表页解析出 10 条岗位；5 条详情解析出标题、公司、地点、人数、截止日期、发布时间和职位描述；Scrapy live 运行写入 raw 11、stage 10、候选 10，failure_count 为 0
- 分页验证: 历史审核确认 `page=0` 是默认页，`page=1` 是第二页；本轮未全量遍历
- 未验证项: 筛选 POST 行为、全部页码、登录后投递、联系方式模板占位符的实际渲染规则

## 下载记录

所有文件均小于 100MB，无需 `OVERSIZE.md`。公开仓库只跟踪脱敏后的 `employ-view-13519.html` 和 `employ-view-13520.html` 结构 fixture；下表是 2026-10-21 的本地 live 证据元数据，原始 HTML 不进入 Git。

| 文件 | URL | 取得时间（Asia/Shanghai） | 大小 | SHA-256 |
| --- | --- | --- | ---: | --- |
| `robots.txt` | `http://nongmuhr.com/robots.txt` | 2026-10-21 21:47:14 | 46 | `06E7E0C0C6E2CB346F78BB24B3E80288AE322169F665D7EEF9CF11678CA0B087` |
| `employ-list.html` | `http://nongmuhr.com/Employ.aspx` | 2026-10-21 21:47:14 | 93333 | `B0B9AF635BA338B992DA9875DD1E7845B319C551A92DC5A2D2CF6A76827144C5` |
| `detail-13553.html` | `http://nongmuhr.com/EmployView.aspx?Id=13553` | 2026-10-21 21:48:02 | 24003 | `41BFEB30C5AB598EAAEFDEBD324F44C798351677025183A30578B6FC4B6798DD` |
| `detail-13556.html` | `http://nongmuhr.com/EmployView.aspx?Id=13556` | 2026-10-21 21:48:02 | 28005 | `91A31C7670D6EF94D813D0508217977F022D1D0A2A3F681CFABDF34D84F2010F` |
| `detail-13555.html` | `http://nongmuhr.com/EmployView.aspx?Id=13555` | 2026-10-21 21:48:02 | 28015 | `71D5B56E57FC0771B5D0518194629B889E621B3037385E5079D85ACDDB9422B5` |
| `detail-13554.html` | `http://nongmuhr.com/EmployView.aspx?Id=13554` | 2026-10-21 21:48:02 | 28080 | `144F75D5EDF99AC33385D27C08D8E2A0F8A91C95E52AF6751FDF5FCABE5DC753` |
| `detail-13561.html` | `http://nongmuhr.com/EmployView.aspx?Id=13561` | 2026-10-21 21:48:03 | 25764 | `3EF339AFDF69A481F836DD6DF11DFAB68CCF1A963F98B8035810523BDCE6EBCB` |

## 审核要求

- 入口可打开: 是
- 样本可复现: 是，两个详情 URL 均可直接打开
- 字段映射完整: 是，联系方式、模板占位符和过期风险已说明
- 详情 URL 可直达: 是

## 实现验证

- 2026-10-21 使用真实结构更新 parser、replay 和脱敏 fixture；旧 `#project_L` 选择器已移除。
- 2026-10-21 Scrapy live 运行：列表 10 条，详情 10 条均解析成功，raw 11、stage 10、候选 10、failure_count 0。
- 长期详情 URL 使用 `EmployView.aspx?Id={id}`。零基分页按本文记录，后续实现分页时从 `page=0` 开始。
- 2026-10-22 岗位地点写入统一使用 `工作地点` 原文和 `company_region` 兜底归一化；每条岗位同时写 `std_jobs`、`std_job_sources` 和 `std_job_locations`。`不限地点` 等无可用地点文本不再静默跳过，缺少可用地点时写 `candidate_status=blocked`，原因 `location:unavailable`。

