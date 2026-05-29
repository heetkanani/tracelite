"""
Tracelite alert delivery channels package.
"""
from app.alert_delivery.base import (
    DeliveryResult,
    deliver_alert,
    register_delivery,
    registered_channels,
)

# Side-effect imports
from app.alert_delivery import log_channel  # noqa: F401
from app.alert_delivery import slack_channel  # noqa: F401


__all__ = [
    "DeliveryResult",
    "deliver_alert",
    "register_delivery",
    "registered_channels",
]