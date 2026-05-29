"""
Tracelite evaluators package.

Importing this module loads and registers all evaluator implementations.
Add new evaluators by creating a new module and importing it here.
"""
from app.evaluators.base import (
    EvalOutcome,
    register_evaluator,
    run_evaluator,
    registered_types,
)

# Import implementation modules so their @register_evaluator decorators run.
# (Import order doesn't matter; the registry is keyed by string.)
from app.evaluators import rule_based  # noqa: F401
from app.evaluators import llm_based   # noqa: F401

__all__ = [
    "EvalOutcome",
    "register_evaluator",
    "run_evaluator",
    "registered_types",
]