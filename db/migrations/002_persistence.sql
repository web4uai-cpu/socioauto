-- Delta for wiring routes to real persistence. Mirrors src/db/models.py — keep in sync.
-- Apply after 001_init.sql.

-- Self-provisioned / invited principals may exist before a password is set.
ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL;

-- Campaign now carries the full serialized agent state plus request metadata.
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS cta VARCHAR(255);
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS platforms JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS state_json JSONB NOT NULL DEFAULT '{}'::jsonb;

-- Broaden campaign status to include the pipeline/human-review states used by the API.
ALTER TABLE campaigns DROP CONSTRAINT IF EXISTS ck_campaigns_status;
ALTER TABLE campaigns ADD CONSTRAINT ck_campaigns_status CHECK (
    status IN ('draft','active','paused','completed',
               'pending_review','needs_revision','scheduled','published')
);

-- Index for the due-post scheduler runner.
CREATE INDEX IF NOT EXISTS ix_posts_due ON posts (status, scheduled_at);

-- Campaign drafts are projected into posts before a platform account is attached.
ALTER TABLE posts ALTER COLUMN social_account_id DROP NOT NULL;

-- Append-only compliance audit trail (docs/SYSTEM_DESIGN.md §5).
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor TEXT NOT NULL,
    action VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id VARCHAR(64),
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_audit_log_entity ON audit_log (entity_type, entity_id);
