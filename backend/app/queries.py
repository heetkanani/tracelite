"""
Database query functions.

Each function takes a connection (or pool) and the data it needs,
and does one well-defined database operation. Routes call these.
"""
import json
from typing import Optional
from uuid import UUID

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
    """Insert a span and return its generated ID."""
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
        json.dumps(span.input) if span.input is not None else None,
        json.dumps(span.output) if span.output is not None else None,
        span.input_tokens,
        span.output_tokens,
        span.cost_usd,
        span.status,
        span.error_message,
        json.dumps(span.attributes),
    )
    return row["id"]