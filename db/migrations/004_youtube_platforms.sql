-- Mirrors alembic/versions/c41a7f2b9e10_youtube_platforms.py.
-- Keep both in sync when the schema changes (see src/db/models.py).

-- Allow YouTube long-form and Shorts as connectable social accounts. They are separate
-- platform keys (sharing one Google OAuth app) so content and scheduling specs can differ.
ALTER TABLE social_accounts DROP CONSTRAINT IF EXISTS ck_social_accounts_platform;

ALTER TABLE social_accounts ADD CONSTRAINT ck_social_accounts_platform
    CHECK (platform IN ('x','instagram','linkedin','tiktok','facebook','youtube','youtube_shorts'));
