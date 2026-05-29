-- =============================================================
-- 005_auth_tables.sql
-- Multi-user auth: users, sessions, api_keys.
--
-- Restructures existing projects table to belong to a user, and
-- migrates the existing api_key column into a separate api_keys table.
-- =============================================================

-- -----------------------------------------------------------
-- users
-- -----------------------------------------------------------

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    name            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Fast lookup by email during login. Functional index on lower(email)
-- enables case-insensitive matching without a full table scan.
CREATE INDEX idx_users_email ON users(lower(email));


-- -----------------------------------------------------------
-- sessions
-- -----------------------------------------------------------

CREATE TABLE sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token           TEXT NOT NULL UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL,
    last_seen_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Most-common lookup: validate a session by its token.
CREATE INDEX idx_sessions_token ON sessions(token);

-- For "show me my active sessions" UI later.
CREATE INDEX idx_sessions_user ON sessions(user_id, last_seen_at DESC);


-- -----------------------------------------------------------
-- api_keys
-- -----------------------------------------------------------

CREATE TABLE api_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    key             TEXT NOT NULL UNIQUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_used_at    TIMESTAMPTZ,
    revoked_at      TIMESTAMPTZ
);

-- Most-common lookup: validate an API key. Partial index excludes
-- revoked keys so the index stays small and lookups skip dead rows.
CREATE INDEX idx_api_keys_active ON api_keys(key) WHERE revoked_at IS NULL;

-- "Show me all keys for this project" UI later.
CREATE INDEX idx_api_keys_project ON api_keys(project_id, created_at DESC);


-- -----------------------------------------------------------
-- projects: add owner_user_id (nullable initially for migration)
-- -----------------------------------------------------------

ALTER TABLE projects
    ADD COLUMN owner_user_id UUID REFERENCES users(id) ON DELETE CASCADE;


-- -----------------------------------------------------------
-- Data migration: create a dev user, assign existing project + key
-- -----------------------------------------------------------

-- bcrypt hash of password "devpassword".
-- This user is created during migration so existing local-dev-key
-- traffic continues to work. You can change the password via the
-- settings UI after Session 8.2 lands.
INSERT INTO users (id, email, password_hash, name)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'dev@tracelite.local',
    '$2b$12$knLPfjA74BZRm5l/SgG7.OAzyewFYCBOdUOhFubqA0yiPqmsLIi7y',
    'Dev User'
);

-- Assign the existing default project to the dev user.
UPDATE projects
SET owner_user_id = '00000000-0000-0000-0000-000000000001'
WHERE name = 'default';

-- Move the existing API key into the new api_keys table.
INSERT INTO api_keys (project_id, name, key)
SELECT id, 'default key (migrated)', api_key
FROM projects
WHERE api_key IS NOT NULL;


-- -----------------------------------------------------------
-- Lock down projects.owner_user_id and remove the old api_key
-- -----------------------------------------------------------

ALTER TABLE projects
    ALTER COLUMN owner_user_id SET NOT NULL;

ALTER TABLE projects
    DROP COLUMN api_key;