-- FeatPoint 初始表结构快照（参考 DDL，运行期由 SQLAlchemy create_all 建表）
-- PostgreSQL 16

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    email         VARCHAR(160) NOT NULL UNIQUE,
    display_name  VARCHAR(80)  NOT NULL,
    role          VARCHAR(16)  NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    daily_quota   INTEGER      NOT NULL DEFAULT 20,
    quota_used    INTEGER      NOT NULL DEFAULT 0,
    quota_date    DATE,
    created_at    TIMESTAMPTZ  DEFAULT now()
);

CREATE TABLE IF NOT EXISTS feature_def (
    id              SERIAL PRIMARY KEY,
    code            VARCHAR(64)  NOT NULL UNIQUE,
    name            VARCHAR(120) NOT NULL,
    description     VARCHAR(400) NOT NULL DEFAULT '',
    entity_type     VARCHAR(32)  NOT NULL DEFAULT 'account',
    event_type      VARCHAR(16),
    amount_min      NUMERIC(14,2),
    window_seconds  INTEGER      NOT NULL,
    window_label    VARCHAR(16)  NOT NULL,
    boundary_policy VARCHAR(16)  NOT NULL DEFAULT 'strict',
    aggregate_kind  VARCHAR(24)  NOT NULL DEFAULT 'sum',
    status          VARCHAR(16)  NOT NULL DEFAULT 'draft',
    version         INTEGER      NOT NULL DEFAULT 1,
    owner_id        INTEGER REFERENCES users(id),
    is_seed         BOOLEAN      NOT NULL DEFAULT false,
    published_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ  DEFAULT now(),
    updated_at      TIMESTAMPTZ  DEFAULT now()
);

CREATE TABLE IF NOT EXISTS feature_version (
    id          SERIAL PRIMARY KEY,
    feature_id  INTEGER NOT NULL REFERENCES feature_def(id),
    version_no  INTEGER NOT NULL,
    snapshot    JSON    NOT NULL DEFAULT '{}',
    change_note VARCHAR(255) NOT NULL DEFAULT '',
    changed_by  VARCHAR(160) NOT NULL DEFAULT 'system',
    created_at  TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_feature_version UNIQUE (feature_id, version_no)
);

CREATE TABLE IF NOT EXISTS entity_event (
    id         SERIAL PRIMARY KEY,
    entity_key VARCHAR(48) NOT NULL,
    event_type VARCHAR(16) NOT NULL,
    event_ts   TIMESTAMPTZ NOT NULL,
    amount     NUMERIC(14,2) NOT NULL DEFAULT 0,
    channel    VARCHAR(16) NOT NULL DEFAULT 'app',
    source_ref VARCHAR(64) NOT NULL DEFAULT '',
    is_seed    BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_event_natural UNIQUE (entity_key, event_type, event_ts)
);

CREATE TABLE IF NOT EXISTS label_set (
    id          SERIAL PRIMARY KEY,
    code        VARCHAR(48) NOT NULL UNIQUE,
    name        VARCHAR(120) NOT NULL,
    description VARCHAR(400) NOT NULL DEFAULT '',
    is_seed     BOOLEAN NOT NULL DEFAULT false,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS label_row (
    id              SERIAL PRIMARY KEY,
    label_set_id    INTEGER NOT NULL REFERENCES label_set(id),
    entity_key      VARCHAR(48) NOT NULL,
    label_time      TIMESTAMPTZ NOT NULL,
    raw_label_time  VARCHAR(48) NOT NULL DEFAULT '',
    label           INTEGER NOT NULL DEFAULT 0,
    is_seed         BOOLEAN NOT NULL DEFAULT false,
    CONSTRAINT uq_label_row UNIQUE (label_set_id, entity_key, label_time)
);

CREATE TABLE IF NOT EXISTS sample_job (
    id               SERIAL PRIMARY KEY,
    code             VARCHAR(48) NOT NULL UNIQUE,
    name             VARCHAR(120) NOT NULL,
    kind             VARCHAR(24) NOT NULL DEFAULT 'sample_build',
    status           VARCHAR(16) NOT NULL DEFAULT 'pending',
    label_set_ids    JSON NOT NULL DEFAULT '[]',
    feature_ids      JSON NOT NULL DEFAULT '[]',
    range_start      TIMESTAMPTZ,
    range_end        TIMESTAMPTZ,
    boundary_policy  VARCHAR(16) NOT NULL DEFAULT 'strict',
    params_snapshot  JSON NOT NULL DEFAULT '{}',
    result_json      JSON,
    sample_count     INTEGER NOT NULL DEFAULT 0,
    leak_count       INTEGER NOT NULL DEFAULT 0,
    failure_reason   VARCHAR(32),
    created_by       VARCHAR(160) NOT NULL DEFAULT 'system',
    started_at       TIMESTAMPTZ,
    finished_at      TIMESTAMPTZ,
    is_seed          BOOLEAN NOT NULL DEFAULT false,
    created_at       TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sample_row (
    id           SERIAL PRIMARY KEY,
    job_id       INTEGER NOT NULL REFERENCES sample_job(id),
    label_row_id INTEGER NOT NULL REFERENCES label_row(id),
    label_set_id INTEGER NOT NULL,
    entity_key   VARCHAR(48) NOT NULL,
    label_time   TIMESTAMPTZ NOT NULL,
    label        INTEGER NOT NULL DEFAULT 0,
    features_json JSON NOT NULL DEFAULT '{}',
    leak_flags   JSON NOT NULL DEFAULT '[]',
    has_leak     BOOLEAN NOT NULL DEFAULT false,
    no_event     BOOLEAN NOT NULL DEFAULT false,
    created_at   TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT uq_sample_row UNIQUE (job_id, label_row_id)
);

CREATE TABLE IF NOT EXISTS backfill_task (
    id                   SERIAL PRIMARY KEY,
    code                 VARCHAR(48) NOT NULL UNIQUE,
    name                 VARCHAR(120) NOT NULL,
    mode                 VARCHAR(16) NOT NULL DEFAULT 'full',
    status               VARCHAR(16) NOT NULL DEFAULT 'pending',
    range_start          TIMESTAMPTZ,
    range_end            TIMESTAMPTZ,
    base_watermark       TIMESTAMPTZ,
    feature_ids          JSON NOT NULL DEFAULT '[]',
    full_checksum        VARCHAR(64),
    incremental_checksum VARCHAR(64),
    invariant_hold       BOOLEAN,
    result_json          JSON,
    created_by           VARCHAR(160) NOT NULL DEFAULT 'system',
    started_at           TIMESTAMPTZ,
    finished_at          TIMESTAMPTZ,
    is_seed              BOOLEAN NOT NULL DEFAULT false,
    created_at           TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_log (
    id          SERIAL PRIMARY KEY,
    actor_id    INTEGER,
    actor_email VARCHAR(160) NOT NULL DEFAULT '',
    action      VARCHAR(48) NOT NULL,
    entity_type VARCHAR(32) NOT NULL DEFAULT '',
    entity_id   INTEGER,
    before_json JSON,
    after_json  JSON,
    ip          VARCHAR(64),
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_event_entity ON entity_event (entity_key);
CREATE INDEX IF NOT EXISTS ix_event_ts ON entity_event (event_ts);
CREATE INDEX IF NOT EXISTS ix_label_row_time ON label_row (label_time);
CREATE INDEX IF NOT EXISTS ix_sample_row_job ON sample_row (job_id);
