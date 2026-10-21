# 标准实体 Module Interface

状态: 设计冻结

日期: 2026-10-19

`std` 是采集库中的跨来源候选标准实体层，不是来源列的投影，也不是业务发布层。每个实体有稳定 identity、自然键、来源关系、候选状态和不变式。转换器只读这里定义的实体，不读 raw 或 stage。

`publish_status` 是历史命名字段，保留在物理表中用于兼容现有转换器和业务写入流程。判断采集准入必须读取 `candidate_status`，不能把 `publish_status` 当作候选状态。`candidate_status` 固定为 `candidate`、`deferred`、`blocked`。

## 公共 Interface

所有 std 实体共享以下能力:

| 能力 | 说明 |
| --- | --- |
| `identity` | 实体内部 ID，由采集库分配，不对业务暴露 |
| `natural_key` | 识别同一实体的规范化字段组合 |
| `provenance` | 主来源和全部来源关系，能回到详情 URL、承载页 URL、locator 和取得时间 |
| `candidate_status` | `candidate`、`deferred`、`blocked`，表示采集侧是否可进入转换器 |
| `candidate_reason` | 候选状态的原因，例如 `robots:not-found`、`detail_url:missing` |
| `publish_status` | 历史命名的兼容字段，不用于采集候选判断 |
| `confidence` | `high`、`medium`、`low` |
| `content_hash` | 规范化内容哈希，用于变更检测 |
| `first_seen_at`、`last_seen_at` | 首次和最近发现时间 |
| `is_active` | 来源是否仍可见 |

公共不变式:

- 实体行不能只有 JSON 来源信息，必须有 `source_id` 和具体来源关系。
- 主实体和关系实体都必须有 `source_url`、`long_term_url`、`detail_url_status` 和 `locator` 证据列；`missing` 行的 `long_term_url` 和 `locator` 都不得为空。
- `detail_url_status=missing` 的记录可以使用承载页 URL 加 locator 进入候选、业务实体和发布审核。承载页为空、locator 为空或无法定位记录时，`candidate_status` 必须为 `deferred`。
- `candidate_status=deferred` 表示数据完整但当前暂不转换或发布，不是解析失败。`blocked` 只用于数据不完整、权利不明、访问禁止或其他真实阻断。
- 会参与自然键、筛选或发布的字段必须是独立列。
- 来源改名或页面改版不能改变内部 ID。
- 失效实体标记 `is_active=0`，不物理删除。
- 采集候选状态只由采集侧准入决定。业务发布状态只能由转换器和审核流程推进。

## 非遗实体

### `std_ich_projects`

Interface:

```text
identity: integer
natural_key: (project_id, source_id, source_item_id)
candidate_key: (ich_code, declaration_region, name)
source_relation: primary source_id + source_url
records: inheritors, related_items, media_links
publish: draft | reviewed | published | blocked
```

关键字段: `source_id`、`source_item_id`、`source_url`、`long_term_url`、`detail_url`、`detail_url_status`、`locator`、`rights_status`、`attribution_required`、`attribution_text`、`rights_evidence_url`、`ich_code`、`name`、`project_serial`、`source_project_num`、`category`、`project_type`、`announcement_batch`、`announcement_year`、`declaration_region`、`protection_unit`、`province`、`city`、`county`、`description_html`、`description_text`、`source_modified_at`、`retrieved_at`、`content_hash`、`confidence`、`license_or_usage`、`publish_status`、`first_seen_at`、`last_seen_at`、`is_active`、`extra`。

不变式:

- 3610 是子项口径，同一项目名可有多条。
- `source_item_id` 来自详情 ID，不混用 `project_serial`、`ich_code`、`source_project_num`。
- 跨来源合并只按候选键评审，不强制唯一。
- 没有教学证据的实体仍可浏览，但 `is_teachable` 不在此层自动置真。

### `std_ich_inheritors`

Interface:

```text
identity: integer
natural_key: (source_id, source_item_id)
relation: project_id -> std_ich_projects.id
publish: source metadata only
```

关键字段: `project_id`、`source_id`、`source_item_id`、`source_url`、`long_term_url`、`detail_url`、`detail_url_status`、`locator`、`rights_status`、`attribution_required`、`attribution_text`、`rights_evidence_url`、`name`、`gender`、`birth_date`、`ethnicity`、`category`、`ich_code`、`project_name`、`declaration_region`、`biography_text`、`retrieved_at`、`content_hash`、`confidence`、`extra`。

不变式: 同一人关联多个项目时保留多条关系，不压缩成一个跨项目人物。

### `std_ich_related_items`

Interface:

```text
identity: integer
natural_key: (source_id, subject_project_id, related_source_item_id, relation_type)
relation: subject_project_id, related_project_id -> std_ich_projects.id
```

关键字段: `source_id`、`subject_project_id`、`related_project_id`、`related_source_item_id`、`relation_type`、`source_url`、`long_term_url`、`detail_url`、`detail_url_status`、`locator`、`rights_status`、`attribution_required`、`attribution_text`、`rights_evidence_url`、`retrieved_at`、`content_hash`、`extra`。

不变式: 关系有方向；资讯和学术只是关系类型，不在本层伪装成项目。

### `std_ich_media_links`

Interface:

```text
identity: integer
natural_key: (project_id, media_url)
availability: available | missing | invalid | unknown
```

关键字段: `source_id`、`source_item_id`、`source_url`、`long_term_url`、`detail_url`、`detail_url_status`、`locator`、`rights_status`、`attribution_required`、`attribution_text`、`rights_evidence_url`、`media_url`、`media_type`、`availability`、`mime_type`、`byte_size`、`sha256`、`retrieved_at`、`extra`。

不变式: 只保存链接和元数据，不把媒体文件复制进业务库。

## 认证农产品实体

### `std_agri_products`

Interface:

```text
identity: integer
natural_key: (source_id, source_item_id)
merge_key: (cert_type, normalized_name, province, region)
source_relation: std_agri_product_sources
publish: draft | reviewed | published | blocked
```

关键字段: `source_id`、`source_item_id`、`source_url`、`long_term_url`、`detail_url`、`detail_url_status`、`locator`、`rights_status`、`attribution_required`、`attribution_text`、`rights_evidence_url`、`cert_type`、`product_name`、`product_name_raw`、`normalized_name`、`category`、`is_aquatic`、`province`、`city`、`county`、`region`、`origin_scope`、`applicant`、`protection_unit`、`certificate_no`、`certified_at`、`content_hash`、`confidence`、`license_or_usage`、`publish_status`、`retrieved_at`、`first_seen_at`、`last_seen_at`、`is_active`、`extra`。

自然键回退:

- `region` 为空时使用 `origin_scope` 的稳定摘要。
- `region` 和 `origin_scope` 都为空时进入冲突或人工复核，不与同省产品合并。
- `cert_type` 永不跨类型合并。

水产三态:

- `is_aquatic=1`: 有官方品类、产品名或申请主体证据，并经规则或人工确认。
- `is_aquatic=0`: 有证据表明不是水产。
- `is_aquatic=NULL`: 证据不足或存在误报风险。

误报复核: `鲅鱼圈鸡蛋`、`安溪毛蟹`、`仪征紫菜薹`、贝母、丹参、鱼腥草、螺丝椒等仅命中关键词时不得标记为水产。人工复核结论写入 `extra.review`，保留复核人、时间和证据。

不变式:

- 物理唯一键是来源记录 `(source_id, source_item_id)`；`merge_key` 只用于转换器把同产品跨来源分组，不强制跨来源行合并。
- 无 direct 详情 URL 的记录使用承载页 URL 和 locator 进入 std。承载页或 locator 不满足条件时写 `candidate_status=deferred`，不进入转换器和业务发布。满足权利和审核条件时，这类记录可以发布。
- `normalized_name` 由可复现规则生成，原始名称保留在 `product_name_raw`。
- 地理标志 PDF 签名 URL 只留在 raw 层。

### `std_agri_product_sources`

Interface:

```text
identity: integer
natural_key: (product_id, source_id, source_url)
product: product_id -> std_agri_products.id
```

关键字段: `source_url`、`long_term_url`、`detail_url`、`detail_url_status`、`locator`、`rights_status`、`attribution_required`、`attribution_text`、`rights_evidence_url`、`announcement_no`、`published_at`、`certified_at`、`source_product_name`、`source_region`、`source_title`、`is_primary`、`retrieved_at`、`content_hash`、`extra`。

不变式: 同一产品多次公告保留多条来源；附件行级证据放 `locator`、`extra` 或 stage，不挤进主表字段。

### `std_agri_product_aliases`

Interface:

```text
identity: integer
natural_key: (product_id, alias, alias_type)
alias_type: raw | abbreviation | former | typo
```

关键字段: `source_id`、`source_item_id`、`source_url`、`long_term_url`、`detail_url`、`detail_url_status`、`locator`、`rights_status`、`attribution_required`、`attribution_text`、`rights_evidence_url`、`alias`、`alias_type`、`confidence`、`extra`。

不变式: 别名只辅助匹配，不替代主自然键。

## 招聘实体

### `std_jobs`

Interface:

```text
identity: integer
natural_key: (source_id, source_item_id)
fallback_key: (source_id, source_url)
source_relation: std_job_sources
location_relation: std_job_locations
publish: draft | reviewed | published | blocked
```

关键字段: `source_id`、`source_item_id`、`source_url`、`long_term_url`、`detail_url`、`detail_url_status`、`locator`、`rights_status`、`attribution_required`、`attribution_text`、`rights_evidence_url`、`title`、`title_raw`、`company_name`、`company_url`、`company_industry`、`company_size`、`company_nature`、`location_raw`、`province`、`city`、`employment_type`、`headcount`、`salary_raw`、`education_raw`、`experience_raw`、`gender_requirement`、`age_requirement`、`major_requirement`、`description`、`requirements`、`published_at`、`deadline_at`、`validity_days`、`status_text`、`content_hash`、`confidence`、`license_or_usage`、`publish_status`、`retrieved_at`、`first_seen_at`、`last_seen_at`、`is_active`、`extra`。

不变式:

- 只承载公开岗位，不承载简历、求职者或个人隐私。
- 过期岗位标记失效，不物理删除。
- 业务目标固定为 `recruitment_postings`，不写 `job_listings` 或 `recruitments`。

### `std_job_sources`

Interface:

```text
identity: integer
natural_key: (job_id, source_id, source_url)
```

关键字段: `source_url`、`long_term_url`、`detail_url`、`detail_url_status`、`locator`、`rights_status`、`attribution_required`、`attribution_text`、`rights_evidence_url`、`source_item_id`、`is_primary`、`retrieved_at`、`content_hash`、`extra`。

### `std_job_locations`

Interface:

```text
identity: integer
natural_key: (job_id, province, city, county, location_raw)
```

关键字段: `source_id`、`source_item_id`、`source_url`、`long_term_url`、`detail_url`、`detail_url_status`、`locator`、`rights_status`、`attribution_required`、`attribution_text`、`rights_evidence_url`、`location_raw`、`province`、`city`、`county`、`is_primary`、`extra`。

不变式: 一个岗位可有多个工作地点，主地点由 `is_primary` 标记。

## 方言实体

### `std_dialect_points`

Interface:

```text
identity: integer
natural_key: (source_id, source_item_id)
fallback_key: (region_raw, dialect_name)
source_url: detail URL when available
publish: draft | reviewed | published | blocked
```

关键字段: `source_id`、`source_item_id`、`source_url`、`long_term_url`、`detail_url`、`detail_url_status`、`locator`、`rights_status`、`attribution_required`、`attribution_text`、`rights_evidence_url`、`region_raw`、`province`、`city`、`county`、`dialect_name`、`point_note`、`confidence`、`retrieved_at`、`content_hash`、`extra`。

不变式: `dialect.org.cn` 的 `/dialect/{id}` 是词条详情，不是独立方言点；地区归一失败时保留原文并进入复核。

### `std_dialect_lexemes`

Interface:

```text
identity: integer
natural_key: (point_id, lemma)
point: point_id -> std_dialect_points.id
audio: available | missing | invalid | unknown
publish: draft | reviewed | published | blocked
```

关键字段: `source_id`、`source_item_id`、`source_url`、`long_term_url`、`detail_url`、`detail_url_status`、`fetch_url`、`locator`、`rights_status`、`attribution_required`、`attribution_text`、`rights_evidence_url`、`phonetic`、`definition`、`example`、`audio_url`、`audio_status`、`confidence`、`content_hash`、`retrieved_at`、`extra`。

不变式: 同一词形在不同方言点不合并；来源差异由 `std_dialect_lexeme_sources` 保留。

### `std_dialect_lexeme_sources`

Interface:

```text
identity: integer
natural_key: (lexeme_id, source_id, source_item_id, source_url)
```

关键字段: `source_url`、`long_term_url`、`detail_url`、`detail_url_status`、`fetch_url`、`locator`、`rights_status`、`attribution_required`、`attribution_text`、`rights_evidence_url`、`is_primary`、`retrieved_at`、`content_hash`、`extra`。来源记录 ID 字段统一为 `source_item_id`。

## 非遗资讯实体

`std_ich_articles` 是已冻结的补充资讯实体，承载 `feiyiw` 和 `ihchina` 的非遗资讯与文章元数据。它不是非遗项目实体，不能直接覆盖 `std_ich_projects` 或 `crafts` 的项目事实。

### `std_ich_articles`

```text
identity: integer
natural_key: (source_id, source_item_id)
source_url: article detail URL
publish: draft | reviewed | published | blocked
```

关键字段: `source_id`、`source_item_id`、`source_url`、`long_term_url`、`detail_url`、`detail_url_status`、`locator`、`rights_status`、`attribution_required`、`attribution_text`、`rights_evidence_url`、`title`、`published_at`、`body_text`、`content_hash`、`confidence`、`license_or_usage`、`publish_status`、`retrieved_at`、`first_seen_at`、`last_seen_at`、`extra`。

不变式: 资讯不是非遗项目，不能直接覆盖 `crafts.history`；只有人工核验后的项目事实才可进入项目实体。

## 研究资料实体

### `std_research_articles`

`std_research_articles` 是已冻结的公开研究资料实体，承载 `cass-linguistics` 的公开文章元数据、摘要和正文快照。它不进入方言词条转换，也不代表论文或期刊全文再发布授权。

```text
identity: integer
natural_key: (source_id, source_item_id)
source_url: public article detail URL
publish: draft | reviewed | published | blocked
```

关键字段: `source_id`、`source_item_id`、`source_url`、`long_term_url`、`detail_url`、`detail_url_status`、`locator`、`rights_status`、`attribution_required`、`attribution_text`、`rights_evidence_url`、`title`、`summary`、`published_at`、`body_text`、`body_access`、`content_hash`、`confidence`、`license_or_usage`、`publish_status`、`retrieved_at`、`first_seen_at`、`last_seen_at`、`extra`。

不变式: 只保存公开可访问页面；`body_access` 必须为 `public`；登录后语料不得写入；研究资讯不得转换为方言词条或论文全文业务发布。

`std_research_sources` 和 `std_research_resources` 仍是建议新增、尚未冻结的实体。它们不进入运行时写入路径或转换器输入。

```text
std_research_sources: article_id + source_id + media
std_research_resources: (source_id, source_item_id), title, item_count, external_url, access
```

不变式: 外部登录平台只记录 URL 和访问等级，不采集登录后数据。

## 公共来源与服务

`std_sources`、`import_batches`、`import_conflicts` 的字段和索引见 `crawler-db.md`。`std_sources` 是转换期来源元数据，提供来源优先级、`access_level`、`license_or_usage`、版权状态和启用状态。

## 与转换器的关系

转换器按 `conversion-interface.md` 调用 `run_batch(domain, batch)`。这个 interface 承诺自然键、来源优先、人工保护、冲突、发布、回滚和统计由 module 内部统一处理。mapping 文件只说明来源字段落到哪个 std 字段和业务 `target_field`，不重复本文件字段定义。
