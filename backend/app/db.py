"""
Database connection pool for tracelite.

Owns a single asyncpg pool for the entire application lifetime.
Modules that need DB access import `get_pool()`.
"""
import os
import json
from typing import Optional

import asyncpg
from dotenv import load_dotenv

# Load environment variables from .env at import time
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL not set. Did you create backend/.env?"
    )

# Module-level pool. Populated by init_pool() on app startup.
_pool: Optional[asyncpg.Pool] = None

async def _setup_connection(conn: asyncpg.Connection) -> None:
    """Tell asyncpg to decode JSONB columns into Python dicts/lists."""
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )
    await conn.set_type_codec(
        "json",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def init_pool() -> None:
    """Create the connection pool. Called once at app startup."""
    global _pool
    _pool = await asyncpg.create_pool(
        dsn=DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=10,
        init=_setup_connection,
    )

async def close_pool() -> None:
    """Close the connection pool. Called at app shutdown."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    """Return the live pool. Raises if init_pool wasn't called."""
    if _pool is None:
        raise RuntimeError(
            "Database pool not initialized. "
            "This usually means init_pool() wasn't called at startup."
        )
    return _pool