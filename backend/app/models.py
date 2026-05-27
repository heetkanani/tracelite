"""
Pydantic models for incoming/outgoing data.

These define the shape of HTTP request bodies and responses.
FastAPI uses them for validation, serialization, and OpenAPI docs.
"""
from datetime import datetime
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# -------------------------------------------------------------
# Span ingestion
# -------------------------------------------------------------

SpanType = Literal["llm", "tool", "retrieval", "generic"]
SpanStatus = Literal["ok", "error"]

class SpanCreate(BaseModel):
    """
    Shape of an incoming span from the SDK.
    ...
    """
    # Optional client-provided span ID. If omitted, server generates one.
    # Required for nested traces so the SDK can set parent_span_id
    # deterministically across siblings.
    id: Optional[UUID] = None

    # Required: which trace this belongs to (the SDK generates this UUID)
    trace_id: UUID

    # Optional: for nested spans (agents, multi-step pipelines)
    parent_span_id: Optional[UUID] = None

    # The operation being measured
    name: str = Field(..., min_length=1, max_length=200)
    span_type: SpanType

    # Timing
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_ms: Optional[int] = Field(default=None, ge=0)

    # LLM-specific (optional — nulls for non-LLM spans)
    model: Optional[str] = None
    input: Optional[Any] = None       # accepts dict, list, or string
    output: Optional[Any] = None
    input_tokens: Optional[int] = Field(default=None, ge=0)
    output_tokens: Optional[int] = Field(default=None, ge=0)
    cost_usd: Optional[float] = Field(default=None, ge=0)

    # Status
    status: SpanStatus = "ok"
    error_message: Optional[str] = None

    # Free-form bag of attributes (the OTel pattern)
    attributes: dict[str, Any] = Field(default_factory=dict)


class SpanResponse(BaseModel):
    """Shape of the response we send back after creating a span."""

    id: UUID
    trace_id: UUID

# -------------------------------------------------------------
# Trace listing & detail
# -------------------------------------------------------------

class TraceListItem(BaseModel):
    """One trace in the list view."""
    id: UUID
    name: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Aggregates (computed via LEFT JOIN in list_traces query).
    # Default to safe values so the detail endpoint can still
    # construct a TraceListItem without recomputing them.
    span_count: int = 0
    total_cost_usd: float = 0.0
    max_duration_ms: Optional[int] = None
    has_error: bool = False


class TraceListResponse(BaseModel):
    """Paginated trace list."""
    items: list[TraceListItem]
    next_cursor: Optional[str] = None


class SpanItem(BaseModel):
    """One span as returned by the API."""
    id: UUID
    trace_id: UUID
    parent_span_id: Optional[UUID] = None
    name: str
    span_type: SpanType
    started_at: datetime
    ended_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    model: Optional[str] = None
    input: Optional[Any] = None
    output: Optional[Any] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None
    status: SpanStatus
    error_message: Optional[str] = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class TraceDetailResponse(BaseModel):
    """One trace with all its spans."""
    trace: TraceListItem
    spans: list[SpanItem]