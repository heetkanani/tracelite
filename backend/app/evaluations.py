"""
Evaluation worker — runs eval definitions against spans.

Two modes:
  1. On-demand: POST /v1/evals/{id}/run kicks off run_eval_against_recent_spans
  2. Automatic: background worker drains a queue of newly-arrived spans
                and runs all active evals against each.
"""
import asyncio
import logging
from typing import Optional
from uuid import UUID

import asyncpg

from app.db import get_pool
from app.evaluators import run_evaluator
from app.queries import (
    get_eval_definition,
    list_eval_definitions,
    list_spans_for_eval_run,
    upsert_eval_result,
)

logger = logging.getLogger("tracelite.evals")


# ----------------------------------------------------------------------
# Manual eval run (called by POST /v1/evals/{id}/run)
# ----------------------------------------------------------------------

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


# ----------------------------------------------------------------------
# Background evaluation worker
# ----------------------------------------------------------------------

# Module-level queue. Holds span IDs waiting to be evaluated.
# Used by enqueue_span_for_eval() (producer) and _worker_loop() (consumer).
_job_queue: Optional[asyncio.Queue[str]] = None

# Reference to the worker task so we can cancel it on shutdown.
_worker_task: Optional[asyncio.Task] = None


def get_job_queue() -> asyncio.Queue[str]:
    """Lazy-init the queue. Must be called from inside the event loop."""
    global _job_queue
    if _job_queue is None:
        _job_queue = asyncio.Queue(maxsize=10_000)
    return _job_queue


async def enqueue_span_for_eval(span_id: str) -> None:
    """
    Mark a newly-inserted span for background evaluation.

    Non-blocking: if the queue is somehow full (10K spans backed up),
    we drop the job and log. Better to lose an eval than to slow down
    the ingest path.
    """
    queue = get_job_queue()
    try:
        queue.put_nowait(span_id)
    except asyncio.QueueFull:
        logger.warning("Eval queue full; dropping span_id=%s", span_id)


async def _worker_loop() -> None:
    """
    Long-running consumer. Pulls span_ids off the queue and runs all
    active evaluations for that span's project.

    Exits cleanly on cancellation (during app shutdown).
    """
    queue = get_job_queue()
    logger.info("Eval worker started")
    try:
        while True:
            span_id_str = await queue.get()
            try:
                await _evaluate_one_span(span_id_str)
            except Exception:
                # Never let a bad span kill the worker. Log + continue.
                logger.exception("Eval worker error on span_id=%s", span_id_str)
            finally:
                queue.task_done()
    except asyncio.CancelledError:
        logger.info("Eval worker cancelled; exiting")
        raise


async def _evaluate_one_span(span_id_str: str) -> None:
    """
    For one span: look up its project, find active evals, run each.

    Each eval result is written via the same upsert path as the
    manual /run endpoint, so re-arriving spans don't duplicate results.
    """
    span_uuid = UUID(span_id_str)
    pool = get_pool()

    async with pool.acquire() as conn:
        # One round-trip to fetch the span (with project_id via the trace)
        # plus its fields we need to score against.
        span_row = await conn.fetchrow(
            """
            SELECT s.id, s.span_type, s.input, s.output, t.project_id
            FROM spans s
            JOIN traces t ON t.id = s.trace_id
            WHERE s.id = $1
            """,
            span_uuid,
        )
        if span_row is None:
            logger.warning("Span %s not found; skipping eval", span_uuid)
            return

        project_id = span_row["project_id"]

        # Pull active evals for this project.
        eval_defs = await list_eval_definitions(
            conn, project_id=project_id, active_only=True
        )

        # Filter to evals that apply to this span's type (or are universal).
        applicable = [
            e for e in eval_defs
            if e["applies_to_span_type"] is None
            or e["applies_to_span_type"] == span_row["span_type"]
        ]

        if not applicable:
            return  # Nothing to do.

        # Run each eval. We could parallelize with asyncio.gather, but
        # serial keeps order predictable and is fine for v1.
        for eval_def in applicable:
            outcome = run_evaluator(
                evaluator_type=eval_def["evaluator_type"],
                span_row=dict(span_row),
                config=eval_def["config"],
            )
            await upsert_eval_result(
                conn,
                span_id=span_row["id"],
                eval_id=eval_def["id"],
                score=outcome.score,
                passed=outcome.passed,
                reasoning=outcome.reasoning,
                cost_usd=outcome.cost_usd,
            )


# ----------------------------------------------------------------------
# Lifecycle hooks (called from main.py)
# ----------------------------------------------------------------------

async def start_eval_worker() -> None:
    """Start the background eval task. Called from FastAPI startup."""
    global _worker_task
    if _worker_task is not None:
        return  # Already running
    _worker_task = asyncio.create_task(_worker_loop(), name="eval_worker")
    logger.info("Eval worker task created")


async def stop_eval_worker() -> None:
    """Cleanly stop the worker. Called from FastAPI shutdown."""
    global _worker_task, _job_queue
    if _worker_task is None:
        return
    _worker_task.cancel()
    try:
        await _worker_task
    except asyncio.CancelledError:
        pass
    _worker_task = None
    _job_queue = None
    logger.info("Eval worker stopped")