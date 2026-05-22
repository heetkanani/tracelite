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

    Mirrors the `spans` table, but only the fields the client controls.
    Server-generated fields (`id`, `created_at`) are not here.
    """

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