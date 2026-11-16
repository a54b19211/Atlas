-- V017 — 文档改从资料库（fabric）拉取：记版本号和每个来源拉到的序号（fabric_pull.py）
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS fabric_version_id TEXT DEFAULT '';

CREATE TABLE IF NOT EXISTS fabric_pull_state (
    source_id  TEXT        PRIMARY KEY,
    last_seq   BIGINT      NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
