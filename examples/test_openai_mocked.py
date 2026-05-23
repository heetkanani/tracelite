"""
End-to-end test of the OpenAI auto-instrumentation.

We use httpx's MockTransport to intercept calls to api.openai.com,
so no real API key (or money) is needed. The instrumented OpenAI SDK
sees a normal response and emits a span exactly as it would in prod.

Run: python examples/test_openai_mocked.py
(Backend must be running on localhost:8000.)
"""
import json
import time

import httpx
from openai import OpenAI

from tracelite import init, shutdown


# --- 1. Build a fake OpenAI server response ----------------------------------

def fake_openai_response(request: httpx.Request) -> httpx.Response:
    """Mock the OpenAI chat completions endpoint."""
    body = json.loads(request.content)
    user_message = body["messages"][-1]["content"]
    response = {
        "id": "chatcmpl-fake-123",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.get("model", "gpt-4o-mini"),
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": f"Mocked reply to: {user_message}",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 12,
            "completion_tokens": 8,
            "total_tokens": 20,
        },
    }
    return httpx.Response(200, json=response)


# --- 2. Initialize tracelite and wait for the background patcher ------------

init(api_key="local-dev-key", base_url="http://localhost:8000")
print("Waiting for background instrumenter to finish...")
time.sleep(60)   # Windows-Defender slowness; remove on faster machines
print("Done waiting.")


# --- 3. Create an OpenAI client that uses the mock transport ----------------

mock_transport = httpx.MockTransport(fake_openai_response)
http_client = httpx.Client(transport=mock_transport)
client = OpenAI(api_key="sk-fake", http_client=http_client)


# --- 4. Make some calls ------------------------------------------------------

print("Making 3 mocked OpenAI calls...")
for i in range(3):
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": f"hello number {i}"}],
    )
    print(f"  call {i}: {resp.choices[0].message.content}")


# --- 5. Flush -----------------------------------------------------------------

print("Shutting down (flushes pending spans)...")
shutdown()
print("Done.")