# CnOpenData 方言与非遗数据

共享契约: 见 `sources/CONTRACT.md`。通用字段、访问等级、状态和详情 URL 规则不在本文重复。

来源 ID: `cnopendata`

状态: `deferred`

验证时间: `2026-10-19 01:10 Asia/Shanghai`

权利状态: `unknown`

## 来源概况

- 名称: CnOpenData，中国开放数据平台
- 域名: `www.cnopendata.com`
- 主管机构: CnOpenData 运营方，页面未公开单一主管机构名称
- 内容域: 方言与非遗聚合数据，公开页面同时覆盖历史文化数据目录
- 优先级: P2
- 访问等级: `login-required`
- `license_or_usage`: 页面仅公开数据集说明、字段和购买方式，页脚显示 `© 2015-2026 CnOpenData. All rights reserved.`。未找到允许批量转载或再分发的公开授权文本。完整数据、API 和下载方案需要登录、购买或联系销售。
- `confidence`: 高，公开元数据由实际 HTTP 与浏览器渲染验证；低，实际数据行、授权范围和 API 调用方式未验证。

本来源状态为 `deferred`。用户当前未订阅文化数据集，公开 API 商店也没有方言或非遗产品，因此只保留公开元数据，不调用数据 API，也不写入业务库。订阅读取权和 API 返回结构确认后再评估接入。

## 入口

| 用途 | URL | 方法 | 说明 |
| --- | --- | --- | --- |
| 首页 | `https://www.cnopendata.com/` | GET | 平台入口 |
| 方言数据集页 | `https://www.cnopendata.com/data/m/culture/zgfyxx.html` | GET | 本次重点页面，标题为“中国各地区方言信息数据” |
| 非遗数据集页 | `https://www.cnopendata.com/data/m/culture/intangible-cultural-heritage.html` | GET | 标题为“中国非物质文化遗产数据”，公开 3 张表的字段结构 |
| 历史文化目录 | `https://www.cnopendata.com/data/m/culture/` | GET | 目录会重定向到该目录的首个数据页，不应把重定向页当作列表契约 |
| API 商店 | `https://www.cnopendata.com/api-store` | GET | 公开 29 个 API 产品条目、14 个分类键、5 个可见主题，公开价格状态均为 `contact` |
| 登录 | `https://sso.cnopendata.com/user/login` | GET | 申请试用、订阅、下载和 API 服务的登录入口 |
| 数据集 URL 模式 | `https://www.cnopendata.com/data/m/culture/{slug}.html` | GET | `slug` 为数据集键，如 `zgfyxx`、`intangible-cultural-heritage` |
| 行级详情页 | 不存在公开模式 | 无 | 公开页面只展示数据集和字段，不提供单条方言点或非遗记录详情页 |

## 请求与分页

- 请求方式: 数据集页为服务端渲染的 HTML，Next.js 同时下发可读的 RSC 数据脚本。普通用户阅读和验证可只请求公开 HTML。
- 查询参数: 数据集详情不需要查询参数。API 商店的主题筛选由页面内分类控制，本次未验证稳定的查询参数契约。
- 分页字段: 数据集页无分页。API 商店当前公开页面展示完整产品集合，未观察到可见分页控件。
- 每页数量: 不适用。
- 总数字段: API 商店页面公开显示 29 个产品条目。方言数据集公开显示 3 张表，非遗数据集公开显示 3 张表。实际行数未公开。
- 筛选字段: API 商店公开 29 个产品、14 个分类键和 5 个可见主题，包括沪深股票、港股、指数与板块、另类数据与文本语料等。未发现方言或非遗 API 产品。
- 禁止自动调用的路径: `robots.txt` 明确禁止 `/api/`、`/user-center`、`/search`、`/userAuth` 等路径。Playwright 加载公开数据页时观察到页面自身发起下载配置请求，未登录返回无权限。该内部请求只作为登录边界证据，不应被爬虫复现或当成采集接口。

## 字段定位

### JSON API

公开 API 商店只展示产品元数据，不含方言或非遗数据接口。代表产品字段如下：

| 来源字段 | 含义 | 样本 |
| --- | --- | --- |
| `categories[].key` | API 主题键 | `ashare-api` |
| `categories[].name` | API 主题名称 | `沪深股票` |
| `products[].slug` | API 产品稳定键 | `ashare-daily-indicator` |
| `products[].name` | API 产品名称 | `A股上市公司每日指数数据` |
| `products[].endpoint` | 调用地址 | `GET https://apiopendata.com/api/Ashare-daily-indicator` |
| `products[].pricing` | 价格状态 | `contact` |
| `products[].statusType` | 产品状态 | `active` |

数据集页内嵌 RSC 数据公开以下元数据：

| 来源字段 | 含义 | 方言数据样本 | 非遗数据样本 |
| --- | --- | --- | --- |
| `contentType` | 内容类型 | `series` | `series` |
| `key` | 数据集键 | `zgfyxx` | `intangible-cultural-heritage` |
| `title` | 数据集标题 | `中国各地区方言信息数据` | `中国非物质文化遗产数据` |
| `timeRange` | 时间范围 | `1986版与2012版` | 空 |
| `updateFrequency` | 更新频率 | `不定时更新` | `不定期更新` |
| `tables[].code` | 表稳定键 | `zgfyxx-t1` | `intangible-cultural-heritage-t1` |
| `tables[].name` | 表名称 | `各地区方言信息表-2012版` | `国家级非遗代表性项目名录` |
| `tables[].fields[].name` | 字段名 | `省份` | `项目序号` |
| `tables[].fields[].dataType` | 字段类型 | `string` | `number` |
| `tables[].fields[].sampleValue` | 公开样本值 | 空 | 空 |
| `tables[].hasSamples` | 是否标记有样本 | `true` | `true` |
| `dataScale` | 数据规模 | 空 | 空 |

`hasSamples=true` 没有转化为公开可读样本。实际页面在 3 张方言表和 3 张非遗表的样本区均显示“暂无样本数据”，因此不把该标志当作样本可用证据。

### HTML DOM

| 字段 | 选择器 | 说明 |
| --- | --- | --- |
| 数据集标题 | `h1` | 方言页唯一 `h1` 为“中国各地区方言信息数据” |
| 数据说明 | `h2` 之后正文区块 | 页面按“数据说明 / 字段展示 / 购买方式 / 下载数据”分段 |
| 字段表 | `table` | 方言页有 3 个字段表；每表列为 `# / 字段名称 / 数据类型 / 字段说明` |
| 样本状态 | 页面文本“样本数据预览 · SAMPLE”后的区块 | 本次 3 个方言表均为“暂无样本数据” |
| 登录后订阅按钮 | 文本“登录后订阅” | 渲染后出现，表示完整订阅受登录约束 |
| 申请试用 | 文本“申请数据试用” | 链接到 SSO 登录页并携带返回地址 |
| 下载边界 | 文本“登录后可查看当前数据的下载方案” | 未登录页面明确显示下载受登录约束 |

### 文件附件

公开页面没有可下载的样本文件。未登录状态下下载配置返回 `files: []`、`hasPermission: false`、`requiresLogin: true`。没有绕过登录或购买边界。

## 真实样本

说明: 本来源没有公开的行级样本。以下两条是公开可打开的数据集级样本，用于证明入口、字段结构和访问边界，不冒充方言点或非遗记录。

### 样本 1: 方言数据集

- 详情 URL: `https://www.cnopendata.com/data/m/culture/zgfyxx.html`
- 抓取时间: `2026-10-19 01:10 Asia/Shanghai`
- 关键字段: 标题“中国各地区方言信息数据”；时间范围“1986版与2012版”；更新频率“不定时更新”；3 张表；2012 版 9 字段，1986 版 8 字段，少数民族 1986 版 10 字段
- 公开字段: `省份`、`市级`、`区县`、`区县经度`、`区县纬度`、`乡镇街道`、`方言大类`、`分片区`、`分小片区`、`小片区细分一级`、`小片区细分二级`
- 目标映射: 有授权数据时，候选映射到 `std_dialect_points` 和粤乡智匠建议表 `dialects`，不映射到 `dialect_phrases`

### 样本 2: 非遗数据集

- 详情 URL: `https://www.cnopendata.com/data/m/culture/intangible-cultural-heritage.html`
- 抓取时间: `2026-10-19 01:10 Asia/Shanghai`
- 关键字段: 标题“中国非物质文化遗产数据”；更新频率“不定期更新”；公开 3 张表
- 公开表: 国家级非遗代表性项目名录、国家级非遗代表性项目代表性传承人、联合国教科文组织非遗名录
- 项目名录字段: `序号`、`项目序号`、`编号`、`名称`、`类别`、`公布时间`、`类型`、`申报地区或单位`、`保护单位`、`链接`、`正文内容`
- 传承人字段: `序号`、`姓名`、`性别`、`民族`、`类别`、`项目编号`、`项目名称`、`申报地区或单位`、`正文内容`
- 教科文名录字段: `序号`、`项目名称`、`列入年份`、`类型`、`申报方式`、`申报国家`、`正文内容`
- 目标映射: 仅作为候选字段参考；获得授权前不映射到 `std_ich_projects`，也不写入粤乡智匠 `crafts`

## 字段映射

### crawler 层

| 来源字段 | crawler 表.字段 | 粤乡智匠建议表.字段 | 转换说明 |
| --- | --- | --- | --- |
| 数据集 `key=zgfyxx` | `raw.source_page.source_id` | 不适用 | 只保存公开说明页的响应和哈希，来源 ID 固定为 `cnopendata` |
| `title` | `stage_cnopendata_dataset.title` | 不适用 | 数据集级标题 |
| `tables[].fields[].name` | `stage_cnopendata_field.field_name` | 不适用 | 保留原始字段名和顺序 |
| `省份` | `std_dialect_points.province` | `dialects.region` 或建议新增 `province` | 候选映射，授权后才能形成 `std` 记录 |
| `市级` | `std_dialect_points.city` | 建议新增 `dialects.city` | 候选映射 |
| `区县` | `std_dialect_points.county` | `dialects.areas` 的地区部分 | 候选映射 |
| `区县经度` | `std_dialect_points.extra.longitude` | 建议新增 `dialects.longitude` | 保留数值类型 |
| `区县纬度` | `std_dialect_points.extra.latitude` | 建议新增 `dialects.latitude` | 保留数值类型 |
| `乡镇街道` | `std_dialect_points.extra.township` | 建议新增 `dialects.township` | 2012 版存在，其他表可为空 |
| `方言大类` | `std_dialect_points.extra.dialect_group` | `dialects.name` 的候选依据 | 不能替代粤乡智匠人工确认的方言名称 |
| `分片区` | `std_dialect_points.extra.subgroup` | `dialects.features` 或建议新增 `subgroup` | 保持来源原文 |
| `分小片区` | `std_dialect_points.extra.sub_subgroup` | `dialects.features` 或建议新增 `sub_subgroup` | 保持来源原文 |
| 非遗 `编号` | `std_ich_projects.ich_code` | 建议新增 `crafts.ich_code` | 候选映射 |
| 非遗 `名称` | `std_ich_projects.name` | `crafts.name` | 仅授权且人工复核后使用 |
| 非遗 `类别` | `std_ich_projects.category` | 建议新增 `crafts.ich_category` | 十大门类原文 |
| 非遗 `申报地区或单位` | `std_ich_projects.declaration_region` | `crafts.origin` 的候选依据 | 地区与单位可能混写，需拆分或保留原文 |
| 非遗 `保护单位` | `std_ich_projects.protection_unit` | 建议新增 `crafts.protection_unit` | 保留原文 |
| 非遗 `链接` | `std_ich_projects.source_url` | 建议新增 `crafts.source_url` | 发布前验证链接可直达 |
| 非遗 `正文内容` | `std_ich_projects.description_text` | `crafts.history` 的候选来源 | 完整正文只在授权范围内保存，不直接公开转载 |

### 粤乡智匠表

- `dialects`: 可承接方言地区名称和概述。现有表没有经纬度、乡镇街道、分片区等列，若采用该来源，应先在目标库变更设计中补列，不能把结构塞进 `extra` 后当作稳定字段。
- `dialect_phrases`: 该来源公开字段没有词形、普通话释义或拼音，不能映射到短语表。
- `crafts`: 可承接经过审核的项目名称、来源地区、级别和历史概述。补充来源不能覆盖官方项目事实。
- `craft_steps`、`craft_videos`、采购指南表: 该来源没有公开教学步骤、视频或采购信息，不映射。

## 数据量与更新

- 当前数量估算: 方言数据集 3 张表，非遗数据集 3 张表；公开页面没有行数或数据规模。API 商店公开 29 个产品，其中未发现方言或非遗 API。
- 更新频率: 方言数据页面写“不定时更新”，非遗数据页面写“不定期更新”。
- 变更检测: 比较数据页 `h1`、`summary`、`timeRange`、`updateFrequency`、字段名称与顺序、`dataScale` 和样本状态；同时比较规范化公开页面的 SHA-256。不要把禁止的 `/api/` 路径纳入自动巡检。
- 建议采集频率: 每月检查一次公开元数据即可。实际数据不自动采集，只有获得书面授权并完成合同或授权记录后才人工导入。
- 历史数据保留: 公开元数据可按月保存内容哈希和字段快照。付费数据在授权范围内保留，不与公开元数据混存。

## 风险与限制

- 登录: 数据下载、试用、订阅和 API 服务均受登录或购买限制。页面未登录时明确显示 `requiresLogin: true`。
- robots: 允许普通页面，禁止 `/api/`、`/user-center`、`/search`、`/userAuth`、`/users/`、`/verify`、`/myip`、`/iframeHTML`。
- 版权: 页脚为保留所有权利，未看到公开再分发许可。即使购买，也应核对合同是否允许写入平台、缓存、派生和公开展示。
- 结构稳定性: 页面为 Next.js 应用，公开 HTML 可读，但字段和产品列表可能随前端发布变化。RSC 脚本结构不是稳定公共 API。
- 缺失字段: 无行级详情 URL、无公开样本、无行数、无许可证全文、无授权范围、无 API 文档和调用配额。
- 数据适用性: 方言数据是地区分类与经纬度，不是词条、发音或例句。非遗数据是聚合整理，不能替代 `ihchina.cn` 官方名录。
- 商业边界: 不应绕过付费墙、登录、验证码或用户中心限制，不应根据销售联系人占位符反推联系方式。

## 验证记录

- 验证方式: Python `requests` 实际请求公开 HTML，使用 BeautifulSoup 解析 DOM 和字段表；Playwright Chromium 无头浏览器渲染方言数据集页，确认“登录后订阅”和下载登录提示；另行请求公开 `robots.txt`、API 商店和公开数据集页。
- 验证结果: 方言数据集页 HTTP 200，标题正确，3 个字段表均为“暂无样本数据”；非遗数据集页 HTTP 200，公开 3 张表和字段结构；API 商店 HTTP 200，公开 29 个产品和 13 个分类，价格均为 `contact`；下载配置公开返回未登录、无文件。
- 内容指纹: 方言页 `330172` 字节，SHA-256 `3e94de23952119b74dcef8351ae70948718355bb9ef10579be786fedbd3214a9`；非遗页 `326184` 字节，SHA-256 `cce83eb63cdb263d2a5bdf65c7cda1fdb9e297ef39a7129786d92ebc1f0f1e61`；API 商店 `228847` 字节，SHA-256 `b25f02c430375dd9344410e966bf1885ee9512083d46de6bb44edec7e417605e`。哈希只用于本次公开页面复核，不表示页面永久不变。
- 未验证项: 登录后可见文件清单、价格、授权合同、行级数据、字段空值率、实际记录数、API 配额、API 返回结构、付费数据是否允许二次发布。
- 下载: 无。没有保存登录后才能获取的数据，也没有把公开页面伪装成样本文件下载。

## 审核要求

- 入口可打开: 是
- 样本可复现: 数据集级样本可复现；行级样本不可得
- 字段映射完整: 公开字段已映射；授权后的类型、空值和自然键仍需复核
- 详情 URL 可直达: 数据集级 URL 可直达；无行级详情 URL
- 合规结论: 状态 `deferred`，只允许公开元数据人工研究；未订阅文化数据集前不调用数据 API，不自动采集完整数据。


