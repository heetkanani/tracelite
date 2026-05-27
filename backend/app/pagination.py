"""
Cursor-based pagination helpers.

A cursor is a base64-encoded JSON of (timestamp, id). It marks the last
row a client saw, so the next request continues from there.
"""
import base64
import json
from datetime import datetime
from typing import Optional, Tuple
from uuid import UUID

from fastapi import HTTPException


def encode_cursor(ts: datetime, row_id: UUID) -> str:
    """Pack a (timestamp, id) into an opaque URL-safe cursor string."""
    payload = {"ts": ts.isoformat(), "id": str(row_id)}
    raw = json.dumps(payload).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_cursor(cursor: str) -> Tuple[datetime, UUID]:
    """Inverse of encode_cursor. Raises 400 if malformed."""
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii"))
        payload = json.loads(raw.decode("utf-8"))
        return datetime.fromisoformat(payload["ts"]), UUID(payload["id"])
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid cursor")


def parse_optional_cursor(
    cursor: Optional[str],
) -> Optional[Tuple[datetime, UUID]]:
    """Convenience wrapper: pass through None, decode if present."""
    if cursor is None:
        return None
    return decode_cursor(cursor)