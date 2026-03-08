-- Audit log: tracks all user actions (login, password changes, model changes, etc.)
CREATE TABLE IF NOT EXISTS audit_log (
    id          BIGSERIAL PRIMARY KEY,
    ts          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    username    TEXT,                     -- who performed the action (NULL for system events)
    action      TEXT NOT NULL,            -- e.g. 'login', 'password_change', 'user_create', 'model_activate'
    detail      JSONB,                    -- action-specific payload
    ip          TEXT                      -- client IP address
);

CREATE INDEX IF NOT EXISTS idx_audit_log_ts ON audit_log (ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_username ON audit_log (username, ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log (action, ts DESC);
