-- =============================================================
-- 004_alert_tables.sql
-- Alert rules (what to watch) and alert events (history of fires).
-- =============================================================

-- -----------------------------------------------------------
-- alert_rules: user-defined conditions to watch
-- -----------------------------------------------------------

CREATE TABLE alert_rules (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    name                TEXT NOT NULL,

    -- e.g. 'eval_pass_rate_below', 'trace_error_rate_above'
    condition_type      TEXT NOT NULL,

    -- type-specific settings (eval_id, threshold, window_minutes, etc.)
    config              JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- 'log' for v1; 'slack_webhook', 'email' added in session 2
    delivery_channel    TEXT NOT NULL DEFAULT 'log',
    delivery_config     JSONB NOT NULL DEFAULT '{}'::jsonb,

    active              BOOLEAN NOT NULL DEFAULT true,

    -- Anti-spam: don't re-fire within this many minutes of the last fire.
    min_resend_minutes  INTEGER NOT NULL DEFAULT 60,

    -- Observability: when the worker last looked at this rule,
    -- and when it last actually fired.
    last_evaluated_at   TIMESTAMPTZ,
    last_fired_at       TIMESTAMPTZ,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT alert_rules_condition_check CHECK (
        condition_type IN (
            'eval_pass_rate_below',
            'trace_error_rate_above'
        )
    ),
    CONSTRAINT alert_rules_channel_check CHECK (
        delivery_channel IN ('log', 'slack_webhook', 'email')
    ),
    CONSTRAINT alert_rules_min_resend_check CHECK (
        min_resend_minutes >= 0
    )
);

-- Worker queries: "active rules due for re-evaluation". Index on
-- (active, last_evaluated_at) supports this scan efficiently.
CREATE INDEX idx_alert_rules_due
    ON alert_rules(last_evaluated_at NULLS FIRST)
    WHERE active = true;

CREATE INDEX idx_alert_rules_project ON alert_rules(project_id);


-- -----------------------------------------------------------
-- alert_events: history of every time a rule fired
-- -----------------------------------------------------------

CREATE TABLE alert_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_rule_id   UUID NOT NULL REFERENCES alert_rules(id) ON DELETE CASCADE,

    fired_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Human-readable summary; goes in Slack/email body
    message         TEXT NOT NULL,

    -- Structured snapshot of the evaluation that produced the fire
    -- (observed_value, threshold, window_start, etc.)
    context         JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Delivery status. False here = the rule fired but delivery (e.g.
    -- Slack call) failed — useful for "show me missed alerts" queries.
    delivered       BOOLEAN NOT NULL DEFAULT false,
    delivery_error  TEXT
);

CREATE INDEX idx_alert_events_rule ON alert_events(alert_rule_id, fired_at DESC);

-- Quick "show me undelivered alerts" lookup
CREATE INDEX idx_alert_events_failed
    ON alert_events(fired_at DESC)
    WHERE delivered = false;