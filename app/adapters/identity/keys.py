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


# FEAT-001: per-key scope + cost caps. Added via guarded migrations.
_MIGRATIONS = {
    "expires_at": "TEXT",              # NULL = never expires
    "subject_type": "TEXT DEFAULT 'user'",   # user | agent | service
    "allowed_backends": "TEXT DEFAULT ''",   # comma-sep; '' = all
    "allowed_models": "TEXT DEFAULT ''",     # comma-sep; '' = all
    "cost_cap_daily": "REAL DEFAULT 0",      # USD/day; 0 = no cap
    "cost_cap_monthly": "REAL DEFAULT 0",    # USD/month; 0 = no cap
}


def ensure_table() -> None:
    with get_conn() as conn:
        conn.execute(_DDL)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(api_keys)")}
        for name, decl in _MIGRATIONS.items():
            if name not in cols:
                conn.execute(f"ALTER TABLE api_keys ADD COLUMN {name} {decl}")


def _csv(values) -> str:
    if isinstance(values, str):
        values = values.split(",")
    return ",".join(v.strip() for v in (values or []) if str(v).strip())


def _is_expired(expires_at: str | None, now: str | None = None) -> bool:
    if not expires_at:
        return False
    return expires_at <= (now or _dt.datetime.now(_dt.UTC).isoformat())


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_key(name: str, role: str = "user", team: str = "",
              expires_in_days: int | None = 90, *, subject_type: str = "user",
              allowed_backends=None, allowed_models=None,
              cost_cap_daily: float = 0, cost_cap_monthly: float = 0) -> tuple[str, str]:
    """Create a key with optional scope + cost caps. Returns (id, plaintext_token).

    The key is an external app's credential into Precepta. It can be pinned to a
    team/role/subject-type, restricted to specific backends & models, and given
    daily/monthly USD cost caps. expires_in_days: default 90; None/0 = never.
    """
    ensure_table()
    token = _PREFIX + secrets.token_urlsafe(32)
    kid = uuid.uuid4().hex
    now = _dt.datetime.now(_dt.UTC)
    expires_at = ((now + _dt.timedelta(days=int(expires_in_days))).isoformat()
                  if expires_in_days else None)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO api_keys (id,key_hash,name,role,team,created_at,expires_at,"
            "subject_type,allowed_backends,allowed_models,cost_cap_daily,cost_cap_monthly) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (kid, _hash(token), name, role, team, now.isoformat(), expires_at,
             subject_type or "user", _csv(allowed_backends), _csv(allowed_models),
             float(cost_cap_daily or 0), float(cost_cap_monthly or 0)),
        )
    return kid, token


def get_key_meta(name: str) -> dict | None:
    """Scope + caps for a key, looked up by its name (= Principal.subject)."""
    ensure_table()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT name,team,role,subject_type,allowed_backends,allowed_models,"
            "cost_cap_daily,cost_cap_monthly FROM api_keys "
            "WHERE name=? AND revoked_at IS NULL", (name,)).fetchone()
    return dict(row) if row else None


def scope_violation(name: str, backend: str, model: str) -> str | None:
    """Block reason if this key may not use this backend/model; else None."""
    meta = get_key_meta(name)
    if not meta:
        return None
    ab = [x for x in (meta["allowed_backends"] or "").split(",") if x]
    if ab and backend not in ab:
        return f"key {name!r} is scoped to backends {ab} and may not use {backend!r}"
    am = [x for x in (meta["allowed_models"] or "").split(",") if x]
    if am and model and model not in am:
        return f"key {name!r} is scoped to models {am} and may not use {model!r}"
    return None


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
            "SELECT id,name,role,team,created_at,revoked_at,expires_at,subject_type,"
            "allowed_backends,allowed_models,cost_cap_daily,cost_cap_monthly FROM api_keys "
            "ORDER BY created_at DESC").fetchall()
    out = []
    for r in rows:
        expired = _is_expired(r["expires_at"])
        out.append(dict(r) | {
            "expired": expired,
            "active": r["revoked_at"] is None and not expired,
            "backends_list": [x for x in (r["allowed_backends"] or "").split(",") if x],
            "models_list": [x for x in (r["allowed_models"] or "").split(",") if x],
        })
    return out


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
        if _is_expired(row["expires_at"]):          # expired key fails auth (FEAT-001)
            return None
        return Principal(subject=row["name"], role=row["role"],
                         display_name=row["name"], team=row["team"] or "")


_api_identity = ApiKeyIdentity()


def get_api_identity() -> ApiKeyIdentity:
    return _api_identity
