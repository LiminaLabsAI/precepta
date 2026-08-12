"""Policy engine — evaluate-before-execution, most-restrictive wins.

Matches the existing `governance_policies` schema. Conditions are stored as
JSON; usage counters (tokens/day, calls/hour) come from the audit log.
"""
from __future__ import annotations

import datetime as _dt
import json
import uuid

from ..db import get_conn
from ..ports import Decision, PolicyCheckContext


# ── policy table + scope (FEAT-002) ─────────────────────────────────────
_DDL = """
CREATE TABLE IF NOT EXISTS governance_policies (
    id              TEXT PRIMARY KEY,
    name            TEXT,
    description     TEXT,
    enabled         INTEGER NOT NULL DEFAULT 1,
    action_type     TEXT,
    effect          TEXT,
    conditions_json TEXT NOT NULL DEFAULT '{}',
    scope_json      TEXT NOT NULL DEFAULT '{}',
    version         INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT,
    updated_at      TEXT
)
"""


def _ensure_scope_column() -> None:
    """Ensure the policy table exists (fresh DB) and has scope_json (older DB)."""
    with get_conn() as conn:
        conn.execute(_DDL)                       # fresh DB → full table incl. scope_json
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(governance_policies)")}
        if "scope_json" not in cols:             # pre-FEAT-002 DB → add the column
            conn.execute("ALTER TABLE governance_policies "
                         "ADD COLUMN scope_json TEXT NOT NULL DEFAULT '{}'")


def scope_matches(scope: dict, key: str | None, backend: str | None, model: str | None) -> bool:
    """A policy applies when, for each non-empty scope dimension, the request's value
    is in the list. Empty scope = applies to all. An unknown request value (None) with
    a restricting list = no match (we can't confirm it's in scope)."""
    if not scope:
        return True
    for dim, val in (("keys", key), ("backends", backend), ("models", model)):
        allowed = scope.get(dim) or []
        if allowed and (val is None or val not in allowed):
            return False
    return True


# ── policy loading ──────────────────────────────────────────────────────
def load_enabled(action_type: str) -> list[dict]:
    """Enabled policies whose action_type matches `action_type` or '*',
    oldest first (created_at ASC), with conditions + scope parsed."""
    _ensure_scope_column()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM governance_policies "
            "WHERE enabled=1 AND (action_type=? OR action_type='*') "
            "ORDER BY created_at ASC",
            (action_type,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for col, key in (("conditions_json", "conditions"), ("scope_json", "scope")):
            try:
                d[key] = json.loads(d.get(col) or "{}")
            except (json.JSONDecodeError, TypeError):
                d[key] = {}
        out.append(d)
    return out


# ── usage counters (from audit_log) ─────────────────────────────────────
class DbUsage:
    def tokens_used_today(self, ctx: PolicyCheckContext) -> int:
        start = _dt.datetime.now(_dt.UTC).replace(hour=0, minute=0, second=0,
                                                  microsecond=0).isoformat()
        with get_conn() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(tokens_requested),0) AS t FROM audit_log "
                "WHERE action_type=? AND timestamp>=?",
                (ctx.action_type, start),
            ).fetchone()
        return int(row["t"] or 0)

    def calls_last_hour(self, ctx: PolicyCheckContext) -> int:
        since = (_dt.datetime.now(_dt.UTC) - _dt.timedelta(hours=1)).isoformat()
        with get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM audit_log WHERE action_type=? AND timestamp>=?",
                (ctx.action_type, since),
            ).fetchone()
        return int(row["c"] or 0)


# ── evaluation ──────────────────────────────────────────────────────────
def _violation(cond: dict, ctx: PolicyCheckContext, usage) -> str | None:
    """First matching violation → its reason; else None. Order per DESIGN.md."""
    allow = cond.get("url_allowlist")
    if ctx.url and allow and not any(a in ctx.url for a in allow):
        return f"url {ctx.url!r} not in allowlist"
    block = cond.get("url_blocklist")
    if ctx.url and block and any(b in ctx.url for b in block):
        return f"url {ctx.url!r} matches blocklist"
    # NOTE: a per-day *token* budget lives on the API KEY (token_cap_daily), not
    # here — a policy condition would duplicate it. Policies keep the rate limit
    # (calls/hour) and governance checks below.
    if cond.get("require_data_tag") and not ctx.has_data_tag:
        return "missing required data-classification tag"
    max_calls = int(cond.get("max_calls_per_hour", 0) or 0)
    if max_calls > 0 and usage.calls_last_hour(ctx) >= max_calls:
        return f"hourly rate limit {max_calls} reached"
    return None


# ── CRUD (for the Console) ──────────────────────────────────────────────
def _parse(row: dict) -> dict:
    d = dict(row)
    for col, key in (("conditions_json", "conditions"), ("scope_json", "scope")):
        try:
            d[key] = json.loads(d.get(col) or "{}")
        except (json.JSONDecodeError, TypeError):
            d[key] = {}
    return d


def list_all() -> list[dict]:
    _ensure_scope_column()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM governance_policies ORDER BY created_at ASC").fetchall()
    return [_parse(r) for r in rows]


def create_policy(name: str, description: str, action_type: str, effect: str,
                  conditions: dict, scope: dict | None = None) -> str:
    _ensure_scope_column()
    pid = uuid.uuid4().hex
    now = _dt.datetime.now(_dt.UTC).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO governance_policies (id,name,description,enabled,action_type,"
            "effect,conditions_json,scope_json,version,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (pid, name, description, 1, action_type, effect,
             json.dumps(conditions or {}), json.dumps(scope or {}), 1, now, now),
        )
    return pid


def update_policy(pid: str, *, name: str | None = None, description: str | None = None,
                  action_type: str | None = None, effect: str | None = None,
                  conditions: dict | None = None, scope: dict | None = None) -> int | None:
    """Edit a policy and BUMP its version (governance change trail). Returns new version."""
    _ensure_scope_column()
    with get_conn() as conn:
        row = conn.execute("SELECT version FROM governance_policies WHERE id=?", (pid,)).fetchone()
        if row is None:
            return None
        sets, vals = ["version=?", "updated_at=?"], [row["version"] + 1,
                                                     _dt.datetime.now(_dt.UTC).isoformat()]
        for col, v in (("name", name), ("description", description),
                       ("action_type", action_type), ("effect", effect)):
            if v is not None:
                sets.append(f"{col}=?"); vals.append(v)
        if conditions is not None:
            sets.append("conditions_json=?"); vals.append(json.dumps(conditions))
        if scope is not None:
            sets.append("scope_json=?"); vals.append(json.dumps(scope))
        vals.append(pid)
        conn.execute(f"UPDATE governance_policies SET {','.join(sets)} WHERE id=?", vals)
        return row["version"] + 1


def toggle_policy(pid: str) -> int | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT enabled FROM governance_policies WHERE id=?", (pid,)).fetchone()
        if row is None:
            return None
        new_val = 0 if row["enabled"] else 1
        conn.execute(
            "UPDATE governance_policies SET enabled=?, updated_at=? WHERE id=?",
            (new_val, _dt.datetime.now(_dt.UTC).isoformat(), pid))
    return new_val


def evaluate(ctx: PolicyCheckContext, policies: list[dict], usage) -> Decision:
    """Most-restrictive wins: block > warn > allow. Block breaks the loop."""
    decision = Decision("allow")
    for p in policies:
        reason = _violation(p.get("conditions", {}), ctx, usage)
        if not reason:
            continue
        mapped = {"block": "block", "warn": "warn"}.get(p.get("effect"), "allow")
        if mapped == "block":
            return Decision("block", reason, str(p.get("id")))
        if mapped == "warn" and decision.effect == "allow":
            decision = Decision("warn", reason, str(p.get("id")))
    return decision
