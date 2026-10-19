import hashlib
import json
import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS raw_fetches (
    id INTEGER PRIMARY KEY,
    source_id TEXT NOT NULL,
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
    CHECK (
        detail_url_status = 'direct'
        OR (locator IS NOT NULL AND length(trim(locator)) > 0)
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
    CHECK (
        detail_url_status = 'direct'
        OR (locator IS NOT NULL AND length(trim(locator)) > 0)
    )
);

CREATE TABLE IF NOT EXISTS stage_source_items (
    id INTEGER PRIMARY KEY,
    raw_fetch_id INTEGER NOT NULL,
    source_id TEXT NOT NULL,
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
    UNIQUE(raw_fetch_id, source_item_id),
    CHECK (
        detail_url_status = 'direct'
        OR (locator IS NOT NULL AND length(trim(locator)) > 0)
    )
);

CREATE VIEW IF NOT EXISTS stage_fixture_items AS
SELECT * FROM stage_source_items;

CREATE TABLE IF NOT EXISTS std_agri_products (
    id INTEGER PRIMARY KEY,
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
    UNIQUE(source_id, source_item_id),
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


def connect(path, *, seed_sources=True):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    _ensure_columns(conn)
    _migrate_raw_files_append_only(conn)
    if seed_sources:
        seed_std_sources(conn)
    return conn


def _ensure_columns(conn):
    """Add contract columns to databases created by earlier crawler versions."""
    migrations = {
        "raw_fetches": {
            "locator": "TEXT",
            "body_path": "TEXT",
            "body_text": "TEXT",
            "body_saved": "INTEGER NOT NULL DEFAULT 0",
            "response_headers": "TEXT NOT NULL DEFAULT '{}'",
            "request_headers": "TEXT NOT NULL DEFAULT '{}'",
            "robots_decision": "TEXT",
            "duration_ms": "INTEGER",
            "rights_status": "TEXT NOT NULL DEFAULT 'unknown'",
        },
        "raw_files": {
            "file_url": "TEXT",
            "final_url": "TEXT",
        },
        "std_agri_product_sources": {
            "long_term_url": "TEXT NOT NULL DEFAULT ''",
            "detail_url": "TEXT",
            "detail_url_status": "TEXT NOT NULL DEFAULT 'missing'",
            "locator": "TEXT",
            "rights_status": "TEXT NOT NULL DEFAULT 'unknown'",
            "attribution_required": "INTEGER NOT NULL DEFAULT 0",
            "attribution_text": "TEXT",
            "rights_evidence_url": "TEXT",
        },
        "std_agri_product_aliases": {
            "source_item_id": "TEXT",
            "long_term_url": "TEXT NOT NULL DEFAULT ''",
            "detail_url": "TEXT",
            "detail_url_status": "TEXT NOT NULL DEFAULT 'missing'",
            "locator": "TEXT",
            "rights_status": "TEXT NOT NULL DEFAULT 'unknown'",
            "attribution_required": "INTEGER NOT NULL DEFAULT 0",
            "attribution_text": "TEXT",
            "rights_evidence_url": "TEXT",
        },
        "std_ich_projects": {
            "locator": "TEXT",
            "announcement_year": "INTEGER",
            "is_active": "INTEGER NOT NULL DEFAULT 1",
        },
        "std_ich_inheritors": {
            "long_term_url": "TEXT NOT NULL DEFAULT ''",
            "detail_url": "TEXT",
            "detail_url_status": "TEXT NOT NULL DEFAULT 'missing'",
            "locator": "TEXT",
            "rights_status": "TEXT NOT NULL DEFAULT 'unknown'",
            "attribution_required": "INTEGER NOT NULL DEFAULT 0",
            "attribution_text": "TEXT",
            "rights_evidence_url": "TEXT",
        },
        "std_ich_related_items": {
            "long_term_url": "TEXT NOT NULL DEFAULT ''",
            "detail_url": "TEXT",
            "detail_url_status": "TEXT NOT NULL DEFAULT 'missing'",
            "locator": "TEXT",
            "rights_status": "TEXT NOT NULL DEFAULT 'unknown'",
            "attribution_required": "INTEGER NOT NULL DEFAULT 0",
            "attribution_text": "TEXT",
            "rights_evidence_url": "TEXT",
        },
        "std_ich_media_links": {
            "source_id": "TEXT NOT NULL DEFAULT 'unknown'",
            "source_item_id": "TEXT",
            "source_url": "TEXT NOT NULL DEFAULT ''",
            "long_term_url": "TEXT NOT NULL DEFAULT ''",
            "detail_url": "TEXT",
            "detail_url_status": "TEXT NOT NULL DEFAULT 'missing'",
            "locator": "TEXT",
            "rights_status": "TEXT NOT NULL DEFAULT 'unknown'",
            "attribution_required": "INTEGER NOT NULL DEFAULT 0",
            "attribution_text": "TEXT",
            "rights_evidence_url": "TEXT",
        },
        "std_jobs": {
            "locator": "TEXT",
            "is_active": "INTEGER NOT NULL DEFAULT 1",
        },
        "std_job_sources": {
            "long_term_url": "TEXT NOT NULL DEFAULT ''",
            "detail_url": "TEXT",
            "detail_url_status": "TEXT NOT NULL DEFAULT 'missing'",
            "locator": "TEXT",
            "rights_status": "TEXT NOT NULL DEFAULT 'unknown'",
            "attribution_required": "INTEGER NOT NULL DEFAULT 0",
            "attribution_text": "TEXT",
            "rights_evidence_url": "TEXT",
        },
        "std_job_locations": {
            "source_id": "TEXT NOT NULL DEFAULT 'unknown'",
            "source_item_id": "TEXT",
            "source_url": "TEXT NOT NULL DEFAULT ''",
            "long_term_url": "TEXT NOT NULL DEFAULT ''",
            "detail_url": "TEXT",
            "detail_url_status": "TEXT NOT NULL DEFAULT 'missing'",
            "locator": "TEXT",
            "rights_status": "TEXT NOT NULL DEFAULT 'unknown'",
            "attribution_required": "INTEGER NOT NULL DEFAULT 0",
            "attribution_text": "TEXT",
            "rights_evidence_url": "TEXT",
        },
        "std_dialect_points": {
            "locator": "TEXT",
            "is_active": "INTEGER NOT NULL DEFAULT 1",
        },
        "std_dialect_lexemes": {
            "source_id": "TEXT",
            "source_item_id": "TEXT",
            "source_url": "TEXT",
            "long_term_url": "TEXT",
            "detail_url": "TEXT",
            "detail_url_status": "TEXT NOT NULL DEFAULT 'missing'",
            "fetch_url": "TEXT",
            "locator": "TEXT",
            "rights_status": "TEXT NOT NULL DEFAULT 'unknown'",
        },
        "std_dialect_lexeme_sources": {
            "long_term_url": "TEXT",
            "detail_url": "TEXT",
            "detail_url_status": "TEXT NOT NULL DEFAULT 'missing'",
            "fetch_url": "TEXT",
            "locator": "TEXT",
            "rights_status": "TEXT NOT NULL DEFAULT 'unknown'",
        },
    }
    for table, columns in migrations.items():
        existing = {
            row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        for name, declaration in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {declaration}")


def _migrate_raw_files_append_only(conn):
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'raw_files'"
    ).fetchone()
    if row is None or "UNIQUE(source_id, source_url, sha256)" not in row[0]:
        return
    conn.execute("ALTER TABLE raw_files RENAME TO raw_files_legacy")
    conn.executescript(SCHEMA)
    conn.execute(
        """
        INSERT INTO raw_files (
            id, raw_fetch_id, source_id, source_url, long_term_url, detail_url,
            detail_url_status, fetch_url, locator, rights_status,
            attribution_required, attribution_text, rights_evidence_url,
            file_url, final_url, file_path, file_name, mime_type, file_ext,
            byte_size, sha256, access_level, download_status, oversize_note,
            media_metadata, retrieved_at, created_at
        )
        SELECT
            id, raw_fetch_id, source_id, source_url, long_term_url, detail_url,
            detail_url_status, fetch_url, locator, rights_status,
            attribution_required, attribution_text, rights_evidence_url,
            COALESCE(file_url, fetch_url, source_url),
            COALESCE(final_url, fetch_url, source_url),
            file_path, file_name, mime_type, file_ext, byte_size, sha256,
            access_level, download_status, oversize_note, media_metadata,
            retrieved_at, created_at
        FROM raw_files_legacy
        """
    )
    conn.execute("DROP TABLE raw_files_legacy")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_raw_files_sha256 ON raw_files(sha256)"
    )


def seed_std_sources(conn):
    path = Path(__file__).resolve().parents[1] / "docs" / "sources.json"
    if not path.exists():
        return
    payload = json.loads(path.read_text(encoding="utf-8"))
    for source in payload.get("sources") or []:
        status = source.get("status") or "draft"
        rights = source.get("rights_status") or "unknown"
        default_enabled = status in {"approved", "approved-with-gaps"}
        enabled = int(source.get("enabled", default_enabled))
        extra = {
            key: value
            for key, value in source.items()
            if key
            not in {
                "id",
                "name",
                "domains",
                "content_domains",
                "priority",
                "status",
                "access",
                "rights_status",
                "document",
                "review",
                "verification",
            }
        }
        conn.execute(
            """
            INSERT INTO std_sources (
                source_id, name, domains, content_domains, priority, status,
                access_level, rights_status, license_or_usage, confidence,
                document_path, review_path, verified_at, is_enabled, extra
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(source_id) DO UPDATE SET
                name=excluded.name,
                domains=excluded.domains,
                content_domains=excluded.content_domains,
                priority=excluded.priority,
                status=excluded.status,
                access_level=excluded.access_level,
                rights_status=excluded.rights_status,
                license_or_usage=excluded.license_or_usage,
                confidence=excluded.confidence,
                document_path=excluded.document_path,
                review_path=excluded.review_path,
                verified_at=excluded.verified_at,
                is_enabled=excluded.is_enabled,
                extra=excluded.extra
            """,
            (
                source["id"],
                source.get("name") or source["id"],
                json.dumps(source.get("domains") or [], ensure_ascii=False),
                json.dumps(
                    source.get("content_domains") or [], ensure_ascii=False
                ),
                source.get("priority") or "P2",
                status,
                source.get("access") or "public",
                rights,
                source.get("license_or_usage") or rights,
                source.get("confidence") or "medium",
                source.get("document"),
                source.get("review"),
                payload.get("generated_at"),
                enabled,
                json.dumps(extra, ensure_ascii=False, sort_keys=True),
            ),
        )
    conn.commit()


def sha256_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _content_hash(item):
    return item.get("content_hash") or sha256_text(
        json.dumps(item, ensure_ascii=False, sort_keys=True)
    )


def _row_id(conn, table, source_id, source_item_id):
    return conn.execute(
        f"SELECT id FROM {table} WHERE source_id = ? AND source_item_id = ?",
        (source_id, source_item_id),
    ).fetchone()[0]


def upsert_std_job(conn, item, retrieved_at):
    conn.execute(
        """
        INSERT INTO std_jobs (
            source_id, source_item_id, source_url, long_term_url, detail_url,
            detail_url_status, locator, rights_status, attribution_required,
            attribution_text, rights_evidence_url, title, title_raw,
            company_name, company_url, company_industry, company_size,
            company_nature, location_raw, province, city, employment_type,
            headcount, salary_raw, education_raw, experience_raw,
            gender_requirement, age_requirement, major_requirement,
            description, requirements, published_at, deadline_at,
            validity_days, status_text, content_hash, confidence,
            license_or_usage, publish_status, retrieved_at, first_seen_at,
            last_seen_at, extra
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(source_id, source_item_id) DO UPDATE SET
            source_url=excluded.source_url,
            long_term_url=excluded.long_term_url,
            detail_url=excluded.detail_url,
            detail_url_status=excluded.detail_url_status,
            locator=excluded.locator,
            rights_status=excluded.rights_status,
            attribution_required=excluded.attribution_required,
            attribution_text=excluded.attribution_text,
            rights_evidence_url=excluded.rights_evidence_url,
            title=excluded.title,
            title_raw=excluded.title_raw,
            company_name=excluded.company_name,
            company_url=excluded.company_url,
            company_industry=excluded.company_industry,
            company_size=excluded.company_size,
            company_nature=excluded.company_nature,
            location_raw=excluded.location_raw,
            province=excluded.province,
            city=excluded.city,
            employment_type=excluded.employment_type,
            headcount=excluded.headcount,
            salary_raw=excluded.salary_raw,
            education_raw=excluded.education_raw,
            experience_raw=excluded.experience_raw,
            gender_requirement=excluded.gender_requirement,
            age_requirement=excluded.age_requirement,
            major_requirement=excluded.major_requirement,
            description=excluded.description,
            requirements=excluded.requirements,
            published_at=excluded.published_at,
            deadline_at=excluded.deadline_at,
            validity_days=excluded.validity_days,
            status_text=excluded.status_text,
            content_hash=excluded.content_hash,
            last_seen_at=excluded.last_seen_at,
            extra=excluded.extra
        """,
        (
            item["source_id"],
            item["source_item_id"],
            item["source_url"],
            item["long_term_url"],
            item.get("detail_url"),
            item["detail_url_status"],
            item.get("locator"),
            item["rights_status"],
            1 if item.get("attribution_required") else 0,
            item.get("attribution_text"),
            item.get("rights_evidence_url"),
            item["title"],
            item.get("title_raw") or item["title"],
            item.get("company_name"),
            item.get("company_url"),
            item.get("company_industry"),
            item.get("company_size"),
            item.get("company_nature"),
            item.get("location_raw"),
            item.get("province"),
            item.get("city"),
            item.get("employment_type"),
            item.get("headcount"),
            item.get("salary_raw"),
            item.get("education_raw"),
            item.get("experience_raw"),
            item.get("gender_requirement"),
            item.get("age_requirement"),
            item.get("major_requirement"),
            item.get("description"),
            item.get("requirements"),
            item.get("published_at"),
            item.get("deadline_at"),
            item.get("validity_days"),
            item.get("status_text"),
            _content_hash(item),
            item.get("confidence") or "medium",
            item.get("license_or_usage") or item["rights_status"],
            item["publish_status"],
            retrieved_at,
            retrieved_at,
            retrieved_at,
            json.dumps(item.get("extra") or {}, ensure_ascii=False),
        ),
    )
    job_id = _row_id(conn, "std_jobs", item["source_id"], item["source_item_id"])
    upsert_std_job_source(conn, job_id, item, retrieved_at, is_primary=1)
    if any(
        item.get(key)
        for key in ("location_raw", "province", "city", "county")
    ):
        upsert_std_job_location(conn, job_id, item, is_primary=1)
    return job_id


def upsert_std_job_source(conn, job_id, item, retrieved_at, *, is_primary=0):
    conn.execute(
        """
        INSERT INTO std_job_sources (
            job_id, source_id, source_item_id, source_url, long_term_url,
            detail_url, detail_url_status, locator, rights_status,
            attribution_required, attribution_text, rights_evidence_url,
            is_primary, retrieved_at, content_hash, extra
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_id, source_id, source_url) DO UPDATE SET
            source_item_id=excluded.source_item_id,
            long_term_url=excluded.long_term_url,
            detail_url=excluded.detail_url,
            detail_url_status=excluded.detail_url_status,
            locator=excluded.locator,
            rights_status=excluded.rights_status,
            attribution_required=excluded.attribution_required,
            attribution_text=excluded.attribution_text,
            rights_evidence_url=excluded.rights_evidence_url,
            is_primary=excluded.is_primary,
            retrieved_at=excluded.retrieved_at,
            content_hash=excluded.content_hash,
            extra=excluded.extra
        """,
        (
            job_id,
            item["source_id"],
            item["source_item_id"],
            item["source_url"],
            item["long_term_url"],
            item.get("detail_url"),
            item["detail_url_status"],
            item.get("locator"),
            item["rights_status"],
            1 if item.get("attribution_required") else 0,
            item.get("attribution_text"),
            item.get("rights_evidence_url"),
            is_primary,
            retrieved_at,
            _content_hash(item),
            json.dumps(item.get("extra") or {}, ensure_ascii=False),
        ),
    )


def upsert_std_job_location(conn, job_id, item, *, is_primary=0):
    conn.execute(
        """
        INSERT INTO std_job_locations (
            job_id, source_id, source_item_id, source_url, long_term_url,
            detail_url, detail_url_status, locator, rights_status,
            attribution_required, attribution_text, rights_evidence_url,
            location_raw, province, city, county, is_primary, extra
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_id, province, city, county, location_raw) DO UPDATE SET
            source_id=excluded.source_id,
            source_item_id=excluded.source_item_id,
            source_url=excluded.source_url,
            long_term_url=excluded.long_term_url,
            detail_url=excluded.detail_url,
            detail_url_status=excluded.detail_url_status,
            locator=excluded.locator,
            rights_status=excluded.rights_status,
            attribution_required=excluded.attribution_required,
            attribution_text=excluded.attribution_text,
            rights_evidence_url=excluded.rights_evidence_url,
            is_primary=excluded.is_primary,
            extra=excluded.extra
        """,
        (
            job_id,
            item["source_id"],
            item.get("source_item_id"),
            item["source_url"],
            item["long_term_url"],
            item.get("detail_url"),
            item["detail_url_status"],
            item.get("locator"),
            item["rights_status"],
            1 if item.get("attribution_required") else 0,
            item.get("attribution_text"),
            item.get("rights_evidence_url"),
            item.get("location_raw"),
            item.get("province"),
            item.get("city"),
            item.get("county"),
            is_primary,
            json.dumps(item.get("extra") or {}, ensure_ascii=False),
        ),
    )


def upsert_std_ich_project(conn, item, retrieved_at):
    conn.execute(
        """
        INSERT INTO std_ich_projects (
            source_id, source_item_id, source_url, long_term_url, detail_url,
            detail_url_status, locator, rights_status, attribution_required,
            attribution_text, rights_evidence_url, ich_code, name,
            project_serial, source_project_num, category, project_type,
            announcement_batch, announcement_year, declaration_region,
            protection_unit, province, city, county, description_html,
            description_text, source_modified_at, content_hash, confidence,
            license_or_usage, publish_status, retrieved_at, first_seen_at,
            last_seen_at, extra
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(source_id, source_item_id) DO UPDATE SET
            source_url=excluded.source_url,
            long_term_url=excluded.long_term_url,
            detail_url=excluded.detail_url,
            detail_url_status=excluded.detail_url_status,
            locator=excluded.locator,
            rights_status=excluded.rights_status,
            attribution_required=excluded.attribution_required,
            attribution_text=excluded.attribution_text,
            rights_evidence_url=excluded.rights_evidence_url,
            ich_code=excluded.ich_code,
            name=excluded.name,
            project_serial=excluded.project_serial,
            source_project_num=excluded.source_project_num,
            category=excluded.category,
            project_type=excluded.project_type,
            announcement_batch=excluded.announcement_batch,
            announcement_year=excluded.announcement_year,
            declaration_region=excluded.declaration_region,
            protection_unit=excluded.protection_unit,
            province=excluded.province,
            city=excluded.city,
            county=excluded.county,
            description_html=excluded.description_html,
            description_text=excluded.description_text,
            source_modified_at=excluded.source_modified_at,
            content_hash=excluded.content_hash,
            last_seen_at=excluded.last_seen_at,
            extra=excluded.extra
        """,
        (
            item["source_id"],
            item["source_item_id"],
            item["source_url"],
            item["long_term_url"],
            item.get("detail_url"),
            item["detail_url_status"],
            item.get("locator"),
            item["rights_status"],
            1 if item.get("attribution_required") else 0,
            item.get("attribution_text"),
            item.get("rights_evidence_url"),
            item.get("ich_code"),
            item["title"],
            item.get("project_serial"),
            item.get("source_project_num"),
            item.get("category"),
            item.get("project_type"),
            item.get("announcement_batch"),
            item.get("announcement_year"),
            item.get("declaration_region"),
            item.get("protection_unit"),
            item.get("province"),
            item.get("city"),
            item.get("county"),
            item.get("description_html"),
            item.get("description_text"),
            item.get("source_modified_at"),
            _content_hash(item),
            item.get("confidence") or "high",
            item.get("license_or_usage") or item["rights_status"],
            item["publish_status"],
            retrieved_at,
            retrieved_at,
            retrieved_at,
            json.dumps(item.get("extra") or {}, ensure_ascii=False),
        ),
    )
    return _row_id(
        conn, "std_ich_projects", item["source_id"], item["source_item_id"]
    )


def upsert_std_agri_product(conn, item, retrieved_at):
    conn.execute(
        """
        INSERT INTO std_agri_products (
            source_id, source_item_id, source_url, long_term_url, detail_url,
            detail_url_status, locator, rights_status, attribution_required,
            attribution_text, rights_evidence_url, cert_type, product_name,
            product_name_raw, normalized_name, category, is_aquatic, province,
            city, county, region, origin_scope, applicant, protection_unit,
            certificate_no, certified_at, content_hash, confidence,
            license_or_usage, publish_status, retrieved_at, first_seen_at,
            last_seen_at, extra
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(source_id, source_item_id) DO UPDATE SET
            source_url=excluded.source_url,
            long_term_url=excluded.long_term_url,
            detail_url=excluded.detail_url,
            detail_url_status=excluded.detail_url_status,
            locator=excluded.locator,
            rights_status=excluded.rights_status,
            cert_type=excluded.cert_type,
            product_name=excluded.product_name,
            product_name_raw=excluded.product_name_raw,
            normalized_name=excluded.normalized_name,
            category=excluded.category,
            is_aquatic=excluded.is_aquatic,
            province=excluded.province,
            city=excluded.city,
            county=excluded.county,
            region=excluded.region,
            origin_scope=excluded.origin_scope,
            applicant=excluded.applicant,
            protection_unit=excluded.protection_unit,
            certificate_no=excluded.certificate_no,
            certified_at=excluded.certified_at,
            content_hash=excluded.content_hash,
            publish_status=excluded.publish_status,
            last_seen_at=excluded.last_seen_at,
            extra=excluded.extra
        """,
        (
            item["source_id"],
            item["source_item_id"],
            item["source_url"],
            item["long_term_url"],
            item.get("detail_url"),
            item["detail_url_status"],
            item.get("locator"),
            item["rights_status"],
            1 if item.get("attribution_required") else 0,
            item.get("attribution_text"),
            item.get("rights_evidence_url"),
            item["cert_type"],
            item["product_name"],
            item.get("product_name_raw"),
            item["normalized_name"],
            item.get("category"),
            item.get("is_aquatic"),
            item.get("province"),
            item.get("city"),
            item.get("county"),
            item.get("region"),
            item.get("origin_scope"),
            item.get("applicant"),
            item.get("protection_unit"),
            item.get("certificate_no"),
            item.get("certified_at"),
            _content_hash(item),
            item.get("confidence") or "medium",
            item.get("license_or_usage") or item["rights_status"],
            item["publish_status"],
            retrieved_at,
            retrieved_at,
            retrieved_at,
            json.dumps(item.get("extra") or {}, ensure_ascii=False),
        ),
    )
    product_id = _row_id(
        conn, "std_agri_products", item["source_id"], item["source_item_id"]
    )
    conn.execute(
        """
        INSERT INTO std_agri_product_sources (
            product_id, source_id, source_item_id, source_url,
            long_term_url, detail_url, detail_url_status, locator,
            rights_status, attribution_required, attribution_text,
            rights_evidence_url, announcement_no, published_at, certified_at,
            source_product_name, source_region, source_title, is_primary,
            retrieved_at, content_hash, extra
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
        ON CONFLICT(product_id, source_id, source_url) DO UPDATE SET
            source_item_id=excluded.source_item_id,
            long_term_url=excluded.long_term_url,
            detail_url=excluded.detail_url,
            detail_url_status=excluded.detail_url_status,
            locator=excluded.locator,
            rights_status=excluded.rights_status,
            attribution_required=excluded.attribution_required,
            attribution_text=excluded.attribution_text,
            rights_evidence_url=excluded.rights_evidence_url,
            announcement_no=excluded.announcement_no,
            published_at=excluded.published_at,
            certified_at=excluded.certified_at,
            source_product_name=excluded.source_product_name,
            source_region=excluded.source_region,
            source_title=excluded.source_title,
            retrieved_at=excluded.retrieved_at,
            content_hash=excluded.content_hash,
            extra=excluded.extra
        """,
        (
            product_id,
            item["source_id"],
            item["source_item_id"],
            item["source_url"],
            item["long_term_url"],
            item.get("detail_url"),
            item["detail_url_status"],
            item.get("locator"),
            item["rights_status"],
            1 if item.get("attribution_required") else 0,
            item.get("attribution_text"),
            item.get("rights_evidence_url"),
            item.get("announcement_no"),
            item.get("published_at"),
            item.get("certified_at"),
            item.get("product_name_raw") or item["product_name"],
            item.get("region"),
            item.get("source_title"),
            retrieved_at,
            _content_hash(item),
            json.dumps(item.get("extra") or {}, ensure_ascii=False),
        ),
    )
    return product_id


def upsert_std_dialect(conn, item, retrieved_at):
    point = item["point"]
    lexeme = item["lexeme"]
    conn.execute(
        """
        INSERT INTO std_dialect_points (
            source_id, source_item_id, source_url, long_term_url, detail_url,
            detail_url_status, locator, rights_status, attribution_required,
            attribution_text, rights_evidence_url, region_raw, province, city,
            county, dialect_name, point_note, confidence, license_or_usage,
            publish_status, retrieved_at, first_seen_at, last_seen_at,
            content_hash, extra
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?
        )
        ON CONFLICT(source_id, source_item_id) DO UPDATE SET
            source_url=excluded.source_url,
            long_term_url=excluded.long_term_url,
            detail_url=excluded.detail_url,
            detail_url_status=excluded.detail_url_status,
            locator=excluded.locator,
            rights_status=excluded.rights_status,
            attribution_required=excluded.attribution_required,
            attribution_text=excluded.attribution_text,
            rights_evidence_url=excluded.rights_evidence_url,
            region_raw=excluded.region_raw,
            province=excluded.province,
            city=excluded.city,
            county=excluded.county,
            dialect_name=excluded.dialect_name,
            point_note=excluded.point_note,
            confidence=excluded.confidence,
            content_hash=excluded.content_hash,
            last_seen_at=excluded.last_seen_at,
            extra=excluded.extra
        """,
        (
            point["source_id"],
            point["source_item_id"],
            point["source_url"],
            point["long_term_url"],
            point.get("detail_url"),
            point["detail_url_status"],
            point.get("locator"),
            point["rights_status"],
            1 if point.get("attribution_required") else 0,
            point.get("attribution_text"),
            point.get("rights_evidence_url"),
            point["region_raw"],
            point.get("province"),
            point.get("city"),
            point.get("county"),
            point.get("dialect_name"),
            point.get("point_note"),
            point.get("confidence") or "medium",
            point.get("license_or_usage") or point["rights_status"],
            point["publish_status"],
            retrieved_at,
            retrieved_at,
            retrieved_at,
            _content_hash(point),
            json.dumps(point.get("extra") or {}, ensure_ascii=False),
        ),
    )
    point_id = _row_id(
        conn, "std_dialect_points", point["source_id"], point["source_item_id"]
    )
    conn.execute(
        """
        INSERT INTO std_dialect_lexemes (
            point_id, source_id, source_item_id, source_url, long_term_url,
            detail_url, detail_url_status, fetch_url, locator, lemma,
            phonetic, definition, example, audio_url, audio_status,
            rights_status, attribution_required, attribution_text,
            rights_evidence_url, confidence, license_or_usage,
            publish_status, retrieved_at, content_hash, extra
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?
        )
        ON CONFLICT(point_id, lemma) DO UPDATE SET
            source_id=excluded.source_id,
            source_item_id=excluded.source_item_id,
            source_url=excluded.source_url,
            long_term_url=excluded.long_term_url,
            detail_url=excluded.detail_url,
            detail_url_status=excluded.detail_url_status,
            fetch_url=excluded.fetch_url,
            locator=excluded.locator,
            phonetic=excluded.phonetic,
            definition=excluded.definition,
            example=excluded.example,
            audio_url=excluded.audio_url,
            audio_status=excluded.audio_status,
            rights_status=excluded.rights_status,
            attribution_required=excluded.attribution_required,
            attribution_text=excluded.attribution_text,
            rights_evidence_url=excluded.rights_evidence_url,
            confidence=excluded.confidence,
            license_or_usage=excluded.license_or_usage,
            publish_status=excluded.publish_status,
            retrieved_at=excluded.retrieved_at,
            content_hash=excluded.content_hash,
            extra=excluded.extra
        """,
        (
            point_id,
            lexeme.get("source_id") or point["source_id"],
            lexeme.get("source_item_id") or point["source_item_id"],
            lexeme.get("source_url") or point["source_url"],
            lexeme.get("long_term_url") or point["long_term_url"],
            lexeme.get("detail_url") or point.get("detail_url"),
            lexeme.get("detail_url_status") or point["detail_url_status"],
            lexeme.get("fetch_url"),
            lexeme.get("locator"),
            lexeme["lemma"],
            lexeme.get("phonetic"),
            lexeme.get("definition"),
            lexeme.get("example"),
            lexeme.get("audio_url"),
            lexeme["audio_status"],
            lexeme.get("rights_status") or point["rights_status"],
            1
            if (
                lexeme.get("attribution_required")
                or point.get("attribution_required")
            )
            else 0,
            lexeme.get("attribution_text") or point.get("attribution_text"),
            lexeme.get("rights_evidence_url")
            or point.get("rights_evidence_url"),
            lexeme.get("confidence") or "medium",
            lexeme.get("license_or_usage") or point["rights_status"],
            lexeme["publish_status"],
            retrieved_at,
            _content_hash(lexeme),
            json.dumps(lexeme.get("extra") or {}, ensure_ascii=False),
        ),
    )
    lexeme_id = conn.execute(
        "SELECT id FROM std_dialect_lexemes WHERE point_id = ? AND lemma = ?",
        (point_id, lexeme["lemma"]),
    ).fetchone()[0]
    conn.execute(
        """
        INSERT INTO std_dialect_lexeme_sources (
            lexeme_id, source_id, source_item_id, source_url, long_term_url,
            detail_url, detail_url_status, fetch_url, locator, rights_status,
            attribution_required, attribution_text, rights_evidence_url,
            is_primary, retrieved_at, content_hash, extra
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
        ON CONFLICT(lexeme_id, source_id, source_item_id, source_url)
        DO UPDATE SET
            long_term_url=excluded.long_term_url,
            detail_url=excluded.detail_url,
            detail_url_status=excluded.detail_url_status,
            fetch_url=excluded.fetch_url,
            locator=excluded.locator,
            rights_status=excluded.rights_status,
            attribution_required=excluded.attribution_required,
            attribution_text=excluded.attribution_text,
            rights_evidence_url=excluded.rights_evidence_url,
            is_primary=excluded.is_primary,
            retrieved_at=excluded.retrieved_at,
            content_hash=excluded.content_hash,
            extra=excluded.extra
        """,
        (
            lexeme_id,
            lexeme.get("source_id") or point["source_id"],
            lexeme.get("source_item_id") or point["source_item_id"],
            lexeme.get("source_url") or point["source_url"],
            lexeme.get("long_term_url") or point["long_term_url"],
            lexeme.get("detail_url") or point.get("detail_url"),
            lexeme.get("detail_url_status") or point["detail_url_status"],
            lexeme.get("fetch_url"),
            lexeme.get("locator"),
            lexeme.get("rights_status") or point["rights_status"],
            1
            if (
                lexeme.get("attribution_required")
                or point.get("attribution_required")
            )
            else 0,
            lexeme.get("attribution_text") or point.get("attribution_text"),
            lexeme.get("rights_evidence_url")
            or point.get("rights_evidence_url"),
            retrieved_at,
            _content_hash(lexeme),
            json.dumps(lexeme.get("extra") or {}, ensure_ascii=False),
        ),
    )
    return point_id, lexeme_id


def upsert_std_ich_article(conn, item, retrieved_at):
    conn.execute(
        """
        INSERT INTO std_ich_articles (
            source_id, source_item_id, source_url, long_term_url, detail_url,
            detail_url_status, locator, rights_status, attribution_required,
            attribution_text, rights_evidence_url, title, published_at,
            body_text, content_hash, confidence, license_or_usage,
            publish_status, retrieved_at, first_seen_at, last_seen_at, extra
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
        ON CONFLICT(source_id, source_item_id) DO UPDATE SET
            source_url=excluded.source_url,
            long_term_url=excluded.long_term_url,
            detail_url=excluded.detail_url,
            detail_url_status=excluded.detail_url_status,
            locator=excluded.locator,
            rights_status=excluded.rights_status,
            attribution_required=excluded.attribution_required,
            attribution_text=excluded.attribution_text,
            rights_evidence_url=excluded.rights_evidence_url,
            title=excluded.title,
            published_at=excluded.published_at,
            body_text=excluded.body_text,
            content_hash=excluded.content_hash,
            last_seen_at=excluded.last_seen_at,
            extra=excluded.extra
        """,
        (
            item["source_id"],
            item["source_item_id"],
            item["source_url"],
            item["long_term_url"],
            item.get("detail_url"),
            item["detail_url_status"],
            item.get("locator"),
            item["rights_status"],
            1 if item.get("attribution_required") else 0,
            item.get("attribution_text"),
            item.get("rights_evidence_url"),
            item["title"],
            item.get("published_at"),
            item.get("body_text"),
            _content_hash(item),
            item.get("confidence") or "medium",
            item.get("license_or_usage") or item["rights_status"],
            item["publish_status"],
            retrieved_at,
            retrieved_at,
            retrieved_at,
            json.dumps(item.get("extra") or {}, ensure_ascii=False),
        ),
    )
    return _row_id(
        conn, "std_ich_articles", item["source_id"], item["source_item_id"]
    )


def upsert_std_research_article(conn, item, retrieved_at):
    conn.execute(
        """
        INSERT INTO std_research_articles (
            source_id, source_item_id, source_url, long_term_url, detail_url,
            detail_url_status, locator, rights_status, attribution_required,
            attribution_text, rights_evidence_url, title, summary,
            published_at, body_text, body_access, content_hash, confidence,
            license_or_usage, publish_status, retrieved_at, first_seen_at,
            last_seen_at, extra
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?
        )
        ON CONFLICT(source_id, source_item_id) DO UPDATE SET
            source_url=excluded.source_url,
            long_term_url=excluded.long_term_url,
            detail_url=excluded.detail_url,
            detail_url_status=excluded.detail_url_status,
            locator=excluded.locator,
            rights_status=excluded.rights_status,
            attribution_required=excluded.attribution_required,
            attribution_text=excluded.attribution_text,
            rights_evidence_url=excluded.rights_evidence_url,
            title=excluded.title,
            summary=excluded.summary,
            published_at=excluded.published_at,
            body_text=excluded.body_text,
            body_access=excluded.body_access,
            content_hash=excluded.content_hash,
            last_seen_at=excluded.last_seen_at,
            extra=excluded.extra
        """,
        (
            item["source_id"],
            item["source_item_id"],
            item["source_url"],
            item["long_term_url"],
            item.get("detail_url"),
            item.get("detail_url_status") or "direct",
            item.get("locator"),
            item["rights_status"],
            1 if item.get("attribution_required") else 0,
            item.get("attribution_text"),
            item.get("rights_evidence_url"),
            item["title"],
            item.get("summary"),
            item.get("published_at"),
            item.get("body_text"),
            item["body_access"],
            _content_hash(item),
            item.get("confidence") or "medium",
            item.get("license_or_usage") or item["rights_status"],
            item["publish_status"],
            retrieved_at,
            retrieved_at,
            retrieved_at,
            json.dumps(item.get("extra") or {}, ensure_ascii=False),
        ),
    )
    return _row_id(
        conn,
        "std_research_articles",
        item["source_id"],
        item["source_item_id"],
    )
