"""
Span ingestion route: POST /v1/spans

Accepts a single span from the SDK, ensures its trace exists,
inserts the span, and returns the new ID.
"""
from fastapi import APIRouter, HTTPException, Header
from app.evaluations import enqueue_span_for_eval
from typing import Annotated

from app.db import get_pool
from app.models import SpanCreate, SpanResponse
from app.queries import (
    get_project_by_api_key,
    ensure_trace_exists,
    insert_span,
)

# A router is like a mini-FastAPI app. We'll mount it under /v1 in main.py.
router = APIRouter(prefix="/v1", tags=["spans"])


@router.post("/spans", response_model=SpanResponse, status_code=201)
async def create_span(
    span: SpanCreate,
    x_api_key: Annotated[str, Header(alias="X-API-Key")],
) -> SpanResponse:
    """
    Ingest a single span.

    The trace is auto-created on first sight of its trace_id.
    Subsequent spans for the same trace_id just reuse it.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        # 1. Validate the API key by looking up its project
        project = await get_project_by_api_key(conn, x_api_key)
        if project is None:
            raise HTTPException(status_code=401, detail="Invalid API key")

        # 2. Insert the trace (if new) and the span — atomically
        async with conn.transaction():
            await ensure_trace_exists(
                conn,
                trace_id=span.trace_id,
                project_id=project["id"],
                started_at=span.started_at,
            )
            span_id = await insert_span(conn, span)

    # Background evaluation: fire-and-forget enqueue.
    # If the worker isn't running yet (e.g. early in startup), the
    # span still lands in the queue and gets evaluated whenever
    # the worker drains it.
    await enqueue_span_for_eval(str(span_id))

    return SpanResponse(id=span_id, trace_id=span.trace_id)