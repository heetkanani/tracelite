"""
Rule-based evaluators: cheap, deterministic, no LLM calls.

Each evaluator function takes (span_row, config) and returns an
EvalOutcome. They're auto-registered via the @register_evaluator
decorator imported from base.py.
"""
import re
from typing import Any

from app.evaluators.base import EvalOutcome, register_evaluator


def _extract_text(span_row: dict) -> str:
    """
    Get a plain-text representation of the span's output, so we can
    apply substring / regex checks to it uniformly regardless of
    whether the output is a dict, list, string, or None.
    """
    output = span_row.get("output")
    if output is None:
        return ""
    if isinstance(output, str):
        return output
    # For dicts/lists, fall back to a string dump.
    # Common case: OpenAI returns {"role": "assistant", "content": "..."}
    if isinstance(output, dict):
        content = output.get("content")
        if isinstance(content, str):
            return content
    # Last resort — repr handles anything; might be noisy but won't crash.
    return repr(output)


# ----------------------------------------------------------------------
# substring_absent: pass if a given text does NOT appear in the output
# ----------------------------------------------------------------------

@register_evaluator("substring_absent")
def substring_absent(span_row: dict, config: dict) -> EvalOutcome:
    """
    config = {"text": "I dont know", "case_sensitive": false}

    Passes when the configured text does NOT appear in the span's output.
    Used to catch refusals, hallucination markers, or any banned phrase.
    """
    target: Any = config.get("text", "")
    if not isinstance(target, str) or not target:
        return EvalOutcome(
            score=None,
            passed=None,
            reasoning="config.text is missing or empty",
        )

    case_sensitive = bool(config.get("case_sensitive", False))
    haystack = _extract_text(span_row)

    if case_sensitive:
        found = target in haystack
    else:
        found = target.lower() in haystack.lower()

    return EvalOutcome(
        score=0.0 if found else 1.0,
        passed=not found,
        reasoning=None,
    )


# ----------------------------------------------------------------------
# regex_match: pass if a given regex matches the output
# ----------------------------------------------------------------------

@register_evaluator("regex_match")
def regex_match(span_row: dict, config: dict) -> EvalOutcome:
    """
    config = {"pattern": "^Answer:", "flags": "i"}

    Passes when the configured regex matches anywhere in the output.
    Flags are an optional string like "i" (case-insensitive),
    "m" (multiline), "s" (dotall), or combinations like "im".
    """
    pattern_str: Any = config.get("pattern", "")
    if not isinstance(pattern_str, str) or not pattern_str:
        return EvalOutcome(
            score=None,
            passed=None,
            reasoning="config.pattern is missing or empty",
        )

    # Compile flags from the string spec.
    flag_str = config.get("flags", "")
    if not isinstance(flag_str, str):
        flag_str = ""
    flags = 0
    if "i" in flag_str:
        flags |= re.IGNORECASE
    if "m" in flag_str:
        flags |= re.MULTILINE
    if "s" in flag_str:
        flags |= re.DOTALL

    try:
        compiled = re.compile(pattern_str, flags)
    except re.error as e:
        return EvalOutcome(
            score=None,
            passed=None,
            reasoning=f"Invalid regex: {e}",
        )

    haystack = _extract_text(span_row)
    matched = bool(compiled.search(haystack))

    return EvalOutcome(
        score=1.0 if matched else 0.0,
        passed=matched,
        reasoning=None,
    )