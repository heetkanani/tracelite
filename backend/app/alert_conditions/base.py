"""
Base types and dispatcher for alert conditions.

A "condition" decides whether an alert rule should fire right now.
Each implementation takes a DB connection + the rule row, queries
whatever data it needs, and returns a ConditionOutcome.
"""
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional, Any

import asyncpg


@dataclass
class ConditionOutcome:
    """
    The result of checking one rule.

    should_fire = True → write an alert_event and deliver it
    should_fire = False → record only that we checked, no event
    """
    should_fire: bool
    message: str = ""
    context: dict[str, Any] = field(default_factory=dict)


# Async-callable registry. Keyed by condition_type string.
ConditionFunc = Callable[[asyncpg.Connection, dict], Awaitable[ConditionOutcome]]
_REGISTRY: dict[str, ConditionFunc] = {}


def register_condition(condition_type: str):
    """Decorator: register a function as the impl of a condition type."""
    def decorator(func: ConditionFunc) -> ConditionFunc:
        if condition_type in _REGISTRY:
            raise ValueError(f"Condition '{condition_type}' already registered")
        _REGISTRY[condition_type] = func
        return func
    return decorator


async def check_condition(
    condition_type: str,
    conn: asyncpg.Connection,
    rule_row: dict,
) -> ConditionOutcome:
    """
    Dispatch to the registered condition for this type.

    Unknown types return a non-firing outcome so the worker keeps
    making progress instead of stopping on a single bad rule.
    """
    impl = _REGISTRY.get(condition_type)
    if impl is None:
        return ConditionOutcome(
            should_fire=False,
            message=f"Condition type '{condition_type}' not implemented",
        )
    return await impl(conn, rule_row)


def registered_types() -> list[str]:
    return sorted(_REGISTRY.keys())