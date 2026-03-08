-- Shadow USDCLP - Database Schema
-- TimescaleDB (PostgreSQL extension)

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Raw price ticks from all sources
CREATE TABLE price_ticks (
    time        TIMESTAMPTZ NOT NULL,
    source      TEXT NOT NULL,        -- 'massive', 'twelvedata', 'buda', 'mindicador', 'cmf', 'manual'
    symbol      TEXT NOT NULL,        -- 'USDCLP', 'USDBRL', 'USDMXN', 'DXY', 'HG', 'VIX', etc.
    bid         DOUBLE PRECISION,
    ask         DOUBLE PRECISION,
    mid         DOUBLE PRECISION,     -- (bid+ask)/2 or last_price if no bid/ask
    volume      DOUBLE PRECISION,
    raw_json    JSONB                 -- full response for auditing
);
SELECT create_hypertable('price_ticks', 'time');
CREATE INDEX ON price_ticks (source, symbol, time DESC);
CREATE INDEX ON price_ticks (symbol, time DESC);

-- Calculated shadow index
CREATE TABLE shadow_usdclp (
    time                TIMESTAMPTZ NOT NULL,
    shadow_price        DOUBLE PRECISION NOT NULL,
    confidence_low      DOUBLE PRECISION,
    confidence_high     DOUBLE PRECISION,
    bec_last_close      DOUBLE PRECISION,
    bec_close_time      TIMESTAMPTZ,
    factors_used        JSONB,         -- which factors were available
    factor_deltas       JSONB,         -- delta% per factor
    model_version       TEXT
);
SELECT create_hypertable('shadow_usdclp', 'time');

-- Model parameters (betas, weights)
CREATE TABLE model_params (
    id              SERIAL PRIMARY KEY,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    name            TEXT NOT NULL,
    is_active       BOOLEAN DEFAULT FALSE,  -- only 1 active at a time
    params          JSONB NOT NULL,
    training_window TEXT,
    r_squared       DOUBLE PRECISION,
    rmse            DOUBLE PRECISION,
    notes           TEXT
);

-- Seed default model params
INSERT INTO model_params (name, is_active, params, notes) VALUES (
    'default_v1',
    TRUE,
    '{
        "beta_ndf": 0.85,
        "beta_usdbrl": 0.25,
        "beta_dxy": 0.30,
        "beta_copper_inv": 0.20,
        "beta_usdmxn": 0.10,
        "beta_vix": 0.05,
        "beta_us10y": 0.05,
        "beta_usdcop": 0.08,
        "beta_ech": 0.03
    }'::jsonb,
    'Initial hardcoded betas based on domain knowledge'
);

-- Historical correlations
CREATE TABLE correlation_snapshots (
    time            TIMESTAMPTZ NOT NULL,
    window_days     INT NOT NULL,
    pair_a          TEXT NOT NULL,
    pair_b          TEXT NOT NULL,
    correlation     DOUBLE PRECISION,
    r_squared       DOUBLE PRECISION,
    beta            DOUBLE PRECISION,
    observations    INT
);
SELECT create_hypertable('correlation_snapshots', 'time');
CREATE INDEX ON correlation_snapshots (window_days, pair_a, pair_b, time DESC);

-- Compression and retention policies
ALTER TABLE price_ticks SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'source, symbol',
    timescaledb.compress_orderby   = 'time DESC'
);
SELECT add_compression_policy('price_ticks', INTERVAL '7 days');
SELECT add_retention_policy('price_ticks',   INTERVAL '90 days');

ALTER TABLE shadow_usdclp SET (
    timescaledb.compress,
    timescaledb.compress_orderby = 'time DESC'
);
SELECT add_compression_policy('shadow_usdclp', INTERVAL '1 day');
SELECT add_retention_policy('shadow_usdclp',   INTERVAL '365 days');

SELECT add_retention_policy('correlation_snapshots', INTERVAL '365 days');

-- Users table (DB-backed auth, replaces AUTH_USERS env var)
CREATE TABLE users (
    id                  SERIAL PRIMARY KEY,
    username            TEXT UNIQUE NOT NULL,
    password_hash       TEXT NOT NULL,
    role                TEXT NOT NULL DEFAULT 'admin',
    otp_enabled         BOOLEAN DEFAULT FALSE,
    otp_secret          TEXT,             -- active TOTP secret
    otp_pending_secret  TEXT,             -- temp secret during OTP setup
    created_at          TIMESTAMPTZ DEFAULT NOW(),
    is_active           BOOLEAN DEFAULT TRUE
);

-- Runtime configuration (editable from the UI)
CREATE TABLE system_config (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL,
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO system_config (key, value) VALUES
    ('collector_fast_interval',     '30'),
    ('collector_yfinance_interval', '300'),
    ('calculator_interval',         '30');

-- Audit log: tracks all user actions
CREATE TABLE audit_log (
    id          BIGSERIAL PRIMARY KEY,
    ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    username    TEXT,
    action      TEXT NOT NULL,
    detail      JSONB,
    ip          TEXT
);

CREATE INDEX idx_audit_log_ts ON audit_log (ts DESC);
CREATE INDEX idx_audit_log_username ON audit_log (username, ts DESC);
CREATE INDEX idx_audit_log_action ON audit_log (action, ts DESC);

-- Chilean holidays table
CREATE TABLE cl_holidays (
    date    DATE PRIMARY KEY,
    name    TEXT NOT NULL
);

-- Load Chilean holidays 2024-2027
INSERT INTO cl_holidays (date, name) VALUES
-- 2024
('2024-01-01', 'Año Nuevo'),
('2024-03-29', 'Viernes Santo'),
('2024-03-30', 'Sábado Santo'),
('2024-05-01', 'Día del Trabajador'),
('2024-05-21', 'Día de las Glorias Navales'),
('2024-06-20', 'Día Nacional de los Pueblos Indígenas'),
('2024-06-29', 'San Pedro y San Pablo'),
('2024-07-15', 'Día de la Virgen del Carmen'),
('2024-08-15', 'Asunción de la Virgen'),
('2024-09-18', 'Independencia Nacional'),
('2024-09-19', 'Día de las Glorias del Ejército'),
('2024-09-20', 'Feriado Adicional'),
('2024-10-12', 'Encuentro de Dos Mundos'),
('2024-10-31', 'Día de las Iglesias Evangélicas'),
('2024-11-01', 'Día de Todos los Santos'),
('2024-12-08', 'Inmaculada Concepción'),
('2024-12-25', 'Navidad'),
-- 2025
('2025-01-01', 'Año Nuevo'),
('2025-04-18', 'Viernes Santo'),
('2025-04-19', 'Sábado Santo'),
('2025-05-01', 'Día del Trabajador'),
('2025-05-21', 'Día de las Glorias Navales'),
('2025-06-20', 'Día Nacional de los Pueblos Indígenas'),
('2025-06-29', 'San Pedro y San Pablo'),
('2025-07-15', 'Día de la Virgen del Carmen'),
('2025-08-15', 'Asunción de la Virgen'),
('2025-09-18', 'Independencia Nacional'),
('2025-09-19', 'Día de las Glorias del Ejército'),
('2025-10-12', 'Encuentro de Dos Mundos'),
('2025-10-31', 'Día de las Iglesias Evangélicas'),
('2025-11-01', 'Día de Todos los Santos'),
('2025-12-08', 'Inmaculada Concepción'),
('2025-12-25', 'Navidad'),
-- 2026
('2026-01-01', 'Año Nuevo'),
('2026-04-03', 'Viernes Santo'),
('2026-04-04', 'Sábado Santo'),
('2026-05-01', 'Día del Trabajador'),
('2026-05-21', 'Día de las Glorias Navales'),
('2026-06-20', 'Día Nacional de los Pueblos Indígenas'),
('2026-06-29', 'San Pedro y San Pablo'),
('2026-07-15', 'Día de la Virgen del Carmen'),
('2026-08-15', 'Asunción de la Virgen'),
('2026-09-18', 'Independencia Nacional'),
('2026-09-19', 'Día de las Glorias del Ejército'),
('2026-10-12', 'Encuentro de Dos Mundos'),
('2026-10-31', 'Día de las Iglesias Evangélicas'),
('2026-11-01', 'Día de Todos los Santos'),
('2026-12-08', 'Inmaculada Concepción'),
('2026-12-25', 'Navidad'),
-- 2027
('2027-01-01', 'Año Nuevo'),
('2027-03-26', 'Viernes Santo'),
('2027-03-27', 'Sábado Santo'),
('2027-05-01', 'Día del Trabajador'),
('2027-05-21', 'Día de las Glorias Navales'),
('2027-06-20', 'Día Nacional de los Pueblos Indígenas'),
('2027-06-29', 'San Pedro y San Pablo'),
('2027-07-15', 'Día de la Virgen del Carmen'),
('2027-08-15', 'Asunción de la Virgen'),
('2027-09-18', 'Independencia Nacional'),
('2027-09-19', 'Día de las Glorias del Ejército'),
('2027-10-12', 'Encuentro de Dos Mundos'),
('2027-10-31', 'Día de las Iglesias Evangélicas'),
('2027-11-01', 'Día de Todos los Santos'),
('2027-12-08', 'Inmaculada Concepción'),
('2027-12-25', 'Navidad');
