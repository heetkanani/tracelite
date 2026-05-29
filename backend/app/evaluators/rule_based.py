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

# ----------------------------------------------------------------------
# json_schema: pass if the output matches a basic shape spec
# ----------------------------------------------------------------------

@register_evaluator("json_schema")
def json_schema(span_row: dict, config: dict) -> EvalOutcome:
    """
    config = {
        "type": "object",                       # optional: "object" | "array" | "string" | "number" | "boolean"
        "required_keys": ["answer", "sources"], # optional: keys that must exist (for type=object)
    }

    Passes when the span's output matches all configured checks.
    A minimalist subset of JSON Schema — enough to catch the common
    "LLM returned the wrong shape" bug.
    """
    output = span_row.get("output")

    # If the LLM auto-instrumentation captured an OpenAI response, the
    # output is wrapped as {"role": "assistant", "content": "..."}.
    # The user's *real* payload is in content (often a JSON string they
    # asked the model to produce). Unwrap so the eval works as expected.
    payload = _unwrap_content(output)

    # Strings that look like JSON should be parsed first so we can check
    # the parsed structure, not the wrapper string.
    parsed = _maybe_parse_json(payload)
    if parsed is None and payload is not None:
        # Caller asked for schema validation on something that isn't JSON.
        return EvalOutcome(
            score=0.0,
            passed=False,
            reasoning="Output is not valid JSON",
        )

    target = parsed if parsed is not None else payload

    # Check 1: expected top-level type
    expected_type = config.get("type")
    if expected_type:
        actual_type = _json_type_of(target)
        if actual_type != expected_type:
            return EvalOutcome(
                score=0.0,
                passed=False,
                reasoning=f"Expected type {expected_type}, got {actual_type}",
            )

    # Check 2: required keys (only meaningful for objects)
    required_keys = config.get("required_keys")
    if required_keys:
        if not isinstance(target, dict):
            return EvalOutcome(
                score=0.0,
                passed=False,
                reasoning="required_keys check expects an object",
            )
        missing = [k for k in required_keys if k not in target]
        if missing:
            return EvalOutcome(
                score=0.0,
                passed=False,
                reasoning=f"Missing required keys: {', '.join(missing)}",
            )

    return EvalOutcome(score=1.0, passed=True, reasoning=None)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _unwrap_content(output: Any) -> Any:
    """
    OpenAI's instrumentation stores assistant messages as
        {"role": "assistant", "content": "..."}.
    For schema validation, we usually care about the content payload,
    not the wrapper. If the shape matches, return content; else passthrough.
    """
    if isinstance(output, dict) and set(output.keys()) <= {"role", "content"} and "content" in output:
        return output["content"]
    return output


def _maybe_parse_json(value: Any) -> Any:
    """Try to parse a JSON string. Return None if it isn't a string or fails."""
    import json
    if not isinstance(value, str):
        return value if not isinstance(value, str) else None
    s = value.strip()
    if not s:
        return None
    if s[0] not in "{[\"" and s not in ("true", "false", "null"):
        return None
    try:
        return json.loads(s)
    except (ValueError, json.JSONDecodeError):
        return None


def _json_type_of(value: Any) -> str:
    """Map a Python value to its JSON Schema 'type' name."""
    if value is None:
        return "null"
    if isinstance(value, bool):  # check before int — bool is a subclass of int
        return "boolean"
    if isinstance(value, int) or isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "unknown"