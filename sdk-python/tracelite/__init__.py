"""
tracelite — open-source observability SDK for LLM apps.

Public API:
    init(api_key, base_url=...)
    observe()                    # decorator
    shutdown()                   # optional explicit shutdown
"""
from tracelite.client import init, get_client, shutdown
from tracelite.observe import observe

__all__ = ["init", "observe", "get_client", "shutdown"]
__version__ = "0.0.1"