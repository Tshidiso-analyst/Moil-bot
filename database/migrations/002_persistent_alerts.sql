BEGIN;

-- Durable alerts and delivery attempts for hosted deployments.
CREATE TABLE IF NOT EXISTS moil_alerts (
    alert_id VARCHAR(32) PRIMARY KEY,
    symbol VARCHAR(32) NOT NULL,
    alert_type VARCHAR(64) NOT NULL,
    severity VARCHAR(16) NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'new'
        CHECK (status IN ('new', 'acknowledged', 'resolved')),
    decision_id VARCHAR(128),
    dedupe_key TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS moil_alerts_dedupe_unique
    ON moil_alerts (dedupe_key)
    WHERE dedupe_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS moil_alerts_created_at_idx
    ON moil_alerts (created_at DESC);
CREATE INDEX IF NOT EXISTS moil_alerts_symbol_created_at_idx
    ON moil_alerts (symbol, created_at DESC);
CREATE INDEX IF NOT EXISTS moil_alerts_status_idx
    ON moil_alerts (status);

CREATE TABLE IF NOT EXISTS moil_alert_deliveries (
    delivery_id BIGSERIAL PRIMARY KEY,
    alert_id VARCHAR(32) NOT NULL REFERENCES moil_alerts(alert_id) ON DELETE CASCADE,
    channel VARCHAR(32) NOT NULL,
    sent BOOLEAN NOT NULL,
    message TEXT NOT NULL,
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS moil_alert_deliveries_alert_idx
    ON moil_alert_deliveries (alert_id, attempted_at DESC);

COMMIT;
