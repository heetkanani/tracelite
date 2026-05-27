"""
Trace listing & detail routes.

GET /v1/traces           — paginated list, newest first
GET /v1/traces/{id}      — one trace with all its spans
"""
from typing import Annotated, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, HTTPException, Header, Query

from app.db import get_pool
from app.models import (
    SpanItem,
    TraceDetailResponse,
    TraceListItem,
    TraceListResponse,
)
from app.pagination import encode_cursor, parse_optional_cursor
from app.queries import (
    get_project_by_api_key,
    get_trace_by_id,
    list_spans_for_trace,
    list_traces,
)

router = APIRouter(prefix="/v1", tags=["traces"])


@router.get("/traces", response_model=TraceListResponse)
async def list_traces_endpoint(
    x_api_key: Annotated[str, Header(alias="X-API-Key")],
    cursor: Optional[str] = Query(default=None),
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    status: Optional[str] = Query(
        default=None,
        pattern="^(ok|error)$",
        description="Filter traces by aggregate status",
    ),
    span_type: Optional[str] = Query(
        default=None,
        pattern="^(llm|tool|retrieval|generic)$",
        description="Include only traces with at least one span of this type",
    ),
    since: Optional[datetime] = Query(
        default=None,
        description="Include only traces started at or after this UTC datetime",
    ),
) -> TraceListResponse:
    """List traces newest-first, cursor-paginated, with optional filters."""
    pool = get_pool()

    parsed_cursor = parse_optional_cursor(cursor)

    async with pool.acquire() as conn:
        project = await get_project_by_api_key(conn, x_api_key)
        if project is None:
            raise HTTPException(status_code=401, detail="Invalid API key")

        rows = await list_traces(
            conn,
            project_id=project["id"],
            cursor=parsed_cursor,
            limit=limit,
            status=status,
            span_type=span_type,
            since=since,
        )

    items = [TraceListItem(**dict(r)) for r in rows]

    # Build next_cursor from the last row, if a full page came back.
    next_cursor: Optional[str] = None
    if len(rows) == limit:
        last = rows[-1]
        next_cursor = encode_cursor(last["started_at"], last["id"])

    return TraceListResponse(items=items, next_cursor=next_cursor)


@router.get("/traces/{trace_id}", response_model=TraceDetailResponse)
async def get_trace_endpoint(
    trace_id: UUID,
    x_api_key: Annotated[str, Header(alias="X-API-Key")],
) -> TraceDetailResponse:
    """Fetch one trace and all its spans."""
    pool = get_pool()

    async with pool.acquire() as conn:
        project = await get_project_by_api_key(conn, x_api_key)
        if project is None:
            raise HTTPException(status_code=401, detail="Invalid API key")

        trace_row = await get_trace_by_id(
            conn, trace_id=trace_id, project_id=project["id"]
        )
        if trace_row is None:
            raise HTTPException(status_code=404, detail="Trace not found")

        span_rows = await list_spans_for_trace(conn, trace_id=trace_id)

    return TraceDetailResponse(
        trace=TraceListItem(**dict(trace_row)),
        spans=[SpanItem(**dict(r)) for r in span_rows],
    )