"""
Base types and dispatcher for evaluators.

Each evaluator is a function with signature:
    (span_row: dict, config: dict) -> EvalOutcome

The dispatcher picks the right function based on the eval
definition's evaluator_type string.
"""
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class EvalOutcome:
    """The result of running one evaluator against one span."""
    # Standardized 0.0 to 1.0. None for "couldn't evaluate this span".
    score: Optional[float]
    # Pass/fail. None for "couldn't evaluate".
    passed: Optional[bool]
    # Optional explanation. Mostly used by llm_judge; rule-based leave it None.
    reasoning: Optional[str] = None
    # USD cost of running this eval. 0 for rule-based; positive for llm_judge.
    cost_usd: float = 0.0


# Registry mapping evaluator_type string -> implementation function.
# Filled in via @register_evaluator decorator on each implementation.
_REGISTRY: dict[str, Callable] = {}


def register_evaluator(evaluator_type: str):
    """Decorator: register a function as the implementation of an evaluator type."""
    def decorator(func: Callable) -> Callable:
        if evaluator_type in _REGISTRY:
            raise ValueError(f"Evaluator '{evaluator_type}' already registered")
        _REGISTRY[evaluator_type] = func
        return func
    return decorator


def run_evaluator(
    evaluator_type: str,
    span_row: dict,
    config: dict,
) -> EvalOutcome:
    """
    Dispatch to the registered evaluator for this type.

    If no evaluator is registered (e.g. llm_judge before Session 2),
    returns an empty outcome rather than crashing — so the worker
    keeps making progress.
    """
    impl = _REGISTRY.get(evaluator_type)
    if impl is None:
        return EvalOutcome(
            score=None,
            passed=None,
            reasoning=f"Evaluator '{evaluator_type}' not implemented",
        )
    return impl(span_row, config)


def registered_types() -> list[str]:
    """For diagnostics — what evaluators are available."""
    return sorted(_REGISTRY.keys())