"""
Alert worker — periodically checks alert rules and fires events.

Architecturally similar to evaluations.py:
  - Background asyncio task started via lifespan hooks
  - Polls the DB for "rules due for evaluation"
  - Dispatches to the condition + delivery registries
  - Records every fire in alert_events

Unlike the eval worker (which reacts to span arrivals), this worker
is purely periodic — there's no queue, just a sleep/poll loop.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.alert_conditions import check_condition
from app.alert_delivery import deliver_alert
from app.db import get_pool
from app.queries import (
    insert_alert_event,
    list_alert_rules_due_for_evaluation,
    mark_alert_rule_evaluated,
    mark_alert_rule_fired,
)

logger = logging.getLogger("tracelite.alerts")

# Polling interval. Tuned for dev — 60s gives reasonably-prompt alerts
# while keeping DB load minimal. Production might tune this lower.
WORKER_INTERVAL_SECONDS = 60

# A rule is "due" if its last_evaluated_at is older than this.
EVALUATION_STALENESS_SECONDS = 60

# Reference to the worker task so we can cancel cleanly on shutdown.
_worker_task: Optional[asyncio.Task] = None


# ----------------------------------------------------------------------
# Core: one pass through all due rules
# ----------------------------------------------------------------------

async def _run_one_pass() -> None:
    """
    Pull all rules due for evaluation, check each, fire if needed.
    Runs inside a fresh DB connection per pass so connections aren't
    held while the worker sleeps.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rules = await list_alert_rules_due_for_evaluation(
            conn, older_than_seconds=EVALUATION_STALENESS_SECONDS
        )

    if not rules:
        return  # Nothing to do.

    logger.debug("Alert worker: checking %d rules", len(rules))

    for rule in rules:
        try:
            await _check_one_rule(dict(rule))
        except Exception:
            # Per-rule isolation: a buggy condition or delivery shouldn't
            # stop us from checking the rest.
            logger.exception(
                "Alert worker error on rule_id=%s", rule["id"]
            )


async def _check_one_rule(rule: dict) -> None:
    """
    Evaluate one rule end-to-end.

    Steps:
      1. Open a fresh connection (one per rule = clean transactional scope)
      2. Check the condition
      3. Mark evaluated (always — so we don't re-check this rule for a while)
      4. If condition fired AND we're past the cooldown:
         - Deliver
         - Write alert_event
         - Mark fired
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        outcome = await check_condition(
            condition_type=rule["condition_type"],
            conn=conn,
            rule_row=rule,
        )

        # Always record that we looked. Even when not firing.
        await mark_alert_rule_evaluated(conn, rule["id"])

        if not outcome.should_fire:
            logger.debug(
                "Rule %s did not fire: %s", rule["name"], outcome.message
            )
            return

        # Cooldown check: don't re-fire too soon after the last fire.
        if _is_in_cooldown(rule):
            logger.debug(
                "Rule %s would fire but is in cooldown (until %s)",
                rule["name"],
                _cooldown_until(rule),
            )
            return

        # Fire: deliver + persist event + mark fired.
        delivery = await deliver_alert(
            channel=rule["delivery_channel"],
            rule_row=rule,
            message=outcome.message,
            context=outcome.context,
        )
        await insert_alert_event(
            conn,
            alert_rule_id=rule["id"],
            message=outcome.message,
            context=outcome.context,
            delivered=delivery.delivered,
            delivery_error=delivery.error_message,
        )
        await mark_alert_rule_fired(conn, rule["id"])
        logger.info(
            "🚨 Rule fired: %s (delivered=%s)",
            rule["name"], delivery.delivered,
        )


def _is_in_cooldown(rule: dict) -> bool:
    """True if we recently fired this rule and shouldn't re-fire yet."""
    last_fired = rule.get("last_fired_at")
    if last_fired is None:
        return False
    cooldown = timedelta(minutes=rule["min_resend_minutes"])
    return datetime.now(timezone.utc) - last_fired < cooldown


def _cooldown_until(rule: dict) -> Optional[datetime]:
    """When the cooldown ends. For logging only."""
    last_fired = rule.get("last_fired_at")
    if last_fired is None:
        return None
    return last_fired + timedelta(minutes=rule["min_resend_minutes"])


# ----------------------------------------------------------------------
# Worker loop — runs forever until cancelled
# ----------------------------------------------------------------------

async def _worker_loop() -> None:
    """
    Long-running poller. Sleeps between passes so we don't burn CPU.
    Exits cleanly on cancellation.
    """
    logger.info("Alert worker started (interval=%ds)", WORKER_INTERVAL_SECONDS)
    try:
        while True:
            try:
                await _run_one_pass()
            except Exception:
                # Outer safety net — if _run_one_pass itself fails (e.g.
                # DB connection issues), we log and keep cycling.
                logger.exception("Alert worker pass failed")
            await asyncio.sleep(WORKER_INTERVAL_SECONDS)
    except asyncio.CancelledError:
        logger.info("Alert worker cancelled; exiting")
        raise


# ----------------------------------------------------------------------
# Lifecycle hooks (called from main.py)
# ----------------------------------------------------------------------

async def start_alert_worker() -> None:
    """Start the background alert task. Called from FastAPI startup."""
    global _worker_task
    if _worker_task is not None:
        return
    _worker_task = asyncio.create_task(_worker_loop(), name="alert_worker")
    logger.info("Alert worker task created")


async def stop_alert_worker() -> None:
    """Cleanly stop the worker. Called from FastAPI shutdown."""
    global _worker_task
    if _worker_task is None:
        return
    _worker_task.cancel()
    try:
        await _worker_task
    except asyncio.CancelledError:
        pass
    _worker_task = None
    logger.info("Alert worker stopped")