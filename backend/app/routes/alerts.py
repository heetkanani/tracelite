"""
HTTP routes for alert rules and events.

Users create rules here. The background worker (added in 7.2)
evaluates them periodically and writes to alert_events on fire.
Events are read-only via this API.

Authentication: accepts either an X-API-Key header or a session cookie.
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.alert_delivery import deliver_alert
from app.db import get_pool
from app.dependencies import AuthContext, get_current_auth, resolve_project_id
from app.models import (
    AlertEventItem,
    AlertEventListResponse,
    AlertRuleCreate,
    AlertRuleItem,
    AlertRuleListResponse,
    AlertRuleUpdate,
)
from app.queries import (
    delete_alert_rule,
    get_alert_rule,
    insert_alert_event,
    insert_alert_rule,
    list_alert_events,
    list_alert_rules,
    update_alert_rule,
)

router = APIRouter(prefix="/v1", tags=["alerts"])


# ----------------------------------------------------------------------
# POST /v1/alerts
# ----------------------------------------------------------------------

@router.post("/alerts", response_model=AlertRuleItem, status_code=201)
async def create_alert_endpoint(
    payload: AlertRuleCreate,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
) -> AlertRuleItem:
    """Create a new alert rule."""
    pool = get_pool()
    async with pool.acquire() as conn:
        project_id = await resolve_project_id(auth, conn)

        row = await insert_alert_rule(
            conn,
            project_id=project_id,
            name=payload.name,
            condition_type=payload.condition_type,
            config=payload.config,
            delivery_channel=payload.delivery_channel,
            delivery_config=payload.delivery_config,
            active=payload.active,
            min_resend_minutes=payload.min_resend_minutes,
        )

    return AlertRuleItem(**dict(row))


# ----------------------------------------------------------------------
# GET /v1/alerts
# ----------------------------------------------------------------------

@router.get("/alerts", response_model=AlertRuleListResponse)
async def list_alerts_endpoint(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    active_only: bool = Query(default=False),
) -> AlertRuleListResponse:
    """List alert rules for the project."""
    pool = get_pool()
    async with pool.acquire() as conn:
        project_id = await resolve_project_id(auth, conn)

        rows = await list_alert_rules(
            conn,
            project_id=project_id,
            active_only=active_only,
        )

    items = [AlertRuleItem(**dict(r)) for r in rows]
    return AlertRuleListResponse(items=items)


# ----------------------------------------------------------------------
# GET /v1/alerts/{rule_id}
# ----------------------------------------------------------------------

@router.get("/alerts/{rule_id}", response_model=AlertRuleItem)
async def get_alert_endpoint(
    rule_id: UUID,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
) -> AlertRuleItem:
    """Fetch one alert rule."""
    pool = get_pool()
    async with pool.acquire() as conn:
        project_id = await resolve_project_id(auth, conn)

        row = await get_alert_rule(conn, rule_id, project_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Alert rule not found")

    return AlertRuleItem(**dict(row))


# ----------------------------------------------------------------------
# PATCH /v1/alerts/{rule_id}
# ----------------------------------------------------------------------

@router.patch("/alerts/{rule_id}", response_model=AlertRuleItem)
async def update_alert_endpoint(
    rule_id: UUID,
    payload: AlertRuleUpdate,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
) -> AlertRuleItem:
    """Update an alert rule. Only provided fields change."""
    pool = get_pool()
    async with pool.acquire() as conn:
        project_id = await resolve_project_id(auth, conn)

        row = await update_alert_rule(
            conn,
            rule_id=rule_id,
            project_id=project_id,
            name=payload.name,
            config=payload.config,
            delivery_channel=payload.delivery_channel,
            delivery_config=payload.delivery_config,
            active=payload.active,
            min_resend_minutes=payload.min_resend_minutes,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Alert rule not found")

    return AlertRuleItem(**dict(row))


# ----------------------------------------------------------------------
# DELETE /v1/alerts/{rule_id}
# ----------------------------------------------------------------------

@router.delete("/alerts/{rule_id}", status_code=204)
async def delete_alert_endpoint(
    rule_id: UUID,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
) -> None:
    """Delete an alert rule. Cascades to its events."""
    pool = get_pool()
    async with pool.acquire() as conn:
        project_id = await resolve_project_id(auth, conn)

        deleted = await delete_alert_rule(conn, rule_id, project_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Alert rule not found")


# ----------------------------------------------------------------------
# GET /v1/alert_events — recent alert fires
# ----------------------------------------------------------------------

@router.get("/alert_events", response_model=AlertEventListResponse)
async def list_alert_events_endpoint(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    limit: int = Query(default=50, ge=1, le=200),
) -> AlertEventListResponse:
    """List recent alert events for the project, newest first."""
    pool = get_pool()
    async with pool.acquire() as conn:
        project_id = await resolve_project_id(auth, conn)

        rows = await list_alert_events(conn, project_id, limit=limit)

    items = [AlertEventItem(**dict(r)) for r in rows]
    return AlertEventListResponse(items=items)


# ----------------------------------------------------------------------
# POST /v1/alerts/{rule_id}/test — fire immediately for testing
# ----------------------------------------------------------------------

@router.post("/alerts/{rule_id}/test")
async def test_alert_endpoint(
    rule_id: UUID,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
) -> dict:
    """
    Fire this alert immediately with a synthetic message. Useful for
    verifying the delivery channel (e.g., a Slack webhook URL).

    Differences from a real fire:
      - Bypasses the condition check
      - Does NOT update last_fired_at (so the cooldown isn't triggered)
      - Message is prefixed with [TEST] so it's distinguishable
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        project_id = await resolve_project_id(auth, conn)

        rule = await get_alert_rule(conn, rule_id, project_id)
        if rule is None:
            raise HTTPException(status_code=404, detail="Alert rule not found")

        rule_dict = dict(rule)
        test_message = f"[TEST] This is a test alert from '{rule_dict['name']}'."
        test_context = {"test": True, "triggered_via": "manual"}

        delivery = await deliver_alert(
            channel=rule_dict["delivery_channel"],
            rule_row=rule_dict,
            message=test_message,
            context=test_context,
        )

        await insert_alert_event(
            conn,
            alert_rule_id=rule_id,
            message=test_message,
            context=test_context,
            delivered=delivery.delivered,
            delivery_error=delivery.error_message,
        )

    return {
        "delivered": delivery.delivered,
        "error_message": delivery.error_message,
        "message": test_message,
    }