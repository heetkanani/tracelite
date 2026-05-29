"""
HTTP routes for eval definitions.

Users create, list, update, and delete "rules" here. Actually running
those rules against spans happens in the background eval worker;
the /run endpoint here is for manual backfills.

Authentication: accepts either an X-API-Key header or a session cookie.
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.db import get_pool
from app.dependencies import AuthContext, get_current_auth, resolve_project_id
from app.evaluations import run_eval_against_recent_spans
from app.models import (
    EvalDefinitionCreate,
    EvalDefinitionItem,
    EvalDefinitionListResponse,
    EvalDefinitionUpdate,
)
from app.queries import (
    delete_eval_definition,
    get_eval_definition,
    insert_eval_definition,
    list_eval_definitions,
    update_eval_definition,
)

router = APIRouter(prefix="/v1", tags=["evals"])


# ----------------------------------------------------------------------
# POST /v1/evals
# ----------------------------------------------------------------------

@router.post(
    "/evals",
    response_model=EvalDefinitionItem,
    status_code=201,
)
async def create_eval_endpoint(
    payload: EvalDefinitionCreate,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
) -> EvalDefinitionItem:
    """Create a new evaluation rule for the caller's project."""
    pool = get_pool()
    async with pool.acquire() as conn:
        project_id = await resolve_project_id(auth, conn)

        row = await insert_eval_definition(
            conn,
            project_id=project_id,
            name=payload.name,
            evaluator_type=payload.evaluator_type,
            config=payload.config,
            applies_to_span_type=payload.applies_to_span_type,
            active=payload.active,
        )

    return EvalDefinitionItem(**dict(row))


# ----------------------------------------------------------------------
# GET /v1/evals
# ----------------------------------------------------------------------

@router.get("/evals", response_model=EvalDefinitionListResponse)
async def list_evals_endpoint(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    active_only: bool = Query(default=False),
) -> EvalDefinitionListResponse:
    """List all eval definitions for the caller's project."""
    pool = get_pool()
    async with pool.acquire() as conn:
        project_id = await resolve_project_id(auth, conn)

        rows = await list_eval_definitions(
            conn,
            project_id=project_id,
            active_only=active_only,
        )

    items = [EvalDefinitionItem(**dict(r)) for r in rows]
    return EvalDefinitionListResponse(items=items)


# ----------------------------------------------------------------------
# GET /v1/evals/{eval_id}
# ----------------------------------------------------------------------

@router.get("/evals/{eval_id}", response_model=EvalDefinitionItem)
async def get_eval_endpoint(
    eval_id: UUID,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
) -> EvalDefinitionItem:
    """Fetch one eval definition."""
    pool = get_pool()
    async with pool.acquire() as conn:
        project_id = await resolve_project_id(auth, conn)

        row = await get_eval_definition(conn, eval_id, project_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Eval not found")

    return EvalDefinitionItem(**dict(row))


# ----------------------------------------------------------------------
# PATCH /v1/evals/{eval_id}
# ----------------------------------------------------------------------

@router.patch("/evals/{eval_id}", response_model=EvalDefinitionItem)
async def update_eval_endpoint(
    eval_id: UUID,
    payload: EvalDefinitionUpdate,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
) -> EvalDefinitionItem:
    """Update some fields on an eval definition. Only provided fields change."""
    pool = get_pool()
    async with pool.acquire() as conn:
        project_id = await resolve_project_id(auth, conn)

        row = await update_eval_definition(
            conn,
            eval_id=eval_id,
            project_id=project_id,
            name=payload.name,
            config=payload.config,
            applies_to_span_type=payload.applies_to_span_type,
            active=payload.active,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Eval not found")

    return EvalDefinitionItem(**dict(row))


# ----------------------------------------------------------------------
# DELETE /v1/evals/{eval_id}
# ----------------------------------------------------------------------

@router.delete("/evals/{eval_id}", status_code=204)
async def delete_eval_endpoint(
    eval_id: UUID,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
) -> None:
    """Delete an eval definition. Cascades to its results."""
    pool = get_pool()
    async with pool.acquire() as conn:
        project_id = await resolve_project_id(auth, conn)

        deleted = await delete_eval_definition(conn, eval_id, project_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Eval not found")
    # 204 No Content — no return body


# ----------------------------------------------------------------------
# POST /v1/evals/{eval_id}/run — manually trigger a run
# ----------------------------------------------------------------------

@router.post("/evals/{eval_id}/run")
async def run_eval_endpoint(
    eval_id: UUID,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    limit: int = Query(default=100, ge=1, le=1000),
) -> dict:
    """
    Run an eval definition against the most recent matching spans.

    Useful for backfilling: you create a new eval, then run it across
    your existing spans to get historical scores.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        project_id = await resolve_project_id(auth, conn)

        try:
            summary = await run_eval_against_recent_spans(
                conn,
                eval_id=eval_id,
                project_id=project_id,
                limit=limit,
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    return summary