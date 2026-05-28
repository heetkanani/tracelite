-- =============================================================
-- 003_eval_tables.sql
-- Add the two tables that power evaluations: definitions (rules)
-- and results (outcomes). One eval_definition is a user-saved
-- rule; one eval_result is the outcome of running that rule
-- against one span.
-- =============================================================

-- -----------------------------------------------------------
-- eval_definitions: user-defined rules
-- -----------------------------------------------------------

CREATE TABLE eval_definitions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,

    name            TEXT NOT NULL,
    evaluator_type  TEXT NOT NULL,            -- 'regex_match' | 'substring_absent' | 'json_schema' | 'llm_judge'
    config          JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Optional filter: only run this eval against spans of this type.
    -- NULL means "run on every span regardless of type".
    applies_to_span_type TEXT,                -- 'llm' | 'tool' | 'retrieval' | 'generic' | NULL

    active          BOOLEAN NOT NULL DEFAULT true,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Quick validation: evaluator_type must be one of the known kinds.
    CONSTRAINT eval_definitions_evaluator_type_check CHECK (
        evaluator_type IN ('regex_match', 'substring_absent', 'json_schema', 'llm_judge')
    ),
    CONSTRAINT eval_definitions_span_type_check CHECK (
        applies_to_span_type IS NULL OR
        applies_to_span_type IN ('llm', 'tool', 'retrieval', 'generic')
    )
);

CREATE INDEX idx_eval_definitions_project ON eval_definitions(project_id) WHERE active = true;


-- -----------------------------------------------------------
-- eval_results: one row per (span, eval) combination
-- -----------------------------------------------------------

CREATE TABLE eval_results (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    span_id         UUID NOT NULL REFERENCES spans(id) ON DELETE CASCADE,
    eval_id         UUID NOT NULL REFERENCES eval_definitions(id) ON DELETE CASCADE,

    -- Standardized score 0.0 to 1.0
    --   rule-based evals:  0.0 (fail) or 1.0 (pass)
    --   llm_judge evals:   continuous (judge_score / max_score)
    score           DOUBLE PRECISION,

    -- Pre-computed pass/fail; redundant with score+threshold but
    -- enables fast SELECT COUNT(*) WHERE passed = false queries.
    passed          BOOLEAN,

    -- Free-text explanation. Mostly used by llm_judge; rule-based
    -- evals leave this NULL.
    reasoning       TEXT,

    -- Cost of running this evaluation. $0 for rule-based;
    -- positive for llm_judge (since it calls an LLM).
    cost_usd        NUMERIC(12, 6) DEFAULT 0,

    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Exactly one result per (span, eval). Re-running overwrites.
    CONSTRAINT eval_results_span_eval_unique UNIQUE (span_id, eval_id)
);

CREATE INDEX idx_eval_results_span ON eval_results(span_id);
CREATE INDEX idx_eval_results_eval ON eval_results(eval_id);

-- Index supporting "show me failed evals for this project, newest first"
CREATE INDEX idx_eval_results_failed ON eval_results(created_at DESC)
WHERE passed = false;