# 农牧人才网

来源 ID: `nongmuhr`

状态: `approved-with-gaps`

验证时间: `2026-10-19 01:06 Asia/Shanghai`

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
| 列表分页 | `http://nongmuhr.com/Employ.aspx?pubtime=-1&experience=-1&page={page}` | GET | `page` 从 1 开始，第二页已实测 |
| 岗位详情模式 | `http://nongmuhr.com/EmployView.aspx?id={job_id}` | GET | 例如 `id=13520`、`id=13519`，均返回 200 |
| 企业详情模式 | `http://nongmuhr.com/CompanyView.aspx?Id={company_id}` | GET | 详情页公司链接，例如 `Id=2333` |
| robots | `http://nongmuhr.com/robots.txt` | GET | 返回 200 |

首页导航“企业招聘”、首页“最新招聘信息”和 `Employ.aspx` 都指向同一岗位列表。`EmployView.aspx` 大写 `Id` 和小写 `id` 均可工作，实现时统一使用小写 `id`。

## 请求与分页

- 请求方式: 列表和详情均可用 GET
- 列表筛选参数: `txtCompany`、`txtEmploy`、`ddlIndustry`、`ddlPubtime`、`ddlExperience`、`ddlJobclass`、`ddlSalary`、`ddlEducation`、`ddlCompanyclass`、`txtGzdd`、`selArea`、`txtKeyword`
- 页面分页参数: `pubtime=-1`、`experience=-1`、`page={page}`
- 每页数量: 10
- 总数字段: 页面脚本 `$("#Pagination").pagination(9026, { items_per_page: 10 })`
- 总页数: 约 903 页，由总数除以每页数量得到
- 职位搜索参数示例: 职位名称输入框 `txtEmploy`，行业下拉 `ddlIndustry`
- 行业筛选值: `园林/园艺/花卉`、`种子/化肥/农药`、`养殖/宠物`、`兽药/动保/生物制品`、`饲料/添加剂/原料`、`水产/种苗`、`农牧机械`、`农业种植养殖`
- 发布时间筛选: `ddlPubtime` 可取 `3`、`7`、`30`
- 经验筛选: `ddlExperience` 可取 `0`、`1`、`2`、`3`、`5`、`8`、`10`
- 工作类型: `ddlJobclass` 可取 `全职`、`兼职`
- 学历: `ddlEducation` 可取 `不限`、`初中`、`高中`、`中技`、`中专`、`大专`、`本科`、`硕士`、`博士`
- 登录要求: 公开列表和详情无需登录

分页链接由 `jquery.pagination.js` 生成，模板为 `?pubtime=-1&experience=-1&page=__id__`。后续采集只需保留筛选参数并替换 `page`，不需要处理 ASP.NET 的 `__VIEWSTATE`。

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
| 分页容器 | `#Pagination` | 由 `jquery.pagination.js` 接收总数 9026 |

详情页:

| 字段 | 选择器 | 说明 |
| --- | --- | --- |
| 岗位名称 | `#joblist .joblistonelf` | 例如 `QC`、`农资销售员` |
| 公司名称 | `#hlCompanyName` | 文本为公司名 |
| 公司详情 URL | `#hlCompanyName[href]` | 相对 URL `CompanyView.aspx?Id={company_id}` |
| 工作性质 | `td:contains("工作性质：") + td` | 例如 `全职` |
| 部门 | `td:contains("部 门：") + td` | 例如 `质量部` |
| 招聘人数 | `td:contains("招聘人数：") + td` | 纯数字 |
| 截止日期 | `td:contains("截止日期：") + td` | 格式 `YYYY-MM-DD` |
| 工作经验 | `td:contains("工作经验：") + td` | 例如 `3年以上` |
| 学历 | `td:contains("学 历：") + td` | 例如 `大专` |
| 工作地点 | `td:contains("工作地点：") + td` | 可为多地区，以 `|` 分隔 |
| 性别 | `td:contains("性 别：") + td` | 例如 `不限` |
| 年龄 | `td:contains("年 龄：") + td` | 例如 `30-45` |
| 邮箱 | `td:contains("邮 件：") + td` | 可能是模板占位符，需判定为不可用 |
| 联系人 | `td:contains("联系人：") + td` | 公开可见时保留，不在文档转录 |
| 联系电话 | `td:contains("联系电话：") + td` | 公开可见时保留，不在文档转录 |
| 职位描述 | 详情页主表最后一个 `td[style*="word-break"]` | 含岗位职责和任职条件 |
| 发布时间 | `td:contains("发布时间：") + td` | 格式 `YYYY-MM-DD` |
| 公司行业 | `#joblist1 td.y12x` | 文本内混合行业、规模、性质、地区 |
| 公司介绍 | `#joblist1 td[colspan="2"]` | 公司简介 |

联系方式是公开页面字段，但仍属于企业联系人信息。采集库可保存公开值并限制访问，业务库默认只展示来源链接，不直接公开个人手机号或联系人姓名。

### 文件附件

本来源未发现岗位附件。

## 真实样本

### 样本 1

- 详情 URL: `http://nongmuhr.com/EmployView.aspx?id=13520`
- 列表位置: `Employ.aspx` 第 1 页第 1 条
- 抓取时间: `2026-10-19 01:04 Asia/Shanghai`
- 岗位名称: `QC`
- 公司: `武汉农大生物科技有限公司`
- 工作性质: `全职`
- 部门: `质量部`
- 招聘人数: `1`
- 工作经验: `3年以上`
- 学历: `大专`
- 工作地点: `武汉市`
- 性别: `不限`
- 年龄: `30-45`
- 截止日期: `2025-11-30`
- 发布时间: 详情页未显示独立发布时间；列表相对时间为 `3天前`
- 正文摘要: 负责原辅材料、半成品、成品的理化和微生物检验，出具检验报告，维护留样和实验室仪器
- 联系方式: 页面公开显示联系电话和联系人，本文档不转录；邮箱为模板占位符
- 目标映射: `recruitment_postings`，畜牧动保企业质检岗位

### 样本 2

- 详情 URL: `http://nongmuhr.com/EmployView.aspx?id=13519`
- 列表位置: `Employ.aspx` 第 1 页第 2 条
- 抓取时间: `2026-10-19 01:06 Asia/Shanghai`
- 岗位名称: `农资销售员`
- 公司: `贵州煜恩企业管理服务有限公司`
- 工作性质: `全职`
- 部门: `销售事业部`
- 招聘人数: `10`
- 工作经验: `3年以上`
- 学历: `大专`
- 工作地点: `贵州省|四川省|重庆市|成都市|昆明市`
- 性别: `不限`
- 年龄: `28-35`
- 截止日期: `2025-12-26`
- 发布时间: `2025-12-23`
- 正文摘要: 维护和开发区域客户、签订销售合同、催收销售款；要求肥料或农业行业销售 3 年以上经验，税前工资 4K-6K+
- 联系方式: 页面公开显示联系人、电话和模板化邮箱，本文档不转录
- 目标映射: `recruitment_postings`，农资销售岗位

两个样本的相对刷新时间与详情日期存在明显不一致，且截止日期早于验证日期。实现时以详情页日期和截止日期为准，把列表相对时间只作为发现信号，并将疑似过期记录标记为 `expired`。

## 字段映射

### crawler std 层

目标标准实体为 `std_recruitment_posting`。raw 层保存列表和详情 HTML；stage 层保留 `nongmuhr_job` 原始字段；std 层统一岗位字段。

| 来源字段 | crawler 表.字段 | 粤乡智匠表.字段 | 转换说明 |
| --- | --- | --- | --- |
| `EmployView.aspx?id={id}` 中的 `id` | `std_recruitment_posting.source_item_id` | `recruitment_postings.source_item_id` | 保留字符串 |
| 详情 URL | `std_recruitment_posting.source_url` | `recruitment_postings.source_url` | 规范化为绝对 URL，作为来源内自然键 |
| `来源 ID = nongmuhr` | `std_recruitment_posting.source_id` | `recruitment_posting_sources.source_id` | 固定 `nongmuhr` |
| `.joblistonelf` | `std_recruitment_posting.title` | `recruitment_postings.title` | 清理空白 |
| `#hlCompanyName` | `std_recruitment_posting.company_name` | `recruitment_postings.company_name` | 直接映射 |
| `#hlCompanyName[href]` | `std_recruitment_posting.company_url` | `recruitment_postings.company_url` | 转绝对 URL |
| `工作性质` | `std_recruitment_posting.employment_type` | `recruitment_postings.employment_type` | 如 `全职` |
| `部 门` | `std_recruitment_posting.department` | `recruitment_postings.department` | 直接映射 |
| `招聘人数` | `std_recruitment_posting.headcount` | `recruitment_postings.headcount` | 转整数 |
| `截止日期` | `std_recruitment_posting.deadline_at` | `recruitment_postings.deadline_at` | 解析为 ISO 日期 |
| `工作经验` | `std_recruitment_posting.experience_raw` | `recruitment_postings.experience_raw` | 保留原文，可派生 `experience_min_years` |
| `学 历` | `std_recruitment_posting.education_raw` | `recruitment_postings.education_raw` | 直接映射 |
| `工作地点` | `std_recruitment_posting.location_raw` | `recruitment_postings.location_raw` | 保留 `|` 分隔的原文，拆首个到 `region` |
| `性 别` | `std_recruitment_posting.gender_requirement` | `recruitment_postings.gender_requirement` | 直接映射 |
| `年 龄` | `std_recruitment_posting.age_requirement` | `recruitment_postings.age_requirement` | 保留区间原文 |
| `邮 件` | `std_recruitment_posting.contact_email` | `recruitment_postings.contact_email` | 识别 `{{EMAIL_*}}` 为模板占位，置 null |
| `联系人` | `std_recruitment_posting.contact_name` | `recruitment_postings.contact_name` | 公开值可入库，默认不公开展示 |
| `联系电话` | `std_recruitment_posting.contact_phone` | `recruitment_postings.contact_phone` | 公开值可入库，默认不公开展示 |
| 职位描述 `td[style*="word-break"]` | `std_recruitment_posting.description_html` | `recruitment_postings.description` | 清洗 HTML，保留职责和要求 |
| `发布时间` | `std_recruitment_posting.published_at` | `recruitment_postings.published_at` | 解析为 ISO 日期 |
| 公司行业/规模/性质/地区 | `std_recruitment_posting.company_industry` 等 | `recruitment_postings.company_industry` 等 | 从 `#joblist1 td.y12x` 分段解析 |
| 公司介绍 | `std_recruitment_posting.company_description` | `recruitment_postings.company_description` | 可截断为摘要，避免全文转载 |
| 列表刷新时间 | `std_recruitment_posting.listed_relative_time` | `recruitment_postings.listed_relative_time` | 只作发现信号，不用于精确日期 |
| 详情 HTML 正文 | `std_recruitment_posting.content_hash` | `recruitment_postings.content_hash` | 对规范化正文计算 SHA-256 |
| 抓取时间 | `std_recruitment_posting.fetched_at` | `recruitment_postings.fetched_at` | 每次采集更新 |

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
- 结构稳定性: 老式 ASP.NET 表格布局，字段依赖中文标签和表格位置
- 缺失字段: 样本 1 无独立发布时间；列表相对时间与详情日期不一致
- 过期风险: 两个样本截止日期均已早于验证日期，首页仍可打开，需显式标记过期
- 联系方式: 部分详情页显示真实电话和联系人，可能被模板占位符替换；不得绕过登录或反爬
- 数据质量: 列表和详情薪资、学历字段可能不一致，详情优先
- 未验证项: 全量 903 页可达性、所有筛选参数组合、公司详情页字段、岗位下架和归档规则

## 验证记录

- 验证方式: 实际 HTTP GET 首页、`Employ.aspx`、`Employ.aspx?page=2`、两个 `EmployView.aspx` 详情和 robots
- 验证结果: 所有目标页面返回 200；分页第二页返回 200 且岗位 ID 变化；详情字段和两个样本可复现
- 未验证项: 筛选 POST 行为、全部页码、登录后投递、联系方式模板占位符的实际渲染规则

## 下载记录

所有文件均小于 100MB，无需 `OVERSIZE.md`。

| 文件 | URL | 大小 | SHA-256 |
| --- | --- | ---: | --- |
| `home.html` | `http://nongmuhr.com/` | 241552 | `D9A9089EA2540A8414BC9F3BB472424A9B8BEEC91083EC842E9711CDAD3C9811` |
| `home.headers` | `http://nongmuhr.com/` | 312 | `3414652E3D4C78BE521BE1E7F48C820A6505F3243693A8026500E0796F3E2DE9` |
| `robots.txt` | `http://nongmuhr.com/robots.txt` | 46 | `06E7E0C0C6E2CB346F78BB24B3E80288AE322169F665D7EEF9CF11678CA0B087` |
| `robots.headers` | `http://nongmuhr.com/robots.txt` | 248 | `92993A04BC3EB9AD39D9500EDE1185CEE3B93A015DD0A05D5A954161297AD8CF` |
| `employ-list.html` | `http://nongmuhr.com/Employ.aspx` | 93566 | `DB33A0758DDBBC8F6217609B39F99144D6C77A9BAF66039FF4586F0F1A7301B8` |
| `employ-list.headers` | `http://nongmuhr.com/Employ.aspx` | 311 | `1728611A40823BF5F8283B514F2D0A8143292B84895167D155EF9E21A4B61209` |
| `employ-page2.html` | `http://nongmuhr.com/Employ.aspx?pubtime=-1&experience=-1&page=2` | 93242 | `FAED08926D961AE7FE3BEE65D247F0E217FAB7D587538A1F9496F7A815237920` |
| `employ-page2.headers` | `http://nongmuhr.com/Employ.aspx?pubtime=-1&experience=-1&page=2` | 311 | `D9BA8D3AB9F72617BAB2D259E3D7CFA320DCA87D66FAA9F8BAB6A332A62227A5` |
| `employ-view-13520.html` | `http://nongmuhr.com/EmployView.aspx?id=13520` | 27533 | `1CD9AA3390C48A8F63DB209E832FAB9F539A8FCCF119A7A704E551CE2D65EBEA` |
| `employ-view-13520.headers` | `http://nongmuhr.com/EmployView.aspx?id=13520` | 311 | `FFF52B8F550ED7185C7050A518F1E56523FECE3E39C108BD1CD82D4B34A2FBC5` |
| `employ-view-13519.html` | `http://nongmuhr.com/EmployView.aspx?id=13519` | 24991 | `2D956126DAF9F5EFB6B3CD8BA76BF966C7244B8EE022663A6DE645CBBE6930A0` |
| `employ-view-13519.headers` | `http://nongmuhr.com/EmployView.aspx?id=13519` | 311 | `66384BC2745CD35A65324479F84BF00B4F64C739D91EC67A4C1A012AE235F70F` |

## 审核要求

- 入口可打开: 是
- 样本可复现: 是，两个详情 URL 均可直接打开
- 字段映射完整: 是，联系方式、模板占位符和过期风险已说明
- 详情 URL 可直达: 是
