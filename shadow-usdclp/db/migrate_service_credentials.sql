-- Service credentials: encrypted API keys for external services
-- Apply with: docker compose exec -T db psql -U shadow -d shadow_usdclp < db/migrate_service_credentials.sql

CREATE TABLE IF NOT EXISTS service_credentials (
    id              SERIAL PRIMARY KEY,
    service_name    TEXT NOT NULL,
    credential_key  TEXT NOT NULL,
    encrypted_value TEXT NOT NULL DEFAULT '',
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_by      TEXT,
    UNIQUE(service_name, credential_key)
);

-- Seed known services (empty values = not yet configured)
INSERT INTO service_credentials (service_name, credential_key) VALUES
    ('twelvedata', 'api_key'),
    ('cmf', 'api_key'),
    ('buda', 'api_key'),
    ('buda', 'api_secret')
ON CONFLICT DO NOTHING;
