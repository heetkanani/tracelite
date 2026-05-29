"""
Log delivery channel — writes the alert to the application log.

Useful for development, testing, and as a safe fallback when a
user creates an alert without configuring Slack/email yet.
"""
import logging

from app.alert_delivery.base import DeliveryResult, register_delivery

logger = logging.getLogger("tracelite.alerts")


@register_delivery("log")
async def log_delivery(
    rule_row: dict,
    message: str,
    context: dict,
) -> DeliveryResult:
    """Write the alert to the standard logger at WARNING level."""
    logger.warning(
        "🚨 ALERT [%s] %s | context=%s",
        rule_row.get("name", "unnamed rule"),
        message,
        context,
    )
    return DeliveryResult(delivered=True)