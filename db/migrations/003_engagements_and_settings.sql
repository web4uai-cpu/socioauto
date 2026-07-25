-- Mirrors alembic/versions/0d35d88ebd83_engagements_and_app_settings.py.
-- Keep both in sync when the schema changes (see src/db/models.py).

-- Inbound mentions/comments/DMs awaiting or holding an Engagement Agent draft.
-- external_id is UNIQUE so redelivered platform webhooks cannot duplicate work.
CREATE TABLE IF NOT EXISTS engagements (
    id              UUID PRIMARY KEY,
    platform        VARCHAR(30)  NOT NULL,
    external_id     VARCHAR(255) NOT NULL UNIQUE,
    kind            VARCHAR(20)  NOT NULL DEFAULT 'mention',
    author          VARCHAR(255),
    message         TEXT         NOT NULL DEFAULT '',
    draft_response  TEXT,
    escalated       BOOLEAN      NOT NULL DEFAULT FALSE,
    status          VARCHAR(20)  NOT NULL DEFAULT 'pending',
    received_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    processed_at    TIMESTAMPTZ,
    CONSTRAINT ck_engagements_kind   CHECK (kind IN ('mention','comment','dm')),
    CONSTRAINT ck_engagements_status CHECK (status IN ('pending','drafted','escalated','responded'))
);

CREATE INDEX IF NOT EXISTS ix_engagements_status ON engagements (status, received_at);

-- Dashboard-editable runtime configuration. Values are AES-256-GCM encrypted by the
-- application before insert (src/security/crypto.py) — never store plaintext keys here.
CREATE TABLE IF NOT EXISTS app_settings (
    key             VARCHAR(100) PRIMARY KEY,
    value_encrypted TEXT         NOT NULL,
    is_secret       BOOLEAN      NOT NULL DEFAULT TRUE,
    updated_by      VARCHAR(320),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT now()
);
