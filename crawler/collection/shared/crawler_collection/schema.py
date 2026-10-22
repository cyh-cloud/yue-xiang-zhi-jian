"""Frozen crawler database DDL shared by collection and conversion."""

SCHEMA = """
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
"""


RUN_ID_COLUMNS = (
    "raw_fetches",
    "stage_source_items",
    "std_agri_products",
    "std_ich_projects",
    "std_jobs",
    "std_dialect_points",
    "std_dialect_lexemes",
    "std_ich_articles",
    "std_research_articles",
)


def ensure_schema(conn):
    """Create the collection schema and migrate the stage natural key."""
    conn.executescript(SCHEMA)
    _ensure_run_id_columns(conn)
    _migrate_stage_natural_key(conn)
    _migrate_ich_inheritor_natural_key(conn)


def _ensure_run_id_columns(conn):
    for table in RUN_ID_COLUMNS:
        columns = {
            row[1]
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if "run_id" not in columns:
            conn.execute(
                f"ALTER TABLE {table} ADD COLUMN run_id TEXT "
                "NOT NULL DEFAULT 'legacy'"
            )


def _migrate_stage_natural_key(conn):
    """Replace the old raw-fetch-scoped stage key without losing rows.

    Rollback: before running this migration on a production copy, retain the
    pre-migration database file. The old key was
    UNIQUE(raw_fetch_id, source_item_id); after migration the surviving row
    per source item is the highest-id row, so the previous file is the
    complete rollback point.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master "
        "WHERE type = 'table' AND name = 'stage_source_items'"
    ).fetchone()
    if row is None or "UNIQUE(raw_fetch_id, source_item_id)" not in row[0]:
        return

    conn.execute("DROP VIEW IF EXISTS stage_fixture_items")
    conn.execute(
        "ALTER TABLE stage_source_items RENAME TO stage_source_items_legacy"
    )
    conn.executescript(SCHEMA)
    conn.execute(
        """
        INSERT INTO stage_source_items (
            id, raw_fetch_id, source_id, run_id, source_item_id, source_url,
            long_term_url, detail_url, detail_url_status, fetch_url, locator,
            rights_status, attribution_required, attribution_text,
            rights_evidence_url, title, retrieved_at, content_hash,
            parser_version, extra
        )
        SELECT
            id, raw_fetch_id, source_id,
            COALESCE(run_id, 'legacy'),
            source_item_id, source_url, long_term_url, detail_url,
            detail_url_status, fetch_url, locator, rights_status,
            attribution_required, attribution_text, rights_evidence_url,
            title, retrieved_at, content_hash, parser_version, extra
        FROM stage_source_items_legacy
        WHERE id IN (
            SELECT MAX(id)
            FROM stage_source_items_legacy
            GROUP BY source_id, source_item_id
        )
        """
    )
    conn.execute("DROP TABLE stage_source_items_legacy")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_stage_source_items_source "
        "ON stage_source_items(source_id, source_item_id)"
    )


def _migrate_ich_inheritor_natural_key(conn):
    """Allow one inheritor identity to relate to multiple projects."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master "
        "WHERE type = 'table' AND name = 'std_ich_inheritors'"
    ).fetchone()
    if row is None or "UNIQUE(source_id, source_item_id)" not in row[0]:
        return

    conn.execute(
        "ALTER TABLE std_ich_inheritors "
        "RENAME TO std_ich_inheritors_legacy"
    )
    conn.executescript(SCHEMA)
    conn.execute(
        """
        INSERT INTO std_ich_inheritors (
            id, project_id, source_id, source_item_id, source_url,
            long_term_url, detail_url, detail_url_status, locator,
            rights_status, attribution_required, attribution_text,
            rights_evidence_url, name, gender, birth_date, ethnicity,
            category, ich_code, project_name, declaration_region,
            biography_text, retrieved_at, content_hash, confidence, extra
        )
        SELECT
            id, project_id, source_id, source_item_id, source_url,
            long_term_url, detail_url, detail_url_status, locator,
            rights_status, attribution_required, attribution_text,
            rights_evidence_url, name, gender, birth_date, ethnicity,
            category, ich_code, project_name, declaration_region,
            biography_text, retrieved_at, content_hash, confidence, extra
        FROM std_ich_inheritors_legacy
        """
    )
    conn.execute("DROP TABLE std_ich_inheritors_legacy")
