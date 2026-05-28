"""
Evaluation worker — runs eval definitions against spans.

Today (Session 1): triggered manually via POST /v1/evals/{id}/run.
Session 2 will add automatic firing when new spans arrive.
"""
from typing import Optional
from uuid import UUID

import asyncpg

from app.evaluators import run_evaluator
from app.queries import (
    get_eval_definition,
    list_spans_for_eval_run,
    upsert_eval_result,
)


async def run_eval_against_recent_spans(
    conn: asyncpg.Connection,
    eval_id: UUID,
    project_id: UUID,
    limit: int = 100,
) -> dict:
    """
    Apply one eval definition to up to `limit` recent matching spans.

    Returns a summary: how many were evaluated, how many passed, how
    many failed, how many couldn't be scored.
    """
    eval_def = await get_eval_definition(conn, eval_id, project_id)
    if eval_def is None:
        raise ValueError(f"Eval {eval_id} not found in project {project_id}")

    if not eval_def["active"]:
        return {
            "evaluated": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "reason": "Eval is paused (active=false)",
        }

    spans = await list_spans_for_eval_run(
        conn,
        project_id=project_id,
        applies_to_span_type=eval_def["applies_to_span_type"],
        limit=limit,
    )

    evaluated = 0
    passed = 0
    failed = 0
    skipped = 0
    total_cost = 0.0

    for span in spans:
        outcome = run_evaluator(
            evaluator_type=eval_def["evaluator_type"],
            span_row=dict(span),
            config=eval_def["config"],
        )

        await upsert_eval_result(
            conn,
            span_id=span["id"],
            eval_id=eval_id,
            score=outcome.score,
            passed=outcome.passed,
            reasoning=outcome.reasoning,
            cost_usd=outcome.cost_usd,
        )

        evaluated += 1
        total_cost += outcome.cost_usd
        if outcome.passed is True:
            passed += 1
        elif outcome.passed is False:
            failed += 1
        else:
            skipped += 1

    return {
        "evaluated": evaluated,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "total_cost_usd": round(total_cost, 6),
    }