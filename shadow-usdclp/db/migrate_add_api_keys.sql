-- API Keys: allow users to generate keys for public API access
CREATE TABLE IF NOT EXISTS api_keys (
    id              SERIAL PRIMARY KEY,
    user_id         INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    key_prefix      TEXT NOT NULL,          -- first 16 chars + "..." for display (e.g. "sk_shadow_a1b2c5...")
    key_hash        TEXT NOT NULL,          -- SHA-256 hash of the full key
    label           TEXT NOT NULL DEFAULT 'default',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    last_used_at    TIMESTAMPTZ,
    is_active       BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_api_keys_hash ON api_keys (key_hash) WHERE is_active = TRUE;
CREATE INDEX idx_api_keys_user ON api_keys (user_id);
