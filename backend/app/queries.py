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
) -> list[asyncpg.Record]:
    """
    Return up to `limit` traces for a project, newest first, with aggregates.

    Optional filters:
      - status: only traces matching this aggregate status (computed via has_error)
      - span_type: only traces containing at least one span of this type
      - since: only traces started at or after this UTC datetime
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
            COUNT(s.id)::int                              AS span_count,
            COALESCE(SUM(s.cost_usd), 0)::float           AS total_cost_usd,
            MAX(s.duration_ms)                            AS max_duration_ms,
            COALESCE(BOOL_OR(s.status = 'error'), false)  AS has_error
        FROM traces t
        LEFT JOIN spans s ON s.trace_id = t.id
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