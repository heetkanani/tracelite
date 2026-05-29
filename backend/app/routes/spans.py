"""
Span ingestion route: POST /v1/spans

Accepts a single span from the SDK, ensures its trace exists,
inserts the span, and returns the new ID.

Authentication: accepts either an X-API-Key header (SDK calls) or a
session cookie. SDK ingestion almost always uses the API key path.
"""
from typing import Annotated

from fastapi import APIRouter, Depends

from app.db import get_pool
from app.dependencies import AuthContext, get_current_auth, resolve_project_id
from app.evaluations import enqueue_span_for_eval
from app.models import SpanCreate, SpanResponse
from app.queries import (
    ensure_trace_exists,
    insert_span,
)

# A router is like a mini-FastAPI app. We'll mount it under /v1 in main.py.
router = APIRouter(prefix="/v1", tags=["spans"])


@router.post("/spans", response_model=SpanResponse, status_code=201)
async def create_span(
    span: SpanCreate,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
) -> SpanResponse:
    """
    Ingest a single span.

    The trace is auto-created on first sight of its trace_id.
    Subsequent spans for the same trace_id just reuse it.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        # 1. Resolve the project from auth context (API key or session)
        project_id = await resolve_project_id(auth, conn)

        # 2. Insert the trace (if new) and the span — atomically
        async with conn.transaction():
            await ensure_trace_exists(
                conn,
                trace_id=span.trace_id,
                project_id=project_id,
                started_at=span.started_at,
            )
            span_id = await insert_span(conn, span)

    # Background evaluation: fire-and-forget enqueue.
    # If the worker isn't running yet (e.g. early in startup), the
    # span still lands in the queue and gets evaluated whenever
    # the worker drains it.
    await enqueue_span_for_eval(str(span_id))

    return SpanResponse(id=span_id, trace_id=span.trace_id)