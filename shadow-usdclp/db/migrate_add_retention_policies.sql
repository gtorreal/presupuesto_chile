-- Migration: add TimescaleDB compression and retention policies
-- Run once: docker compose exec -T db psql -U shadow -d shadow_usdclp < db/migrate_add_retention_policies.sql
--
-- Retention:
--   price_ticks           → 90 days  (high-frequency raw ticks)
--   shadow_usdclp         → 365 days (calculated index history)
--   correlation_snapshots → 365 days (daily snapshots)
--
-- Compression (price_ticks, shadow_usdclp only — high row count):
--   Compress chunks older than 7 days / 1 day respectively.

-- ── price_ticks ────────────────────────────────────────────────────────────────

ALTER TABLE price_ticks SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'source, symbol',
    timescaledb.compress_orderby   = 'time DESC'
);

SELECT add_compression_policy('price_ticks', INTERVAL '7 days', if_not_exists => true);
SELECT add_retention_policy('price_ticks',   INTERVAL '90 days', if_not_exists => true);

-- ── shadow_usdclp ──────────────────────────────────────────────────────────────

ALTER TABLE shadow_usdclp SET (
    timescaledb.compress,
    timescaledb.compress_orderby = 'time DESC'
);

SELECT add_compression_policy('shadow_usdclp', INTERVAL '1 day',   if_not_exists => true);
SELECT add_retention_policy('shadow_usdclp',   INTERVAL '365 days', if_not_exists => true);

-- ── correlation_snapshots ──────────────────────────────────────────────────────

SELECT add_retention_policy('correlation_snapshots', INTERVAL '365 days', if_not_exists => true);
