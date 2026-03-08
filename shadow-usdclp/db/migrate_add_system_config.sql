-- Migration: add system_config table (for existing deployments)
-- Run once: docker compose exec -T db psql -U shadow -d shadow_usdclp < db/migrate_add_system_config.sql

CREATE TABLE IF NOT EXISTS system_config (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO system_config (key, value)
VALUES
    ('collector_fast_interval',     '30'),
    ('collector_yfinance_interval', '300'),
    ('calculator_interval',         '30')
ON CONFLICT (key) DO NOTHING;
