"""
Tracelite alert conditions package.

Importing this module loads and registers all condition implementations.
"""
from app.alert_conditions.base import (
    ConditionOutcome,
    check_condition,
    register_condition,
    registered_types,
)

# Side-effect imports — each module registers its conditions via decorator.
from app.alert_conditions import eval_conditions  # noqa: F401

__all__ = [
    "ConditionOutcome",
    "check_condition",
    "register_condition",
    "registered_types",
]