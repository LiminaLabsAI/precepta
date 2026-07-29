"""Login sessions (Phase 8 last-mile) — turns an SSO login into a Console session.

After OIDC callback we mint a session token for the authenticated principal and
hand it to the browser; every subsequent API call carries it as a bearer token,
so the signed-in Google user's identity flows through the whole app.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import secrets

from ...db import get_conn
from ...ports import Principal

_DDL = """
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    subject    TEXT NOT NULL,
    role       TEXT NOT NULL,
    name       TEXT,
    team       TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
)
"""

_PREFIX = "ps-"
_TTL_HOURS = 12


def ensure_table() -> None:
    with get_conn() as conn:
        conn.execute(_DDL)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(principal: Principal) -> str:
    ensure_table()
    token = _PREFIX + secrets.token_urlsafe(32)
    now = _dt.datetime.now(_dt.UTC)
    exp = now + _dt.timedelta(hours=_TTL_HOURS)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sessions (token_hash,subject,role,name,team,created_at,expires_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (_hash(token), principal.subject, principal.role,
             principal.display_name or principal.subject, principal.team,
             now.isoformat(), exp.isoformat()))
    return token


def revoke_session(token: str) -> None:
    ensure_table()
    with get_conn() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash=?", (_hash(token),))


class SessionIdentity:
    name = "session"

    def authenticate(self, token: str) -> Principal | None:
        if not token or not token.startswith(_PREFIX):
            return None
        ensure_table()
        now = _dt.datetime.now(_dt.UTC).isoformat()
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE token_hash=? AND expires_at > ?",
                (_hash(token), now)).fetchone()
        if row is None:
            return None
        return Principal(subject=row["subject"], role=row["role"],
                         display_name=row["name"] or row["subject"], team=row["team"] or "")


_session_identity = SessionIdentity()


def get_session_identity() -> SessionIdentity:
    return _session_identity
