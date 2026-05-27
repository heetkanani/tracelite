"""
Tracing context propagation.

A single ContextVar holds the (trace_id, span_id) of the currently
active span. When a new @observe'd function runs:
  - It reads the current context to find its parent (if any)
  - It pushes itself as the new context
  - When it returns, it pops back to what was there before

This is async-safe by design — Python's ContextVar gives each asyncio
task its own context automatically.
"""
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Optional
from uuid import UUID, uuid4


@dataclass(frozen=True)
class SpanContext:
    """The two IDs needed to link a child span to its parent."""
    trace_id: UUID
    span_id: UUID


# The ContextVar holds None when no span is active.
_current: ContextVar[Optional[SpanContext]] = ContextVar(
    "tracelite_current_span",
    default=None,
)


def get_current() -> Optional[SpanContext]:
    """Return the currently active span context, or None if none."""
    return _current.get()


def push(span_id: UUID, trace_id: Optional[UUID] = None) -> "ContextToken":
    """
    Push a new span context. Returns a token used to restore later.

    If trace_id is None and there's an active context, inherit its
    trace_id (this span is a child of the current span). Otherwise,
    a fresh trace_id is generated (this span is a new root).
    """
    parent = _current.get()
    if trace_id is None:
        trace_id = parent.trace_id if parent else uuid4()
    new_ctx = SpanContext(trace_id=trace_id, span_id=span_id)
    token = _current.set(new_ctx)
    return ContextToken(token=token, span_context=new_ctx)


def pop(token: "ContextToken") -> None:
    """Restore the previous span context."""
    _current.reset(token.token)


@dataclass
class ContextToken:
    """Opaque handle returned by push(), passed to pop()."""
    token: object
    span_context: SpanContext