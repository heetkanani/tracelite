"""
Backend-side settings, especially around the OpenAI client used
by the llm_judge evaluator.

We support a mock mode so tests, demos, and dev environments
without a real OpenAI key still work.
"""
import json
import os
import random
import time
from typing import Any

import httpx


def is_openai_mocked() -> bool:
    """True when the backend should mock OpenAI calls."""
    return os.getenv("TRACELITE_MOCK_OPENAI", "0") == "1"


def get_openai_api_key() -> str:
    """The API key the backend uses for evaluator LLM calls.

    Returns a placeholder when in mock mode (the mock transport
    doesn't actually validate the key).
    """
    if is_openai_mocked():
        return "sk-mock"
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY not set. Either provide a key or set "
            "TRACELITE_MOCK_OPENAI=1 to use the mock."
        )
    return key


def _mock_transport_handler(request: httpx.Request) -> httpx.Response:
    """
    Stand-in for the OpenAI chat-completions endpoint.

    Returns a deterministic 'judge' verdict so eval tests run without
    needing a real API key. The mock alternates between high-score
    and low-score responses based on whether the user prompt contains
    common positive-signal words ('correct', 'good', 'accurate'); a
    crude heuristic, but good enough for end-to-end testing.
    """
    body = json.loads(request.content)
    messages = body.get("messages", [])
    user_msg = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

    pos_words = ["correct", "accurate", "relevant", "complete", "well"]
    score = 5 if any(w in user_msg.lower() for w in pos_words) else random.choice([1, 2, 3, 4])
    reasoning = (
        f"[mock judge] Heuristic score {score} based on keyword match in the prompt."
    )

    judge_json = {"score": score, "reasoning": reasoning}
    return httpx.Response(
        200,
        json={
            "id": f"chatcmpl-mock-{random.randint(1000, 9999)}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": body.get("model", "gpt-4o-mini"),
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": json.dumps(judge_json)},
                "finish_reason": "stop",
            }],
            "usage": {
                "prompt_tokens": max(30, len(user_msg) // 4),
                "completion_tokens": 40,
                "total_tokens": 0,
            },
        },
    )


def get_openai_client() -> Any:
    """
    Return an OpenAI client instance the backend can use.

    - Real mode: passes through OPENAI_API_KEY to a fresh client.
    - Mock mode: uses httpx.MockTransport so no network call goes out.
    """
    # Lazy import to keep startup fast and avoid circular issues.
    from openai import OpenAI

    if is_openai_mocked():
        transport = httpx.MockTransport(_mock_transport_handler)
        http_client = httpx.Client(transport=transport)
        return OpenAI(api_key="sk-mock", http_client=http_client)

    return OpenAI(api_key=get_openai_api_key())