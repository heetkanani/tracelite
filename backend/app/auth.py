"""
Authentication helpers: password hashing, session tokens.

Kept separate from queries.py because these are pure utility functions
that don't touch the DB on their own. Routes glue them together with
DB queries.
"""
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt


# Session lifetime. 30 days = roughly the right balance between "users
# don't have to re-login constantly" and "stolen tokens don't last forever".
SESSION_LIFETIME = timedelta(days=30)

# bcrypt cost factor. 12 is the OWASP-recommended minimum for 2024+.
# Each step doubles the work; 12 takes ~250ms per hash on modern hardware.
BCRYPT_ROUNDS = 12


def hash_password(plaintext: str) -> str:
    """
    Hash a password with bcrypt. Returns the storable hash string.

    bcrypt rejects passwords longer than 72 bytes. We truncate proactively
    rather than letting the library raise — the truncation has the same
    cryptographic strength because bcrypt only consumes the first 72 bytes
    internally.
    """
    truncated = plaintext.encode("utf-8")[:72]
    hashed = bcrypt.hashpw(truncated, bcrypt.gensalt(rounds=BCRYPT_ROUNDS))
    return hashed.decode("utf-8")


def verify_password(plaintext: str, password_hash: str) -> bool:
    """Return True if `plaintext` matches the stored hash."""
    try:
        truncated = plaintext.encode("utf-8")[:72]
        return bcrypt.checkpw(truncated, password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # Malformed hash (corrupted DB row?) → fail closed.
        return False


def new_session_token() -> str:
    """
    Generate a cryptographically random session token.

    secrets.token_urlsafe(48) gives 384 bits of entropy, encoded as
    ~64 url-safe chars. Wide enough that no two tokens collide in
    any reasonable lifetime.
    """
    return secrets.token_urlsafe(48)


def session_expiry_from_now() -> datetime:
    """Compute the expiration timestamp for a new session."""
    return datetime.now(timezone.utc) + SESSION_LIFETIME

# ----------------------------------------------------------------------
# Session-based current-user resolution
# ----------------------------------------------------------------------

from typing import Optional
from uuid import UUID

import asyncpg

from app.queries import (
    get_session_by_token,
    get_user_by_id,
    touch_session,
)


async def resolve_user_from_session(
    conn: asyncpg.Connection,
    session_token: Optional[str],
) -> Optional[asyncpg.Record]:
    """
    Look up the user for a session cookie.

    Returns None if the cookie is absent, malformed, or expired.
    On success, also bumps last_seen_at so we know the session is alive.
    """
    if not session_token:
        return None

    session = await get_session_by_token(conn, session_token)
    if session is None:
        return None  # Expired or unknown token

    # Activity tracking. If it fails, don't break auth.
    try:
        await touch_session(conn, session["id"])
    except Exception:
        pass

    return await get_user_by_id(conn, session["user_id"])