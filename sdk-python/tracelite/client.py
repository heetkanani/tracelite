"""
Client config + singleton for the tracelite SDK.

Users call init() once at app startup; everything else reads from
the module-level _client.
"""

import threading
from dataclasses import dataclass
from typing import Optional

from tracelite.sender import BackgroundSender


@dataclass
class Client:
    """Holds runtime config and the background sender."""
    api_key: str
    base_url: str = "http://localhost:8000"
    enabled: bool = True
    sender: Optional[BackgroundSender] = None


# Module-level singleton. Populated by init().
_client: Optional[Client] = None


def init(
    api_key: str,
    base_url: str = "http://localhost:8000",
    enabled: bool = True,
    instrument: bool = True,
) -> None:
    """
    Initialize the SDK. Call once at app startup.

    Args:
        api_key: Your tracelite project API key.
        base_url: The tracelite backend URL.
        enabled: Set False to disable all tracing.
        instrument: Auto-patch known LLM libraries (currently OpenAI).
                    Runs in a background thread so init() returns
                    immediately even if `import openai` is slow.
    """
    global _client

    if _client is not None and _client.sender is not None:
        _client.sender.shutdown()

    sender = BackgroundSender(base_url=base_url, api_key=api_key) if enabled else None
    _client = Client(
        api_key=api_key,
        base_url=base_url,
        enabled=enabled,
        sender=sender,
    )

    if enabled and instrument:
        # Don't block init() on potentially-slow library imports.
        threading.Thread(
            target=_auto_instrument,
            name="tracelite-instrumenter",
            daemon=True,
        ).start()


def _auto_instrument() -> None:
    """Patch every supported LLM library that's importable."""
    # OpenAI
    try:
        from tracelite.integrations.openai import instrument_openai
        instrument_openai()
    except Exception as e:
        # Never crash init() because of an instrumentation failure
        print(f"[tracelite] openai instrumentation failed: {e}")


def get_client() -> Optional[Client]:
    """Return the active client, or None if init() wasn't called."""
    return _client


def shutdown() -> None:
    """Cleanly stop the background sender. Optional — atexit handles it too."""
    global _client
    if _client is not None and _client.sender is not None:
        _client.sender.shutdown()
        _client = None