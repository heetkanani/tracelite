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
# Shared literal types — defined first so other models can use them
# -------------------------------------------------------------

SpanType = Literal["llm", "tool", "retrieval", "generic"]
SpanStatus = Literal["ok", "error"]
EvaluatorType = Literal["regex_match", "substring_absent", "json_schema", "llm_judge"]


# -------------------------------------------------------------
# Span ingestion
# -------------------------------------------------------------

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
    has_failed_eval: bool = False



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


class EvalResultItem(BaseModel):
    """One eval result, with denormalized eval name and type for display."""
    result_id: UUID
    span_id: UUID
    eval_id: UUID
    eval_name: str
    eval_type: EvaluatorType
    score: Optional[float] = None
    passed: Optional[bool] = None
    reasoning: Optional[str] = None
    cost_usd: float = 0.0
    created_at: datetime


class TraceDetailResponse(BaseModel):
    """One trace with all its spans, plus any eval results across the trace."""
    trace: TraceListItem
    spans: list[SpanItem]
    eval_results: list[EvalResultItem] = Field(default_factory=list)


# -------------------------------------------------------------
# Evaluations — definitions (CRUD)
# -------------------------------------------------------------

class EvalDefinitionCreate(BaseModel):
    """Shape of an incoming eval definition from the user."""
    name: str = Field(..., min_length=1, max_length=200)
    evaluator_type: EvaluatorType
    config: dict[str, Any] = Field(default_factory=dict)
    applies_to_span_type: Optional[SpanType] = None
    active: bool = True


class EvalDefinitionItem(BaseModel):
    """An eval definition as returned by the API."""
    id: UUID
    name: str
    evaluator_type: EvaluatorType
    config: dict[str, Any]
    applies_to_span_type: Optional[SpanType] = None
    active: bool
    created_at: datetime
    updated_at: datetime


class EvalDefinitionListResponse(BaseModel):
    """List of eval definitions for a project."""
    items: list[EvalDefinitionItem]


class EvalDefinitionUpdate(BaseModel):
    """Patch payload for updating an eval definition.
    Every field optional; only what's sent is updated."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    config: Optional[dict[str, Any]] = None
    applies_to_span_type: Optional[SpanType] = None
    active: Optional[bool] = None

# -------------------------------------------------------------
# Alerts
# -------------------------------------------------------------

ConditionType = Literal[
    "eval_pass_rate_below",
    "trace_error_rate_above",
]

DeliveryChannel = Literal["log", "slack_webhook", "email"]


class AlertRuleCreate(BaseModel):
    """Shape of an incoming alert rule from the user."""
    name: str = Field(..., min_length=1, max_length=200)
    condition_type: ConditionType
    config: dict[str, Any] = Field(default_factory=dict)
    delivery_channel: DeliveryChannel = "log"
    delivery_config: dict[str, Any] = Field(default_factory=dict)
    active: bool = True
    min_resend_minutes: int = Field(default=60, ge=0, le=1440)  # 0-24h


class AlertRuleItem(BaseModel):
    """An alert rule as returned by the API."""
    id: UUID
    name: str
    condition_type: ConditionType
    config: dict[str, Any]
    delivery_channel: DeliveryChannel
    delivery_config: dict[str, Any]
    active: bool
    min_resend_minutes: int
    last_evaluated_at: Optional[datetime] = None
    last_fired_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class AlertRuleListResponse(BaseModel):
    items: list[AlertRuleItem]


class AlertRuleUpdate(BaseModel):
    """Patch payload — every field optional."""
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    config: Optional[dict[str, Any]] = None
    delivery_channel: Optional[DeliveryChannel] = None
    delivery_config: Optional[dict[str, Any]] = None
    active: Optional[bool] = None
    min_resend_minutes: Optional[int] = Field(default=None, ge=0, le=1440)


class AlertEventItem(BaseModel):
    """One alert fire event."""
    id: UUID
    alert_rule_id: UUID
    fired_at: datetime
    message: str
    context: dict[str, Any]
    delivered: bool
    delivery_error: Optional[str] = None


class AlertEventListResponse(BaseModel):
    items: list[AlertEventItem]