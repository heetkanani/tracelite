"""
FastAPI dependencies for authenticated routes.

These wrap "who is calling this request?" logic so route handlers can
simply declare `user = Depends(get_current_user_or_project)` and get
the authenticated context without re-implementing the lookup.

Two ways to authenticate:
  1. Session cookie (set by /v1/auth/login or /v1/auth/signup)
  2. X-API-Key header (used by SDK)

Both resolve to a (user, project) pair the route can scope by.
"""
from dataclasses import dataclass
from typing import Annotated, Optional
from uuid import UUID
import asyncpg

from fastapi import Cookie, Header, HTTPException

from app.auth import resolve_user_from_session
from app.db import get_pool
from app.queries import get_project_by_api_key


@dataclass
class AuthContext:
    """
    The authenticated context for a request.

    user_id   — always set; either the session's user or the API key's owner
    project_id — set when the SDK auth (X-API-Key) was used; None for
                 session-only requests (they may have many projects)
    """
    user_id: UUID
    project_id: Optional[UUID]


async def get_current_auth(
    x_api_key: Annotated[Optional[str], Header(alias="X-API-Key")] = None,
    tracelite_session: Annotated[Optional[str], Cookie()] = None,
) -> AuthContext:
    """
    Resolve the caller. Tries API key first (fast, project-scoped path),
    falls back to session cookie. Raises 401 if neither works.
    """
    pool = get_pool()

    async with pool.acquire() as conn:
        # 1. API key path (SDK calls)
        if x_api_key:
            project = await get_project_by_api_key(conn, x_api_key)
            if project is not None:
                return AuthContext(
                    user_id=project["owner_user_id"],
                    project_id=project["id"],
                )

        # 2. Session cookie path (dashboard)
        if tracelite_session:
            user = await resolve_user_from_session(conn, tracelite_session)
            if user is not None:
                return AuthContext(
                    user_id=user["id"],
                    project_id=None,
                )

    raise HTTPException(status_code=401, detail="Not authenticated")\
    
async def resolve_project_id(
    auth: AuthContext,
    conn: asyncpg.Connection,
) -> UUID:
    """
    Resolve a project_id for the current request.

    - If auth came from X-API-Key: project_id is already set.
    - If auth came from a session cookie: look up the user's default project.

    Raises 404 if the user has no project. The frontend should redirect
    them to project creation UI in that case.
    """
    from app.queries import get_user_default_project

    if auth.project_id is not None:
        return auth.project_id

    project = await get_user_default_project(conn, auth.user_id)
    if project is None:
        raise HTTPException(
            status_code=404,
            detail="No project found for this user. Please create a project.",
        )
    return project["id"]