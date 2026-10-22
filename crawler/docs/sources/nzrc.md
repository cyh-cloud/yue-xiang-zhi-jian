# 中国农业人才网

共享契约: 见 `sources/CONTRACT.md`。通用字段、访问等级、状态和详情 URL 规则不在本文重复。

来源 ID: `nzrc`

状态: `approved-with-gaps`

权利状态: `attribution-required`

验证时间: `2026-10-19 01:07 Asia/Shanghai`

## 来源概况

- 名称: 中国农业人才网，页面标题也使用“中国农资人才网”
- 域名: `www.nzrc.com.cn`
- 主管机构: 商业招聘站，页面版权署名 `nongzirencai.com`
- 内容域: `jobs`
- 优先级: P1
- 访问等级: `public`
- `license_or_usage`: 未发现开放数据许可。详情页和站点页脚均提示招聘信息及作品未经授权不得转载。仅采集公开岗位索引和岗位字段，用于跳转来源页和内部筛选，发布前需取得授权或用摘要加链接方式展示。
- `confidence`: 高。公开首页、职位查询列表、两个岗位详情页和联系方式接口均已实测。
- 收录边界: 只收农业、农资、种植、养殖、水产、乡村相关岗位。登录页、企业后台、简历页和个人求职信息不采集。

## 入口

| 用途 | URL | 方法 | 说明 |
| --- | --- | --- | --- |
| 首页 | `http://www.nzrc.com.cn/` | GET | 返回 200，可见岗位、企业和职位查询入口 |
| 职位列表页 | `http://www.nzrc.com.cn/career_seek.html` | GET | 返回 200，首页“招聘信息”入口 |
| 岗位搜索 URL | `http://www.nzrc.com.cn/user/personjobsearch_list.aspx?whichfile=6.2` | GET | 首页搜索表单目标；直接 GET 当前返回“文件不存在”页面，需从职位查询页提交或使用会话流程 |
| 岗位详情模式 | `http://www.nzrc.com.cn/company/jobs/{job_id}.html` | GET | 例如 `8235500.html`、`8240109.html`，均返回 200 |
| 企业详情模式 | `http://www.nzrc.com.cn/company/companys/{company_id}.html` | GET | 例如 `14747.html`、`16381.html` |
| 联系方式接口 | `http://www.nzrc.com.cn/company/Ajax.html?action=jobs&id={company_id}&zid={job_id}` | GET | 未登录返回 `islogin=0` 和空联系方式 |

职位查询页是岗位发现的稳定入口。页面同时提供关键词、职位类别 `gzhiwei` 和地区 `area` 筛选。页面内部搜索表单提交到 `user/personjobsearch_list.aspx`，但直接 GET 该地址会落到 404；实现时应优先按职位查询页的列表 DOM 采集，或用 Playwright 走页面表单，不要依赖手工拼接搜索 URL。

## 请求与分页

- 请求方式: GET 页面；搜索表单为 POST
- 列表页总数: 职位查询页第一页显示 20 条
- 分页控件: ASP.NET `AspNetPager 7.4.3`，页码通过 `__doPostBack('ctl00$ContentPlaceHolder1$AspNetPager1', '{page}')` 提交
- 分页状态: 当前页为第 1 页，页码控件显示共 903 页
- 每页数量: 20
- 查询参数: `gzhiwei`、`area`、`szhiwei=企业职位`，以及隐藏字段 `__VIEWSTATE`、`__VIEWSTATEGENERATOR`、`__EVENTTARGET`、`__EVENTARGUMENT`
- 关键词参数: 首页表单把它们命名为 `jobname` 或 `companyname`；职位查询页本身使用分类下拉筛选
- 总数字段: 未找到直接文本总数。页码总数 903 乘以每页 20，量级约 18000 条，不能当成精确岗位数
- 筛选字段: 职位类别 `gzhiwei`、地区 `area`、关键词、企业名称
- 登录要求: 列表和岗位详情无需登录；联系方式需要个人登录并完善简历

分页实现建议:

1. 先 GET `career_seek.html` 获取表单隐藏字段。
2. 用 Playwright 点击页码，或把 `__EVENTTARGET` 设为 `ctl00$ContentPlaceHolder1$AspNetPager1`、`__EVENTARGUMENT` 设为目标页码后 POST。
3. 每页解析 `div.detail_headline`。
4. 详情 URL 规范化为 `company/jobs/{job_id}.html`。

## 字段定位

### HTML DOM

列表页:

| 字段 | 选择器 | 说明 |
| --- | --- | --- |
| 列表项 | `div.detail_headline` | 每条岗位一行 |
| 列表岗位 ID | `div.detail_headline input[name="checkbox2"]` | `value` 为岗位 ID，例如 `8237578` |
| 岗位名称 | `div.career_name a.green` | 文本可能包含多个岗位，以逗号分隔 |
| 岗位详情 URL | `div.career_name a.green` | `href` 相对路径 `company/jobs/{id}.html` |
| 公司名称 | `div.corp_name a.green` | 文本为公司名 |
| 公司详情 URL | `div.corp_name a.green` | `href` 相对路径 `company/companys/{id}.html` |
| 所在地 | `div.suozaidi` | 例如 `南昌市`、`安徽` |
| 更新时间 | `div.shijian` | 例如 `2026-10-18` |
| 职位类别筛选 | `select[name="gzhiwei"]` | 如 `农艺师`、`植保医生`、`技术员`、`科研人员` |
| 地区筛选 | `select[name="area"]` | 省、市两级选项 |

详情页:

| 字段 | 选择器 | 说明 |
| --- | --- | --- |
| 公司名称 | `#project_L h1 a` | 同时可取 `href` 得公司详情 URL |
| 招聘职位 | `#project_L h2` | 文本以 `招聘职位：` 开头，可能含多个岗位 |
| 工作地点 | `#project_L li:contains("工作地点：")` | 文本清理 `工作地点：` 和多余空白 |
| 有效时间 | `#project_L li:contains("有效时间：")` | 例如 `90 天`，不是截止日期 |
| 招聘方式 | `#project_L li:contains("招聘方式：")` | 例如 `全职` |
| 招聘人数 | `#project_L li:contains("招聘人数：")` | 例如 `1人` |
| 性别要求 | `#project_L li:contains("性别要求：")` | 例如 `男`、`不限` |
| 承诺月薪 | `#project_L li:contains("承诺月薪：")` | 例如 `面议` |
| 发布日期 | `#project_L li:contains("发布日期：")` | 例如 `2026-10-17` |
| 学历要求 | `#project_L li:contains("学历要求：")` | 例如 `大专`、`专科` |
| 岗位正文 | `#brief_info p` | 包含岗位职责、任职要求、工作目标和待遇 |
| 联系方式地址 | `#address` | 未登录时为星号占位 |
| 联系方式联系人 | `#officeuser` | 未登录时为星号占位 |
| 联系方式电话 | `#fixtel` | 未登录时为星号占位 |
| 联系方式传真 | `#fax` | 未登录时为星号占位 |
| 联系方式网址 | `#site` | 未登录时为星号占位 |
| 联系方式邮编 | `#postNumber` | 未登录时为星号占位 |
| 联系方式登录提示 | `#needlogin` | 未登录时显示 |

联系方式接口:

| 字段 | 含义 | 样本 |
| --- | --- | --- |
| `islogin` | 是否登录 | `"0"` |
| `address` | 企业地址 | 未登录为空 |
| `site` | 企业网址 | 未登录为空 |
| `officeuser` | 联系人 | 未登录为空 |
| `tel` | 电话 | 未登录为空 |
| `fax` | 传真 | 未登录为空 |
| `post` | 邮编 | 未登录为空 |
| `email` | 邮箱 | 未登录为空 |

### 文件附件

本来源未发现岗位附件。

## 真实样本

### 样本 1

- 详情 URL: `http://www.nzrc.com.cn/company/jobs/8235500.html`
- 列表位置: `career_seek.html` 第 1 页，企业 `江苏省农药研究所股份有限公司`
- 抓取时间: `2026-10-19 01:03 Asia/Shanghai`
- 岗位名称: `【广东】销售经理,区域经理`
- 公司: `江苏省农药研究所股份有限公司`
- 工作地点: `广东` 或 `广西`
- 招聘方式: `全职`
- 招聘人数: `1人`
- 承诺月薪: `面议`
- 学历要求: `大专`
- 性别要求: `男`
- 发布日期: `2026-10-17`
- 有效时间: `90 天`
- 正文摘要: 面向渠道和终端用户做农药产品推广，要求植保、农学、农药、园艺、市场营销等专业优先，3 年以上农药销售经验优先
- 目标映射: `recruitment_postings`，农业投入品销售岗位

### 样本 2

- 详情 URL: `http://www.nzrc.com.cn/company/jobs/8240109.html`
- 列表位置: `career_seek.html` 第 1 页，企业 `海南正茂生物科技有限公司`
- 抓取时间: `2026-10-19 01:04 Asia/Shanghai`
- 岗位名称: `农艺师`
- 公司: `海南正茂生物科技有限公司`
- 工作地点: `河北`
- 招聘方式: `全职`
- 招聘人数: `1人`
- 承诺月薪: `面议`
- 学历要求: `专科`
- 性别要求: `不限`
- 发布日期: `2026-10-18`
- 有效时间: `90 天`
- 正文摘要: 负责田间作物病害诊断、土壤问题检测、绿色增效和土壤修复方案，开展田间示范试验、农户技术培训
- 目标映射: `recruitment_postings`，农艺技术服务岗位

## 字段映射

### crawler std 层

目标标准实体为 `std_jobs`。raw 层保存列表和详情 HTML；stage 层保留 `nzrc_job` 的原始字段和抓取上下文；std 层统一岗位字段。

| 来源字段 | crawler 表.字段 | 粤乡智匠表.字段 | 转换说明 |
| --- | --- | --- | --- |
| `checkbox2.value` / 详情 URL 中的 `{job_id}` | `std_jobs.source_item_id` | `recruitment_postings.source_item_id` | 来源内岗位 ID，保留字符串 |
| 详情 URL | `std_jobs.source_url` | `recruitment_postings.source_url` | 规范化为绝对 URL，作为来源内自然键 |
| `来源 ID = nzrc` | `std_jobs.source_id` | `recruitment_posting_sources.source_id` | 固定 `nzrc` |
| `h2` | `std_jobs.title` | `recruitment_postings.title` | 去掉 `招聘职位：` 前缀，多个岗位以逗号拆分为 `title_extra` |
| `h1 a` | `std_jobs.company_name` | `recruitment_postings.company_name` | 直接映射 |
| `h1 a[href]` | `std_jobs.company_url` | `recruitment_postings.company_url` | 转绝对 URL |
| `li:contains("工作地点")` | `std_jobs.location_raw` | `recruitment_postings.location_raw` | 保留原文，拆出首个地区到 `region` |
| `li:contains("招聘方式")` | `std_jobs.employment_type` | `recruitment_postings.employment_type` | 如 `全职` |
| `li:contains("招聘人数")` | `std_jobs.headcount` | `recruitment_postings.headcount` | 去掉 `人` 后转整数，原文进入 `std_jobs.extra.headcount_raw`，无法解析存 null |
| `li:contains("承诺月薪")` | `std_jobs.salary_raw` | `recruitment_postings.salary_raw` | `面议` 保持原文，不推断金额 |
| `li:contains("学历要求")` | `std_jobs.education_raw` | `recruitment_postings.education_raw` | 直接映射 |
| `li:contains("性别要求")` | `std_jobs.gender_requirement` | `recruitment_postings.gender_requirement` | 直接映射 |
| `li:contains("发布日期")` | `std_jobs.published_at` | `recruitment_postings.published_at` | 解析为 ISO 日期 |
| `li:contains("有效时间")` | `std_jobs.validity_days` | `recruitment_postings.validity_days` | 解析天数；截止日按发布日期加天数计算，并与抓取时间交叉校验 |
| `#brief_info p` | `std_jobs.description` | `recruitment_postings.description` | 保留清洗后纯文本，移除脚本和样式 |
| `#brief_info p` 中职责和要求 | `std_jobs.requirements` | `recruitment_postings.requirements` | 可按“岗位职责”“任职要求”分段 |
| `#address` / Ajax `address` | `std_jobs.extra.company_address` | `recruitment_postings.company_address` | 未登录为 null，不越过登录限制 |
| `#officeuser` / Ajax `officeuser` | `std_jobs.extra.public_contact_name` | `recruitment_postings.contact_name` | 未登录为 null |
| `#fixtel` / Ajax `tel` | `std_jobs.extra.public_contact_phone` | `recruitment_postings.contact_phone` | 未登录为 null；公开页有值时可保留 |
| `#fax` / Ajax `fax` | `std_jobs.extra.contact_fax` | `recruitment_postings.contact_fax` | 未登录为 null |
| `#site` / Ajax `site` | `std_jobs.extra.company_website` | `recruitment_postings.company_website` | 转绝对 URL |
| `#postNumber` / Ajax `post` | `std_jobs.extra.postal_code` | `recruitment_postings.postal_code` | 未登录为 null |
| Ajax `email` | `std_jobs.extra.public_contact_email` | `recruitment_postings.contact_email` | 只接收公开响应中的值，不登录提取 |
| 列表 `div.suozaidi` | `std_jobs.location_raw` | `recruitment_postings.location_raw` | 详情缺失时回退 |
| 列表 `div.shijian` | `std_jobs.extra.listed_at` | `recruitment_postings.listed_at` | 详情发布日期缺失时回退 |
| 详情 HTML 正文 | `std_jobs.content_hash` | `recruitment_postings.content_hash` | 对规范化正文计算 SHA-256 |
| 抓取时间 | `std_jobs.retrieved_at` | `recruitment_postings.retrieved_at` | 每次采集更新 |

### 粤乡智匠建议表

写入 `recruitment_postings` 和 `recruitment_posting_sources`，不写入 `job_listings` 或 `recruitments`。

`recruitment_postings` 建议字段:

- `id`
- `source_id`
- `source_item_id`
- `source_url`
- `title`
- `title_extra`
- `company_name`
- `company_url`
- `company_address`
- `region`
- `location_raw`
- `employment_type`
- `headcount`
- `salary_raw`
- `education_raw`
- `experience_raw`
- `gender_requirement`
- `published_at`
- `validity_days`
- `deadline_at`
- `description`
- `requirements`
- `contact_name`
- `contact_phone`
- `contact_fax`
- `contact_email`
- `company_website`
- `postal_code`
- `industry`
- `is_agriculture_related`
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

自然键: `source_id + source_item_id`，并保留 `source_url` 唯一约束用于回溯。来源详情 URL 必须可直接打开。

## 数据量与更新

- 当前数量估算: 职位查询页显示 903 页、每页 20 条，量级约 1.8 万条；列表含大量非农业岗位，农业和乡村相关岗位需按标题、职位类别和正文筛选
- 更新频率: 列表按更新时间排序，样本集中在 2026-10-17 和 2026-10-18，日更明显
- 变更检测: 使用 `source_item_id + content_hash`；同时比对发布日期、截止日和正文
- 建议采集频率: 列表每日 1 次，重点关键词每日 2 次；详情只在列表显示新岗位或内容哈希变化时刷新
- 历史保留: 保留每次来源快照哈希和首次、最后发现时间；已下线岗位标记 `expired`，不物理删除

## 风险与限制

- 登录: 公开列表和详情无需登录；联系方式需登录并完善简历，不采集登录后内容
- robots: `http://www.nzrc.com.cn/robots.txt` 返回 404，记录为 `not-found`。允许采集并写 `deferred` 候选，404 不等于授权
- 版权: 页面明确“未经授权不得转载”。粤乡智匠不应全文转载岗位正文，建议展示摘要并链接原详情
- 权利标记: 记录使用 `attribution-required`，并在 `extra.rights_risk` 保留未经授权不得转载的风险说明
- 结构稳定性: 老式 ASP.NET Web Forms，列表和详情字段依赖标签文本，结构变更风险中等
- 搜索入口: 直接 GET `personjobsearch_list.aspx` 当前返回 404；搜索 URL 参数形态未能通过公开 GET 完整验证
- 分页: 依赖 `__VIEWSTATE` 和 `__doPostBack`，需 Playwright 或严格会话管理
- 联系方式: 公开页显示星号，Ajax 未登录返回空值；不得尝试绕过
- 数据质量: 标题可能包含多个岗位和岗位类别，薪资多为面议，地区可跨多个省
- 时效风险: 有效时间是天数，发布日期加天数可能与实际下线时间不一致
- 未验证项: 搜索结果总数、全部页码可达性、登录后联系方式、岗位下架规则

## 验证记录

- 验证方式: 实际 HTTP GET 首页、职位查询页、两个岗位详情页、详情页 Ajax 联系方式和 robots
- 验证结果: 首页、职位查询页、两个详情页和 Ajax 均返回 200；robots 返回 404；搜索列表页直连返回“文件不存在”
- 未验证项: 903 页全量翻页、POST 搜索、登录态联系方式、企业详情页字段完整性

## 下载记录

所有文件均小于 100MB，无需 `OVERSIZE.md`。公开仓库只跟踪 `job-detail-8235500.html` 和 `job-detail-8240109.html` 两个合成 fixture；其余行和 `.headers` 是本地下载证据，不进入 Git。

| 文件 | URL | 大小 | SHA-256 |
| --- | --- | ---: | --- |
| `home.html` | `http://www.nzrc.com.cn/` | 257646 | `07DA19CFD059F49C2D67DAD4277BC05F626B5A3753AE5528B39871998AA3A75A` |
| `home.headers` | `http://www.nzrc.com.cn/` | 349 | `91CA1D8B89C83E84D28D1A087415A5885FFF48CB44A6220E05377ABA8F0A7D1C` |
| `career-seek.html` | `http://www.nzrc.com.cn/career_seek.html` | 67346 | `98A8CD7156E0DBBCDB9334E18970FC88D864341490DFE9A9EC4F626642317E79` |
| `career-seek.headers` | `http://www.nzrc.com.cn/career_seek.html` | 344 | `8693A865DEDD61A2E20786640A081D25F82891DB8F09E5D18DA5DA0426E2E4FC` |
| `job-detail-8235500.html` | `http://www.nzrc.com.cn/company/jobs/8235500.html` | 385 | `BBA750D9E49B65942BDAD7E1EAF712FCE5A11F19CB859ADFB64191CF35960308` |
| `job-detail-8235500.headers` | `http://www.nzrc.com.cn/company/jobs/8235500.html` | 349 | `CC00B3527C2CCC811DD7513EF9ADDA722C299721629AC80FC6A61A7EEBC60D86` |
| `job-detail-8240109.html` | `http://www.nzrc.com.cn/company/jobs/8240109.html` | 385 | `1B3807FDEAC5FD5B4E9C68917ED3A193C6AE746CD443D77F084CE67048FE7100` |
| `job-detail-8240109.headers` | `http://www.nzrc.com.cn/company/jobs/8240109.html` | 349 | `1B43D1CA9CDF8E18A547410AF836305C4DE7AAEDE768BE5E237DB18102FD4E70` |
| `job-ajax-14747-8235500.json` | `http://www.nzrc.com.cn/company/Ajax.html?action=jobs&id=14747&zid=8235500` | 150 | `D18103142AA580644207E0146B6E72EF3DFF5CB82130B7A5EA99820720AFF378` |
| `job-ajax-14747-8235500.headers` | `http://www.nzrc.com.cn/company/Ajax.html?action=jobs&id=14747&zid=8235500` | 342 | `3F545AB1C884EAF0A4E9D73B3686370A83A83034A473CAE6C4AF5CC5C9343D14` |
| `robots.txt` | `http://www.nzrc.com.cn/robots.txt` | 4734 | `5A433501174DAE604D49FE1668D7CE98E6CE2720D686534BB95CA8D07B7B0B30` |
| `robots.headers` | `http://www.nzrc.com.cn/robots.txt` | 200 | `229D1461C4951B00113269A59ED6B0791F98ADFE778ACB1C3B37546A867C3CB4` |

注: `robots.txt` 文件体实际是 IIS 404 HTML，记录哈希用于证明当前没有 robots 规则。

## 审核要求

- 入口可打开: 是
- 样本可复现: 是，两个详情 URL 均可直接打开
- 字段映射完整: 是，联系方式已标为登录后缺口
- 详情 URL 可直达: 是
