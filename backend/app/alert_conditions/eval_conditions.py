"""
Conditions that look at eval_results.
"""
from datetime import datetime, timedelta, timezone

import asyncpg

from app.alert_conditions.base import ConditionOutcome, register_condition


@register_condition("eval_pass_rate_below")
async def eval_pass_rate_below(
    conn: asyncpg.Connection,
    rule_row: dict,
) -> ConditionOutcome:
    """
    Fire when the rolling pass rate of a specific eval falls below a threshold.

    config:
      eval_id          — which eval to watch (required)
      threshold        — minimum acceptable pass rate, 0.0-1.0 (required)
      window_minutes   — look-back window in minutes (default 60)
      min_sample_size  — don't fire if fewer than this many results (default 5)
    """
    config = rule_row["config"]
    eval_id = config.get("eval_id")
    threshold = config.get("threshold")
    window_minutes = int(config.get("window_minutes", 60))
    min_sample_size = int(config.get("min_sample_size", 5))

    # Defensive: bad config -> don't fire, but explain why.
    if not eval_id or threshold is None:
        return ConditionOutcome(
            should_fire=False,
            message="Config missing eval_id or threshold",
        )

    window_start = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)

    row = await conn.fetchrow(
        """
        SELECT
            COUNT(*)                                     AS total,
            COUNT(*) FILTER (WHERE passed = true)        AS passed,
            COUNT(*) FILTER (WHERE passed = false)       AS failed
        FROM eval_results
        WHERE eval_id = $1
          AND created_at >= $2
          AND passed IS NOT NULL
        """,
        eval_id, window_start,
    )

    total = row["total"] or 0
    passed = row["passed"] or 0

    # Not enough data: stay quiet.
    if total < min_sample_size:
        return ConditionOutcome(
            should_fire=False,
            message=f"Only {total} results in window (need >= {min_sample_size})",
        )

    pass_rate = passed / total

    if pass_rate < threshold:
        return ConditionOutcome(
            should_fire=True,
            message=(
                f"Pass rate {pass_rate:.0%} below threshold {threshold:.0%} "
                f"({passed}/{total} passed in last {window_minutes}m)"
            ),
            context={
                "observed_pass_rate": pass_rate,
                "threshold": threshold,
                "passed": passed,
                "failed": row["failed"] or 0,
                "total": total,
                "window_minutes": window_minutes,
            },
        )

    return ConditionOutcome(
        should_fire=False,
        message=f"Pass rate {pass_rate:.0%} at or above threshold",
    )