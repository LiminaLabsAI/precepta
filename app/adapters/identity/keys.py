"""Per-team API keys (Phase 7) — an IdentityPort adapter backed by SQLite.

Enterprises give each team/app its own scoped key. Only the SHA-256 hash is
stored; the plaintext key is shown once at issue time. Every governed request
made with a key is attributed to that key's name in the audit log.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import secrets
import uuid

from ...db import get_conn
from ...ports import Principal

_DDL = """
CREATE TABLE IF NOT EXISTS api_keys (
    id         TEXT PRIMARY KEY,
    key_hash   TEXT NOT NULL UNIQUE,
    name       TEXT NOT NULL,
    role       TEXT NOT NULL,
    team       TEXT,
    created_at TEXT NOT NULL,
    revoked_at TEXT
)
"""

_PREFIX = "pk-"


def ensure_table() -> None:
    with get_conn() as conn:
        conn.execute(_DDL)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_key(name: str, role: str = "user", team: str = "") -> tuple[str, str]:
    """Create a key. Returns (id, plaintext_token) — the token is shown once."""
    ensure_table()
    token = _PREFIX + secrets.token_urlsafe(32)
    kid = uuid.uuid4().hex
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO api_keys (id,key_hash,name,role,team,created_at) "
            "VALUES (?,?,?,?,?,?)",
            (kid, _hash(token), name, role, team,
             _dt.datetime.now(_dt.UTC).isoformat()),
        )
    return kid, token


def revoke_key(kid: str) -> bool:
    ensure_table()
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE api_keys SET revoked_at=? WHERE id=? AND revoked_at IS NULL",
            (_dt.datetime.now(_dt.UTC).isoformat(), kid))
        return cur.rowcount > 0


def list_keys() -> list[dict]:
    """All keys (never the secret) — for the admin Console."""
    ensure_table()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id,name,role,team,created_at,revoked_at FROM api_keys "
            "ORDER BY created_at DESC").fetchall()
    return [dict(r) | {"active": r["revoked_at"] is None} for r in rows]


class ApiKeyIdentity:
    """IdentityPort: bearer token → Principal, via key-hash lookup."""

    name = "api_key"

    def authenticate(self, token: str) -> Principal | None:
        if not token or not token.startswith(_PREFIX):
            return None
        ensure_table()
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM api_keys WHERE key_hash=? AND revoked_at IS NULL",
                (_hash(token),)).fetchone()
        if row is None:
            return None
        return Principal(subject=row["name"], role=row["role"],
                         display_name=row["name"], team=row["team"] or "")


_api_identity = ApiKeyIdentity()


def get_api_identity() -> ApiKeyIdentity:
    return _api_identity
