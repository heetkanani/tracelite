"""
Base types and dispatcher for alert delivery channels.

A "delivery" sends a fired alert somewhere — to a log, to Slack,
to email. Each channel takes the rule row and the fire details,
ships the message, and reports success/failure.
"""
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional, Any


@dataclass
class DeliveryResult:
    """
    Whether the alert was successfully delivered.

    error_message is set when delivered=False; useful for displaying
    "alert fired but Slack call failed" in the dashboard later.
    """
    delivered: bool
    error_message: Optional[str] = None


DeliveryFunc = Callable[
    [dict, str, dict],   # rule_row, message, context
    Awaitable[DeliveryResult],
]
_REGISTRY: dict[str, DeliveryFunc] = {}


def register_delivery(channel: str):
    """Decorator: register a function as the impl of a delivery channel."""
    def decorator(func: DeliveryFunc) -> DeliveryFunc:
        if channel in _REGISTRY:
            raise ValueError(f"Delivery channel '{channel}' already registered")
        _REGISTRY[channel] = func
        return func
    return decorator


async def deliver_alert(
    channel: str,
    rule_row: dict,
    message: str,
    context: dict[str, Any],
) -> DeliveryResult:
    """
    Send the alert through the requested channel.

    Unknown channels are treated as "delivered with a warning" — the
    fire still gets recorded in alert_events so users can see it.
    """
    impl = _REGISTRY.get(channel)
    if impl is None:
        return DeliveryResult(
            delivered=False,
            error_message=f"Delivery channel '{channel}' not implemented",
        )
    try:
        return await impl(rule_row, message, context)
    except Exception as e:
        # Never let a misbehaving delivery channel kill the worker.
        return DeliveryResult(
            delivered=False,
            error_message=f"{type(e).__name__}: {e}",
        )


def registered_channels() -> list[str]:
    return sorted(_REGISTRY.keys())