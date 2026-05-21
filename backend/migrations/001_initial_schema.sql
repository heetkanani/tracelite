-- =============================================================
-- 001_initial_schema.sql
-- Initial schema for tracelite: projects, traces, spans.
-- =============================================================

-- Postgres needs this extension for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- -------------------------------------------------------------
-- projects: a workspace. Even for solo devs, this lets you
-- separate "my chatbot" from "my agent experiment".
-- -------------------------------------------------------------
CREATE TABLE projects (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    api_key     TEXT NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -------------------------------------------------------------
-- traces: the top-level "request" or "conversation turn".
-- One trace contains many spans.
-- -------------------------------------------------------------
CREATE TABLE traces (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name        TEXT,
    user_id     TEXT,
    session_id  TEXT,
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at  TIMESTAMPTZ NOT NULL,
    ended_at    TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- -------------------------------------------------------------
-- spans: individual operations within a trace.
-- An LLM call, a tool call, a retrieval — each is a span.
-- -------------------------------------------------------------
CREATE TABLE spans (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id        UUID NOT NULL REFERENCES traces(id) ON DELETE CASCADE,
    parent_span_id  UUID REFERENCES spans(id) ON DELETE CASCADE,
    name            TEXT NOT NULL,
    span_type       TEXT NOT NULL CHECK (span_type IN ('llm', 'tool', 'retrieval', 'generic')),

    started_at      TIMESTAMPTZ NOT NULL,
    ended_at        TIMESTAMPTZ,
    duration_ms     INTEGER,

    -- LLM-specific (nullable for non-LLM spans)
    model           TEXT,
    input           JSONB,
    output          JSONB,
    input_tokens    INTEGER,
    output_tokens   INTEGER,
    cost_usd        NUMERIC(12, 6),

    -- Error tracking
    status          TEXT NOT NULL DEFAULT 'ok' CHECK (status IN ('ok', 'error')),
    error_message   TEXT,

    -- Free-form attributes
    attributes      JSONB NOT NULL DEFAULT '{}'::jsonb
);

-- -------------------------------------------------------------
-- Indexes: every query pattern needs an index.
-- -------------------------------------------------------------
CREATE INDEX idx_traces_project_started   ON traces(project_id, started_at DESC);
CREATE INDEX idx_spans_trace_id           ON spans(trace_id);
CREATE INDEX idx_spans_started_at         ON spans(started_at DESC);
CREATE INDEX idx_spans_parent_span_id     ON spans(parent_span_id);

-- -------------------------------------------------------------
-- Seed: a default project for local dev so we can test immediately
-- -------------------------------------------------------------
INSERT INTO projects (name, api_key)
VALUES ('default', 'local-dev-key');