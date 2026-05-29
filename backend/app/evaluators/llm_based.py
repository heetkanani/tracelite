"""
LLM-as-judge evaluator.

Calls another LLM to score a span. Used for subjective qualities
(relevance, factual accuracy, tone) that rule-based evals can't catch.
"""
import json
from typing import Any

from app.evaluators.base import EvalOutcome, register_evaluator
from app.settings import get_openai_client


# Default judge prompt — a "scoring rubric" the LLM follows.
# Users can override via config.prompt; the default is "relevance".
_DEFAULT_PROMPT = (
    "You are evaluating an AI assistant's response. "
    "Score the response from 1 to 5 on relevance to the user's input.\n\n"
    "1 = completely irrelevant\n"
    "3 = somewhat relevant\n"
    "5 = directly addresses the input\n\n"
    "Respond with JSON only, in this exact shape:\n"
    "{\"score\": <1-5>, \"reasoning\": \"<one short sentence>\"}"
)

# Default model — cheapest reasonable judge.
_DEFAULT_MODEL = "gpt-4o-mini"

# Default max score (so we can normalize to 0-1).
_DEFAULT_MAX_SCORE = 5

# Default pass threshold (>= this raw score = passed).
_DEFAULT_MIN_PASS = 3


# Pricing for cost tracking. Kept here (not imported from SDK) because the
# SDK pricing table is in a different package and importing across the
# SDK/backend boundary is uglier than duplicating 6 lines.
_JUDGE_PRICING = {
    "gpt-4o":         {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":    {"input": 0.15,  "output": 0.60},
    "gpt-4-turbo":    {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo":  {"input": 0.50,  "output": 1.50},
}


def _estimate_judge_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """USD cost of the judge call. Returns 0 for unknown models."""
    for known in sorted(_JUDGE_PRICING.keys(), key=len, reverse=True):
        if model.startswith(known):
            rates = _JUDGE_PRICING[known]
            return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
    return 0.0


def _serialize_for_prompt(value: Any) -> str:
    """Turn any span input/output into a string the judge can read."""
    if value is None:
        return "(none)"
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        return repr(value)


@register_evaluator("llm_judge")
def llm_judge(span_row: dict, config: dict) -> EvalOutcome:
    """
    Score the span by asking another LLM.

    config = {
        "prompt": "...",          # rubric (default: relevance scoring)
        "model": "gpt-4o-mini",   # which model judges
        "max_score": 5,           # raw scale upper bound (default 5)
        "min_pass": 3,            # raw score >= this = passed (default 3)
    }
    """
    prompt = config.get("prompt", _DEFAULT_PROMPT)
    model = config.get("model", _DEFAULT_MODEL)
    max_score = int(config.get("max_score", _DEFAULT_MAX_SCORE))
    min_pass = int(config.get("min_pass", _DEFAULT_MIN_PASS))

    user_input = _serialize_for_prompt(span_row.get("input"))
    assistant_output = _serialize_for_prompt(span_row.get("output"))

    # Compose the request: judge prompt + the original exchange to evaluate.
    judge_messages = [
        {"role": "system", "content": prompt},
        {
            "role": "user",
            "content": (
                "INPUT TO ASSISTANT:\n"
                f"{user_input}\n\n"
                "ASSISTANT RESPONSE:\n"
                f"{assistant_output}"
            ),
        },
    ]

    # Call the LLM. Any failure -> a "skipped" outcome so the worker
    # keeps going on the next span instead of stopping the whole batch.
    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model=model,
            messages=judge_messages,
            response_format={"type": "json_object"},
        )
    except Exception as e:
        return EvalOutcome(
            score=None,
            passed=None,
            reasoning=f"Judge call failed: {type(e).__name__}: {e}",
            cost_usd=0.0,
        )

    # Parse the verdict from the judge's reply.
    raw_content = response.choices[0].message.content or ""
    try:
        verdict = json.loads(raw_content)
        raw_score = int(verdict.get("score", 0))
        reasoning = str(verdict.get("reasoning", ""))[:500]  # cap at 500 chars
    except (json.JSONDecodeError, ValueError, TypeError):
        return EvalOutcome(
            score=None,
            passed=None,
            reasoning=f"Could not parse judge reply: {raw_content[:200]}",
            cost_usd=_compute_response_cost(response, model),
        )

    # Clamp score and normalize to 0.0-1.0.
    raw_score = max(0, min(raw_score, max_score))
    normalized = raw_score / max_score if max_score > 0 else 0.0
    passed = raw_score >= min_pass

    return EvalOutcome(
        score=normalized,
        passed=passed,
        reasoning=reasoning,
        cost_usd=_compute_response_cost(response, model),
    )


def _compute_response_cost(response: Any, model: str) -> float:
    """Helper: pull usage off the OpenAI response and compute USD cost."""
    try:
        usage = response.usage
        return _estimate_judge_cost(model, usage.prompt_tokens, usage.completion_tokens)
    except AttributeError:
        return 0.0