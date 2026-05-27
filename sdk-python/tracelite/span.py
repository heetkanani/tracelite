"""
The Span dataclass — the SDK's internal representation of one operation.

Spans are constructed by @observe (and later by auto-instrumentation),
serialized to JSON, and sent to the backend's POST /v1/spans endpoint.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID, uuid4


@dataclass
class Span:
    """One traced operation. Mirrors the backend's spans table."""

    # Identity
    trace_id: UUID
    name: str
    span_type: str = "generic"  # "llm" | "tool" | "retrieval" | "generic"
    parent_span_id: Optional[UUID] = None
    # Client-generated id. Set by the decorator before pushing onto context.
    # The backend will use this id when inserting (enables parent_span_id
    # references from sibling spans to resolve correctly).
    id: Optional[UUID] = None

    # Client-generated id, used by the decorator to know its own id BEFORE
    # creating the Span (so it can push itself onto context). Backend
    # currently ignores this and generates its own id, but having it here
    # is essential for parent_span_id linking from siblings.
    id_override: Optional[UUID] = None

    # Timing
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ended_at: Optional[datetime] = None
    duration_ms: Optional[int] = None

    # LLM-specific
    model: Optional[str] = None
    input: Optional[Any] = None
    output: Optional[Any] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cost_usd: Optional[float] = None

    # Status
    status: str = "ok"
    error_message: Optional[str] = None

    # Free-form
    attributes: dict[str, Any] = field(default_factory=dict)

    def finish(self) -> None:
        """Mark the span as complete and compute duration."""
        if self.ended_at is None:
            self.ended_at = datetime.now(timezone.utc)
        delta = self.ended_at - self.started_at
        self.duration_ms = int(delta.total_seconds() * 1000)

    def to_payload(self) -> dict:
        """Serialize to the JSON shape the backend expects."""
        data = asdict(self)
        # UUIDs and datetimes must be strings for JSON
        if self.id is not None:
            data["id"] = str(self.id)
        else:
            data.pop("id", None)
        data["trace_id"] = str(self.trace_id)
        if self.parent_span_id is not None:
            data["parent_span_id"] = str(self.parent_span_id)
        data["started_at"] = self.started_at.isoformat()
        if self.ended_at is not None:
            data["ended_at"] = self.ended_at.isoformat()
        return data

def new_trace_id() -> UUID:
    """Generate a fresh trace ID. Public so users can correlate manually."""
    return uuid4()