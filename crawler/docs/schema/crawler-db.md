# 采集库 Schema 设计

状态：设计冻结

日期：2026-10-19

适用数据库：`crawler.db`（独立 SQLite）

本次只定义文档，不创建表、不写 SQL、不迁移数据。字段类型使用 SQLite 亲和类型，时间统一写 ISO 8601 带时区字符串，布尔值使用 `INTEGER` 的 `0/1`，金额和比例不在此层做业务换算。

## 设计原则

1. `raw` 只追加，不修改已保存响应；同一 URL 的多次访问是不同记录。
2. `stage` 按来源原始形状保存，允许多个来源各自命名，不强行统一字段。
3. `std` 是转换器唯一输入，保存跨来源标准实体和来源引用。
4. 所有从网络取得的记录都必须带 `source_id`、`retrieved_at`、`source_url` 和响应或内容哈希。
5. 任何可发布实体都必须能回溯到 `std_sources`、具体来源记录和 `raw_fetches`。
6. JSON 字段只用于结构不稳定或附带信息，稳定、可筛选的字段使用独立列。
7. 缺失值写 `NULL` 或明确的 `unknown`，不编造标准号、文号、日期、授权和行政区划。
8. 主键统一使用 `INTEGER PRIMARY KEY`（SQLite rowid 别名）；自然键用 `UNIQUE` 约束表达，不把自然键拼成主键。

## 公共列约定

| 列 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 代理主键 |
| `source_id` | TEXT | NOT NULL | 来源 ID，取值见 `sources.json` |
| `source_item_id` | TEXT | 可空 | 来源内记录 ID，保留字符串 |
| `source_url` | TEXT | 可空 | 可直接打开的单条详情 URL |
| `content_hash` | TEXT | 可空 | 规范化内容 SHA-256，十六进制小写 |
| `retrieved_at` | TEXT | 可空 | 该版本内容实际取得时间 |
| `first_seen_at` | TEXT | 可空 | 首次进入该层的时间 |
| `last_seen_at` | TEXT | 可空 | 最近一次仍在来源中出现的时间 |
| `is_active` | INTEGER | 默认 1 | 是否仍在来源中出现 |
| `extra` | TEXT | 默认 `'{}'` | JSON 对象，保存未建模的附带字段 |

`retrieved_at` 与 `last_seen_at` 不同：前者是内容版本时间，后者是发现状态时间。转换器不得用采集时间替代来源发布时间。

## JSON 字段语义

| 字段 | 形状 | 语义 |
| --- | --- | --- |
| `request_headers` | object | 实际请求头，敏感值已脱敏 |
| `response_headers` | object | 响应头，小写键名 |
| `metadata_json` | object | 来源响应中的顶层辅助字段 |
| `field_provenance` | object | `{字段: {raw_fetch_id, source_path, retrieved_at}}`，记录字段级来源 |
| `extra` | object | 未建模字段，禁止放账号、Cookie、令牌或个人简历 |
| `media_metadata` | object | 宽高、时长、MIME、字节数等，未验证写 `null` |
| `constraints_json` | object | 地区、类别、认证类型等过滤条件 |
| `normalization_json` | object | 名称归一、行政区划推导和置信度说明 |

JSON 必须能被标准 JSON 解析器读取；空值用 `{}` 或 `[]`，不用空字符串冒充结构。任何会影响自然键或发布的字段都应提升为独立列，不能只放在 JSON 中。

## raw 层

`raw` 保存请求、响应、文件元数据和短期响应快照。响应正文可以存放在文件系统中，由 `raw_files` 记录路径和哈希；小响应可以直接存 `body_text`，但必须设置大小上限。

### raw_fetches

一次 HTTP 或浏览器请求对应一行。重试、跳转后的最终请求和同一 URL 的再次采集各自成行。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 请求记录主键 |
| `source_id` | TEXT | NOT NULL | 来源 ID |
| `job_key` | TEXT | 可空 | 调度任务标识 |
| `request_url` | TEXT | NOT NULL | 实际请求 URL，不含账号密码 |
| `final_url` | TEXT | 可空 | 跟随跳转后的 URL |
| `request_method` | TEXT | NOT NULL 默认 GET | HTTP 方法 |
| `request_headers` | TEXT | 默认 `'{}'` | 脱敏后的请求头 JSON |
| `status_code` | INTEGER | 可空 | HTTP 状态码，浏览器失败可空 |
| `content_type` | TEXT | 可空 | 响应 MIME |
| `response_headers` | TEXT | 默认 `'{}'` | 响应头 JSON |
| `body_bytes` | INTEGER | 可空 | 响应体字节数 |
| `body_sha256` | TEXT | 可空 | 响应体 SHA-256 |
| `body_path` | TEXT | 可空 | 快照相对路径 |
| `body_text` | TEXT | 可空 | 小型文本响应的内联副本 |
| `body_saved` | INTEGER | 默认 1 | 是否保存了响应体 |
| `access_level` | TEXT | NOT NULL | `public`、`login-required`、`robots-restricted`、`manual-only` |
| `robots_decision` | TEXT | 可空 | `allowed`、`disallowed`、`unknown` |
| `fetch_status` | TEXT | NOT NULL | `ok`、`http_error`、`blocked`、`timeout`、`parse_error` |
| `error_message` | TEXT | 可空 | 脱敏错误摘要 |
| `started_at` | TEXT | NOT NULL | 请求开始时间 |
| `retrieved_at` | TEXT | 可空 | 响应取得时间 |
| `duration_ms` | INTEGER | 可空 | 请求耗时 |
| `metadata_json` | TEXT | 默认 `'{}'` | 分页、跳转、内容长度等辅助信息 |
| `created_at` | TEXT | NOT NULL | 入库时间 |

主键：`id`。

自然键：不设业务唯一键。请求 ID 是审计键，允许同 URL 多行。

索引：

- `(source_id, retrieved_at)`
- `(request_url, retrieved_at)`
- `(fetch_status, started_at)`
- `(body_sha256)`

外键：

- `raw_fetches.id` 被 `raw_files.raw_fetch_id` 引用。
- 不向业务库建外键。

保留策略：

- 采集库永久保留请求元数据。
- `body_text` 建议仅用于小于 1MB 的文本，正文快照优先落在 `raw_files` 或响应文件目录。
- 失败请求保留 180 天；成功请求的响应体按来源文档保留，至少保留最近一次和最近一次内容变更版本。

### raw_files

保存单个响应、附件、图片、PDF、XLSX 或媒体文件的文件级元数据。一个响应可以拆出多个文件，一个文件也可以来自一次抓取。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 文件记录主键 |
| `raw_fetch_id` | INTEGER | 可空 | 来源请求 |
| `source_id` | TEXT | NOT NULL | 来源 ID |
| `source_url` | TEXT | 可空 | 文件原始 URL |
| `detail_url` | TEXT | 可空 | 承载文件的可打开页面 |
| `file_path` | TEXT | 可空 | 相对采集库的下载路径 |
| `file_name` | TEXT | 可空 | 原始文件名 |
| `mime_type` | TEXT | 可空 | MIME |
| `file_ext` | TEXT | 可空 | 小写扩展名 |
| `byte_size` | INTEGER | 可空 | 字节数 |
| `sha256` | TEXT | NOT NULL | 文件哈希 |
| `width` | INTEGER | 可空 | 图片或视频宽度 |
| `height` | INTEGER | 可空 | 图片或视频高度 |
| `duration_ms` | INTEGER | 可空 | 音视频时长 |
| `access_level` | TEXT | NOT NULL | 文件访问等级 |
| `download_status` | TEXT | NOT NULL | `saved`、`oversize`、`blocked`、`missing`、`error` |
| `oversize_note` | TEXT | 可空 | 超限说明路径或原因 |
| `media_metadata` | TEXT | 默认 `'{}'` | 媒体附加信息 |
| `retrieved_at` | TEXT | 可空 | 文件取得时间 |
| `created_at` | TEXT | NOT NULL | 入库时间 |

主键：`id`。

自然键：`(source_id, source_url, sha256)` 唯一；同一 URL 内容变化会产生新哈希和新记录。

索引：

- `(raw_fetch_id)`
- `(source_id, file_ext)`
- `(sha256)`
- `(download_status)`

外键：

- `raw_fetch_id` 引用 `raw_fetches.id`，删除请求记录时置空或保留文件记录。

保留策略：

- 文件原件按大小和来源文档保留，单文件不得超过 100MB。
- 超限文件只保存 `OVERSIZE.md` 说明，不保存文件体。
- 业务库只引用 `std_sources` 和 URL，不直接引用文件路径。

## stage 层

`stage` 按来源形状组织。每个来源可以有独立的 `stage_<source>_*` 表，表内字段名尽量贴近来源字段，便于对照页面和接口。stage 可以保留 HTML 片段、原始文本和本次解析产物，但不替代 raw 快照。

所有 stage 表共享以下审计列：

| 列 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 代理主键 |
| `raw_fetch_id` | INTEGER | 可回溯到 raw 请求 |
| `source_id` | TEXT | 来源 ID |
| `source_item_id` | TEXT | 来源内 ID |
| `source_url` | TEXT | 详情 URL |
| `retrieved_at` | TEXT | 内容取得时间 |
| `content_hash` | TEXT | 规范化解析结果哈希 |
| `parser_version` | TEXT | 解析器版本 |
| `extra` | TEXT | 未建模字段 JSON |

### stage_ich_*

来源于 `ihchina` 的项目、传承人、关联项、媒体和文章。

#### stage_ich_projects

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键 |
| `raw_fetch_id` | INTEGER | 列表或详情请求 |
| `source_id` | TEXT | 固定 `ihchina` |
| `source_item_id` | TEXT | 详情页数字 ID |
| `source_url` | TEXT | `project_details/{id}.html` |
| `title` | TEXT | 项目名称 |
| `title2` | TEXT | 副标题或别名 |
| `auto_id` | TEXT | 页面项目序号 |
| `num` | TEXT | 项目编号，如 `Ⅰ-1` |
| `project_num` | TEXT | 含批次和地区的内部编号 |
| `type` | TEXT | 类别名称 |
| `cate` | TEXT | 新增项目或扩展项目 |
| `rx_time` | TEXT | 原始公布时间文本，可含 `<br>` |
| `province_raw` | TEXT | 申报地区或单位展示名 |
| `address_code` | TEXT | 省级行政区划代码 |
| `city_code` | TEXT | 地级行政区划代码 |
| `area_code` | TEXT | 县级行政区划代码 |
| `unit_raw` | TEXT | 申报地区或单位原文 |
| `protect_unit` | TEXT | 保护单位 |
| `content_html` | TEXT | 正文 HTML |
| `content_text` | TEXT | 去标签正文 |
| `source_modified_at` | TEXT | 来源修改时间，ISO 8601 |
| `detail_fields_json` | TEXT | 详情页键值对 JSON |
| `retrieved_at` | TEXT | 取得时间 |
| `content_hash` | TEXT | 解析结果哈希 |
| `parser_version` | TEXT | 解析器版本 |
| `extra` | TEXT | 其他来源字段 JSON |

自然键：`(source_id, source_item_id)`。

索引：`(source_id, num)`、`(source_id, rx_time)`、`(source_id, type)`、`(source_id, content_hash)`。

外键：`raw_fetch_id` 引用 `raw_fetches.id`。

保留策略：保留最近一次解析结果和每次内容哈希变化版本。

#### stage_ich_inheritors

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键 |
| `raw_fetch_id` | INTEGER | 来源请求 |
| `source_id` | TEXT | `ihchina` |
| `source_item_id` | TEXT | 传承人详情 ID |
| `source_url` | TEXT | 传承人详情 URL |
| `project_source_item_id` | TEXT | 关联项目 ID |
| `name` | TEXT | 姓名 |
| `gender` | TEXT | 性别 |
| `birth_date_raw` | TEXT | 出生日期原文 |
| `ethnicity` | TEXT | 民族 |
| `category` | TEXT | 类别 |
| `ich_code` | TEXT | 项目编号 |
| `project_name` | TEXT | 项目名称 |
| `declaration_region` | TEXT | 申报地区或单位 |
| `biography_html` | TEXT | 小传 HTML |
| `biography_text` | TEXT | 小传纯文本 |
| `retrieved_at` | TEXT | 取得时间 |
| `content_hash` | TEXT | 内容哈希 |
| `parser_version` | TEXT | 解析器版本 |
| `extra` | TEXT | 其他字段 JSON |

自然键：`(source_id, source_item_id, project_source_item_id)`。

索引：`(source_id, source_item_id)`、`(source_id, project_source_item_id)`、`(source_id, name)`。

#### stage_ich_related_items

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键 |
| `raw_fetch_id` | INTEGER | 来源请求 |
| `source_id` | TEXT | `ihchina` |
| `subject_source_item_id` | TEXT | 当前项目 ID |
| `related_source_item_id` | TEXT | 相关项目 ID |
| `related_url` | TEXT | 相关项目 URL |
| `ich_code` | TEXT | 相关项目编号 |
| `related_name` | TEXT | 相关项目名称 |
| `relation_type` | TEXT | 页面区块或关系类型 |
| `declaration_region` | TEXT | 申报地区或单位 |
| `retrieved_at` | TEXT | 取得时间 |
| `content_hash` | TEXT | 内容哈希 |
| `extra` | TEXT | 其他字段 JSON |

自然键：`(source_id, subject_source_item_id, related_source_item_id, relation_type)`。

索引：`(source_id, subject_source_item_id)`、`(source_id, related_source_item_id)`。

#### stage_ich_media_links

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键 |
| `raw_fetch_id` | INTEGER | 来源请求 |
| `source_id` | TEXT | `ihchina` |
| `subject_source_item_id` | TEXT | 项目 ID |
| `source_page_url` | TEXT | 承载媒体的详情页 |
| `media_url` | TEXT | 媒体绝对 URL |
| `media_type` | TEXT | image、video、audio、iframe |
| `media_role` | TEXT | header、body、attachment 等 |
| `caption` | TEXT | 说明文字 |
| `media_metadata` | TEXT | 尺寸、时长、MIME 等 JSON |
| `availability` | TEXT | `available`、`missing`、`invalid`、`unknown` |
| `retrieved_at` | TEXT | 取得时间 |
| `content_hash` | TEXT | 链接集合或媒体元数据哈希 |
| `extra` | TEXT | 其他字段 JSON |

自然键：`(source_id, subject_source_item_id, media_url)`。

索引：`(source_id, subject_source_item_id)`、`(media_type)`、`(availability)`。

#### stage_ich_articles

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键 |
| `raw_fetch_id` | INTEGER | 来源请求 |
| `source_id` | TEXT | `ihchina` |
| `subject_source_item_id` | TEXT | 关联项目 ID |
| `article_source_item_id` | TEXT | 资讯或学术 ID |
| `relation_type` | TEXT | 相关资讯、相关学术 |
| `title` | TEXT | 标题 |
| `published_date` | TEXT | 发布日期 |
| `source_url` | TEXT | 文章 URL |
| `body_html` | TEXT | 正文 HTML，可为空 |
| `body_text` | TEXT | 正文纯文本，可为空 |
| `body_saved` | INTEGER | 是否已保存正文 |
| `retrieved_at` | TEXT | 取得时间 |
| `content_hash` | TEXT | 内容哈希 |
| `extra` | TEXT | 其他字段 JSON |

自然键：`(source_id, subject_source_item_id, article_source_item_id, relation_type)`。

索引：`(source_id, published_date)`、`(source_id, relation_type)`。

保留策略：元数据长期保留；资讯和学术全文按来源文档决定是否保存，默认不进入业务发布。

### stage_agri_*

来源于 `aqsc-moa` 的公告、附件行和 `cnipa` 的地理标志公告与产品行。

#### stage_agri_announcements

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键 |
| `raw_fetch_id` | INTEGER | 列表或详情请求 |
| `source_id` | TEXT | `aqsc-moa` 或 `cnipa` |
| `source_item_id` | TEXT | 公告 ID |
| `source_url` | TEXT | 公告详情或检索详情 |
| `title` | TEXT | 公告标题 |
| `announcement_no` | TEXT | 公告文号或编号，缺失为 `NULL` |
| `published_at` | TEXT | 栏目发布日期 |
| `certified_at` | TEXT | 认定或落款日期 |
| `cert_type` | TEXT | 名特优新、特质农品、地理标志 |
| `issuer` | TEXT | 发布机构 |
| `attachment_count` | INTEGER | 附件数量 |
| `retrieved_at` | TEXT | 取得时间 |
| `content_hash` | TEXT | 公告内容哈希 |
| `parser_version` | TEXT | 解析器版本 |
| `extra` | TEXT | 其他字段 JSON |

自然键：`(source_id, source_item_id)`；缺少 ID 时用 `(source_id, source_url, content_hash)`。

索引：`(source_id, cert_type, published_at)`、`(source_id, announcement_no)`。

#### stage_agri_rows

把 XLSX、PDF 或 HTML 表格中的一行原样落到 stage，不先合并跨公告产品。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键 |
| `raw_fetch_id` | INTEGER | 来源请求 |
| `raw_file_id` | INTEGER | 附件文件 |
| `source_id` | TEXT | 来源 ID |
| `announcement_source_item_id` | TEXT | 所属公告 |
| `sheet_name` | TEXT | Excel 工作表名 |
| `page_no` | INTEGER | PDF 页码 |
| `row_no` | INTEGER | 文件内行号 |
| `cert_type` | TEXT | 认证类型 |
| `product_name_raw` | TEXT | 产品名称原文 |
| `province_raw` | TEXT | 省份原文 |
| `city_raw` | TEXT | 地市原文，可空 |
| `county_raw` | TEXT | 区县原文，可空 |
| `region_raw` | TEXT | 展示地区原文 |
| `applicant_raw` | TEXT | 申请人或申请机构 |
| `protection_unit_raw` | TEXT | 保护单位 |
| `origin_scope_raw` | TEXT | 产地范围原文 |
| `category_raw` | TEXT | 产品类别原文 |
| `certificate_no` | TEXT | 证书编号，仅来源明确给出时填写 |
| `row_json` | TEXT | 原始行对象 JSON |
| `retrieved_at` | TEXT | 取得时间 |
| `content_hash` | TEXT | 行内容哈希 |
| `parser_version` | TEXT | 解析器版本 |
| `extra` | TEXT | 其他字段 JSON |

自然键：没有跨文件稳定 ID，使用 `(source_id, raw_file_id, sheet_name, page_no, row_no, content_hash)` 作审计键。

索引：`(source_id, cert_type)`、`(product_name_raw)`、`(province_raw)`、`(raw_file_id)`。

外键：`raw_file_id` 引用 `raw_files.id`，`raw_fetch_id` 引用 `raw_fetches.id`。

保留策略：附件行随批次保留；解析器升级时新建版本，不覆盖旧解析结果。

#### stage_agri_cnipa_products

`cnipa` 的 PDF 产品行需要保留公告号、页码和产品字段。它与 `stage_agri_rows` 同源，但保留检索系统特有的 ID 和签名文件信息。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键 |
| `raw_fetch_id` | INTEGER | 详情或 PDF 请求 |
| `raw_file_id` | INTEGER | PDF 文件 |
| `source_id` | TEXT | 固定 `cnipa` |
| `announcement_source_item_id` | TEXT | 公告 ID |
| `product_name_raw` | TEXT | 产品名称 |
| `announcement_no` | TEXT | 公告编号 |
| `certified_at` | TEXT | 落款日期 |
| `province_raw` | TEXT | 省份 |
| `region_raw` | TEXT | 地区 |
| `origin_scope_raw` | TEXT | 产地范围 |
| `applicant_raw` | TEXT | 申请人 |
| `category_raw` | TEXT | 类别 |
| `pdf_page_no` | INTEGER | PDF 页码 |
| `retrieved_at` | TEXT | 取得时间 |
| `content_hash` | TEXT | 行内容哈希 |
| `extra` | TEXT | 其他字段 JSON |

自然键：`(source_id, announcement_source_item_id, product_name_raw, pdf_page_no, content_hash)`。

索引：`(source_id, product_name_raw)`、`(source_id, announcement_no)`、`(raw_file_id)`。

### stage_jobs_*

招聘来源各自保存原始岗位行。该层可以出现多个来源不同的字段名，但必须保留统一审计列。

#### stage_jobs_nzrc

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键 |
| `raw_fetch_id` | INTEGER | 列表或详情请求 |
| `source_id` | TEXT | `nzrc` |
| `source_item_id` | TEXT | 岗位 ID |
| `source_url` | TEXT | 岗位详情 URL |
| `company_source_item_id` | TEXT | 企业 ID |
| `title_raw` | TEXT | 岗位名称原文 |
| `company_name` | TEXT | 企业名称 |
| `company_url` | TEXT | 企业详情 URL |
| `location_raw` | TEXT | 工作地点 |
| `listed_at` | TEXT | 列表更新时间 |
| `published_at` | TEXT | 详情发布日期 |
| `validity_days` | INTEGER | 有效天数 |
| `employment_type` | TEXT | 招聘方式 |
| `headcount_raw` | TEXT | 招聘人数原文 |
| `salary_raw` | TEXT | 薪资原文 |
| `education_raw` | TEXT | 学历原文 |
| `experience_raw` | TEXT | 经验原文 |
| `gender_required` | TEXT | 性别要求 |
| `description_html` | TEXT | 岗位正文 HTML |
| `description_text` | TEXT | 岗位正文纯文本 |
| `contact_fields_json` | TEXT | 公开页联系方式字段 JSON，未登录为空 |
| `retrieved_at` | TEXT | 取得时间 |
| `content_hash` | TEXT | 内容哈希 |
| `parser_version` | TEXT | 解析器版本 |
| `extra` | TEXT | 其他字段 JSON |

自然键：`(source_id, source_item_id)`。

索引：`(source_id, source_url)`、`(source_id, published_at)`、`(source_id, content_hash)`。

#### stage_jobs_nongmuhr

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键 |
| `raw_fetch_id` | INTEGER | 来源请求 |
| `source_id` | TEXT | `nongmuhr` |
| `source_item_id` | TEXT | 岗位 ID |
| `source_url` | TEXT | 岗位详情 URL |
| `title_raw` | TEXT | 岗位名称原文 |
| `company_name` | TEXT | 企业名称 |
| `company_url` | TEXT | 企业 URL |
| `department` | TEXT | 部门 |
| `employment_type` | TEXT | 工作性质 |
| `headcount_raw` | TEXT | 招聘人数原文 |
| `deadline_at` | TEXT | 截止日期 |
| `experience_raw` | TEXT | 工作经验 |
| `education_raw` | TEXT | 学历 |
| `location_raw` | TEXT | 工作地点 |
| `gender_required` | TEXT | 性别要求 |
| `age_requirement` | TEXT | 年龄要求 |
| `salary_raw` | TEXT | 薪资原文 |
| `contact_fields_json` | TEXT | 联系人、电话、邮件等公开字段 JSON |
| `description_html` | TEXT | 岗位描述 HTML |
| `description_text` | TEXT | 岗位描述纯文本 |
| `company_industry` | TEXT | 公司行业 |
| `company_size` | TEXT | 公司规模 |
| `company_nature` | TEXT | 公司性质 |
| `company_description` | TEXT | 公司介绍 |
| `published_at` | TEXT | 发布时间 |
| `listed_relative_time` | TEXT | 列表相对时间 |
| `retrieved_at` | TEXT | 取得时间 |
| `content_hash` | TEXT | 内容哈希 |
| `parser_version` | TEXT | 解析器版本 |
| `extra` | TEXT | 其他字段 JSON |

自然键：`(source_id, source_item_id)`。

索引：`(source_id, source_url)`、`(source_id, published_at)`、`(source_id, deadline_at)`。

#### stage_jobs_5ajob

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键 |
| `raw_fetch_id` | INTEGER | 来源请求 |
| `source_id` | TEXT | `5ajob` |
| `source_item_id` | TEXT | 岗位 ID |
| `source_url` | TEXT | canonical 详情 URL |
| `title_raw` | TEXT | 岗位名称原文 |
| `company_name` | TEXT | 企业名称 |
| `location_raw` | TEXT | 工作地点原文 |
| `industry_raw` | TEXT | 行业原文 |
| `salary_raw` | TEXT | 月薪原文 |
| `headcount_raw` | TEXT | 招聘人数原文 |
| `employment_type` | TEXT | 招聘方式 |
| `major_requirement` | TEXT | 专业要求 |
| `experience_raw` | TEXT | 工作经验 |
| `education_raw` | TEXT | 学历要求 |
| `description_text` | TEXT | 岗位描述 |
| `requirements_text` | TEXT | 应聘要求 |
| `expires_at_text` | TEXT | 有效期原文 |
| `status_text` | TEXT | 列表状态 |
| `published_at` | TEXT | 发布时间，来源缺失时为 `NULL` |
| `retrieved_at` | TEXT | 取得时间 |
| `content_hash` | TEXT | 内容哈希 |
| `parser_version` | TEXT | 解析器版本 |
| `extra` | TEXT | 其他字段 JSON |

自然键：`(source_id, source_item_id)`；缺失 ID 时用 `(source_id, source_url)`。

索引：`(source_id, source_url)`、`(source_id, industry_raw)`、`(source_id, published_at)`。

保留策略：所有 stage 招聘表保留首次、最近发现时间和正文哈希；下架岗位不物理删除。

### stage_dialect_*

#### stage_dialect_points

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键 |
| `raw_fetch_id` | INTEGER | 来源请求 |
| `source_id` | TEXT | 来源 ID |
| `source_item_id` | TEXT | 来源内方言点或地区 ID |
| `source_url` | TEXT | 来源详情 URL |
| `region_raw` | TEXT | 地区原文，如 `广东广州` |
| `province_raw` | TEXT | 省份原文或推导值 |
| `city_raw` | TEXT | 城市原文或推导值 |
| `county_raw` | TEXT | 区县原文 |
| `dialect_name_raw` | TEXT | 方言名原文 |
| `point_note` | TEXT | 调查点说明 |
| `retrieved_at` | TEXT | 取得时间 |
| `content_hash` | TEXT | 内容哈希 |
| `parser_version` | TEXT | 解析器版本 |
| `extra` | TEXT | 其他字段 JSON |

自然键：`(source_id, source_item_id)`；缺少 ID 时用 `(source_id, region_raw, dialect_name_raw)`。

索引：`(source_id, region_raw)`、`(source_id, province_raw, city_raw)`。

#### stage_dialect_lexemes

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键 |
| `raw_fetch_id` | INTEGER | 来源请求 |
| `source_id` | TEXT | 来源 ID |
| `source_item_id` | TEXT | 来源词条 ID |
| `source_url` | TEXT | 词条详情 URL |
| `point_source_item_id` | TEXT | 关联方言点来源 ID |
| `lemma_raw` | TEXT | 词条或词形原文 |
| `phonetic_raw` | TEXT | 读音、拼音或音标原文 |
| `definition_raw` | TEXT | 释义原文 |
| `example_raw` | TEXT | 例句原文 |
| `audio_url` | TEXT | 音频 URL，仅在有可用证据时填写 |
| `audio_status` | TEXT | `available`、`missing`、`invalid`、`unknown` |
| `retrieved_at` | TEXT | 取得时间 |
| `content_hash` | TEXT | 内容哈希 |
| `parser_version` | TEXT | 解析器版本 |
| `extra` | TEXT | 其他字段 JSON |

自然键：`(source_id, source_item_id)`。

索引：`(source_id, point_source_item_id)`、`(source_id, lemma_raw)`、`(audio_status)`。

#### stage_dialect_sources

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键 |
| `raw_fetch_id` | INTEGER | 来源请求 |
| `source_id` | TEXT | 来源 ID |
| `source_item_id` | TEXT | 来源记录 ID |
| `source_url` | TEXT | 详情 URL |
| `record_type` | TEXT | point、lexeme、audio |
| `title` | TEXT | 来源标题 |
| `access_level` | TEXT | 访问等级 |
| `license_or_usage` | TEXT | 权利说明 |
| `confidence` | TEXT | 来源置信度 |
| `retrieved_at` | TEXT | 取得时间 |
| `content_hash` | TEXT | 内容哈希 |
| `extra` | TEXT | 其他字段 JSON |

自然键：`(source_id, source_item_id, record_type)`。

索引：`(source_id, record_type)`、`(access_level)`。

保留策略：方言 stage 保留每次来源快照摘要；音频只保存 URL 和可访问性结论，不在业务库复制音频。

## std 层

`std` 是跨来源标准实体层。实体 interface、自然键、来源关系、发布状态和不变式以 `std-entities.md` 为准。本节只定义物理表、列、索引和外键，不重复实体语义。每个实体表必须有 `source_id` 或来源关联表，不得把来源信息藏在 JSON 中。以下字段类型均为建议类型，实际实现应使用 SQLite 参数化语句。

天气不建立 std 表。实时天气只作为运行时 DTO 或短期缓存，见 `mapping/weather.md`，不进入转换批次。

### 非遗域

#### std_ich_projects

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 标准实体 ID |
| `source_id` | TEXT | NOT NULL | 主来源，通常为 `ihchina` |
| `source_item_id` | TEXT | NOT NULL | 来源项目 ID |
| `source_url` | TEXT | NOT NULL | 可直接打开的详情 URL |
| `ich_code` | TEXT | 可空 | 项目编号 |
| `name` | TEXT | NOT NULL | 项目名称 |
| `project_serial` | TEXT | 可空 | 项目序号 |
| `source_project_num` | TEXT | 可空 | 来源内部编号 |
| `category` | TEXT | 可空 | 非遗类别 |
| `project_type` | TEXT | 可空 | 新增或扩展项目 |
| `announcement_batch` | TEXT | 可空 | 批次 |
| `announcement_year` | INTEGER | 可空 | 公布年份 |
| `declaration_region` | TEXT | 可空 | 申报地区或单位 |
| `protection_unit` | TEXT | 可空 | 保护单位 |
| `province` | TEXT | 可空 | 省级名称 |
| `city` | TEXT | 可空 | 地级名称 |
| `county` | TEXT | 可空 | 县级名称 |
| `description_html` | TEXT | 可空 | 正文 HTML，采集库保留 |
| `description_text` | TEXT | 可空 | 正文纯文本 |
| `source_modified_at` | TEXT | 可空 | 来源修改时间 |
| `retrieved_at` | TEXT | NOT NULL | 取得时间 |
| `content_hash` | TEXT | NOT NULL | 内容哈希 |
| `confidence` | TEXT | NOT NULL | `high`、`medium`、`low` |
| `license_or_usage` | TEXT | NOT NULL | 来源权利说明 |
| `publish_status` | TEXT | NOT NULL | `draft`、`reviewed`、`published`、`blocked` |
| `first_seen_at` | TEXT | NOT NULL | 首次进入标准层 |
| `last_seen_at` | TEXT | NOT NULL | 最近出现 |
| `extra` | TEXT | 默认 `'{}'` | 其他字段 JSON |

主键：`id`。

自然键：`(source_id, source_item_id)` 唯一；跨来源合并使用 `(ich_code, declaration_region, name)` 作为候选键，不直接强制唯一。

索引：

- `(ich_code)`
- `(name)`
- `(category, announcement_year)`
- `(province, city, county)`
- `(publish_status, confidence)`

外键：

- `id` 被 `std_ich_inheritors.project_id`、`std_ich_related_items.subject_project_id`、`std_ich_media_links.project_id` 引用。
- `source_id` 逻辑上引用 `std_sources.source_id`。

JSON 语义：`extra` 保存来源未建模的附加字段；关键可筛选属性必须使用独立列。

保留策略：保留当前版本和每次 `content_hash` 变化的历史；被来源移除的项目标记 `is_active=0`，不物理删除。

#### std_ich_inheritors

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 传承人标准 ID |
| `project_id` | INTEGER | 可空 | 关联 `std_ich_projects.id` |
| `source_id` | TEXT | NOT NULL | 来源 ID |
| `source_item_id` | TEXT | NOT NULL | 来源传承人 ID |
| `source_url` | TEXT | NOT NULL | 传承人详情 URL |
| `name` | TEXT | NOT NULL | 姓名 |
| `gender` | TEXT | 可空 | 性别 |
| `birth_date` | TEXT | 可空 | 可保留 `YYYY.MM` 精度 |
| `ethnicity` | TEXT | 可空 | 民族 |
| `category` | TEXT | 可空 | 类别 |
| `ich_code` | TEXT | 可空 | 项目编号 |
| `project_name` | TEXT | 可空 | 项目名称 |
| `declaration_region` | TEXT | 可空 | 申报地区或单位 |
| `biography_text` | TEXT | 可空 | 小传 |
| `retrieved_at` | TEXT | NOT NULL | 取得时间 |
| `content_hash` | TEXT | NOT NULL | 内容哈希 |
| `confidence` | TEXT | NOT NULL | 置信度 |
| `extra` | TEXT | 默认 `'{}'` | 附加字段 JSON |

自然键：`(source_id, source_item_id)`；同一人跨项目关系不合并成单条。

索引：`(project_id)`、`(ich_code)`、`(name)`、`(source_id, source_item_id)`。

外键：`project_id` 引用 `std_ich_projects.id`，删除项目时置空或级联由实现策略决定。

保留策略：人物资料按来源文档保留，业务发布须经审核。

#### std_ich_related_items

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 关系 ID |
| `subject_project_id` | INTEGER | NOT NULL | 当前项目 |
| `related_project_id` | INTEGER | 可空 | 已能匹配的相关项目 |
| `source_id` | TEXT | NOT NULL | 来源 ID |
| `related_source_item_id` | TEXT | 可空 | 相关项目来源 ID |
| `related_name` | TEXT | 可空 | 相关项目名称 |
| `ich_code` | TEXT | 可空 | 编号 |
| `relation_type` | TEXT | NOT NULL | 相关项目、资讯、学术 |
| `related_url` | TEXT | 可空 | 可打开 URL |
| `declaration_region` | TEXT | 可空 | 申报地区或单位 |
| `retrieved_at` | TEXT | NOT NULL | 取得时间 |
| `content_hash` | TEXT | NOT NULL | 内容哈希 |
| `extra` | TEXT | 默认 `'{}'` | 附加字段 JSON |

自然键：`(source_id, subject_project_id, related_source_item_id, relation_type)`。

索引：`(subject_project_id)`、`(related_project_id)`、`(relation_type)`。

外键：`subject_project_id`、`related_project_id` 引用 `std_ich_projects.id`。

#### std_ich_media_links

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 媒体关系 ID |
| `project_id` | INTEGER | NOT NULL | 项目 |
| `source_id` | TEXT | NOT NULL | 来源 ID |
| `source_page_url` | TEXT | 可空 | 承载页面 |
| `media_url` | TEXT | NOT NULL | 绝对 URL |
| `media_type` | TEXT | NOT NULL | image、video、audio、iframe |
| `media_role` | TEXT | 可空 | header、body、attachment |
| `caption` | TEXT | 可空 | 说明 |
| `availability` | TEXT | NOT NULL | 可用性 |
| `license_or_usage` | TEXT | NOT NULL | 权利说明 |
| `retrieved_at` | TEXT | NOT NULL | 取得时间 |
| `content_hash` | TEXT | 可空 | 元数据哈希 |
| `extra` | TEXT | 默认 `'{}'` | 附加字段 JSON |

自然键：`(project_id, media_url)`。

索引：`(project_id)`、`(media_type)`、`(availability)`。

外键：`project_id` 引用 `std_ich_projects.id`。

保留策略：只保存链接和元数据，不把媒体文件复制进业务库。

### 农产品域

#### std_agri_products

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 产品标准 ID |
| `cert_type` | TEXT | NOT NULL | 名特优新、特质农品、地理标志 |
| `product_name` | TEXT | NOT NULL | 规范产品名 |
| `product_name_raw` | TEXT | 可空 | 来源原名 |
| `normalized_name` | TEXT | NOT NULL | 去空白、统一全半角后的名称，用于自然键和匹配 |
| `category` | TEXT | 可空 | 水果、蔬菜、水产等 |
| `is_aquatic` | INTEGER | 可空 | 水产三态：`1` 是、`0` 否、`NULL` 证据不足 |
| `province` | TEXT | 可空 | 省份 |
| `city` | TEXT | 可空 | 地市 |
| `county` | TEXT | 可空 | 区县 |
| `region` | TEXT | 可空 | 来源地区展示值 |
| `origin_scope` | TEXT | 可空 | 产地范围原文 |
| `applicant` | TEXT | 可空 | 申请人或申请机构 |
| `protection_unit` | TEXT | 可空 | 保护单位 |
| `certificate_no` | TEXT | 可空 | 证书编号，来源明确时填写 |
| `certified_at` | TEXT | 可空 | 认定或公布日期 |
| `source_url` | TEXT | NOT NULL | 主来源详情 URL |
| `content_hash` | TEXT | NOT NULL | 规范化内容哈希 |
| `confidence` | TEXT | NOT NULL | 置信度 |
| `license_or_usage` | TEXT | NOT NULL | 权利说明 |
| `publish_status` | TEXT | NOT NULL | 发布状态 |
| `retrieved_at` | TEXT | NOT NULL | 取得时间 |
| `first_seen_at` | TEXT | NOT NULL | 首次进入标准层 |
| `last_seen_at` | TEXT | NOT NULL | 最近出现 |
| `extra` | TEXT | 默认 `'{}'` | 附加字段 JSON |

自然键：`(cert_type, normalized_name, province, region)` 唯一。`region` 取来源地区展示值；缺少 `region` 时使用 `origin_scope` 规范化文本的稳定摘要，并在 `extra` 中记录推导依据。`region` 和 `origin_scope` 都为空时进入冲突，不与同省产品合并。`normalized_name` 的归一规则见 `std-entities.md`。

索引：`(cert_type, province, city, county)`、`(category)`、`(normalized_name)`、`(publish_status)`。

外键：`id` 被 `std_agri_product_sources.product_id` 引用。

保留策略：保留当前版本和历史来源；注销或失效产品标记 `is_active=0`，不删除来源证据。

#### std_agri_product_sources

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 来源关系 ID |
| `product_id` | INTEGER | NOT NULL | 产品 |
| `source_id` | TEXT | NOT NULL | 来源 ID |
| `source_item_id` | TEXT | 可空 | 公告或产品来源 ID |
| `source_url` | TEXT | NOT NULL | 可打开详情 URL |
| `announcement_no` | TEXT | 可空 | 公告号或文号 |
| `published_at` | TEXT | 可空 | 栏目发布日期 |
| `certified_at` | TEXT | 可空 | 认定日期 |
| `source_product_name` | TEXT | 可空 | 来源产品名 |
| `source_region` | TEXT | 可空 | 来源地区 |
| `source_title` | TEXT | 可空 | 公告标题 |
| `is_primary` | INTEGER | 默认 0 | 是否主来源 |
| `retrieved_at` | TEXT | NOT NULL | 取得时间 |
| `content_hash` | TEXT | 可空 | 来源内容哈希 |
| `extra` | TEXT | 默认 `'{}'` | 附加字段 JSON |

自然键：`(product_id, source_id, source_url)`。

索引：`(product_id)`、`(source_id, source_item_id)`、`(announcement_no)`、`(is_primary)`。

外键：`product_id` 引用 `std_agri_products.id`。

保留策略：来源关系不因产品合并而删除；多次公告保留多次来源。

#### std_agri_product_aliases

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 别名 ID |
| `product_id` | INTEGER | NOT NULL | 产品 |
| `alias` | TEXT | NOT NULL | 别名或原文名称 |
| `alias_type` | TEXT | NOT NULL | raw、abbreviation、former、typo |
| `source_id` | TEXT | 可空 | 别名来源 |
| `source_url` | TEXT | 可空 | 来源 URL |
| `confidence` | TEXT | NOT NULL | 置信度 |
| `extra` | TEXT | 默认 `'{}'` | 附加字段 JSON |

自然键：`(product_id, alias, alias_type)`。

索引：`(alias)`、`(product_id)`。

外键：`product_id` 引用 `std_agri_products.id`。

### 招聘域

#### std_jobs

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 标准岗位 ID |
| `source_id` | TEXT | NOT NULL | 主来源 |
| `source_item_id` | TEXT | NOT NULL | 来源岗位 ID |
| `source_url` | TEXT | NOT NULL | 可直接打开的详情 URL |
| `title` | TEXT | NOT NULL | 岗位名称 |
| `title_raw` | TEXT | 可空 | 来源原题 |
| `company_name` | TEXT | 可空 | 企业名称 |
| `company_url` | TEXT | 可空 | 企业 URL |
| `company_industry` | TEXT | 可空 | 行业 |
| `company_size` | TEXT | 可空 | 规模 |
| `company_nature` | TEXT | 可空 | 性质 |
| `location_raw` | TEXT | 可空 | 地点原文 |
| `province` | TEXT | 可空 | 省份 |
| `city` | TEXT | 可空 | 城市 |
| `employment_type` | TEXT | 可空 | 全职、兼职等 |
| `headcount` | INTEGER | 可空 | 招聘人数，仅可可靠解析时填写 |
| `salary_raw` | TEXT | 可空 | 薪资原文 |
| `education_raw` | TEXT | 可空 | 学历原文 |
| `experience_raw` | TEXT | 可空 | 经验原文 |
| `gender_requirement` | TEXT | 可空 | 性别要求 |
| `age_requirement` | TEXT | 可空 | 年龄要求 |
| `major_requirement` | TEXT | 可空 | 专业要求 |
| `description` | TEXT | 可空 | 岗位描述或摘要 |
| `requirements` | TEXT | 可空 | 应聘要求 |
| `published_at` | TEXT | 可空 | 发布日期 |
| `deadline_at` | TEXT | 可空 | 截止日期 |
| `validity_days` | INTEGER | 可空 | 有效天数 |
| `status_text` | TEXT | 可空 | 来源状态 |
| `content_hash` | TEXT | NOT NULL | 内容哈希 |
| `confidence` | TEXT | NOT NULL | 置信度 |
| `license_or_usage` | TEXT | NOT NULL | 权利说明 |
| `publish_status` | TEXT | NOT NULL | 发布状态 |
| `retrieved_at` | TEXT | NOT NULL | 取得时间 |
| `first_seen_at` | TEXT | NOT NULL | 首次发现 |
| `last_seen_at` | TEXT | NOT NULL | 最近发现 |
| `extra` | TEXT | 默认 `'{}'` | 附加字段 JSON |

自然键：`(source_id, source_item_id)`；缺失 ID 时使用规范化后的 `(source_id, source_url)`。

索引：`(source_id, published_at)`、`(province, city)`、`(company_name)`、`(publish_status, deadline_at)`、`(content_hash)`。

外键：`id` 被 `std_job_sources.job_id`、`std_job_locations.job_id` 引用。

保留策略：下架岗位标记 `is_active=0` 和 `expired`，保留来源快照和首次发现时间。

#### std_job_sources

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 来源关系 ID |
| `job_id` | INTEGER | NOT NULL | 标准岗位 |
| `source_id` | TEXT | NOT NULL | 来源 |
| `source_item_id` | TEXT | NOT NULL | 来源岗位 ID |
| `source_url` | TEXT | NOT NULL | 详情 URL |
| `is_primary` | INTEGER | 默认 0 | 是否主来源 |
| `retrieved_at` | TEXT | NOT NULL | 取得时间 |
| `content_hash` | TEXT | 可空 | 来源内容哈希 |
| `extra` | TEXT | 默认 `'{}'` | 附加字段 JSON |

自然键：`(job_id, source_id, source_url)`。

索引：`(source_id, source_item_id)`、`(job_id)`、`(is_primary)`。

外键：`job_id` 引用 `std_jobs.id`。

#### std_job_locations

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 地点关系 ID |
| `job_id` | INTEGER | NOT NULL | 岗位 |
| `location_raw` | TEXT | 可空 | 原文地点 |
| `province` | TEXT | 可空 | 省份 |
| `city` | TEXT | 可空 | 城市 |
| `county` | TEXT | 可空 | 区县 |
| `is_primary` | INTEGER | 默认 0 | 是否主工作地点 |
| `extra` | TEXT | 默认 `'{}'` | 附加字段 JSON |

自然键：`(job_id, province, city, county, location_raw)`。

索引：`(province, city)`、`(job_id)`。

外键：`job_id` 引用 `std_jobs.id`。

### 方言域

#### std_dialect_points

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 方言点 ID |
| `source_id` | TEXT | NOT NULL | 主来源 |
| `source_item_id` | TEXT | 可空 | 来源点 ID |
| `source_url` | TEXT | 可空 | 详情 URL |
| `region_raw` | TEXT | NOT NULL | 地区原文 |
| `province` | TEXT | 可空 | 省 |
| `city` | TEXT | 可空 | 市 |
| `county` | TEXT | 可空 | 县 |
| `dialect_name` | TEXT | 可空 | 方言名，来源明确时填写 |
| `point_note` | TEXT | 可空 | 调查点说明 |
| `confidence` | TEXT | NOT NULL | 置信度 |
| `retrieved_at` | TEXT | NOT NULL | 取得时间 |
| `content_hash` | TEXT | 可空 | 内容哈希 |
| `extra` | TEXT | 默认 `'{}'` | 附加字段 JSON |

自然键：`(source_id, source_item_id)`；缺少 ID 时使用 `(region_raw, dialect_name)`，并保留来源差异。

索引：`(province, city, county)`、`(dialect_name)`、`(region_raw)`。

外键：`id` 被 `std_dialect_lexemes.point_id` 引用。

#### std_dialect_lexemes

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 词条 ID |
| `point_id` | INTEGER | NOT NULL | 方言点 |
| `lemma` | TEXT | NOT NULL | 词形或词条 |
| `phonetic` | TEXT | 可空 | 读音、拼音或音标原文 |
| `definition` | TEXT | 可空 | 释义 |
| `example` | TEXT | 可空 | 例句 |
| `audio_url` | TEXT | 可空 | 音频 URL |
| `audio_status` | TEXT | NOT NULL | 可用性 |
| `confidence` | TEXT | NOT NULL | 置信度 |
| `publish_status` | TEXT | NOT NULL | 发布状态 |
| `content_hash` | TEXT | 可空 | 内容哈希 |
| `retrieved_at` | TEXT | NOT NULL | 取得时间 |
| `extra` | TEXT | 默认 `'{}'` | 附加字段 JSON |

自然键：`(point_id, lemma)`；同一词形的来源差异通过 `std_dialect_lexeme_sources` 保持。

索引：`(point_id, lemma)`、`(audio_status)`、`(publish_status)`。

外键：`point_id` 引用 `std_dialect_points.id`。

#### std_dialect_lexeme_sources

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 词条来源 ID |
| `lexeme_id` | INTEGER | NOT NULL | 词条 |
| `source_id` | TEXT | NOT NULL | 来源 |
| `source_item_id` | TEXT | 可空 | 来源词条 ID |
| `source_url` | TEXT | NOT NULL | 详情 URL |
| `is_primary` | INTEGER | 默认 0 | 是否主来源 |
| `retrieved_at` | TEXT | NOT NULL | 取得时间 |
| `content_hash` | TEXT | 可空 | 来源内容哈希 |
| `extra` | TEXT | 默认 `'{}'` | 附加字段 JSON |

自然键：`(lexeme_id, source_id, source_item_id, source_url)`。

索引：`(source_id, source_item_id)`、`(lexeme_id)`。

外键：`lexeme_id` 引用 `std_dialect_lexemes.id`。

### 公共来源与服务表

#### std_sources

本条表是 std 层的来源登记，与 `sources.json` 对应，记录用于转换和发布判断的来源元数据。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 代理主键 |
| `source_id` | TEXT | UNIQUE NOT NULL | 全局来源 ID |
| `name` | TEXT | NOT NULL | 来源名称 |
| `domains` | TEXT | 默认 `'[]'` | 域名数组 JSON |
| `content_domains` | TEXT | 默认 `'[]'` | 内容域数组 JSON |
| `priority` | TEXT | NOT NULL | P0、P1、P2 |
| `access_level` | TEXT | NOT NULL | 访问等级 |
| `license_or_usage` | TEXT | NOT NULL | 权利与使用边界 |
| `confidence` | TEXT | NOT NULL | 来源整体置信度 |
| `document_path` | TEXT | 可空 | 来源文档路径 |
| `review_path` | TEXT | 可空 | 审核文档路径 |
| `verified_at` | TEXT | 可空 | 最近验证时间 |
| `is_enabled` | INTEGER | 默认 1 | 是否允许调度 |
| `extra` | TEXT | 默认 `'{}'` | 附加字段 JSON |

自然键：`source_id`。

索引：`(access_level, is_enabled)`、`(priority)`。

保留策略：来源登记长期保留；停用来源保留历史记录。

#### import_batches

记录转换器每次读取 std 并写入业务库的批次。批次属于采集库，业务库只保存引用 ID 或导入时间。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 批次 ID |
| `batch_key` | TEXT | UNIQUE NOT NULL | 可读批次键 |
| `source_id` | TEXT | 可空 | 单来源批次 |
| `content_domain` | TEXT | 可空 | ich、agri、jobs、dialects |
| `started_at` | TEXT | NOT NULL | 开始时间 |
| `finished_at` | TEXT | 可空 | 结束时间 |
| `status` | TEXT | NOT NULL | `running`、`succeeded`、`partial`、`failed`、`rolled_back` |
| `input_count` | INTEGER | 默认 0 | 读取 std 行数 |
| `inserted_count` | INTEGER | 默认 0 | 新建数 |
| `updated_count` | INTEGER | 默认 0 | 更新数 |
| `skipped_count` | INTEGER | 默认 0 | 因人工保护或状态跳过 |
| `conflict_count` | INTEGER | 默认 0 | 冲突数 |
| `failed_count` | INTEGER | 默认 0 | 失败数 |
| `target_database` | TEXT | 默认 `yuexiang` | 目标库标识 |
| `converter_version` | TEXT | NOT NULL | 转换器版本 |
| `rollback_note` | TEXT | 可空 | 回滚说明 |
| `extra` | TEXT | 默认 `'{}'` | 运行摘要 JSON |

自然键：`batch_key`。

索引：`(status, started_at)`、`(source_id, content_domain)`。

保留策略：永久保留批次和汇总；回滚只撤销本批次尚未被人工修改的结果。

#### import_conflicts

保存无法自动裁决的字段冲突，供人工复核。冲突两侧都必须能回到来源 URL 和取得时间。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK | 冲突 ID |
| `batch_id` | INTEGER | NOT NULL | 批次 |
| `content_domain` | TEXT | NOT NULL | 内容域 |
| `target_table` | TEXT | NOT NULL | 业务目标表 |
| `target_key` | TEXT | NOT NULL | 目标自然键序列化值 |
| `target_field` | TEXT | NOT NULL | 冲突字段 |
| `existing_value` | TEXT | 可空 | 已有值 |
| `incoming_value` | TEXT | 可空 | 新值 |
| `existing_source_id` | TEXT | 可空 | 已有来源 |
| `existing_source_url` | TEXT | 可空 | 已有详情 URL |
| `incoming_source_id` | TEXT | 可空 | 新来源 |
| `incoming_source_url` | TEXT | 可空 | 新详情 URL |
| `existing_retrieved_at` | TEXT | 可空 | 已有取得时间 |
| `incoming_retrieved_at` | TEXT | 可空 | 新取得时间 |
| `reason` | TEXT | NOT NULL | 冲突原因 |
| `resolution` | TEXT | NOT NULL | `unresolved`、`prefer_existing`、`prefer_incoming`、`merged`、`manual` |
| `resolved_by` | TEXT | 可空 | 复核人 |
| `resolved_at` | TEXT | 可空 | 复核时间 |
| `resolution_note` | TEXT | 可空 | 复核说明 |
| `created_at` | TEXT | NOT NULL | 创建时间 |

自然键：`(batch_id, target_table, target_key, target_field, reason)`。

索引：`(resolution, created_at)`、`(target_table, target_key)`、`(batch_id)`。

外键：`batch_id` 引用 `import_batches.id`。

保留策略：冲突记录永久保留，不因批次回滚删除。

## 表数量与关系

| 层 | 表或表组 | 数量 |
| --- | --- | --- |
| raw | `raw_fetches`、`raw_files` | 2 |
| stage | `stage_ich_*`（5） | 5 |
| stage | `stage_agri_*`（3） | 3 |
| stage | `stage_jobs_*`（3） | 3 |
| stage | `stage_dialect_*`（3） | 3 |
| std | `std_ich_*`（4） | 4 |
| std | `std_agri_*`（3） | 3 |
| std | `std_jobs`、`std_job_sources`、`std_job_locations` | 3 |
| std | `std_dialect_*`（3） | 3 |
| 服务 | `std_sources`、`import_batches`、`import_conflicts` | 3 |
| 合计 |  | 29 |

## 索引与查询边界

- 采集调度按 `raw_fetches(source_id, fetch_status, started_at)` 查失败和积压。
- 回溯按 `raw_fetches(body_sha256)`、`raw_files(sha256)` 查重复响应。
- 标准层按 `source_id + source_item_id` 做幂等检查，按内容域索引做转换筛选。
- 冲突表按 `resolution` 和 `target_key` 查待复核和单条历史。
- 不允许业务 API 直接访问采集库索引；跨库只在转换器中发生。

## 数据保留总则

| 数据 | 保留期限 | 说明 |
| --- | --- | --- |
| `raw_fetches` 元数据 | 长期 | 便于审计和重跑 |
| 成功响应体 | 至少最近一次和内容变更版本 | 按来源文档决定全文保存范围 |
| 失败响应体 | 180 天 | 只保留脱敏错误摘要和必要状态 |
| `raw_files` 文件 | 按来源文档 | 单文件不超过 100MB |
| `stage` 解析结果 | 至少最近两个解析器版本 | 解析器升级时可比较 |
| `std` 当前实体 | 长期 | 失效记录标记，不直接删除 |
| `import_batches`、`import_conflicts` | 长期 | 支撑回滚和审计 |

## 待确认缺口

- 响应体存放采用文件系统还是 SQLite BLOB 上限，需要实现时按部署容量确认。
- `std_ich_articles` 是否独立成表，取决于后续映射文档是否要求发布资讯和学术摘要。
- 招聘联系方式字段属于“公开但默认不展示”，最终展示策略需运营审核确认。
- 方言音频和媒体文件只登记 URL，是否允许缓存仍取决于来源授权。
