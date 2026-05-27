"""
OpenAI auto-instrumentation for tracelite.

Calling instrument_openai() monkey-patches OpenAI's chat.completions.create
to emit a Span for every call. Both sync (OpenAI) and async (AsyncOpenAI)
clients are patched.
"""
import functools
from typing import Any

from tracelite.client import get_client
from tracelite.span import Span, new_trace_id
from uuid import uuid4
from tracelite import context

# USD per 1M tokens. Update as new models ship.
# Source: openai.com/api/pricing (snapshot, not live).
_PRICING: dict[str, dict[str, float]] = {
    "gpt-4o":          {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":     {"input": 0.15,  "output": 0.60},
    "gpt-4-turbo":     {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo":   {"input": 0.50,  "output": 1.50},
    "o1-mini":         {"input": 3.00,  "output": 12.00},
    "o1":              {"input": 15.00, "output": 60.00},
}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float | None:
    """
    Return cost in USD, or None if we don't know this model.
    Matches the LONGEST known prefix first so "gpt-4o-mini" doesn't
    accidentally match "gpt-4o".
    """
    # Sort keys longest-first so the most specific match wins.
    for known in sorted(_PRICING.keys(), key=len, reverse=True):
        if model.startswith(known):
            rates = _PRICING[known]
            return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
    return None

def _extract_output(response: Any) -> Any:
    """Pull the assistant's reply out of an OpenAI ChatCompletion."""
    try:
        choice = response.choices[0]
        message = choice.message
        return {
            "role": message.role,
            "content": message.content,
        }
    except Exception:
        return None


def _extract_usage(response: Any) -> tuple[int | None, int | None]:
    """Pull (input_tokens, output_tokens) from a ChatCompletion, or (None, None)."""
    try:
        usage = response.usage
        return usage.prompt_tokens, usage.completion_tokens
    except Exception:
        return None, None
    
def _build_llm_span(model: str, messages: Any) -> Span:
    """
    Start an LLM span. Caller fills in output and finishes it.

    Reads parent from the current tracing context — so if this call
    happens inside an @observe'd function, the resulting span is
    nested correctly. If there's no active context, this is a root.
    """
    from uuid import uuid4
    from tracelite import context

    parent_ctx = context.get_current()
    span_id = uuid4()
    trace_id = parent_ctx.trace_id if parent_ctx else uuid4()

    return Span(
        id=span_id,
        trace_id=trace_id,
        parent_span_id=parent_ctx.span_id if parent_ctx else None,
        name="openai.chat.completions.create",
        span_type="llm",
        model=model,
        input=messages,
    )


def _finalize_span(span: Span, response: Any) -> None:
    """Populate a span from a successful OpenAI response."""
    span.output = _extract_output(response)
    input_tokens, output_tokens = _extract_usage(response)
    span.input_tokens = input_tokens
    span.output_tokens = output_tokens
    if span.model and input_tokens is not None and output_tokens is not None:
        span.cost_usd = _estimate_cost(span.model, input_tokens, output_tokens)
    span.finish()


def _emit(span: Span) -> None:
    """Hand the span off to the background sender (non-blocking)."""
    client = get_client()
    if client is None or client.sender is None:
        return
    client.sender.submit(span)

def instrument_openai() -> None:
    """
    Monkey-patch openai.resources.chat.completions.{Completions,AsyncCompletions}
    so every .create() call emits a Span.

    Safe to call multiple times — applies the patch only once.
    """
    try:
        import openai
        from openai.resources.chat.completions import Completions, AsyncCompletions
    except ImportError:
        # openai not installed → silently do nothing
        return

    # Guard against double-patching (e.g. user calls init() twice)
    if getattr(Completions, "_tracelite_patched", False):
        return

    _patch_sync(Completions)
    _patch_async(AsyncCompletions)

    Completions._tracelite_patched = True
    AsyncCompletions._tracelite_patched = True


def _patch_sync(cls) -> None:
    original_create = cls.create

    @functools.wraps(original_create)
    def wrapper(self, *args, **kwargs):
        client = get_client()
        # SDK off → call through unchanged
        if client is None or not client.enabled:
            return original_create(self, *args, **kwargs)

        model = kwargs.get("model", "unknown")
        messages = kwargs.get("messages")
        span = _build_llm_span(model, messages)

        try:
            response = original_create(self, *args, **kwargs)
            _finalize_span(span, response)
            return response
        except Exception as e:
            span.status = "error"
            span.error_message = f"{type(e).__name__}: {e}"
            span.finish()
            raise
        finally:
            _emit(span)

    cls.create = wrapper


def _patch_async(cls) -> None:
    original_create = cls.create

    @functools.wraps(original_create)
    async def wrapper(self, *args, **kwargs):
        client = get_client()
        if client is None or not client.enabled:
            return await original_create(self, *args, **kwargs)

        model = kwargs.get("model", "unknown")
        messages = kwargs.get("messages")
        span = _build_llm_span(model, messages)

        try:
            response = await original_create(self, *args, **kwargs)
            _finalize_span(span, response)
            return response
        except Exception as e:
            span.status = "error"
            span.error_message = f"{type(e).__name__}: {e}"
            span.finish()
            raise
        finally:
            _emit(span)

    cls.create = wrapper