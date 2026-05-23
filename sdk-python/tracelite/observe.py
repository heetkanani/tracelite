"""
The @observe decorator — wraps any function to capture it as a Span.

Usage:
    @observe()
    def my_function(x):
        return x * 2
"""
import asyncio
import functools
import json
from typing import Any, Callable, Optional

from tracelite.client import get_client
from tracelite.span import Span, new_trace_id


def observe(
    name: Optional[str] = None,
    span_type: str = "generic",
):
    """
    Decorator that traces a function call as a Span.

    Works on both sync and async functions.

    Args:
        name: Override the span name (defaults to the function's name).
        span_type: One of "llm" | "tool" | "retrieval" | "generic".
    """
    def decorator(func: Callable) -> Callable:
        # --- Async branch ----------------------------------------------------
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                client = get_client()
                if client is None or not client.enabled:
                    return await func(*args, **kwargs)

                span = Span(
                    trace_id=new_trace_id(),
                    name=name or func.__name__,
                    span_type=span_type,
                    input=_safe_serialize({"args": args, "kwargs": kwargs}),
                )
                try:
                    result = await func(*args, **kwargs)
                    span.output = _safe_serialize(result)
                    return result
                except Exception as e:
                    span.status = "error"
                    span.error_message = f"{type(e).__name__}: {e}"
                    raise
                finally:
                    span.finish()
                    _emit(span)
            return async_wrapper

        # --- Sync branch -----------------------------------------------------
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            client = get_client()
            if client is None or not client.enabled:
                return func(*args, **kwargs)

            span = Span(
                trace_id=new_trace_id(),
                name=name or func.__name__,
                span_type=span_type,
                input=_safe_serialize({"args": args, "kwargs": kwargs}),
            )
            try:
                result = func(*args, **kwargs)
                span.output = _safe_serialize(result)
                return result
            except Exception as e:
                span.status = "error"
                span.error_message = f"{type(e).__name__}: {e}"
                raise
            finally:
                span.finish()
                _emit(span)

        return sync_wrapper

    return decorator

def _safe_serialize(value: Any) -> Any:
    """
    Convert a value into something JSON-friendly.
    Falls back to str() if it's not natively serializable.
    """
    try:
        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return str(value)


def _emit(span: Span) -> None:
    """Hand the span off to the background sender (non-blocking)."""
    client = get_client()
    if client is None or client.sender is None:
        return
    client.sender.submit(span)