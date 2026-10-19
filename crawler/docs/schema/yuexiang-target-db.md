# 粤乡智匠业务库变更建议

状态：设计建议，未实施

日期：2026-10-19

适用数据库：粤乡智匠业务库（现有 SQLite）

本文只描述未来迁移建议。本次不得修改 `backend/db_schema.py`、`db_domains`、前端、数据库文件或迁移脚本。现有 `recruitments`、`recruitment_sources`、`job_listings` 和 `dialects`、`dialect_phrases`、`dialect_quick_questions` 三张方言表保持原样。

## 现状摘要

| 现有表 | 当前用途 | 本次处理 |
| --- | --- | --- |
| `crafts` | 手工技艺主表，字段为 `id`、`name`、`origin`、`history`、`level`、`sort_order`、`extra` | 补列，不新建非遗主表 |
| `farming_products` | 农时日历的作物目录，不等同于认证农产品 | 不改，新增认证产品表 |
| `recruitments` | 平台策展的公开招聘公告 | 不改 |
| `recruitment_sources` | 招募公告来源 | 不改 |
| `job_listings` | 企业站内发布岗位，走审核和投递 | 不改 |
| `dialects` | 现有方言展示主表 | 不改 |
| `dialect_phrases` | 现有短语展示表 | 不改 |
| `dialect_quick_questions` | 现有快捷问题表 | 不改 |
| 天气 | 当前无业务表 | 不建表 |

## 迁移总原则

1. 认证农产品、招聘采集岗位和方言规范化词条进入新表，避免改变现有页面和 API 的返回形状。
2. 非遗项目继续使用 `crafts` 作为前台主表，只补采集和分类所需列。
3. 所有补列使用可空列或带默认值的 `TEXT`/`INTEGER` 列，旧库升级不需要重写已有行。
4. 迁移顺序为新增表、补列、建索引、回填、切换读路径、再清理旧兼容代码。回填和切换分开发布。
5. 迁移脚本必须可重复执行；重复执行不产生重复行，不覆盖人工字段。
6. 回滚先恢复读路径，再删除新表或新列。SQLite 删除列需确认当前 SQLite 版本支持 `ALTER TABLE DROP COLUMN`，否则采用重建表方式并保留备份。
7. 现有 API 字段和键序保持不变。新字段只通过新增端点、显式筛选参数或后台接口暴露。

## 新增 agri_certified_products

用途：承载全国名特优新、全国特质农品和农业食品相关地理标志产品。它与 `farming_products` 分开，后者继续服务农时日历的作物维度。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK AUTOINCREMENT | 业务主键 |
| `cert_type` | TEXT | NOT NULL | `名特优新`、`特质农品`、`地理标志` |
| `product_name` | TEXT | NOT NULL | 规范产品名 |
| `product_name_raw` | TEXT | 默认 `''` | 来源原名 |
| `normalized_name` | TEXT | NOT NULL | 去空白、统一全半角后的名称 |
| `category` | TEXT | 默认 `''` | 水果、蔬菜、粮油、茶叶、水产等 |
| `is_aquatic` | INTEGER | 默认 0 | 是否水产，供筛选 |
| `province` | TEXT | 默认 `''` | 省份 |
| `city` | TEXT | 默认 `''` | 地市 |
| `county` | TEXT | 默认 `''` | 区县 |
| `region` | TEXT | 默认 `''` | 展示地区 |
| `origin_scope` | TEXT | 默认 `''` | 产地范围原文 |
| `applicant` | TEXT | 默认 `''` | 申请人或申请机构 |
| `protection_unit` | TEXT | 默认 `''` | 保护单位 |
| `certificate_no` | TEXT | 默认 `''` | 来源明确的证书编号 |
| `certified_at` | TEXT | 默认 `''` | 认定或公布日期 |
| `source_url` | TEXT | NOT NULL | 主来源详情 URL |
| `content_hash` | TEXT | 默认 `''` | 规范化内容哈希 |
| `confidence` | TEXT | 默认 `medium` | `high`、`medium`、`low` |
| `publish_status` | TEXT | 默认 `draft` | `draft`、`reviewed`、`published`、`blocked` |
| `import_batch_id` | INTEGER | 默认 0 | 采集库批次引用 |
| `imported_at` | TEXT | 默认 `''` | 导入时间 |
| `first_seen_at` | TEXT | 默认 `''` | 首次发现 |
| `last_seen_at` | TEXT | 默认 `''` | 最近发现 |
| `extra` | TEXT | 默认 `'{}'` | 附加字段 JSON |

自然键：`(cert_type, normalized_name, province, region)` 唯一。

索引：

- `(cert_type, publish_status)`
- `(province, city, county)`
- `(category, is_aquatic)`
- `(normalized_name)`
- `(import_batch_id)`

外键：

- `id` 被 `agri_product_sources.product_id` 引用。
- `import_batch_id` 只保存采集库批次 ID，不跨库建物理外键。

兼容策略：

- 新表不参与现有农时接口，除非新增农产品目录端点或显式开关。
- `farming_products` 继续按原字段读取。
- `cert_type` 使用独立字段，不把三种认证口径合并成一个标签。

回滚方式：

- 停止读新表，保留表和数据作为审计副本。
- 如确认无引用，按 `agri_product_sources`、`agri_certified_products` 顺序删除。

## 新增 agri_product_sources

用途：保存认证产品的多个来源和公告信息。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK AUTOINCREMENT | 业务主键 |
| `product_id` | INTEGER | NOT NULL | 认证产品 |
| `source_id` | TEXT | NOT NULL | 来源 ID |
| `source_item_id` | TEXT | 默认 `''` | 来源记录 ID |
| `source_url` | TEXT | NOT NULL | 可直接打开 |
| `announcement_no` | TEXT | 默认 `''` | 公告号或文号，缺失留空 |
| `source_title` | TEXT | 默认 `''` | 公告标题 |
| `published_at` | TEXT | 默认 `''` | 栏目发布日期 |
| `certified_at` | TEXT | 默认 `''` | 认定日期 |
| `source_product_name` | TEXT | 默认 `''` | 来源产品名 |
| `source_region` | TEXT | 默认 `''` | 来源地区 |
| `exclusion_reason` | TEXT | 默认 `''` | 排除原因，可追溯 |
| `is_primary` | INTEGER | 默认 0 | 主来源标记 |
| `retrieved_at` | TEXT | 默认 `''` | 取得时间 |
| `content_hash` | TEXT | 默认 `''` | 来源内容哈希 |
| `import_batch_id` | INTEGER | 默认 0 | 批次 |
| `extra` | TEXT | 默认 `'{}'` | 附加字段 JSON |

自然键：`(product_id, source_id, source_url)` 唯一。

索引：`(product_id)`、`(source_id, source_item_id)`、`(announcement_no)`、`(is_primary)`。

外键：`product_id` 引用 `agri_certified_products.id ON DELETE CASCADE`。

兼容策略：不改变 `farming_sources`。认证产品来源只在新增端点和导入流程使用。

回滚方式：先删除本表，再删除 `agri_certified_products`。

## 补列 crafts

用途：让国家级非遗项目复用现有手工技艺主表和前台详情结构，同时保留可浏览但不可教学的状态。

| 新增列 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `source_url` | TEXT | `''` | 项目详情页 URL |
| `ich_code` | TEXT | `''` | 项目编号 |
| `ich_category` | TEXT | `''` | 非遗类别 |
| `ich_batch` | TEXT | `''` | 公布批次 |
| `ich_type` | TEXT | `''` | 新增项目或扩展项目 |
| `protection_unit` | TEXT | `''` | 保护单位 |
| `province` | TEXT | `''` | 省 |
| `city` | TEXT | `''` | 市 |
| `county` | TEXT | `''` | 县 |
| `is_teachable` | INTEGER | 0 | 是否具备可审核教学步骤、视频或采购指南 |
| `content_hash` | TEXT | `''` | 规范化内容哈希 |
| `imported_at` | TEXT | `''` | 最近导入时间 |

自然键与升级规则：

- 采集侧自然键为 `(source_id, source_item_id)`，其中来源通常为 `ihchina`。
- 业务侧候选唯一键为 `(ich_code, province, city, county, name)`，不得只用项目名称去重。
- 同一项目名因申报地区、批次或保护单位不同而保留多条。

索引：

- `(ich_code)`
- `(ich_category, ich_batch)`
- `(province, city, county)`
- `(is_teachable)`
- `(content_hash)`

外键：不新增。`craft_steps`、`craft_videos`、`craft_purchase_*` 继续引用 `crafts.id`。

兼容策略：

- 现有 `/api/crafts/list` 仍只返回 `id`、`name`、`origin`、`level`，不增加新键。
- 现有 `/api/crafts/<id>` 的 `name`、`origin`、`history`、`steps`、`purchase_guide` 键集保持不变。
- 新字段只通过新的筛选接口或详情附加字段发布，且需要版本化响应。
- `is_teachable=0` 的项目可浏览基础资料和来源链接，不展示空步骤、空视频或空采购指南。
- 现有四门手工技艺的 `id` 不重命名，避免前端旧链接失效。

迁移顺序：

1. 新增可空列。
2. 回填现有手工技艺的默认值。
3. 导入非遗基础资料，先 `publish_status=draft` 或 `is_teachable=0`。
4. 运营审核教学内容和来源。
5. 切换列表筛选到新字段。

回滚方式：

- 先停止新字段读写，恢复旧查询列。
- 保留新列不删除也可安全回滚；确认无引用后再按 SQLite 支持方式删列。
- 若采用重建表回滚，必须保留 `crafts` 原主键和关联表数据。

## 新增 recruitment_postings

用途：承载从招聘来源采集的公开岗位。现有 `job_listings` 保持为企业站内岗位，`recruitments` 保持为策展公告。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK AUTOINCREMENT | 业务主键 |
| `source_id` | TEXT | NOT NULL | 来源 ID |
| `source_item_id` | TEXT | NOT NULL | 来源岗位 ID |
| `source_url` | TEXT | NOT NULL | 可直接打开 |
| `title` | TEXT | NOT NULL | 岗位名称 |
| `title_raw` | TEXT | 默认 `''` | 原题 |
| `company_name` | TEXT | 默认 `''` | 企业名称 |
| `company_url` | TEXT | 默认 `''` | 企业 URL |
| `company_address` | TEXT | 默认 `''` | 公开企业地址 |
| `region` | TEXT | 默认 `''` | 首个工作地区 |
| `location_raw` | TEXT | 默认 `''` | 地点原文 |
| `province` | TEXT | 默认 `''` | 省份，来自 std 的规范化地点 |
| `city` | TEXT | 默认 `''` | 城市，来自 std 的规范化地点 |
| `county` | TEXT | 默认 `''` | 区县，来自 std 的规范化地点 |
| `employment_type` | TEXT | 默认 `''` | 全职、兼职等 |
| `headcount` | INTEGER | 可空 | 可靠解析时填写 |
| `salary_raw` | TEXT | 默认 `''` | 薪资原文 |
| `education_raw` | TEXT | 默认 `''` | 学历原文 |
| `experience_raw` | TEXT | 默认 `''` | 经验原文 |
| `gender_requirement` | TEXT | 默认 `''` | 性别要求 |
| `age_requirement` | TEXT | 默认 `''` | 年龄要求 |
| `major_requirement` | TEXT | 默认 `''` | 专业要求 |
| `published_at` | TEXT | 默认 `''` | 发布日期 |
| `validity_days` | INTEGER | 可空 | 有效天数 |
| `deadline_at` | TEXT | 默认 `''` | 截止日期 |
| `description` | TEXT | 默认 `''` | 摘要或审核后正文 |
| `requirements` | TEXT | 默认 `''` | 应聘要求 |
| `contact_name` | TEXT | 默认 `''` | 公开联系人，默认不展示 |
| `contact_phone` | TEXT | 默认 `''` | 公开电话，默认不展示 |
| `contact_email` | TEXT | 默认 `''` | 公开邮箱，默认不展示 |
| `company_website` | TEXT | 默认 `''` | 企业网站 |
| `company_industry` | TEXT | 默认 `''` | 行业 |
| `company_size` | TEXT | 默认 `''` | 规模 |
| `company_nature` | TEXT | 默认 `''` | 性质 |
| `company_description` | TEXT | 默认 `''` | 公司介绍摘要 |
| `is_agriculture_related` | INTEGER | 默认 0 | 主题过滤结果 |
| `content_hash` | TEXT | 默认 `''` | 内容哈希 |
| `confidence` | TEXT | 默认 `medium` | 置信度 |
| `publish_status` | TEXT | 默认 `draft` | 发布状态 |
| `fetched_at` | TEXT | 默认 `''` | 采集时间 |
| `first_seen_at` | TEXT | 默认 `''` | 首次发现 |
| `last_seen_at` | TEXT | 默认 `''` | 最近发现 |
| `status` | TEXT | 默认 `active` | `active`、`expired`、`removed`、`blocked` |
| `import_batch_id` | INTEGER | 默认 0 | 批次 |
| `imported_at` | TEXT | 默认 `''` | 导入时间 |
| `extra` | TEXT | 默认 `'{}'` | 附加字段 JSON |

自然键：`(source_id, source_item_id)` 唯一；缺少来源 ID 时使用 `(source_id, source_url)`。

索引：

- `(source_id, published_at)`
- `(province, city, county)`
- `(region)`
- `(is_agriculture_related, publish_status)`
- `(deadline_at)`
- `(content_hash)`
- `(import_batch_id)`

外键：`id` 被 `recruitment_posting_sources.posting_id` 引用。

兼容策略：

- `job_listings` 不变，站内投递、收藏、审核和 `job_applications` 全部保持。
- `recruitments` 不变，现有公告状态计算和求职意向继续读取原表。
- 新岗位通过新增端点或 `source_type=external_posting` 的新响应组暴露，不混入企业岗位数组。
- 前台明确提示“来源站岗位，站内不代办报名”，避免用户误以为可站内投递。

回滚方式：停止新端点，先删来源表再删主表；原招聘 API 不受影响。

## 新增 recruitment_posting_sources

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK AUTOINCREMENT | 主键 |
| `posting_id` | INTEGER | NOT NULL | 招聘岗位 |
| `source_id` | TEXT | NOT NULL | 来源 |
| `source_item_id` | TEXT | 默认 `''` | 来源 ID |
| `source_url` | TEXT | NOT NULL | 详情 URL |
| `is_primary` | INTEGER | 默认 0 | 主来源 |
| `retrieved_at` | TEXT | 默认 `''` | 取得时间 |
| `http_status` | INTEGER | 可空 | 最近 HTTP 状态 |
| `content_hash` | TEXT | 默认 `''` | 内容哈希 |
| `import_batch_id` | INTEGER | 默认 0 | 批次 |
| `extra` | TEXT | 默认 `'{}'` | 附加字段 JSON |

自然键：`(posting_id, source_id, source_url)` 唯一。

索引：`(posting_id)`、`(source_id, source_item_id)`、`(is_primary)`。

外键：`posting_id` 引用 `recruitment_postings.id ON DELETE CASCADE`。

兼容策略：只服务新招聘表，不改 `recruitment_sources`。

回滚方式：先删本表，再删 `recruitment_postings`。

迁移兼容：`province`、`city`、`county` 以新增可空列发布，旧行默认空字符串。转换器只从 `std_jobs.province`、`std_jobs.city`、`std_jobs.location_raw` 升级写入，无法确认的行政区写空值并保留 `location_raw`。索引不得引用不存在的列。

## 新增 dialect_points

用途：承载方言点和调查地区，不替代现有 `dialects`。

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK AUTOINCREMENT | 主键 |
| `source_id` | TEXT | NOT NULL | 来源 |
| `source_item_id` | TEXT | 默认 `''` | 来源点 ID |
| `source_url` | TEXT | 默认 `''` | 详情 URL |
| `region_raw` | TEXT | NOT NULL | 地区原文 |
| `province` | TEXT | 默认 `''` | 省 |
| `city` | TEXT | 默认 `''` | 市 |
| `county` | TEXT | 默认 `''` | 县 |
| `dialect_name` | TEXT | 默认 `''` | 方言名 |
| `point_note` | TEXT | 默认 `''` | 说明 |
| `confidence` | TEXT | 默认 `medium` | 置信度 |
| `publish_status` | TEXT | 默认 `draft` | 发布状态 |
| `content_hash` | TEXT | 默认 `''` | 内容哈希 |
| `fetched_at` | TEXT | 默认 `''` | 采集时间 |
| `import_batch_id` | INTEGER | 默认 0 | 批次 |
| `extra` | TEXT | 默认 `'{}'` | 附加字段 JSON |

自然键：`(source_id, source_item_id)`；缺少来源 ID 时使用 `(region_raw, dialect_name)`。

索引：`(province, city, county)`、`(dialect_name)`、`(region_raw)`、`(publish_status)`。

外键：`id` 被 `dialect_lexemes.dialect_point_id` 引用。

兼容策略：不修改 `dialects`。现有 `/api/resources/dialects` 和 `/api/resources/dialect-info` 继续读取原三张表。

回滚方式：先删词条来源和词条，再删方言点；原方言接口不受影响。

## 新增 dialect_lexemes

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK AUTOINCREMENT | 主键 |
| `dialect_point_id` | INTEGER | NOT NULL | 方言点 |
| `lemma` | TEXT | NOT NULL | 词条或词形 |
| `phonetic` | TEXT | 默认 `''` | 读音、拼音或音标原文 |
| `definition` | TEXT | 默认 `''` | 短释义 |
| `example` | TEXT | 默认 `''` | 例句 |
| `audio_url` | TEXT | 默认 `''` | 可用音频 URL |
| `audio_status` | TEXT | 默认 `unknown` | `available`、`missing`、`invalid`、`unknown` |
| `confidence` | TEXT | 默认 `medium` | 置信度 |
| `publish_status` | TEXT | 默认 `draft` | 发布状态 |
| `content_hash` | TEXT | 默认 `''` | 内容哈希 |
| `fetched_at` | TEXT | 默认 `''` | 采集时间 |
| `import_batch_id` | INTEGER | 默认 0 | 批次 |
| `extra` | TEXT | 默认 `'{}'` | 附加字段 JSON |

自然键：`(dialect_point_id, lemma)`，跨来源差异由来源表保留。

索引：`(dialect_point_id, lemma)`、`(audio_status)`、`(publish_status)`、`(import_batch_id)`。

外键：`dialect_point_id` 引用 `dialect_points.id ON DELETE CASCADE`。

兼容策略：现有 `dialect_phrases` 继续服务前台短语；新词条不自动写入旧表，只有运营明确发布时才生成展示短语。

回滚方式：先删来源关系，再删词条，再删方言点。

## 新增 dialect_lexeme_sources

| 字段 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- |
| `id` | INTEGER | PK AUTOINCREMENT | 主键 |
| `lexeme_id` | INTEGER | NOT NULL | 词条 |
| `source_id` | TEXT | NOT NULL | 来源 |
| `source_item_id` | TEXT | 默认 `''` | 来源记录 ID |
| `source_url` | TEXT | NOT NULL | 详情 URL |
| `is_primary` | INTEGER | 默认 0 | 主来源 |
| `retrieved_at` | TEXT | 默认 `''` | 取得时间 |
| `content_hash` | TEXT | 默认 `''` | 内容哈希 |
| `import_batch_id` | INTEGER | 默认 0 | 批次 |
| `extra` | TEXT | 默认 `'{}'` | 附加字段 JSON |

自然键：`(lexeme_id, source_id, source_item_id, source_url)`。

索引：`(lexeme_id)`、`(source_id, source_item_id)`、`(is_primary)`。

外键：`lexeme_id` 引用 `dialect_lexemes.id ON DELETE CASCADE`。

兼容策略：原 `dialects`、`dialect_phrases`、`dialect_quick_questions` 的读路径和响应结构完全不变。

回滚方式：先删本表，再删词条和方言点。

## 天气

不建表。实时天气只作为运行时 DTO 或短期缓存候选，必须带 `fetched_at` 和 `source_url`。不保存历史天气快照，不用天气表替代气象预警。

## 迁移顺序

建议按以下顺序分开发布：

1. 备份业务库并记录 `schema_migrations` 当前版本。
2. 新增 `agri_certified_products`、`agri_product_sources`。
3. 给 `crafts` 增加采集与分类列。
4. 新增 `recruitment_postings`、`recruitment_posting_sources`。
5. 新增 `dialect_points`、`dialect_lexemes`、`dialect_lexeme_sources`。
6. 建索引和唯一约束。
7. 用转换器导入一批 `draft` 数据，执行人工复核。
8. 切换新增端点或后台筛选，观察错误率和响应形状。
9. 完成审核后逐步发布，不为天气建表。

每一步都应在现有 `schema_migrations` 机制下记录版本，具体脚本由后续实现票据决定。

## 兼容策略汇总

| 现有对象 | 兼容要求 |
| --- | --- |
| `/api/crafts/list` | 字段和顺序不变 |
| `/api/crafts/<id>` | 原有键集不变；新字段需要版本或新端点 |
| `/api/employment/jobs` | 现有 `jobs` 和 `recruitments` 两组不变 |
| `/api/employment/jobs/<id>` | 仍只查企业岗位 |
| `/api/employment/apply` | 只接受 `job_listings.id`，不接受采集岗位 ID |
| `/api/resources/dialects` | 仍读现有 `dialects` |
| `/api/resources/dialect-info` | 仍读现有三张方言表 |
| `/api/agriculture/*` | 农时日历仍读 `farming_products` 和任务表 |

## 回滚方式

| 变更 | 回滚顺序 | 注意 |
| --- | --- | --- |
| 认证农产品 | 停读新端点，先删 `agri_product_sources`，再删 `agri_certified_products` | 保留导出副本 |
| `crafts` 补列 | 停写新列，恢复旧查询；必要时重建表删列 | 保留原主键和关联表 |
| 招聘岗位 | 停用新端点，先删 `recruitment_posting_sources`，再删 `recruitment_postings` | 不影响 `job_listings` |
| 方言规范化 | 停用新端点，按来源表、词条、方言点顺序删除 | 不影响现有三张方言表 |
| 批次导入 | 按 `import_batches` 和 `import_conflicts` 撤销尚未人工修改的结果 | 人工字段保护优先 |

## 对现有 API 的影响

- 本次不改代码，因此短期 API 影响为零。
- 新表上线后先只供转换器、后台和新增查询使用。
- 任何新增响应字段都应新增键或新增端点，不能改变现有键的类型、键序或含义。
- 需要在前端展示的新内容，应先确认分页、筛选和空状态，再接入页面。

## 缺口

- `crafts` 与 `std_ich_projects` 的多来源合并策略仍需以实际导入样本验证。
- `agri_certified_products` 的 `normalized_name` 规则已冻结为去空白、统一全半角和大小写不敏感比较值，仍需用 PDF/XLSX 样本做回归。
- 招聘岗位是否展示公开联系方式需要运营和来源授权共同确认。
- 方言词条发布到现有 `dialect_phrases` 的映射规则未在本次冻结。
- `schema_migrations` 的具体迁移编号由后续实现票据分配。
