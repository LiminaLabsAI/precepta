"""OpenGuard authorization adapter (AuthorizationPort) — FEAT-004.

Richer authZ behind the same port the domain already depends on (DIP), so it
swaps in for the hardcoded RoleCheck with no core change:

  - **RBAC (configurable):** role → permission set, editable at runtime and
    persisted. Seeded to preserve today's behaviour (admin=all, auditor=read,
    user=chat+read), so nothing regresses on first boot.
  - **ABAC (attribute conditions):** a permission may carry a `when` clause
    (e.g. `{"team": "finance"}`) — granted only if the principal matches. This
    is the attribute-based layer; the condition vocabulary is small and
    extensible.
  - **Agent budgets:** a per-`agent_id` daily request cap (ties to the agent
    attribution in TD-005) — an autonomous caller can be bounded independently
    of the human/key it runs under.

A full external OpenGuard/OPA policy engine would slot in behind this same port;
this is the in-boundary V1.
"""
from __future__ import annotations

import datetime as _dt
import json

from ...db import get_conn
from ...ports import Principal

_READ_ONLY = {"audit.read", "attestation.read"}

_DEFAULT_ROLES = {
    "admin": ["*"],
    "auditor": sorted(_READ_ONLY),
    "user": sorted({"chat.completion"} | _READ_ONLY),
}

_DDL_ROLES = "CREATE TABLE IF NOT EXISTS authz_roles (role TEXT PRIMARY KEY, permissions TEXT NOT NULL)"
_DDL_BUDGET = ("CREATE TABLE IF NOT EXISTS agent_budgets "
               "(agent_id TEXT PRIMARY KEY, daily_request_cap INTEGER, note TEXT, created_at TEXT)")
_DDL_USAGE = ("CREATE TABLE IF NOT EXISTS agent_usage "
              "(agent_id TEXT, day TEXT, count INTEGER DEFAULT 0, PRIMARY KEY (agent_id, day))")


def ensure_tables() -> None:
    with get_conn() as conn:
        conn.execute(_DDL_ROLES)
        conn.execute(_DDL_BUDGET)
        conn.execute(_DDL_USAGE)


def _today() -> str:
    return _dt.datetime.now(_dt.UTC).date().isoformat()


# ── RBAC config ──────────────────────────────────────────────────────────
def permissions_for(role: str) -> list:
    ensure_tables()
    with get_conn() as conn:
        row = conn.execute("SELECT permissions FROM authz_roles WHERE role=?", (role,)).fetchone()
    if row is not None:
        try:
            return json.loads(row["permissions"])
        except (ValueError, TypeError):
            return []
    return list(_DEFAULT_ROLES.get(role, []))


def all_roles() -> dict:
    return {role: permissions_for(role) for role in _DEFAULT_ROLES}


def set_role_permissions(role: str, permissions: list) -> None:
    ensure_tables()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO authz_roles (role,permissions) VALUES (?,?) "
            "ON CONFLICT(role) DO UPDATE SET permissions=excluded.permissions",
            (role, json.dumps(permissions)))


def _conditions_ok(when: dict, principal: Principal) -> bool:
    """ABAC: every attribute in `when` must match the principal. Small, extensible."""
    for key, val in (when or {}).items():
        if key == "team" and (getattr(principal, "team", "") or "") != val:
            return False
        if key == "role" and getattr(principal, "role", "") != val:
            return False
    return True


# ── agent budgets ────────────────────────────────────────────────────────
def set_agent_budget(agent_id: str, daily_request_cap: int, note: str = "") -> None:
    ensure_tables()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO agent_budgets (agent_id,daily_request_cap,note,created_at) VALUES (?,?,?,?) "
            "ON CONFLICT(agent_id) DO UPDATE SET daily_request_cap=excluded.daily_request_cap, "
            "note=excluded.note",
            (agent_id, int(daily_request_cap), note, _dt.datetime.now(_dt.UTC).isoformat()))


def list_agent_budgets() -> list[dict]:
    ensure_tables()
    day = _today()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT b.agent_id, b.daily_request_cap, b.note, "
            "COALESCE(u.count,0) used_today FROM agent_budgets b "
            "LEFT JOIN agent_usage u ON u.agent_id=b.agent_id AND u.day=? "
            "ORDER BY b.agent_id", (day,)).fetchall()
    return [dict(r) for r in rows]


def check_and_record_agent(agent_id: str) -> tuple[bool, str | None]:
    """Count one request against the agent's daily cap. Returns (allowed, reason).
    No budget set → unbounded (allowed). Over cap → blocked, not counted."""
    if not agent_id:
        return True, None
    ensure_tables()
    day = _today()
    with get_conn() as conn:
        b = conn.execute("SELECT daily_request_cap FROM agent_budgets WHERE agent_id=?",
                         (agent_id,)).fetchone()
        if b is None or b["daily_request_cap"] is None:
            return True, None                       # no budget → unbounded
        cap = int(b["daily_request_cap"])
        u = conn.execute("SELECT count FROM agent_usage WHERE agent_id=? AND day=?",
                         (agent_id, day)).fetchone()
        used = u["count"] if u else 0
        if used >= cap:
            return False, (f"agent {agent_id!r} exceeded its daily request cap "
                           f"({cap}) — {used} used today")
        conn.execute(
            "INSERT INTO agent_usage (agent_id,day,count) VALUES (?,?,1) "
            "ON CONFLICT(agent_id,day) DO UPDATE SET count=count+1", (agent_id, day))
    return True, None


class OpenGuard:
    """AuthorizationPort — configurable RBAC + ABAC conditions (agent budgets are
    enforced in the request path via check_and_record_agent)."""

    name = "openguard"

    def can(self, principal: Principal, action: str, resource: str = "") -> bool:
        role = getattr(principal, "role", "")
        for perm in permissions_for(role):
            if isinstance(perm, str):
                act, when = perm, {}
            elif isinstance(perm, dict):
                act, when = perm.get("action", ""), perm.get("when", {})
            else:
                continue
            if (act == "*" or act == action) and _conditions_ok(when, principal):
                return True
        return False

    def budget(self, principal: Principal) -> dict:
        return {}


_authz = OpenGuard()


def get_openguard() -> OpenGuard:
    return _authz
