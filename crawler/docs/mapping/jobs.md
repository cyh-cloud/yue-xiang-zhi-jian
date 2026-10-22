# 招聘岗位字段映射

状态: draft

日期: 2026-10-19

本文覆盖全国农业与乡村招聘岗位。当前最小可用链路写现有 `recruitments` 和 `recruitment_sources`，不写 `job_listings`。新增建议表 `recruitment_postings` 和 `recruitment_posting_sources` 保留为后续独立岗位索引方案。

## 边界

- `job_listings` 是企业站内岗位，支持站内申请和审核，不是公开采集目标。
- `recruitments` 是现有公开招聘表。本阶段把 `candidate` 岗位以 `draft` / `pending_review` 状态写入，批次、来源和版权证据保存在 `extra` 与 `recruitment_sources.extra`。
- `recruitment_postings` 是建议新增的公开岗位索引表，用于筛选和跳转原站，不支持站内投递。
- `recruitment_posting_sources` 保存每个岗位的来源、快照哈希和抓取状态。
- 不采集个人简历、求职者信息、登录后联系方式、投递记录或任何个人隐私。

## 来源

| 来源 ID | 站点 | 发现入口 | 详情模式 | 访问等级 | 已知限制 |
| --- | --- | --- | --- | --- | --- |
| `nzrc` | 中国农业人才网 | `career_seek.html` | `company/jobs/{job_id}.html` | `public` | 分页为 ASP.NET PostBack；联系方式需登录 |
| `nongmuhr` | 农牧人才网 | `Employ.aspx` | `EmployView.aspx?id={job_id}` | `public` | 公开列表和详情无需登录 |
| `5ajob` | 5A 农业人才网 | `/job/` | 两套 canonical 详情 URL | `public` | 无稳定发布时间；部分有效期由脚本注入 |

## 字段映射

| 业务字段 | 来源字段 | crawler std 层 | 建议业务表.字段 | 说明 |
| --- | --- | --- | --- | --- |
| 来源站 | 来源 ID | `std_jobs.source_id` | `recruitment_postings.source_id` | `nzrc`、`nongmuhr` 或 `5ajob` |
| 原始详情 URL | canonical 详情页 | `std_jobs.source_url` | `recruitment_postings.source_url` | 直接打开原岗位，不用列表页或公司首页 |
| 岗位标题 | 详情标题 | `std_jobs.title` | `recruitment_postings.title` | 保留原岗位名；多岗位标题保留原文 |
| 公司/机构 | 详情公司名 | `std_jobs.company_name` | `recruitment_postings.company_name` | 只取公开组织名 |
| 公司 URL | 详情公司链接 | `std_jobs.company_url` | `recruitment_postings.company_url` | 可为空 |
| 地区 | 工作地点原文 | `std_jobs.location_raw` | `recruitment_postings.location_raw` | 同时生成 `region`，不丢失原文 |
| 地区规范化 | 省、市拆分结果 | `std_jobs.province`、`city` | `recruitment_postings.province`、`city` | 无法确认时 null |
| 薪资 | 承诺月薪或薪资区间 | `std_jobs.salary_raw` | `recruitment_postings.salary_raw` | `面议` 原样保存，不推算金额 |
| 薪资数值 | 可解析区间 | `std_jobs.extra` 的 `salary_min`、`salary_max`、`salary_period` | 不适用 | 只作为原名附加信息，解析失败只保留原文 |
| 学历 | 学历要求 | `std_jobs.education_raw` | `recruitment_postings.education_raw` | 保留 `大专`、`本科`、`不限` 等原文 |
| 经验 | 工作经验 | `std_jobs.experience_raw` | `recruitment_postings.experience_raw` | 可派生 `experience_min_years` |
| 岗位描述 | 岗位职责和任职要求 | `std_jobs.description`、`requirements` | 同名 | 采集库可存全文，业务库按授权展示摘要 |
| 发布时间 | 详情发布日期 | `std_jobs.published_at` | `recruitment_postings.published_at` | 解析为 ISO 日期，解析失败保留原值 |
| 截止时间 | 截止日期或有效期 | `deadline_at`、`std_jobs.extra.deadline_raw` | 同名 | `nzrc` 的“有效时间 90 天”不能直接当截止日期，需结合发布日期 |
| 联系方式 | 公开联系人、电话、邮箱 | `extra.contact_name`、`extra.contact_phone`、`extra.contact_email` | 同名 | 默认不公开展示；登录后才能看的内容不采集 |
| 原始类别 | 来源行业、职位类别或岗位类型 | `std_jobs.extra` 的 `source_category` | `recruitment_postings.source_category` | 保留来源枚举，不映射成平台自创分类 |
| 农业相关性 | 标题、行业、专业和正文规则 | `std_jobs.extra.agriculture_relevance` | `recruitment_postings.is_agriculture_related` | 反例：`前台接待` 不因公司涉农而自动纳入 |
| 抓取时间 | 响应取得时间 | `std_jobs.retrieved_at` | `recruitment_posting_sources.retrieved_at` | 每次请求记录 |
| 首次/最后发现 | 列表或详情出现时间 | `first_seen_at`、`last_seen_at` | `recruitment_postings.first_seen_at`、`last_seen_at` | 过期岗位不物理删除 |
| 内容哈希 | 规范化详情正文 SHA-256 | `content_hash` | `recruitment_postings.content_hash` | 用于变化检测 |
| 来源快照 | raw 文件路径和 HTTP 状态 | `raw_fetches`、`raw_files` | `recruitment_posting_sources.raw_snapshot_path`、`http_status` | 只保存公开响应 |

## 来源表

`recruitment_posting_sources` 建议字段:

- `id`
- `posting_id`
- `source_id`
- `source_item_id`
- `source_url`
- `retrieved_at`
- `http_status`
- `content_hash`
- `raw_snapshot_path`
- `is_primary`

自然键: `source_id + source_item_id`。缺少来源 ID 时退回 canonical `source_url`，不要用岗位标题做唯一键。

## 不采内容

- `nzrc` 的 `/P_ResumeView.aspx`、人才求职、个人简历和登录后联系方式。
- `nongmuhr` 的简历路径和任何登录后页面。
- `5ajob` 的 `/personal/`、`/resume/`、登录后投递和受限公司页。
- 求职者姓名、身份证、手机号、邮箱、住址、教育经历、工作经历和投递记录。
- 企业联系人个人信息除公开岗位联系方式外不扩展采集。

## 过滤规则

- 行业字段属于种植、养殖、水产、畜牧、饲料、兽药、农资、农机、园艺、农业科研和乡村服务时优先纳入。
- 标题或正文命中农业、畜牧、水产、植保、农艺、作物、种子、肥料、饲料、兽药等词时通过。
- 纯行政、财务、前台、销售岗位只有与农业岗位职责或农业专业要求相关时才纳入。
- 每条纳入和排除都保留 `is_agriculture_related` 的判定依据摘要。
- 截止日期早于采集日的记录在转换计划中标记 `expired`，不删除。

## 落层

| 内容 | crawler 层 | 粤乡智匠 |
| --- | --- | --- |
| 列表和详情 HTML、Ajax 公开响应 | raw | 不进入业务库 |
| 单来源列表行和详情字段 | stage，一来源一表 | 不直接进入业务库 |
| 统一岗位字段 | std | `recruitments`（当前最小链路） |
| 来源快照、HTTP 状态、哈希 | std | `recruitment_sources`（当前最小链路） |
| 个人简历和登录后数据 | 不采集 | 不进入业务库 |

## 已知缺口

- `5ajob` 没有稳定发布时间，发布时间字段写 null 或“待验证”。
- `nzrc` 的搜索和分页依赖 PostBack，公开 GET 搜索 URL 不可复现。
- `nongmuhr` 详情缺少独立发布时间时只能使用列表相对时间作为发现信号。
- 三个来源的薪资、学历和经验文本格式不一致。
- 联系方式能否展示需逐来源确认授权，业务默认不公开个人联系方式。

## 待验证

- `5ajob` `#jobexpire` 在不同页面脚本下是否稳定。
- `nzrc` 903 页是否都存在且不重复。
- 每个来源的转载授权和联系方式展示范围。
- 农业主题过滤规则在真实样本上的误收率和漏收率。
