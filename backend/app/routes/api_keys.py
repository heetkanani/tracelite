"""
API key management routes.
Requires session cookie auth (dashboard only — not SDK).
"""
import secrets
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.dependencies import AuthContext, get_current_auth
from app.db import get_pool
from app.queries import (
    get_user_default_project,
    insert_api_key,
    list_api_keys,
    revoke_api_key,
)

router = APIRouter(prefix="/v1/api-keys", tags=["api-keys"])


# ----------------------------------------------------------------------
# Models
# ----------------------------------------------------------------------

class ApiKeyItem(BaseModel):
    id: UUID
    name: str
    created_at: str
    last_used_at: str | None = None


class ApiKeyCreated(BaseModel):
    """Returned only on creation — includes the raw key (shown once)."""
    id: UUID
    name: str
    key: str          # full key — only time we ever return it
    created_at: str


class CreateApiKeyRequest(BaseModel):
    name: str


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

async def _get_project_id(conn, auth: AuthContext) -> UUID:
    """Resolve project_id from the session user."""
    project = await get_user_default_project(conn, auth.user_id)
    if project is None:
        raise HTTPException(status_code=404, detail="No project found for this user")
    return project["id"]


def _generate_key() -> str:
    """Generate a secure random API key with a recognizable prefix."""
    return "tl-" + secrets.token_urlsafe(32)


# ----------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------

@router.get("", response_model=list[ApiKeyItem])
async def list_keys(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
) -> list[ApiKeyItem]:
    pool = get_pool()
    async with pool.acquire() as conn:
        project_id = await _get_project_id(conn, auth)
        rows = await list_api_keys(conn, project_id)

    return [
        ApiKeyItem(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"].isoformat(),
            last_used_at=row["last_used_at"].isoformat() if row["last_used_at"] else None,
        )
        for row in rows
    ]


@router.post("", response_model=ApiKeyCreated, status_code=201)
async def create_key(
    payload: CreateApiKeyRequest,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
) -> ApiKeyCreated:
    pool = get_pool()
    async with pool.acquire() as conn:
        project_id = await _get_project_id(conn, auth)
        key = _generate_key()
        row = await insert_api_key(conn, project_id, payload.name, key)

    return ApiKeyCreated(
        id=row["id"],
        name=row["name"],
        key=row["key"],
        created_at=row["created_at"].isoformat(),
    )


@router.delete("/{key_id}", status_code=204)
async def delete_key(
    key_id: UUID,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        project_id = await _get_project_id(conn, auth)
        found = await revoke_api_key(conn, key_id, project_id)

    if not found:
        raise HTTPException(status_code=404, detail="API key not found")