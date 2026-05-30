"""
Authentication routes: signup and login.

These do NOT require X-API-Key — they're how users get into the system.
Once authenticated, the returned session token can be used for dashboard
API calls.
"""
from typing import Annotated, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from app.dependencies import AuthContext, get_current_auth
from app.auth import (
    hash_password,
    new_session_token,
    session_expiry_from_now,
    verify_password,
)
from app.db import get_pool
from app.models import (
    LoginRequest,
    SessionResponse,
    SignupRequest,
    UserResponse,
)
from app.queries import (
    delete_session,
    get_user_by_email,
    get_user_by_id,
    insert_project,
    insert_session,
    insert_user,
)

router = APIRouter(prefix="/v1/auth", tags=["auth"])


SESSION_COOKIE = "tracelite_session"


def _set_session_cookie(response: Response, token: str) -> None:
    """
    Attach a cookie carrying the session token.

    HttpOnly → JavaScript can't read it (XSS defense).
    SameSite=Lax → not sent on cross-site POSTs (CSRF defense).
    Path=/ → sent on every request.

    Note: we DON'T set Secure because dev runs over http://. In production,
    add Secure=True via an env-conditional config.
    """
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        max_age=60 * 60 * 24 * 30,  # 30 days
        httponly=True,
        samesite="lax",
        path="/",
    )


# ----------------------------------------------------------------------
# POST /v1/auth/signup
# ----------------------------------------------------------------------

@router.post("/signup", response_model=SessionResponse, status_code=201)
async def signup_endpoint(
    payload: SignupRequest,
    response: Response,
) -> SessionResponse:
    """Create a new user and log them in."""
    pool = get_pool()
    async with pool.acquire() as conn:
        # Check for existing user by email.
        existing = await get_user_by_email(conn, payload.email)
        if existing is not None:
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists",
            )

        password_hash = hash_password(payload.password)
        user_row = await insert_user(
            conn,
            email=payload.email,
            password_hash=password_hash,
            name=payload.name,
        )

        # Auto-create a default project for the new user.
        # Every downstream query (traces, evals, alerts) needs a project_id.
        await insert_project(
            conn,
            owner_user_id=user_row["id"],
            name="My Project",
        )

        token = new_session_token()

        token = new_session_token()
        expires_at = session_expiry_from_now()
        await insert_session(
            conn,
            user_id=user_row["id"],
            token=token,
            expires_at=expires_at,
        )

    _set_session_cookie(response, token)
    return SessionResponse(
        user=UserResponse(
            id=user_row["id"],
            email=user_row["email"],
            name=user_row["name"],
        ),
        token=token,
        expires_at=expires_at,
    )


# ----------------------------------------------------------------------
# POST /v1/auth/login
# ----------------------------------------------------------------------

@router.post("/login", response_model=SessionResponse)
async def login_endpoint(
    payload: LoginRequest,
    response: Response,
) -> SessionResponse:
    """Verify credentials and issue a new session."""
    pool = get_pool()
    async with pool.acquire() as conn:
        user_row = await get_user_by_email(conn, payload.email)
        if user_row is None or not verify_password(
            payload.password, user_row["password_hash"]
        ):
            # Same error for "wrong email" and "wrong password" so attackers
            # can't learn whether an email exists.
            raise HTTPException(
                status_code=401,
                detail="Invalid email or password",
            )

        token = new_session_token()
        expires_at = session_expiry_from_now()
        await insert_session(
            conn,
            user_id=user_row["id"],
            token=token,
            expires_at=expires_at,
        )

    _set_session_cookie(response, token)
    return SessionResponse(
        user=UserResponse(
            id=user_row["id"],
            email=user_row["email"],
            name=user_row["name"],
        ),
        token=token,
        expires_at=expires_at,
    )


# ----------------------------------------------------------------------
# POST /v1/auth/logout
# ----------------------------------------------------------------------

@router.post("/logout", status_code=204)
async def logout_endpoint(
    response: Response,
    tracelite_session: Annotated[Optional[str], Cookie()] = None,
) -> None:
    """Invalidate the current session and clear the cookie."""
    if tracelite_session is not None:
        pool = get_pool()
        async with pool.acquire() as conn:
            await delete_session(conn, tracelite_session)
    response.delete_cookie(SESSION_COOKIE, path="/")


# ----------------------------------------------------------------------
# GET /v1/auth/me — current user info
# ----------------------------------------------------------------------

@router.get("/me", response_model=UserResponse)
async def me_endpoint(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
) -> UserResponse:
    """Return the currently authenticated user."""
    pool = get_pool()
    async with pool.acquire() as conn:
        user = await get_user_by_id(conn, auth.user_id)
        if user is None:
            # Session valid but user got deleted somehow → treat as logout.
            raise HTTPException(status_code=401, detail="User no longer exists")

    return UserResponse(
        id=user["id"],
        email=user["email"],
        name=user["name"],
    )