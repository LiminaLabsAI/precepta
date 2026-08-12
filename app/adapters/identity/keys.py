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


# FEAT-001: per-key scope + cost/token caps + suspend. Added via guarded migrations.
_MIGRATIONS = {
    "expires_at": "TEXT",              # NULL = never expires
    "subject_type": "TEXT DEFAULT 'user'",   # legacy; no longer set from the UI
    "allowed_backends": "TEXT DEFAULT ''",   # comma-sep; '' = all
    "allowed_models": "TEXT DEFAULT ''",     # comma-sep; '' = all
    "cost_cap_daily": "REAL DEFAULT 0",      # USD/day; 0 = no cap
    "cost_cap_monthly": "REAL DEFAULT 0",    # USD/month; 0 = no cap
    "token_cap_daily": "INTEGER DEFAULT 0",  # tokens/day; 0 = no cap
    "token_cap_monthly": "INTEGER DEFAULT 0",# tokens/month; 0 = no cap
    "suspended_at": "TEXT",           # non-NULL = temporarily disabled
    "scope": "TEXT DEFAULT 'inference'",   # 'inference' | 'manage' (Phase 15)
    "manage_write": "INTEGER DEFAULT 0",   # manage keys: 0 = read-only, 1 = read-write
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
              expires_in_days: int | None = 90, *,
              allowed_backends=None, allowed_models=None,
              cost_cap_daily: float = 0, cost_cap_monthly: float = 0,
              token_cap_daily: int = 0, token_cap_monthly: int = 0,
              scope: str = "inference", manage_write: bool = False) -> tuple[str, str]:
    """Create a key (an external app's credential into Precepta). Returns (id, token).

    Restrictable to specific backends & models, with daily/monthly USD cost caps and
    token caps. expires_in_days: default 90; None/0 = never.

    scope='manage' issues a MANAGEMENT key (Phase 15) — it can drive the
    management API. `manage_write` picks read-only vs read-write. A management key
    maps to admin/auditor role so existing role checks pass, but it is NEVER a
    platform owner, so it cannot change sovereignty (that stays owner-only).
    """
    ensure_table()
    scope = "manage" if str(scope).lower() == "manage" else "inference"
    if scope == "manage":
        role = "admin" if manage_write else "auditor"
    token = _PREFIX + secrets.token_urlsafe(32)
    kid = uuid.uuid4().hex
    now = _dt.datetime.now(_dt.UTC)
    expires_at = ((now + _dt.timedelta(days=int(expires_in_days))).isoformat()
                  if expires_in_days else None)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO api_keys (id,key_hash,name,role,team,created_at,expires_at,"
            "allowed_backends,allowed_models,cost_cap_daily,cost_cap_monthly,"
            "token_cap_daily,token_cap_monthly,scope,manage_write) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (kid, _hash(token), name, role, team, now.isoformat(), expires_at,
             _csv(allowed_backends), _csv(allowed_models),
             float(cost_cap_daily or 0), float(cost_cap_monthly or 0),
             int(token_cap_daily or 0), int(token_cap_monthly or 0),
             scope, 1 if manage_write else 0),
        )
    return kid, token


def update_key(kid: str, **fields) -> bool:
    """Edit an existing key's config (never its name or secret)."""
    ensure_table()
    # role is intentionally NOT editable — keys are app-level, never admin.
    allowed = {"allowed_backends", "allowed_models", "cost_cap_daily",
               "cost_cap_monthly", "token_cap_daily", "token_cap_monthly"}
    sets, vals = [], []
    for k, v in fields.items():
        if k in ("allowed_backends", "allowed_models"):
            v = _csv(v)
        if k == "expires_in_days":
            k = "expires_at"
            v = ((_dt.datetime.now(_dt.UTC) + _dt.timedelta(days=int(v))).isoformat()
                 if v else None)
            sets.append("expires_at=?"); vals.append(v); continue
        if k in allowed:
            sets.append(f"{k}=?"); vals.append(v)
    if not sets:
        return False
    vals.append(kid)
    with get_conn() as conn:
        cur = conn.execute(f"UPDATE api_keys SET {','.join(sets)} WHERE id=?", vals)
        return cur.rowcount > 0


def set_suspended(kid: str, suspended: bool) -> bool:
    ensure_table()
    val = _dt.datetime.now(_dt.UTC).isoformat() if suspended else None
    with get_conn() as conn:
        cur = conn.execute("UPDATE api_keys SET suspended_at=? WHERE id=? AND revoked_at IS NULL",
                           (val, kid))
        return cur.rowcount > 0


def get_key_meta(name: str) -> dict | None:
    """Scope + caps for a key, looked up by its name (= Principal.subject)."""
    ensure_table()
    with get_conn() as conn:
        row = conn.execute(
            "SELECT name,team,role,allowed_backends,allowed_models,"
            "cost_cap_daily,cost_cap_monthly,token_cap_daily,token_cap_monthly "
            "FROM api_keys WHERE name=? AND revoked_at IS NULL", (name,)).fetchone()
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
            "SELECT id,name,role,team,created_at,revoked_at,expires_at,suspended_at,"
            "allowed_backends,allowed_models,cost_cap_daily,cost_cap_monthly,"
            "token_cap_daily,token_cap_monthly FROM api_keys "
            "ORDER BY created_at DESC").fetchall()
    out = []
    for r in rows:
        expired = _is_expired(r["expires_at"])
        suspended = r["suspended_at"] is not None
        out.append(dict(r) | {
            "expired": expired,
            "suspended": suspended,
            "active": r["revoked_at"] is None and not expired and not suspended,
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
        if row["suspended_at"] is not None:         # suspended key fails auth
            return None
        keys = row.keys()
        scope = "inference"
        if "scope" in keys and row["scope"] == "manage":
            scope = "manage:rw" if ("manage_write" in keys and row["manage_write"]) else "manage:ro"
        return Principal(subject=row["name"], role=row["role"],
                         display_name=row["name"], team=row["team"] or "", scope=scope)


_api_identity = ApiKeyIdentity()


def get_api_identity() -> ApiKeyIdentity:
    return _api_identity
