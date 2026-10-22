# 采集库 Schema 设计

状态：设计冻结

日期：2026-10-20

适用数据库：`crawler.db`（独立 SQLite）

本文件记录 `crawler/pipeline/database.py` 的实际物理契约。`Physical DDL` 代码块由 `database.SCHEMA` 直接复制，并由 `crawler/tests/test_schema_contract.py` 做逐字符规范化比对。字段类型、列顺序、`UNIQUE`、`CHECK`、外键、索引和视图都以该代码块为准。

## 设计原则

1. raw 追加保存请求和文件证据，不覆盖历史响应。
2. stage 保存来源形状和解析结果，当前实现使用中性 `stage_source_items`。
3. std 保存已归一成跨来源标准字段的候选实体和来源关系。候选状态由独立 `candidate_status` 表达，不复用业务发布状态。
4. 每条带 URL 的记录至少有 `source_url` 和 `long_term_url`。
5. `detail_url_status` 只允许 `direct` 或 `missing`。`direct` 必须有 `detail_url`；`missing` 必须有非空 `long_term_url` 和能定位记录的 `locator`。
6. 没有 direct 详情 URL 的记录可以使用承载页 URL 加 locator 进入候选、业务实体和发布审核。承载页或 locator 不满足条件时写 `deferred`。
7. 关系表与主 std 表使用同一套 URL、locator 和版权列，避免来源关系丢失。
8. 稳定、可筛选的字段使用独立列；`extra` 只保存未建模信息。

## 实际表与自然键

| 层 | 表 | 自然键与边界 |
| --- | --- | --- |
| raw | `raw_fetches` | 一次请求一行，追加保存请求、最终 URL、详情 URL、locator、响应头和响应体元数据。自然键：无，允许同一 URL 多次请求。 |
| raw | `raw_files` | 文件级证据，追加保存文件 URL、承载页 URL、本地路径、字节数和 SHA-256。自然键：无。 |
| stage | `stage_source_items` | 当前唯一 stage 表，按中性来源行保存解析结果。自然键：`(source_id, source_item_id)`，`raw_fetch_id` 指向最近一次证据。来源专属 stage 表仍 deferred。 |
| std | `std_agri_products` | 认证农产品标准实体。物理自然键：`(source_id, source_item_id)`；转换合并键：`(cert_type, normalized_name, province, region)`，跨来源差异由来源关系表保留。 |
| std | `std_agri_product_sources` | 产品来源关系。自然键：`(product_id, source_id, source_url)`，并带完整来源与 locator 证据。 |
| std | `std_agri_product_aliases` | 产品别名关系。自然键：`(product_id, alias, alias_type)`，并带来源证据。 |
| std | `std_ich_projects` | 非遗项目标准实体。自然键：`(source_id, source_item_id)`；`(ich_code, declaration_region, name)` 只作跨来源候选键。 |
| std | `std_ich_inheritors` | 项目传承人关系。自然键：`(project_id, source_id, source_item_id)`，并带完整来源与 locator 证据。 |
| std | `std_ich_related_items` | 非遗项目有向关系。自然键：`(source_id, subject_project_id, related_source_item_id, relation_type)`。 |
| std | `std_ich_media_links` | 项目媒体链接。自然键：`(project_id, media_url)`，并带承载页与来源证据。 |
| std | `std_jobs` | 公开岗位标准实体。自然键：`(source_id, source_item_id)`；缺 ID 时使用 `(source_id, source_url)`。 |
| std | `std_job_sources` | 岗位来源关系。自然键：`(job_id, source_id, source_url)`，并带完整来源与 locator 证据。 |
| std | `std_job_locations` | 岗位地点关系。自然键：`(job_id, province, city, county, location_raw)`，并带来源证据。 |
| std | `std_dialect_points` | 方言点标准实体。自然键：`(source_id, source_item_id)`；地区原文保留用于复核。 |
| std | `std_dialect_lexemes` | 方言词条标准实体。自然键：`(point_id, lemma)`。 |
| std | `std_dialect_lexeme_sources` | 词条来源关系。自然键：`(lexeme_id, source_id, source_item_id, source_url)`，并带完整来源与 locator 证据。 |
| std | `std_ich_articles` | 非遗资讯文章。自然键：`(source_id, source_item_id)`。 |
| std | `std_research_articles` | 公开研究资料。自然键：`(source_id, source_item_id)`；`body_access` 只允许 `public`。 |
| std | `std_sources` | 来源登记。自然键：`source_id`。 |
| service | `import_batches` | 转换批次。自然键：`batch_key`。 |
| service | `import_conflicts` | 字段冲突。自然键：`(batch_id, target_table, target_key, target_field, reason)`。 |
| service | `import_batch_items` | 批次对象映射。自然键：`(batch_id, target_table, target_key)`。 |

`std_agri_products` 的物理唯一键是 `(source_id, source_item_id)`。`std-entities.md` 中的 `(cert_type, normalized_name, province, region)` 是转换器合并键，不是跨来源物理唯一键；同一合并键的不同来源由 `std_agri_product_sources` 保留。

## 表结构索引

### raw_fetches

一次请求一行，追加保存请求、最终 URL、详情 URL、locator、响应头和响应体元数据。自然键：无，允许同一 URL 多次请求。

### raw_files

文件级证据，追加保存文件 URL、承载页 URL、本地路径、字节数和 SHA-256。自然键：无。

### stage_source_items

当前唯一 stage 表，按中性来源行保存解析结果。自然键：`(source_id, source_item_id)`，`raw_fetch_id` 指向最近一次证据。来源专属 stage 表仍 deferred。

从旧版 `UNIQUE(raw_fetch_id, source_item_id)` 升级时，迁移保留每个来源自然键的最大 `id` 行，并把旧 `run_id` 补为 `legacy`。回滚点是迁移前的数据库文件；迁移不删除 raw 证据。

#### std_agri_products

认证农产品标准实体。物理自然键：`(source_id, source_item_id)`；转换合并键：`(cert_type, normalized_name, province, region)`，跨来源差异由来源关系表保留。

#### std_agri_product_sources

产品来源关系。自然键：`(product_id, source_id, source_url)`，并带完整来源与 locator 证据。

#### std_agri_product_aliases

产品别名关系。自然键：`(product_id, alias, alias_type)`，并带来源证据。

#### std_ich_projects

非遗项目标准实体。自然键：`(source_id, source_item_id)`；`(ich_code, declaration_region, name)` 只作跨来源候选键。

#### std_ich_inheritors

项目传承人关系。自然键：`(source_id, source_item_id)`，并带完整来源与 locator 证据。

#### std_ich_related_items

非遗项目有向关系。自然键：`(source_id, subject_project_id, related_source_item_id, relation_type)`。

#### std_ich_media_links

项目媒体链接。自然键：`(project_id, media_url)`，并带承载页与来源证据。

#### std_jobs

公开岗位标准实体。自然键：`(source_id, source_item_id)`；缺 ID 时使用 `(source_id, source_url)`。

#### std_job_sources

岗位来源关系。自然键：`(job_id, source_id, source_url)`，并带完整来源与 locator 证据。

#### std_job_locations

岗位地点关系。自然键：`(job_id, province, city, county, location_raw)`，并带来源证据。

#### std_dialect_points

方言点标准实体。自然键：`(source_id, source_item_id)`；地区原文保留用于复核。

#### std_dialect_lexemes

方言词条标准实体。自然键：`(point_id, lemma)`。

#### std_dialect_lexeme_sources

词条来源关系。自然键：`(lexeme_id, source_id, source_item_id, source_url)`，并带完整来源与 locator 证据。

#### std_ich_articles

非遗资讯文章。自然键：`(source_id, source_item_id)`。

#### std_research_articles

公开研究资料。自然键：`(source_id, source_item_id)`；`body_access` 只允许 `public`。

#### std_sources

来源登记。自然键：`source_id`。

### import_batches

转换批次。自然键：`batch_key`。

### import_conflicts

字段冲突。自然键：`(batch_id, target_table, target_key, target_field, reason)`。

### import_batch_items

批次对象映射。自然键：`(batch_id, target_table, target_key)`。

## Physical DDL

```sql
CREATE TABLE IF NOT EXISTS raw_fetches (
    id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL,
    run_id TEXT NOT NULL DEFAULT 'legacy',
    job_key TEXT,
    request_url TEXT NOT NULL,
    final_url TEXT NOT NULL,
    source_url TEXT NOT NULL,
    long_term_url TEXT NOT NULL,
    detail_url TEXT,
    detail_url_status TEXT NOT NULL DEFAULT 'missing'
        CHECK (detail_url_status IN ('direct', 'missing')),
    fetch_url TEXT,
    locator TEXT,
    request_method TEXT NOT NULL DEFAULT 'GET',
    request_headers TEXT NOT NULL DEFAULT '{}',
    status_code INTEGER,
    content_type TEXT,
    response_headers TEXT NOT NULL DEFAULT '{}',
    body_bytes INTEGER,
    body_sha256 TEXT,
    body_path TEXT,
    body_text TEXT,
    body_saved INTEGER NOT NULL DEFAULT 0,
    access_level TEXT NOT NULL,
    rights_status TEXT NOT NULL,
    attribution_required INTEGER NOT NULL DEFAULT 0,
    attribution_text TEXT,
    rights_evidence_url TEXT,
    robots_decision TEXT,
    fetch_status TEXT NOT NULL,
    error_message TEXT,
    started_at TEXT NOT NULL,
    retrieved_at TEXT,
    duration_ms INTEGER,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    CHECK (length(trim(request_url)) > 0),
    CHECK (length(trim(final_url)) > 0),
    CHECK (length(trim(source_url)) > 0),
    CHECK (length(trim(long_term_url)) > 0),
    CHECK (
        (
            detail_url_status = 'direct'
            AND detail_url IS NOT NULL
            AND length(trim(detail_url)) > 0
        )
        OR (
            detail_url_status = 'missing'
            AND locator IS NOT NULL
            AND length(trim(locator)) > 0
        )
    )
);

CREATE TABLE IF NOT EXISTS raw_files (
    id INTEGER PRIMARY KEY,
    raw_fetch_id INTEGER NOT NULL,
    source_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    long_term_url TEXT NOT NULL,
    detail_url TEXT,
    detail_url_status TEXT NOT NULL
        CHECK (detail_url_status IN ('direct', 'missing')),
    fetch_url TEXT,
    locator TEXT,
    rights_status TEXT NOT NULL,
    attribution_required INTEGER NOT NULL DEFAULT 0,
    attribution_text TEXT,
    rights_evidence_url TEXT,
    file_url TEXT NOT NULL,
    final_url TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    file_ext TEXT,
    byte_size INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    access_level TEXT NOT NULL,
    download_status TEXT NOT NULL,
    oversize_note TEXT,
    media_metadata TEXT NOT NULL DEFAULT '{}',
    retrieved_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    CHECK (length(trim(source_url)) > 0),
    CHECK (length(trim(long_term_url)) > 0),
    CHECK (length(trim(file_url)) > 0),
    CHECK (length(trim(final_url)) > 0),
    CHECK (
        (
            detail_url_status = 'direct'
            AND detail_url IS NOT NULL
            AND length(trim(detail_url)) > 0
        )
        OR (
            detail_url_status = 'missing'
            AND locator IS NOT NULL
            AND length(trim(locator)) > 0
        )
    )
);

CREATE TABLE IF NOT EXISTS stage_source_items (
    id INTEGER PRIMARY KEY,
    raw_fetch_id INTEGER NOT NULL,
    source_id TEXT NOT NULL,
    run_id TEXT NOT NULL DEFAULT 'legacy',
    source_item_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    long_term_url TEXT NOT NULL,
    detail_url TEXT,
    detail_url_status TEXT NOT NULL
        CHECK (detail_url_status IN ('direct', 'missing')),
    fetch_url TEXT,
    locator TEXT,
    rights_status TEXT NOT NULL,
    attribution_required INTEGER NOT NULL DEFAULT 0,
    attribution_text TEXT,
    rights_evidence_url TEXT,
    title TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    parser_version TEXT NOT NULL,
    extra TEXT NOT NULL DEFAULT '{}',
    UNIQUE(source_id, source_item_id),
    CHECK (length(trim(source_url)) > 0),
    CHECK (length(trim(long_term_url)) > 0),
    CHECK (
        (
            detail_url_status = 'direct'
            AND detail_url IS NOT NULL
            AND length(trim(detail_url)) > 0
        )
        OR (
            detail_url_status = 'missing'
            AND locator IS NOT NULL
            AND length(trim(locator)) > 0
        )
    )
);

CREATE VIEW IF NOT EXISTS stage_fixture_items AS
SELECT * FROM stage_source_items;

CREATE TABLE IF NOT EXISTS std_agri_products (
    id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_item_id TEXT NOT NULL,
    run_id TEXT NOT NULL DEFAULT 'legacy',
    source_url TEXT NOT NULL,
    long_term_url TEXT NOT NULL,
    detail_url TEXT,
    detail_url_status TEXT NOT NULL
        CHECK (detail_url_status IN ('direct', 'missing')),
    locator TEXT,
    rights_status TEXT NOT NULL,
    attribution_required INTEGER NOT NULL DEFAULT 0,
    attribution_text TEXT,
    rights_evidence_url TEXT,
    cert_type TEXT NOT NULL,
    product_name TEXT NOT NULL,
    product_name_raw TEXT,
    normalized_name TEXT NOT NULL,
    category TEXT,
    is_aquatic INTEGER,
    province TEXT,
    city TEXT,
    county TEXT,
    region TEXT,
    origin_scope TEXT,
    applicant TEXT,
    protection_unit TEXT,
    certificate_no TEXT,
    certified_at TEXT,
    content_hash TEXT NOT NULL,
    confidence TEXT NOT NULL,
    license_or_usage TEXT NOT NULL,
    publish_status TEXT NOT NULL,
    candidate_status TEXT NOT NULL DEFAULT 'candidate'
        CHECK (candidate_status IN ('candidate', 'blocked', 'deferred')),
    candidate_reason TEXT,
    retrieved_at TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    extra TEXT NOT NULL DEFAULT '{}',
    UNIQUE(source_id, source_item_id),
    CHECK (length(trim(source_url)) > 0),
    CHECK (length(trim(long_term_url)) > 0),
    CHECK (
        (
            detail_url_status = 'direct'
            AND detail_url IS NOT NULL
            AND length(trim(detail_url)) > 0
        )
        OR (
            detail_url_status = 'missing'
            AND locator IS NOT NULL
            AND length(trim(locator)) > 0
        )
    )
);

CREATE TABLE IF NOT EXISTS std_agri_product_sources (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL,
    source_id TEXT NOT NULL,
    source_item_id TEXT,
    source_url TEXT NOT NULL,
    long_term_url TEXT NOT NULL,
    detail_url TEXT,
    detail_url_status TEXT NOT NULL
        CHECK (detail_url_status IN ('direct', 'missing')),
    locator TEXT,
    rights_status TEXT NOT NULL,
    attribution_required INTEGER NOT NULL DEFAULT 0,
    attribution_text TEXT,
    rights_evidence_url TEXT,
    announcement_no TEXT,
    published_at TEXT,
    certified_at TEXT,
    source_product_name TEXT,
    source_region TEXT,
    source_title TEXT,
    is_primary INTEGER NOT NULL DEFAULT 0,
    retrieved_at TEXT NOT NULL,
    content_hash TEXT,
    extra TEXT NOT NULL DEFAULT '{}',
    UNIQUE(product_id, source_id, source_url),
    FOREIGN KEY(product_id) REFERENCES std_agri_products(id),
    CHECK (length(trim(source_url)) > 0),
    CHECK (length(trim(long_term_url)) > 0),
    CHECK (
        (
            detail_url_status = 'direct'
            AND detail_url IS NOT NULL
            AND length(trim(detail_url)) > 0
        )
        OR (
            detail_url_status = 'missing'
            AND locator IS NOT NULL
            AND length(trim(locator)) > 0
        )
    )
);

CREATE TABLE IF NOT EXISTS std_agri_product_aliases (
    id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL,
    alias TEXT NOT NULL,
    alias_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    source_item_id TEXT,
    source_url TEXT NOT NULL,
    long_term_url TEXT NOT NULL,
    detail_url TEXT,
    detail_url_status TEXT NOT NULL
        CHECK (detail_url_status IN ('direct', 'missing')),
    locator TEXT,
    rights_status TEXT NOT NULL,
    attribution_required INTEGER NOT NULL DEFAULT 0,
    attribution_text TEXT,
    rights_evidence_url TEXT,
    confidence TEXT NOT NULL,
    extra TEXT NOT NULL DEFAULT '{}',
    UNIQUE(product_id, alias, alias_type),
    FOREIGN KEY(product_id) REFERENCES std_agri_products(id),
    CHECK (length(trim(source_url)) > 0),
    CHECK (length(trim(long_term_url)) > 0),
    CHECK (
        (
            detail_url_status = 'direct'
            AND detail_url IS NOT NULL
            AND length(trim(detail_url)) > 0
        )
        OR (
            detail_url_status = 'missing'
            AND locator IS NOT NULL
            AND length(trim(locator)) > 0
        )
    )
);

CREATE TABLE IF NOT EXISTS std_ich_projects (
    id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_item_id TEXT NOT NULL,
    run_id TEXT NOT NULL DEFAULT 'legacy',
    source_url TEXT NOT NULL,
    long_term_url TEXT NOT NULL,
    detail_url TEXT,
    detail_url_status TEXT NOT NULL
        CHECK (detail_url_status IN ('direct', 'missing')),
    locator TEXT,
    rights_status TEXT NOT NULL,
    attribution_required INTEGER NOT NULL DEFAULT 0,
    attribution_text TEXT,
    rights_evidence_url TEXT,
    ich_code TEXT,
    name TEXT NOT NULL,
    project_serial TEXT,
    source_project_num TEXT,
    category TEXT,
    project_type TEXT,
    announcement_batch TEXT,
    announcement_year INTEGER,
    declaration_region TEXT,
    protection_unit TEXT,
    province TEXT,
    city TEXT,
    county TEXT,
    description_html TEXT,
    description_text TEXT,
    source_modified_at TEXT,
    content_hash TEXT NOT NULL,
    confidence TEXT NOT NULL,
    license_or_usage TEXT NOT NULL,
    publish_status TEXT NOT NULL,
    candidate_status TEXT NOT NULL DEFAULT 'candidate'
        CHECK (candidate_status IN ('candidate', 'blocked', 'deferred')),
    candidate_reason TEXT,
    retrieved_at TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    extra TEXT NOT NULL DEFAULT '{}',
    UNIQUE(source_id, source_item_id),
    CHECK (length(trim(source_url)) > 0),
    CHECK (length(trim(long_term_url)) > 0),
    CHECK (
        (
            detail_url_status = 'direct'
            AND detail_url IS NOT NULL
            AND length(trim(detail_url)) > 0
        )
        OR (
            detail_url_status = 'missing'
            AND locator IS NOT NULL
            AND length(trim(locator)) > 0
        )
    )
);

CREATE TABLE IF NOT EXISTS std_ich_inheritors (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    source_id TEXT NOT NULL,
    source_item_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    long_term_url TEXT NOT NULL,
    detail_url TEXT,
    detail_url_status TEXT NOT NULL
        CHECK (detail_url_status IN ('direct', 'missing')),
    locator TEXT,
    rights_status TEXT NOT NULL,
    attribution_required INTEGER NOT NULL DEFAULT 0,
    attribution_text TEXT,
    rights_evidence_url TEXT,
    name TEXT NOT NULL,
    gender TEXT,
    birth_date TEXT,
    ethnicity TEXT,
    category TEXT,
    ich_code TEXT,
    project_name TEXT,
    declaration_region TEXT,
    biography_text TEXT,
    retrieved_at TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    confidence TEXT NOT NULL,
    extra TEXT NOT NULL DEFAULT '{}',
    UNIQUE(project_id, source_id, source_item_id),
    FOREIGN KEY(project_id) REFERENCES std_ich_projects(id),
    CHECK (length(trim(source_url)) > 0),
    CHECK (length(trim(long_term_url)) > 0),
    CHECK (
        (
            detail_url_status = 'direct'
            AND detail_url IS NOT NULL
            AND length(trim(detail_url)) > 0
        )
        OR (
            detail_url_status = 'missing'
            AND locator IS NOT NULL
            AND length(trim(locator)) > 0
        )
    )
);

CREATE TABLE IF NOT EXISTS std_ich_related_items (
    id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL,
    subject_project_id INTEGER NOT NULL,
    related_project_id INTEGER,
    related_source_item_id TEXT,
    relation_type TEXT NOT NULL,
    source_url TEXT NOT NULL,
    long_term_url TEXT NOT NULL,
    detail_url TEXT,
    detail_url_status TEXT NOT NULL
        CHECK (detail_url_status IN ('direct', 'missing')),
    locator TEXT,
    rights_status TEXT NOT NULL,
    attribution_required INTEGER NOT NULL DEFAULT 0,
    attribution_text TEXT,
    rights_evidence_url TEXT,
    retrieved_at TEXT NOT NULL,
    content_hash TEXT,
    extra TEXT NOT NULL DEFAULT '{}',
    UNIQUE(
        source_id, subject_project_id, related_source_item_id, relation_type
    ),
    FOREIGN KEY(subject_project_id) REFERENCES std_ich_projects(id),
    FOREIGN KEY(related_project_id) REFERENCES std_ich_projects(id),
    CHECK (length(trim(source_url)) > 0),
    CHECK (length(trim(long_term_url)) > 0),
    CHECK (
        (
            detail_url_status = 'direct'
            AND detail_url IS NOT NULL
            AND length(trim(detail_url)) > 0
        )
        OR (
            detail_url_status = 'missing'
            AND locator IS NOT NULL
            AND length(trim(locator)) > 0
        )
    )
);

CREATE TABLE IF NOT EXISTS std_ich_media_links (
    id INTEGER PRIMARY KEY,
    project_id INTEGER NOT NULL,
    source_id TEXT NOT NULL,
    source_item_id TEXT,
    source_url TEXT NOT NULL,
    long_term_url TEXT NOT NULL,
    detail_url TEXT,
    detail_url_status TEXT NOT NULL
        CHECK (detail_url_status IN ('direct', 'missing')),
    locator TEXT,
    media_url TEXT NOT NULL,
    media_type TEXT,
    availability TEXT NOT NULL DEFAULT 'unknown',
    rights_status TEXT NOT NULL,
    attribution_required INTEGER NOT NULL DEFAULT 0,
    attribution_text TEXT,
    rights_evidence_url TEXT,
    mime_type TEXT,
    byte_size INTEGER,
    sha256 TEXT,
    retrieved_at TEXT NOT NULL,
    extra TEXT NOT NULL DEFAULT '{}',
    UNIQUE(project_id, media_url),
    FOREIGN KEY(project_id) REFERENCES std_ich_projects(id),
    CHECK (length(trim(source_url)) > 0),
    CHECK (length(trim(long_term_url)) > 0),
    CHECK (
        (
            detail_url_status = 'direct'
            AND detail_url IS NOT NULL
            AND length(trim(detail_url)) > 0
        )
        OR (
            detail_url_status = 'missing'
            AND locator IS NOT NULL
            AND length(trim(locator)) > 0
        )
    )
);

CREATE TABLE IF NOT EXISTS std_jobs (
    id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_item_id TEXT NOT NULL,
    run_id TEXT NOT NULL DEFAULT 'legacy',
    source_url TEXT NOT NULL,
    long_term_url TEXT NOT NULL,
    detail_url TEXT,
    detail_url_status TEXT NOT NULL
        CHECK (detail_url_status IN ('direct', 'missing')),
    locator TEXT,
    rights_status TEXT NOT NULL,
    attribution_required INTEGER NOT NULL DEFAULT 0,
    attribution_text TEXT,
    rights_evidence_url TEXT,
    title TEXT NOT NULL,
    title_raw TEXT,
    company_name TEXT,
    company_url TEXT,
    company_industry TEXT,
    company_size TEXT,
    company_nature TEXT,
    location_raw TEXT,
    province TEXT,
    city TEXT,
    employment_type TEXT,
    headcount INTEGER,
    salary_raw TEXT,
    education_raw TEXT,
    experience_raw TEXT,
    gender_requirement TEXT,
    age_requirement TEXT,
    major_requirement TEXT,
    description TEXT,
    requirements TEXT,
    published_at TEXT,
    deadline_at TEXT,
    validity_days INTEGER,
    status_text TEXT,
    content_hash TEXT NOT NULL,
    confidence TEXT NOT NULL,
    license_or_usage TEXT NOT NULL,
    publish_status TEXT NOT NULL,
    candidate_status TEXT NOT NULL DEFAULT 'candidate'
        CHECK (candidate_status IN ('candidate', 'blocked', 'deferred')),
    candidate_reason TEXT,
    retrieved_at TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    extra TEXT NOT NULL DEFAULT '{}',
    UNIQUE(source_id, source_item_id),
    CHECK (length(trim(source_url)) > 0),
    CHECK (length(trim(long_term_url)) > 0),
    CHECK (
        (
            detail_url_status = 'direct'
            AND detail_url IS NOT NULL
            AND length(trim(detail_url)) > 0
        )
        OR (
            detail_url_status = 'missing'
            AND locator IS NOT NULL
            AND length(trim(locator)) > 0
        )
    )
);

CREATE TABLE IF NOT EXISTS std_job_sources (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL,
    source_id TEXT NOT NULL,
    source_item_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    long_term_url TEXT NOT NULL,
    detail_url TEXT,
    detail_url_status TEXT NOT NULL
        CHECK (detail_url_status IN ('direct', 'missing')),
    locator TEXT,
    rights_status TEXT NOT NULL,
    attribution_required INTEGER NOT NULL DEFAULT 0,
    attribution_text TEXT,
    rights_evidence_url TEXT,
    is_primary INTEGER NOT NULL DEFAULT 0,
    retrieved_at TEXT NOT NULL,
    content_hash TEXT,
    extra TEXT NOT NULL DEFAULT '{}',
    UNIQUE(job_id, source_id, source_url),
    FOREIGN KEY(job_id) REFERENCES std_jobs(id),
    CHECK (length(trim(source_url)) > 0),
    CHECK (length(trim(long_term_url)) > 0),
    CHECK (
        (
            detail_url_status = 'direct'
            AND detail_url IS NOT NULL
            AND length(trim(detail_url)) > 0
        )
        OR (
            detail_url_status = 'missing'
            AND locator IS NOT NULL
            AND length(trim(locator)) > 0
        )
    )
);

CREATE TABLE IF NOT EXISTS std_job_locations (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL,
    source_id TEXT NOT NULL,
    source_item_id TEXT,
    source_url TEXT NOT NULL,
    long_term_url TEXT NOT NULL,
    detail_url TEXT,
    detail_url_status TEXT NOT NULL
        CHECK (detail_url_status IN ('direct', 'missing')),
    locator TEXT,
    rights_status TEXT NOT NULL,
    attribution_required INTEGER NOT NULL DEFAULT 0,
    attribution_text TEXT,
    rights_evidence_url TEXT,
    location_raw TEXT,
    province TEXT,
    city TEXT,
    county TEXT,
    is_primary INTEGER NOT NULL DEFAULT 0,
    extra TEXT NOT NULL DEFAULT '{}',
    UNIQUE(job_id, province, city, county, location_raw),
    FOREIGN KEY(job_id) REFERENCES std_jobs(id),
    CHECK (length(trim(source_url)) > 0),
    CHECK (length(trim(long_term_url)) > 0),
    CHECK (
        (
            detail_url_status = 'direct'
            AND detail_url IS NOT NULL
            AND length(trim(detail_url)) > 0
        )
        OR (
            detail_url_status = 'missing'
            AND locator IS NOT NULL
            AND length(trim(locator)) > 0
        )
    )
);

CREATE TABLE IF NOT EXISTS std_dialect_points (
    id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_item_id TEXT NOT NULL,
    run_id TEXT NOT NULL DEFAULT 'legacy',
    source_url TEXT NOT NULL,
    long_term_url TEXT NOT NULL,
    detail_url TEXT,
    detail_url_status TEXT NOT NULL
        CHECK (detail_url_status IN ('direct', 'missing')),
    locator TEXT,
    rights_status TEXT NOT NULL,
    attribution_required INTEGER NOT NULL DEFAULT 0,
    attribution_text TEXT,
    rights_evidence_url TEXT,
    region_raw TEXT NOT NULL,
    province TEXT,
    city TEXT,
    county TEXT,
    dialect_name TEXT,
    point_note TEXT,
    confidence TEXT NOT NULL,
    license_or_usage TEXT NOT NULL,
    publish_status TEXT NOT NULL,
    candidate_status TEXT NOT NULL DEFAULT 'candidate'
        CHECK (candidate_status IN ('candidate', 'blocked', 'deferred')),
    candidate_reason TEXT,
    retrieved_at TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    extra TEXT NOT NULL DEFAULT '{}',
    UNIQUE(source_id, source_item_id),
    CHECK (length(trim(source_url)) > 0),
    CHECK (length(trim(long_term_url)) > 0),
    CHECK (
        (
            detail_url_status = 'direct'
            AND detail_url IS NOT NULL
            AND length(trim(detail_url)) > 0
        )
        OR (
            detail_url_status = 'missing'
            AND locator IS NOT NULL
            AND length(trim(locator)) > 0
        )
    )
);

CREATE TABLE IF NOT EXISTS std_dialect_lexemes (
    id INTEGER PRIMARY KEY,
    point_id INTEGER NOT NULL,
    source_id TEXT NOT NULL,
    source_item_id TEXT NOT NULL,
    run_id TEXT NOT NULL DEFAULT 'legacy',
    source_url TEXT NOT NULL,
    long_term_url TEXT NOT NULL,
    detail_url TEXT,
    detail_url_status TEXT NOT NULL DEFAULT 'missing'
        CHECK (detail_url_status IN ('direct', 'missing')),
    fetch_url TEXT,
    locator TEXT,
    lemma TEXT NOT NULL,
    phonetic TEXT,
    definition TEXT,
    example TEXT,
    audio_url TEXT,
    audio_status TEXT NOT NULL,
    rights_status TEXT NOT NULL,
    attribution_required INTEGER NOT NULL DEFAULT 0,
    attribution_text TEXT,
    rights_evidence_url TEXT,
    confidence TEXT NOT NULL,
    license_or_usage TEXT NOT NULL,
    publish_status TEXT NOT NULL,
    candidate_status TEXT NOT NULL DEFAULT 'candidate'
        CHECK (candidate_status IN ('candidate', 'blocked', 'deferred')),
    candidate_reason TEXT,
    retrieved_at TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    extra TEXT NOT NULL DEFAULT '{}',
    UNIQUE(point_id, lemma),
    FOREIGN KEY(point_id) REFERENCES std_dialect_points(id),
    CHECK (length(trim(source_url)) > 0),
    CHECK (length(trim(long_term_url)) > 0),
    CHECK (
        (
            detail_url_status = 'direct'
            AND detail_url IS NOT NULL
            AND length(trim(detail_url)) > 0
        )
        OR (
            detail_url_status = 'missing'
            AND locator IS NOT NULL
            AND length(trim(locator)) > 0
        )
    )
);

CREATE TABLE IF NOT EXISTS std_dialect_lexeme_sources (
    id INTEGER PRIMARY KEY,
    lexeme_id INTEGER NOT NULL,
    source_id TEXT NOT NULL,
    source_item_id TEXT NOT NULL,
    source_url TEXT NOT NULL,
    long_term_url TEXT NOT NULL,
    detail_url TEXT,
    detail_url_status TEXT NOT NULL DEFAULT 'missing'
        CHECK (detail_url_status IN ('direct', 'missing')),
    fetch_url TEXT,
    locator TEXT,
    rights_status TEXT NOT NULL,
    attribution_required INTEGER NOT NULL DEFAULT 0,
    attribution_text TEXT,
    rights_evidence_url TEXT,
    is_primary INTEGER NOT NULL DEFAULT 0,
    retrieved_at TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    extra TEXT NOT NULL DEFAULT '{}',
    UNIQUE(lexeme_id, source_id, source_item_id, source_url),
    FOREIGN KEY(lexeme_id) REFERENCES std_dialect_lexemes(id),
    CHECK (length(trim(source_url)) > 0),
    CHECK (length(trim(long_term_url)) > 0),
    CHECK (
        (
            detail_url_status = 'direct'
            AND detail_url IS NOT NULL
            AND length(trim(detail_url)) > 0
        )
        OR (
            detail_url_status = 'missing'
            AND locator IS NOT NULL
            AND length(trim(locator)) > 0
        )
    )
);

CREATE TABLE IF NOT EXISTS std_ich_articles (
    id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_item_id TEXT NOT NULL,
    run_id TEXT NOT NULL DEFAULT 'legacy',
    source_url TEXT NOT NULL,
    long_term_url TEXT NOT NULL,
    detail_url TEXT,
    detail_url_status TEXT NOT NULL
        CHECK (detail_url_status IN ('direct', 'missing')),
    locator TEXT,
    rights_status TEXT NOT NULL,
    attribution_required INTEGER NOT NULL DEFAULT 0,
    attribution_text TEXT,
    rights_evidence_url TEXT,
    title TEXT NOT NULL,
    published_at TEXT,
    body_text TEXT,
    content_hash TEXT NOT NULL,
    confidence TEXT NOT NULL,
    license_or_usage TEXT NOT NULL,
    publish_status TEXT NOT NULL,
    candidate_status TEXT NOT NULL DEFAULT 'candidate'
        CHECK (candidate_status IN ('candidate', 'blocked', 'deferred')),
    candidate_reason TEXT,
    retrieved_at TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    extra TEXT NOT NULL DEFAULT '{}',
    UNIQUE(source_id, source_item_id),
    CHECK (length(trim(source_url)) > 0),
    CHECK (length(trim(long_term_url)) > 0),
    CHECK (
        (
            detail_url_status = 'direct'
            AND detail_url IS NOT NULL
            AND length(trim(detail_url)) > 0
        )
        OR (
            detail_url_status = 'missing'
            AND locator IS NOT NULL
            AND length(trim(locator)) > 0
        )
    )
);

CREATE TABLE IF NOT EXISTS std_research_articles (
    id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL,
    source_item_id TEXT NOT NULL,
    run_id TEXT NOT NULL DEFAULT 'legacy',
    source_url TEXT NOT NULL,
    long_term_url TEXT NOT NULL,
    detail_url TEXT,
    detail_url_status TEXT NOT NULL
        CHECK (detail_url_status IN ('direct', 'missing')),
    locator TEXT,
    rights_status TEXT NOT NULL,
    attribution_required INTEGER NOT NULL DEFAULT 0,
    attribution_text TEXT,
    rights_evidence_url TEXT,
    title TEXT NOT NULL,
    summary TEXT,
    published_at TEXT,
    body_text TEXT,
    body_access TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    confidence TEXT NOT NULL,
    license_or_usage TEXT NOT NULL,
    publish_status TEXT NOT NULL,
    candidate_status TEXT NOT NULL DEFAULT 'candidate'
        CHECK (candidate_status IN ('candidate', 'blocked', 'deferred')),
    candidate_reason TEXT,
    retrieved_at TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    extra TEXT NOT NULL DEFAULT '{}',
    UNIQUE(source_id, source_item_id),
    CHECK (length(trim(source_url)) > 0),
    CHECK (length(trim(long_term_url)) > 0),
    CHECK (body_access = 'public'),
    CHECK (
        (
            detail_url_status = 'direct'
            AND detail_url IS NOT NULL
            AND length(trim(detail_url)) > 0
        )
        OR (
            detail_url_status = 'missing'
            AND locator IS NOT NULL
            AND length(trim(locator)) > 0
        )
    )
);

CREATE TABLE IF NOT EXISTS std_sources (
    id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    domains TEXT NOT NULL DEFAULT '[]',
    content_domains TEXT NOT NULL DEFAULT '[]',
    priority TEXT NOT NULL,
    status TEXT NOT NULL,
    access_level TEXT NOT NULL,
    rights_status TEXT NOT NULL,
    license_or_usage TEXT NOT NULL,
    confidence TEXT NOT NULL,
    document_path TEXT,
    review_path TEXT,
    verified_at TEXT,
    is_enabled INTEGER NOT NULL DEFAULT 1,
    extra TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS import_batches (
    id INTEGER PRIMARY KEY,
    batch_key TEXT NOT NULL UNIQUE,
    source_id TEXT,
    content_domain TEXT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    input_count INTEGER NOT NULL DEFAULT 0,
    inserted_count INTEGER NOT NULL DEFAULT 0,
    updated_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    conflict_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    target_database TEXT NOT NULL DEFAULT 'yuexiang',
    converter_version TEXT NOT NULL,
    rollback_note TEXT,
    extra TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS import_conflicts (
    id INTEGER PRIMARY KEY,
    batch_id INTEGER NOT NULL,
    content_domain TEXT NOT NULL,
    target_table TEXT NOT NULL,
    target_key TEXT NOT NULL,
    target_field TEXT NOT NULL,
    existing_value TEXT,
    incoming_value TEXT,
    existing_source_id TEXT,
    existing_source_url TEXT,
    incoming_source_id TEXT,
    incoming_source_url TEXT,
    existing_retrieved_at TEXT,
    incoming_retrieved_at TEXT,
    reason TEXT NOT NULL,
    resolution TEXT NOT NULL DEFAULT 'unresolved',
    resolved_by TEXT,
    resolved_at TEXT,
    resolution_note TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(batch_id, target_table, target_key, target_field, reason),
    FOREIGN KEY(batch_id) REFERENCES import_batches(id)
);

CREATE TABLE IF NOT EXISTS import_batch_items (
    id INTEGER PRIMARY KEY,
    batch_id INTEGER NOT NULL,
    content_domain TEXT NOT NULL,
    target_table TEXT NOT NULL,
    target_key TEXT NOT NULL,
    operation TEXT NOT NULL,
    status TEXT NOT NULL,
    source_id TEXT,
    source_item_id TEXT,
    content_hash TEXT,
    created_at TEXT NOT NULL,
    extra TEXT NOT NULL DEFAULT '{}',
    UNIQUE(batch_id, target_table, target_key),
    FOREIGN KEY(batch_id) REFERENCES import_batches(id)
);

CREATE INDEX IF NOT EXISTS idx_raw_fetches_source_time
    ON raw_fetches(source_id, retrieved_at);
CREATE INDEX IF NOT EXISTS idx_raw_fetches_status_time
    ON raw_fetches(fetch_status, started_at);
CREATE INDEX IF NOT EXISTS idx_raw_files_sha256 ON raw_files(sha256);
CREATE INDEX IF NOT EXISTS idx_stage_source_items_source
    ON stage_source_items(source_id, source_item_id);
CREATE INDEX IF NOT EXISTS idx_std_sources_enabled
    ON std_sources(is_enabled, priority);
CREATE INDEX IF NOT EXISTS idx_import_conflicts_resolution
    ON import_conflicts(resolution, created_at);
```

## 关系与发布边界

- `std_agri_product_sources`、`std_agri_product_aliases`、`std_ich_inheritors`、`std_ich_related_items`、`std_ich_media_links`、`std_job_sources`、`std_job_locations`、`std_dialect_lexeme_sources` 都带 `source_url`、`long_term_url`、`detail_url`、`detail_url_status`、`locator` 和版权列。
- 关系表的 `CHECK` 与主 std 表相同，直接 SQL 写入不能绕过 direct/missing 和 locator 规则。
- `std_research_articles.body_access` 只允许 `public`；登录后语料不写入。
- `std_sources` 由 `sources.json` 幂等播种；转换器和发布门禁读取同一来源登记。
- 当前没有 source-shaped stage 表。需要来源专属可查询列时，先更新本文件和 `database.py`，再迁移。

## 索引与查询边界

- 调度和失败排查使用 `raw_fetches(source_id, fetch_status, started_at)`。
- 证据去重使用 `raw_fetches(body_sha256)` 和 `raw_files(sha256)`。
- std 幂等写入使用各表的物理唯一键。
- 冲突复核使用 `import_conflicts(resolution, created_at)`。
