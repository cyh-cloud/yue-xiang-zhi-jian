# 5A 农业人才网

共享契约: 见 `sources/CONTRACT.md`。通用字段、访问等级、状态和详情 URL 规则不在本文重复。

来源 ID: `5ajob`

状态: `approved-with-gaps`

验证时间: `2026-10-19 01:08 Asia/Shanghai`

## 来源概况

- 名称: 5A 农业人才网
- 域名: `www.5ajob.com`
- 主管机构: 未见公开的主办单位页，站点页脚仅写“5A 农业人才网 版权所有”
- 内容域: 农业与乡村相关招聘岗位
- 优先级: P1
- 访问等级: `public`
- 权利状态: `prohibited`
- `license_or_usage`: 页面明确声明“未经5ajob.com许可，不得转载本站之所有农业人才求职招聘信息及作品”。只保存必要字段、短摘要和可回链的详情 URL，不进入业务发布
- `confidence`: `medium`（列表、详情、分页、字段已实测；发布时间未提供，部分详情有效期依赖页面脚本）

## 入口

| 用途 | URL | 方法 | 说明 |
| --- | --- | --- | --- |
| 首页 | `http://www.5ajob.com/` | GET | 农业招聘入口，返回 200 |
| 列表页 | `http://www.5ajob.com/job/` | GET | 20 条/页，首个有效页 |
| 关键词列表 | `http://www.5ajob.com/job/index.asp?JobName=%C5%A9%D2%B5` | GET | `JobName=农业` 的 GBK 编码查询，返回 200 |
| 行业/地区列表 | `http://www.5ajob.com/nongzuowu/job.html`、`http://www.5ajob.com/aguangdong/job.html` | GET | 行业、地区均提供路径式列表，适合避开查询串限制 |
| 详情页模式 | `http://www.5ajob.com/c-d-{company_hash}-h/{job_id}.html` | GET | 详情页 canonical，样本 1 |
| 详情页模式 2 | `http://www.5ajob.com/companyinfo/detail/{company_hash}/htmljob/{job_id}.html` | GET | 详情页 canonical，样本 2 |
| 移动详情 | `http://m.5ajob.com/companyinfo/jobdetail.asp?JobID={job_id}` | GET | 页面 meta 声明的移动版；未作为主采集入口 |

## 请求与分页

- 请求方式: HTML `GET`，响应编码为 `gb2312` / `gb18030`，需按字节解码后解析
- 查询参数: 搜索表单 `form[name="formzjob"]` 使用 `GET index.asp`，字段为 `JobEduLevel`、`JobMajor`、`JobWorkAge`、`JobSalary`、`JobMode`、`JobLanguage`、`JobSex`、`Company`、`JobIndustry`、`JobProv`、`JobCity`、`JobType`、`JobName`
- 分页字段: 路径 `index-p{N}.html`；关键词结果为 `index-j{GBK关键词}-p{N}.html`，例如 `index-j%C5%A9%D2%B5-p2.html`
- 每页数量: 20 条（`tr[id^="compareColor"]` 和 `tr.jobdesc` 各 20）
- 总数字段: 未发现可用总数；尾页链接指向 `/job/index-p250.html`
- 筛选字段: 行业、省份、城市、职位类别、学历、专业、工作经验、薪资、工作方式、外语、性别、公司、关键词
- 翻页边界: `p250` 是尾页；`p251` 仍返回 200 且内容回绕到较早岗位，不能把页码递增当作完整或有序保证。以尾页、详情 ID 集合和最后页 20 条去重终止

## 字段定位

### JSON API

未发现列表或详情 JSON API。详情页的“该公司其它职位”等是 HTML 脚本片段，不作为主数据源。

### HTML DOM

| 字段 | 选择器 | 说明 |
| --- | --- | --- |
| 列表行 | `tr[id^="compareColor"]` | 每页 20 行 |
| 岗位名称 | `tr[id^="compareColor"] td.joblink a` | 文本为岗位名，`href` 为详情 URL |
| 公司名称 | `tr[id^="compareColor"] td:nth-child(3)` | 同时可读 `td:nth-child(3) a` |
| 工作地点 | `tr[id^="compareColor"] td:nth-child(4)` | 如 `安徽`、`广东.广州`、`全国各地` |
| 薪资 | `tr[id^="compareColor"] td:nth-child(5)` | 区间或“面议” |
| 状态 | `tr[id^="compareColor"] td:nth-child(6)` | 观测到“热聘中”“停招” |
| 列表摘要 | `tr.jobdesc[id^="jobdesc"] td` | 含专业、学历、招聘人数、经验、岗位描述 |
| 详情公司 | `#zhtitle` | 公司名称 |
| 详情岗位 | `#jobdetail h1` | 岗位名，通常带“招聘”后缀 |
| 详情字段表 | `#jobdetail tr` | 左侧标签、右侧值 |
| 工作地点 | `#jobdetail tr:has(td:first-child:text-is("工作地点")) td:nth-child(2)` | 建议按标签取值，避免列位置变化 |
| 月薪 | 标签归一为“月薪”的行 | 原始标签可能含全角空格“月　　薪” |
| 岗位描述 | 标签“岗位描述”的右侧单元格 | 保留换行，清理站内链接文本 |
| 应聘要求 | 标签“应聘要求”的右侧单元格 | 与岗位描述分开保存 |
| 职位有效期 | `#jobexpire` | 普通 HTTP 为空，浏览器执行页面脚本后出现日期 |
| 职位 ID | `#rjobid` 的 `value` | 样本 1 为 `50506` |

详情标签行在 HTTP 解析时应把全角空格归一化，例如“月　　薪”映射为“月薪”、“工作地点”去除空白后再匹配。不要把 `#zhtitle`、公司展台页或 `/company/` 路径当作采集入口。

## 真实样本

### 样本 1

- 详情 URL: `http://www.5ajob.com/c-d-9975f684d6022631-h/50506.html`
- 抓取时间: `2026-10-19 01:08 Asia/Shanghai`
- 抓取方式: HTTP 200；Playwright 实际打开确认
- 关键字段: 岗位 `肥料区域经理-安徽`；公司 `时科生物科技（上海）有限公司`；工作地点 `安徽(华东地区)`；行业 `肥料`；招聘人数 `2人`；招聘方式 `全职`；月薪 `5001-10000元`；专业 `农学、植物保护、土壤学、市场营销`；经验 `5年以上`；学历 `中专`；有效期 `2026年05月25日至2026年11月21日`（Playwright 读取 `#jobexpire`）
- 目标映射: `std_jobs` + `std_job_sources`；业务建议 `recruitment_postings` + `recruitment_posting_sources`

### 样本 2

- 详情 URL: `http://www.5ajob.com/companyinfo/detail/2d90e70b22e22eee/htmljob/50688.html`
- 抓取时间: `2026-10-19 01:08 Asia/Shanghai`
- 抓取方式: HTTP 200 与 Playwright 均已打开
- 关键字段: 岗位 `农作物种植技术员`；公司 `山东省祥盛种业科技有限责任公司`；工作地点 `山东.聊城(华东地区)`；行业 `农作物`；招聘人数 `2人`；招聘方式 `全职`；月薪 `5001-10000元`；专业 `农学、作物生产技术、作物栽培与耕作、植物科学与技术、植物保护、农业昆虫与害虫防治、农药学、植物病理学`；经验 `不限`；学历 `本科`；岗位描述为田间植保巡查、方案制定、技术指导与台账管理
- 目标映射: 同上；该样本属于种植/植保，优先进入农业主题

### 样本 3

- 详情 URL: `http://www.5ajob.com/companyinfo/detail/7411bc9cc6dadd45/htmljob/50687.html`
- 抓取时间: `2026-10-19 01:08 Asia/Shanghai`
- 关键字段: 列表中出现岗位 `前台接待`，公司 `金华市喆农商贸有限公司`，地点 `全国各地`，薪资 `5001-10000元`，状态 `热聘中`
- 用途: 反例样本。站内公司属于农业相关企业也不等于岗位属于农业与乡村相关；`前台接待` 应被主题过滤排除

## 字段映射

| 来源字段 | crawler 表.字段 | 粤乡智匠表.字段 | 转换说明 |
| --- | --- | --- | --- |
| canonical 详情 URL | `std_jobs.source_url` | `recruitment_posting_sources.source_url` | 自然键的一部分；保留原始 URL，不把公司展台页当详情 |
| `#rjobid` | `std_jobs.source_item_id` | `recruitment_postings.source_item_id` | 站点职位 ID；与来源 ID 组成自然键 |
| `#jobdetail h1` | `std_jobs.title` | `recruitment_postings.title` | 去除末尾“招聘”后缀时保留原值到 `std_jobs.title_raw` |
| `#zhtitle` | `std_jobs.company_name` | `recruitment_postings.company_name` | 只取公开公司名，不采集企业联系人 |
| “工作地点”行 | `std_jobs.location_raw` | `recruitment_postings.region_raw` | 保留原文，再拆分省/市 |
| “所在行业”行 | `std_jobs.company_industry` | `recruitment_postings.industry` | 用于农业主题过滤 |
| “月薪”行 | `std_jobs.salary_raw` | `recruitment_postings.salary_text` | 保留区间或“面议”；不推断具体数值 |
| “招聘人数”行 | `std_jobs.headcount` | `recruitment_postings.headcount_text` | 仅在可靠解析时填整数，原文进 `extra` |
| “招聘方式”行 | `std_jobs.employment_type` | `recruitment_postings.employment_type` | 如全职、兼职 |
| “专业要求”行 | `std_jobs.major_requirement` | `recruitment_postings.major_requirement` | 原文保留 |
| “工作经验”“学历要求”行 | `std_jobs.experience_raw`、`std_jobs.education_raw` | `recruitment_postings.experience_requirement`、`education_requirement` | 原文保留 |
| “岗位描述”“应聘要求”行 | `std_jobs.description`、`std_jobs.requirements` | `recruitment_postings.description`、`requirements` | 采集库保存全文，业务库按发布策略展示 |
| `#jobexpire` | `std_jobs.deadline_at` | `recruitment_postings.expires_at_text` | 浏览器读取；解析失败原文进 `extra` |
| 列表状态 | `std_jobs.status_text` | `recruitment_postings.status_text` | 来源状态，不推断是否仍可投递 |
| 抓取时间 | `std_jobs.retrieved_at` | `recruitment_postings.fetched_at` | 所有时效字段必须带取得时间 |

建议的业务库表名是新增的 `recruitment_postings` 与 `recruitment_posting_sources`，不写入现有 `job_listings`（该表是站内岗位/策展数据）。自然键使用 `(source_id, source_item_id)`，缺失时退回 canonical URL。

## 数据量与更新

- 当前数量估算: 列表尾页为 250，每页 20 条，量级约 5,000 条，包含大量“停招”历史记录；农业主题过滤后数量显著更少
- 更新频率: 新岗位按日新增，旧岗位状态会变成“停招”；详情有效期跨数月
- 变更检测: 列表页岗位 ID 集合、详情页字段文本哈希、`#jobexpire`、列表状态
- 建议采集频率: 列表每日 1 次；农业主题详情每周 1 次；有效期临近的岗位每日复核
- 历史数据保留: 采集库保留首次/最近取得时间和正文快照；业务库按审核结果发布

## 风险与限制

- 登录: 浏览岗位详情不需要登录；投递、收藏、联系企业等操作需要登录，均不在采集范围
- robots: `robots.txt` 禁止 `/company/`、`/personal/`、`/about/`、`/*zpt.html`、`/*product.html`、`/*contact.html`、`/*news.html`、`/chart/gern.asp`；`/job/` 未禁。对 Baidu、Google 等 UA 还禁止 `?*` 和部分 `job-s*`、`index-*` 路径。后续采集器应先检查实际 UA 的 robots 规则，并只请求未禁的列表和详情
- 版权: 页面明确保留转载权。保存原始响应仅用于内部回溯，`rights_status=prohibited`，不复制简历、联系方式或受限公司页，不进入业务发布
- 结构稳定性: 页面是 IIS/ASP 老站，GBK 编码、两套详情 URL 并存；详情有效期由脚本注入，纯 HTTP 与浏览器结果不同
- 缺失字段: 没有稳定发布时间；没有公开总数字段；部分列表链接公司 hash 为空（如 `companyinfo/detail//htmljob/...`）；部分岗位标题、职位 ID 需要从详情补全
- 主题风险: 全站虽为农业人才网，仍出现“前台接待”“行政经理”“销售”等非农业岗位。必须按岗位名称、行业、专业、描述和公司业务做二次过滤，不能只靠站点域名
- 个人数据: 禁止采集 `/resume/`、`/personal/`、简历详情、联系电话、联系人和任何登录后内容

## 验证记录

- 验证方式: `requests` 实际 HTTP + Playwright Chromium
- 验证结果: 首页、`/job/`、`index-p2.html`、`index-p250.html`、关键词列表、样本详情均返回 200；列表 20 条/页；样本 1 的 `#jobexpire` 在浏览器中为 `2026年05月25日至2026年11月21日`；样本 2 的 `#jobdetail` 字段表可读
- 未验证项: 不同 UA 下 robots 的精确匹配、全部 250 页的历史完整性、每个行业/地区路径的 robots 允许性、是否存在未公开 API

## 审核要求

- 入口可打开: 是
- 样本可复现: 是（2 条正面样本 + 1 条反例样本）
- 字段映射完整: 主要岗位字段已覆盖；发布时间缺失已注明
- 详情 URL 可直达: 是

## 实现验证

- 2026-10-20 已实现列表 fixture 纵向切片。该来源保持 `prohibited` 且没有 Scrapy 项目，只允许通过 `python -m unittest crawler.tests.test_5ajob -v` 验证离线解析器。
- canonical 岗位 URL 同时写入 `source_url`、`long_term_url` 和 `detail_url`；`source_item_id` 使用职位 ID。
- 全局按职位 ID 和 canonical URL 去重。某页没有新增职位 ID 时停止，因此后续回绕页不会被继续处理。
- 农业相关性仅使用标题、行业和描述证据，保留命中字段、命中文案、排除记录和处理页数；公司名不参与判定。
- 权利状态使用 `prohibited`，并在 `extra.risk_acceptance` 保留“转载需 5ajob.com 许可”的来源声明。
- 来源注册表判定为 `prohibited`，调度器和 Scrapy 项目均不得启动该来源；离线解析器测试不创建 raw/stage/std 记录。
- 离线 fixture 可携带 `detail_html`，解析公司、地点、薪资、学历、描述、要求和有效期；该能力只用于解析器测试。
- 测试使用本地 fixture，不访问网络。真实 250 页全量列表、脚本注入有效期和许可恢复仍为 `deferred`。
