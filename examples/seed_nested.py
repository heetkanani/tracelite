"""
Generate realistic, nested trace data for the waterfall view.

Creates ~15 agent-like traces with:
  - A root agent_run span
  - Nested retrieval, LLM, and postprocessing spans
  - A few traces that fail to exercise the error UI
  - Varied durations so the waterfall has visual depth

Run: python examples/seed_nested.py
(Backend must be running on localhost:8000)
"""
import json
import random
import time

import httpx
from openai import OpenAI

from tracelite import init, observe, shutdown


# --- Mock OpenAI ----------------------------------------------------------

QUESTIONS = [
    "What's the weather in Paris?",
    "Summarize the latest research on transformers.",
    "Best practices for caching in distributed systems?",
    "Explain monads to a 10-year-old.",
    "How do I optimize PostgreSQL for write-heavy workloads?",
    "What's the difference between gRPC and REST?",
    "Recommend three sci-fi novels from the 1980s.",
    "Translate 'observability' into French and German.",
    "Why does my Python script hang at exit?",
    "Generate a SQL schema for a blog with comments.",
]


def fake_openai_response(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    user_msg = body["messages"][-1]["content"]
    model = body.get("model", "gpt-4o-mini")
    input_tokens = max(10, len(user_msg) // 4)
    output_tokens = random.randint(20, 120)
    return httpx.Response(200, json={
        "id": f"chatcmpl-fake-{random.randint(1000, 9999)}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": f"[Mocked answer to: {user_msg}]",
            },
            "finish_reason": "stop",
        }],
        "usage": {
            "prompt_tokens": input_tokens,
            "completion_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        },
    })


# --- @observe'd functions that form the agent shape -----------------------

@observe(name="retrieve_context", span_type="retrieval")
def retrieve_context(query: str) -> str:
    """Simulated retrieval step — varies in latency."""
    time.sleep(random.uniform(0.05, 0.25))
    return f"Retrieved 3 docs relevant to: {query[:30]}..."


@observe(name="postprocess", span_type="tool")
def postprocess(text: str) -> str:
    """Simulated cleanup step — usually fast."""
    time.sleep(random.uniform(0.01, 0.05))
    return text.strip()


@observe(name="validate_output", span_type="tool")
def validate_output(text: str) -> str:
    """A second tool call to make the waterfall deeper."""
    time.sleep(random.uniform(0.02, 0.08))
    if len(text) < 5:
        raise ValueError("Output failed validation: too short")
    return text


@observe(name="agent_run")
def agent_run(question: str, client: OpenAI) -> str:
    """Root span of a typical agent: retrieve → LLM → postprocess → validate."""
    context = retrieve_context(question)

    response = client.chat.completions.create(
        model=random.choice(["gpt-4o-mini", "gpt-4o", "gpt-4o-mini"]),
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
    )

    answer = response.choices[0].message.content
    cleaned = postprocess(answer)
    validated = validate_output(cleaned)
    return validated


# --- Main -----------------------------------------------------------------

def main():
    init(api_key="local-dev-key", base_url="http://localhost:8000")
    print("Waiting for background instrumenter...")
    time.sleep(60)
    print("Generating ~15 nested traces...")

    mock_transport = httpx.MockTransport(fake_openai_response)
    http_client = httpx.Client(transport=mock_transport)
    openai_client = OpenAI(api_key="sk-fake", http_client=http_client)

    for i in range(15):
        question = random.choice(QUESTIONS)
        try:
            agent_run(question, openai_client)
            print(f"  [{i+1}/15] ok: {question[:40]}...")
        except Exception as e:
            print(f"  [{i+1}/15] err: {type(e).__name__}: {e}")
        time.sleep(random.uniform(0.05, 0.2))

    print("Flushing...")
    shutdown()
    print("Done. Open http://localhost:3000 to see the traces.")


if __name__ == "__main__":
    main()