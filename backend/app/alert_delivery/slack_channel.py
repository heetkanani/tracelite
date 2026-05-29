"""
Slack delivery channel — posts the alert to a Slack incoming webhook.

Delivery config:
    {"webhook_url": "https://hooks.slack.com/services/..."}

For development/testing without a real Slack workspace, use a URL
starting with "mock://" — the mock branch logs the payload instead
of making a network call.
"""
import json
import logging
from typing import Any

import httpx

from app.alert_delivery.base import DeliveryResult, register_delivery

logger = logging.getLogger("tracelite.alerts")


def _build_payload(rule_name: str, message: str, context: dict) -> dict[str, Any]:
    """
    Build a Slack incoming-webhook payload.

    Uses blocks for nicer formatting. Falls back to `text` for clients
    that don't render blocks (mobile, screen readers).
    """
    context_lines = [
        f"• *{k}*: `{v}`"
        for k, v in context.items()
    ]

    return {
        "text": f"🚨 {rule_name}: {message}",  # fallback / notification text
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🚨 {rule_name}"},
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": message},
            },
            *([{
                "type": "section",
                "text": {"type": "mrkdwn", "text": "\n".join(context_lines)},
            }] if context_lines else []),
        ],
    }


@register_delivery("slack_webhook")
async def slack_delivery(
    rule_row: dict,
    message: str,
    context: dict,
) -> DeliveryResult:
    """
    POST the alert as JSON to the configured Slack webhook.

    Returns success when Slack returns 2xx. On any other status or
    connection error, captures the failure reason for alert_events.
    """
    delivery_config = rule_row.get("delivery_config") or {}
    webhook_url = delivery_config.get("webhook_url", "").strip()

    if not webhook_url:
        return DeliveryResult(
            delivered=False,
            error_message="No webhook_url configured",
        )

    payload = _build_payload(
        rule_name=rule_row.get("name", "Unnamed rule"),
        message=message,
        context=context,
    )

    # Mock branch — useful in dev when no real Slack URL is available.
    if webhook_url.startswith("mock://"):
        logger.info(
            "🪝 Slack mock delivery to %s | payload=%s",
            webhook_url,
            json.dumps(payload)[:500],
        )
        return DeliveryResult(delivered=True)

    # Real Slack call.
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(webhook_url, json=payload)
    except httpx.RequestError as e:
        return DeliveryResult(
            delivered=False,
            error_message=f"Network error: {type(e).__name__}: {e}",
        )

    if response.status_code >= 200 and response.status_code < 300:
        return DeliveryResult(delivered=True)

    return DeliveryResult(
        delivered=False,
        error_message=(
            f"Slack returned {response.status_code}: "
            f"{response.text[:200]}"
        ),
    )