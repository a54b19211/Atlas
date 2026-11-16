-- V018 — 拉取改成常驻服务（pull/）：来源/类型白名单、可改的设置、每来源状态、管理改动记录

-- 第 1 关：哪些 fabric 来源（可选再限定文档类型）进图谱。doc_type 为空 = 这个来源的全部类型。
CREATE TABLE IF NOT EXISTS atlas_pull_whitelist (
    id         BIGSERIAL   PRIMARY KEY,
    source_id  TEXT        NOT NULL,
    doc_type   TEXT        NOT NULL DEFAULT '',
    enabled    BOOLEAN     NOT NULL DEFAULT TRUE,
    note       TEXT        NOT NULL DEFAULT '',
    updated_by TEXT        NOT NULL DEFAULT 'migration',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_id, doc_type)
);

-- source_id 以 fabric 的 fetch/catalog.py 为准
INSERT INTO atlas_pull_whitelist (source_id, enabled, note) VALUES
    ('fda_api_drug_label',  TRUE,  'openFDA 药品说明书'),
    ('fda_api_enforcement', TRUE,  'openFDA 药品召回执行报告'),
    ('nmpa',                TRUE,  '国家药监局'),
    ('cde',                 TRUE,  '药审中心'),
    ('cde_xxgk',            TRUE,  '药审中心·信息公开'),
    ('cde_zdyz',            TRUE,  '药审中心·指导原则'),
    ('cde_ctr',             TRUE,  'CDE 临床试验登记（fabric 里还是 declared）'),
    ('clinicaltrials',      TRUE,  'ClinicalTrials.gov'),
    ('chictr',              TRUE,  '中国临床试验注册中心'),
    ('fda_drug_safety',     FALSE, 'FDA 药品安全通讯，待定'),
    ('fda_crl',             FALSE, 'FDA 完全回应函，待定'),
    ('fda_press',           FALSE, '新闻稿'),
    ('pubmed',              FALSE, '文献'),
    ('europe_pmc',          FALSE, '文献'),
    ('gdelt_doc',           FALSE, '新闻索引'),
    ('fiercepharma',        FALSE, '新闻'),
    ('roche',               FALSE, '企业新闻稿'),
    ('who_don',             FALSE, '疫情通报'),
    ('hkex',                FALSE, '港交所披露'),
    ('sec_companyfacts',    FALSE, '财务数据'),
    ('nccn',                FALSE, '指南'),
    ('phirda_industry',     FALSE, '药促会资讯'),
    ('phirda_policy',       FALSE, '药促会资讯'),
    ('phirda_rd',           FALSE, '药促会资讯'),
    ('phirda_healthcare_reform', FALSE, '药促会资讯'),
    ('local_files',         FALSE, '本地导入')
ON CONFLICT (source_id, doc_type) DO NOTHING;

-- 可改的设置（键见 pull/store.py 的 DEFAULTS；没有的行用默认值）
CREATE TABLE IF NOT EXISTS atlas_settings (
    key        TEXT        PRIMARY KEY,
    value      JSONB       NOT NULL,
    updated_by TEXT        NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 管理接口的每次改动：谁、何时、改了什么
CREATE TABLE IF NOT EXISTS atlas_admin_log (
    id     BIGSERIAL   PRIMARY KEY,
    actor  TEXT        NOT NULL,
    action TEXT        NOT NULL,
    detail JSONB       NOT NULL DEFAULT '{}',
    at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 每来源状态：fabric 最新序号（积压 = max_seq - last_seq）、跳过数（累计）、上轮起止、上次错误
ALTER TABLE fabric_pull_state
    ADD COLUMN IF NOT EXISTS max_seq           BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS skipped_whitelist BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS skipped_quality   BIGINT NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS last_started_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_finished_at  TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS last_error        TEXT;
