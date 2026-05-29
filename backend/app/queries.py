"""
Database query functions.

Each function takes a connection (or pool) and the data it needs,
and does one well-defined database operation. Routes call these.
"""
from typing import Optional
from uuid import UUID
from datetime import datetime
import asyncpg

from app.models import SpanCreate


# -------------------------------------------------------------
# Project lookup — we'll use this for API key validation later
# -------------------------------------------------------------

async def get_project_by_api_key(
    conn: asyncpg.Connection,
    api_key: str,
) -> Optional[asyncpg.Record]:
    """Return the project row matching this API key, or None."""
    return await conn.fetchrow(
        "SELECT id, name FROM projects WHERE api_key = $1",
        api_key,
    )


# -------------------------------------------------------------
# Trace upsert — auto-create a trace row if one doesn't exist
# -------------------------------------------------------------

async def ensure_trace_exists(
    conn: asyncpg.Connection,
    trace_id: UUID,
    project_id: UUID,
    started_at,
) -> None:
    """
    Insert a trace row if one with this ID doesn't already exist.

    This lets the SDK send spans freely without separately creating traces.
    The first span for a trace creates it; later spans reuse it.
    """
    await conn.execute(
        """
        INSERT INTO traces (id, project_id, started_at)
        VALUES ($1, $2, $3)
        ON CONFLICT (id) DO NOTHING
        """,
        trace_id, project_id, started_at,
    )


# -------------------------------------------------------------
# Span insert
# -------------------------------------------------------------

async def insert_span(
    conn: asyncpg.Connection,
    span: SpanCreate,
) -> UUID:
    """
    Insert a span and return its ID.

    If span.id is provided (modern SDK with context propagation),
    we use it so parent_span_id links from sibling spans are valid.
    Otherwise the DB generates one.

    Note: JSONB values (input, output, attributes) are passed as
    Python dicts directly — asyncpg's registered JSONB codec
    handles the encoding. Do NOT json.dumps() these here; that
    causes double-encoding and corrupts the stored JSON.
    """
    if span.id is not None:
        # Client supplied an id — use it (required for parent-child linking).
        row = await conn.fetchrow(
            """
            INSERT INTO spans (
                id, trace_id, parent_span_id, name, span_type,
                started_at, ended_at, duration_ms,
                model, input, output,
                input_tokens, output_tokens, cost_usd,
                status, error_message, attributes
            )
            VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, $8,
                $9, $10, $11,
                $12, $13, $14,
                $15, $16, $17
            )
            ON CONFLICT (id) DO NOTHING
            RETURNING id
            """,
            span.id,
            span.trace_id,
            span.parent_span_id,
            span.name,
            span.span_type,
            span.started_at,
            span.ended_at,
            span.duration_ms,
            span.model,
            span.input,
            span.output,
            span.input_tokens,
            span.output_tokens,
            span.cost_usd,
            span.status,
            span.error_message,
            span.attributes,
        )
        if row is None:
            # Conflict — span with this id already exists. Return the existing id.
            return span.id
        return row["id"]

    # No client id — old SDK or test caller. Let DB generate.
    row = await conn.fetchrow(
        """
        INSERT INTO spans (
            trace_id, parent_span_id, name, span_type,
            started_at, ended_at, duration_ms,
            model, input, output,
            input_tokens, output_tokens, cost_usd,
            status, error_message, attributes
        )
        VALUES (
            $1, $2, $3, $4,
            $5, $6, $7,
            $8, $9, $10,
            $11, $12, $13,
            $14, $15, $16
        )
        RETURNING id
        """,
        span.trace_id,
        span.parent_span_id,
        span.name,
        span.span_type,
        span.started_at,
        span.ended_at,
        span.duration_ms,
        span.model,
        span.input,
        span.output,
        span.input_tokens,
        span.output_tokens,
        span.cost_usd,
        span.status,
        span.error_message,
        span.attributes,
    )
    return row["id"]


# -------------------------------------------------------------
# Trace listing (cursor-paginated)
# -------------------------------------------------------------

async def list_traces(
    conn: asyncpg.Connection,
    project_id: UUID,
    cursor: Optional[tuple] = None,
    limit: int = 50,
    status: Optional[str] = None,           # 'ok' | 'error' | None
    span_type: Optional[str] = None,        # 'llm' | 'tool' | 'retrieval' | 'generic' | None
    since: Optional[datetime] = None,       # filter traces with started_at >= this
    has_failed_eval: Optional[bool] = None, # True = only traces with eval failures
) -> list[asyncpg.Record]:
    """
    Return up to `limit` traces for a project, newest first, with aggregates.

    Optional filters:
      - status: only traces matching this aggregate status (computed via has_error)
      - span_type: only traces containing at least one span of this type
      - since: only traces started at or after this UTC datetime
      - has_failed_eval: when True, only traces with at least one failed eval result
    """
    # Build parameter list dynamically. $1 is always project_id.
    params: list = [project_id]

    # Optional WHERE clauses we'll AND together.
    where_clauses: list[str] = ["t.project_id = $1"]

    if since is not None:
        params.append(since)
        where_clauses.append(f"t.started_at >= ${len(params)}")

    if span_type is not None:
        # "Traces with at least one span of this type" — subquery is clearest.
        params.append(span_type)
        where_clauses.append(
            f"EXISTS (SELECT 1 FROM spans WHERE trace_id = t.id AND span_type = ${len(params)})"
        )

    if cursor is not None:
        cursor_ts, cursor_id = cursor
        params.append(cursor_ts)
        params.append(cursor_id)
        where_clauses.append(
            f"(t.started_at, t.id) < (${len(params) - 1}, ${len(params)})"
        )

    # HAVING applies to aggregate results; we need it for status filtering
    # because has_error is computed from the LEFT JOIN aggregation.
    having_clauses: list[str] = []
    if status == "error":
        having_clauses.append("COALESCE(BOOL_OR(s.status = 'error'), false) = true")
    elif status == "ok":
        having_clauses.append("COALESCE(BOOL_OR(s.status = 'error'), false) = false")

    # has_failed_eval is also an aggregate -> goes in HAVING.
    if has_failed_eval is True:
        having_clauses.append("COALESCE(BOOL_OR(er.passed = false), false) = true")
    elif has_failed_eval is False:
        having_clauses.append("COALESCE(BOOL_OR(er.passed = false), false) = false")

    # The LIMIT param is always last.
    params.append(limit)
    limit_placeholder = f"${len(params)}"

    where_sql = " AND ".join(where_clauses)
    having_sql = (
        "HAVING " + " AND ".join(having_clauses) if having_clauses else ""
    )

    sql = f"""
        SELECT
            t.id,
            t.name,
            t.started_at,
            t.ended_at,
            t.user_id,
            t.session_id,
            t.metadata,
            COUNT(DISTINCT s.id)::int                       AS span_count,
            COALESCE(SUM(DISTINCT s.cost_usd), 0)::float    AS total_cost_usd,
            MAX(s.duration_ms)                              AS max_duration_ms,
            COALESCE(BOOL_OR(s.status = 'error'), false)    AS has_error,
            COALESCE(BOOL_OR(er.passed = false), false)     AS has_failed_eval
        FROM traces t
        LEFT JOIN spans s ON s.trace_id = t.id
        LEFT JOIN eval_results er ON er.span_id = s.id
        WHERE {where_sql}
        GROUP BY t.id
        {having_sql}
        ORDER BY t.started_at DESC, t.id DESC
        LIMIT {limit_placeholder}
    """

    return await conn.fetch(sql, *params)


# -------------------------------------------------------------
# Trace detail with all its spans
# -------------------------------------------------------------

async def get_trace_by_id(
    conn: asyncpg.Connection,
    trace_id: UUID,
    project_id: UUID,
) -> Optional[asyncpg.Record]:
    """
    Fetch one trace with span aggregates, scoped to a project.

    Aggregates match the trace list query so the detail header shows
    consistent numbers (cost, duration, span count, error status).
    """
    return await conn.fetchrow(
        """
        SELECT
            t.id, t.name, t.started_at, t.ended_at,
            t.user_id, t.session_id, t.metadata,
            COUNT(s.id)::int                              AS span_count,
            COALESCE(SUM(s.cost_usd), 0)::float           AS total_cost_usd,
            MAX(s.duration_ms)                            AS max_duration_ms,
            COALESCE(BOOL_OR(s.status = 'error'), false)  AS has_error
        FROM traces t
        LEFT JOIN spans s ON s.trace_id = t.id
        WHERE t.id = $1 AND t.project_id = $2
        GROUP BY t.id
        """,
        trace_id, project_id,
    )


async def list_spans_for_trace(
    conn: asyncpg.Connection,
    trace_id: UUID,
) -> list[asyncpg.Record]:
    """Return all spans for a trace, ordered by start time (oldest first)."""
    return await conn.fetch(
        """
        SELECT
            id, trace_id, parent_span_id, name, span_type,
            started_at, ended_at, duration_ms,
            model, input, output,
            input_tokens, output_tokens, cost_usd,
            status, error_message, attributes
        FROM spans
        WHERE trace_id = $1
        ORDER BY started_at ASC
        """,
        trace_id,
    )

# -------------------------------------------------------------
# Evaluation definitions — CRUD
# -------------------------------------------------------------

async def insert_eval_definition(
    conn: asyncpg.Connection,
    project_id: UUID,
    name: str,
    evaluator_type: str,
    config: dict,
    applies_to_span_type: Optional[str],
    active: bool,
) -> asyncpg.Record:
    """Insert a new eval definition and return the inserted row."""
    return await conn.fetchrow(
        """
        INSERT INTO eval_definitions (
            project_id, name, evaluator_type, config,
            applies_to_span_type, active
        )
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id, name, evaluator_type, config,
                  applies_to_span_type, active, created_at, updated_at
        """,
        project_id, name, evaluator_type, config,
        applies_to_span_type, active,
    )


async def list_eval_definitions(
    conn: asyncpg.Connection,
    project_id: UUID,
    active_only: bool = False,
) -> list[asyncpg.Record]:
    """Return all eval definitions for a project, newest first."""
    if active_only:
        sql = """
            SELECT id, name, evaluator_type, config,
                   applies_to_span_type, active, created_at, updated_at
            FROM eval_definitions
            WHERE project_id = $1 AND active = true
            ORDER BY created_at DESC
        """
    else:
        sql = """
            SELECT id, name, evaluator_type, config,
                   applies_to_span_type, active, created_at, updated_at
            FROM eval_definitions
            WHERE project_id = $1
            ORDER BY created_at DESC
        """
    return await conn.fetch(sql, project_id)


async def get_eval_definition(
    conn: asyncpg.Connection,
    eval_id: UUID,
    project_id: UUID,
) -> Optional[asyncpg.Record]:
    """Fetch one eval definition, scoped to a project."""
    return await conn.fetchrow(
        """
        SELECT id, name, evaluator_type, config,
               applies_to_span_type, active, created_at, updated_at
        FROM eval_definitions
        WHERE id = $1 AND project_id = $2
        """,
        eval_id, project_id,
    )


async def update_eval_definition(
    conn: asyncpg.Connection,
    eval_id: UUID,
    project_id: UUID,
    name: Optional[str] = None,
    config: Optional[dict] = None,
    applies_to_span_type: Optional[str] = None,
    active: Optional[bool] = None,
) -> Optional[asyncpg.Record]:
    """
    Update only the provided fields. Returns the updated row, or None
    if no eval with that id exists in the project.
    """
    # Build SET clause dynamically based on which fields are non-None.
    # We use COALESCE so unset fields keep their existing value.
    return await conn.fetchrow(
        """
        UPDATE eval_definitions
        SET
            name = COALESCE($3, name),
            config = COALESCE($4, config),
            applies_to_span_type = CASE WHEN $5::text IS NOT NULL THEN $5 ELSE applies_to_span_type END,
            active = COALESCE($6, active),
            updated_at = now()
        WHERE id = $1 AND project_id = $2
        RETURNING id, name, evaluator_type, config,
                  applies_to_span_type, active, created_at, updated_at
        """,
        eval_id, project_id, name, config, applies_to_span_type, active,
    )


async def delete_eval_definition(
    conn: asyncpg.Connection,
    eval_id: UUID,
    project_id: UUID,
) -> bool:
    """Delete an eval definition. Returns True if a row was deleted."""
    result = await conn.execute(
        """
        DELETE FROM eval_definitions
        WHERE id = $1 AND project_id = $2
        """,
        eval_id, project_id,
    )
    # execute() returns a string like "DELETE 1" or "DELETE 0"
    return result.split()[-1] != "0"

# -------------------------------------------------------------
# Evaluation results — upsert pattern
# -------------------------------------------------------------

async def upsert_eval_result(
    conn: asyncpg.Connection,
    span_id: UUID,
    eval_id: UUID,
    score: Optional[float],
    passed: Optional[bool],
    reasoning: Optional[str],
    cost_usd: float,
) -> asyncpg.Record:
    """
    Insert an eval result, or overwrite if one exists for this (span, eval).

    The UNIQUE (span_id, eval_id) constraint on eval_results means we
    can use ON CONFLICT to make re-running an eval idempotent: the new
    result replaces the old one, no duplicates.
    """
    return await conn.fetchrow(
        """
        INSERT INTO eval_results (
            span_id, eval_id, score, passed, reasoning, cost_usd
        )
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (span_id, eval_id) DO UPDATE SET
            score       = EXCLUDED.score,
            passed      = EXCLUDED.passed,
            reasoning   = EXCLUDED.reasoning,
            cost_usd    = EXCLUDED.cost_usd,
            created_at  = now()
        RETURNING id, span_id, eval_id, score, passed, reasoning, cost_usd, created_at
        """,
        span_id, eval_id, score, passed, reasoning, cost_usd,
    )


async def list_spans_for_eval_run(
    conn: asyncpg.Connection,
    project_id: UUID,
    applies_to_span_type: Optional[str],
    limit: int = 100,
) -> list[asyncpg.Record]:
    """
    Fetch recent spans this eval should run against.

    Filters by span_type when the eval specifies one. Newest first.
    """
    if applies_to_span_type is None:
        sql = """
            SELECT s.id, s.trace_id, s.name, s.span_type, s.output
            FROM spans s
            JOIN traces t ON t.id = s.trace_id
            WHERE t.project_id = $1
            ORDER BY s.started_at DESC
            LIMIT $2
        """
        return await conn.fetch(sql, project_id, limit)

    sql = """
        SELECT s.id, s.trace_id, s.name, s.span_type, s.output
        FROM spans s
        JOIN traces t ON t.id = s.trace_id
        WHERE t.project_id = $1 AND s.span_type = $2
        ORDER BY s.started_at DESC
        LIMIT $3
    """
    return await conn.fetch(sql, project_id, applies_to_span_type, limit)

# -------------------------------------------------------------
# Eval results — for a whole trace
# -------------------------------------------------------------

async def list_eval_results_for_trace(
    conn: asyncpg.Connection,
    trace_id: UUID,
) -> list[asyncpg.Record]:
    """
    All eval results for every span in this trace, joined with the
    eval definitions so the frontend has names and types ready to render.
    """
    return await conn.fetch(
        """
        SELECT
            er.id              AS result_id,
            er.span_id,
            er.eval_id,
            er.score,
            er.passed,
            er.reasoning,
            er.cost_usd,
            er.created_at,
            ed.name            AS eval_name,
            ed.evaluator_type  AS eval_type
        FROM eval_results er
        JOIN spans s ON s.id = er.span_id
        JOIN eval_definitions ed ON ed.id = er.eval_id
        WHERE s.trace_id = $1
        ORDER BY er.created_at DESC
        """,
        trace_id,
    )

# -------------------------------------------------------------
# Alert rules — CRUD
# -------------------------------------------------------------

async def insert_alert_rule(
    conn: asyncpg.Connection,
    project_id: UUID,
    name: str,
    condition_type: str,
    config: dict,
    delivery_channel: str,
    delivery_config: dict,
    active: bool,
    min_resend_minutes: int,
) -> asyncpg.Record:
    """Insert a new alert rule and return the row."""
    return await conn.fetchrow(
        """
        INSERT INTO alert_rules (
            project_id, name, condition_type, config,
            delivery_channel, delivery_config,
            active, min_resend_minutes
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        RETURNING id, name, condition_type, config,
                  delivery_channel, delivery_config,
                  active, min_resend_minutes,
                  last_evaluated_at, last_fired_at,
                  created_at, updated_at
        """,
        project_id, name, condition_type, config,
        delivery_channel, delivery_config,
        active, min_resend_minutes,
    )


async def list_alert_rules(
    conn: asyncpg.Connection,
    project_id: UUID,
    active_only: bool = False,
) -> list[asyncpg.Record]:
    """Return alert rules for a project, newest first."""
    sql = """
        SELECT id, name, condition_type, config,
               delivery_channel, delivery_config,
               active, min_resend_minutes,
               last_evaluated_at, last_fired_at,
               created_at, updated_at
        FROM alert_rules
        WHERE project_id = $1
    """
    if active_only:
        sql += " AND active = true"
    sql += " ORDER BY created_at DESC"
    return await conn.fetch(sql, project_id)


async def get_alert_rule(
    conn: asyncpg.Connection,
    rule_id: UUID,
    project_id: UUID,
) -> Optional[asyncpg.Record]:
    """Fetch one alert rule, scoped to a project."""
    return await conn.fetchrow(
        """
        SELECT id, name, condition_type, config,
               delivery_channel, delivery_config,
               active, min_resend_minutes,
               last_evaluated_at, last_fired_at,
               created_at, updated_at
        FROM alert_rules
        WHERE id = $1 AND project_id = $2
        """,
        rule_id, project_id,
    )


async def update_alert_rule(
    conn: asyncpg.Connection,
    rule_id: UUID,
    project_id: UUID,
    name: Optional[str] = None,
    config: Optional[dict] = None,
    delivery_channel: Optional[str] = None,
    delivery_config: Optional[dict] = None,
    active: Optional[bool] = None,
    min_resend_minutes: Optional[int] = None,
) -> Optional[asyncpg.Record]:
    """Update only provided fields. None = leave alone."""
    return await conn.fetchrow(
        """
        UPDATE alert_rules
        SET
            name               = COALESCE($3, name),
            config             = COALESCE($4, config),
            delivery_channel   = COALESCE($5, delivery_channel),
            delivery_config    = COALESCE($6, delivery_config),
            active             = COALESCE($7, active),
            min_resend_minutes = COALESCE($8, min_resend_minutes),
            updated_at         = now()
        WHERE id = $1 AND project_id = $2
        RETURNING id, name, condition_type, config,
                  delivery_channel, delivery_config,
                  active, min_resend_minutes,
                  last_evaluated_at, last_fired_at,
                  created_at, updated_at
        """,
        rule_id, project_id, name, config,
        delivery_channel, delivery_config, active, min_resend_minutes,
    )


async def delete_alert_rule(
    conn: asyncpg.Connection,
    rule_id: UUID,
    project_id: UUID,
) -> bool:
    """Delete an alert rule. True if a row was deleted."""
    result = await conn.execute(
        "DELETE FROM alert_rules WHERE id = $1 AND project_id = $2",
        rule_id, project_id,
    )
    return result.split()[-1] != "0"


# -------------------------------------------------------------
# Alert rules — used by the background worker
# -------------------------------------------------------------

async def list_alert_rules_due_for_evaluation(
    conn: asyncpg.Connection,
    older_than_seconds: int = 300,
) -> list[asyncpg.Record]:
    """
    Pull active alert rules across all projects that haven't been
    evaluated in the last `older_than_seconds` seconds.

    Used by the background worker — runs every minute or so.
    `NULLS FIRST` ensures brand-new rules (never evaluated) come first.

    Note: make_interval(secs => $1) lets us pass an integer parameter
    cleanly. The earlier approach using string concatenation forced
    asyncpg to infer $1 as text and reject our int input.
    """
    return await conn.fetch(
        """
        SELECT id, project_id, name, condition_type, config,
               delivery_channel, delivery_config,
               min_resend_minutes,
               last_evaluated_at, last_fired_at
        FROM alert_rules
        WHERE active = true
          AND (
              last_evaluated_at IS NULL
              OR last_evaluated_at < now() - make_interval(secs => $1)
          )
        ORDER BY last_evaluated_at ASC NULLS FIRST
        LIMIT 100
        """,
        older_than_seconds,
    )

async def mark_alert_rule_evaluated(
    conn: asyncpg.Connection,
    rule_id: UUID,
) -> None:
    """Set last_evaluated_at = now(). Called after every check."""
    await conn.execute(
        "UPDATE alert_rules SET last_evaluated_at = now() WHERE id = $1",
        rule_id,
    )


async def mark_alert_rule_fired(
    conn: asyncpg.Connection,
    rule_id: UUID,
) -> None:
    """Set last_fired_at = now(). Called only when the rule fires."""
    await conn.execute(
        "UPDATE alert_rules SET last_fired_at = now() WHERE id = $1",
        rule_id,
    )


# -------------------------------------------------------------
# Alert events
# -------------------------------------------------------------

async def insert_alert_event(
    conn: asyncpg.Connection,
    alert_rule_id: UUID,
    message: str,
    context: dict,
    delivered: bool,
    delivery_error: Optional[str],
) -> asyncpg.Record:
    """Record one fire event."""
    return await conn.fetchrow(
        """
        INSERT INTO alert_events (
            alert_rule_id, message, context, delivered, delivery_error
        )
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, alert_rule_id, fired_at, message, context,
                  delivered, delivery_error
        """,
        alert_rule_id, message, context, delivered, delivery_error,
    )


async def list_alert_events(
    conn: asyncpg.Connection,
    project_id: UUID,
    limit: int = 50,
) -> list[asyncpg.Record]:
    """
    Recent alert events for a project, newest first.
    JOINs through alert_rules to scope by project.
    """
    return await conn.fetch(
        """
        SELECT ae.id, ae.alert_rule_id, ae.fired_at, ae.message,
               ae.context, ae.delivered, ae.delivery_error
        FROM alert_events ae
        JOIN alert_rules ar ON ar.id = ae.alert_rule_id
        WHERE ar.project_id = $1
        ORDER BY ae.fired_at DESC
        LIMIT $2
        """,
        project_id, limit,
    )