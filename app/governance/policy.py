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


# ── policy loading ──────────────────────────────────────────────────────
def load_enabled(action_type: str) -> list[dict]:
    """Enabled policies whose action_type matches `action_type` or '*',
    oldest first (created_at ASC), with conditions parsed."""
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
        try:
            d["conditions"] = json.loads(d.get("conditions_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            d["conditions"] = {}
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
    max_tok = int(cond.get("max_tokens_per_day", 0) or 0)
    if max_tok > 0 and ctx.tokens_requested:
        if usage.tokens_used_today(ctx) + ctx.tokens_requested > max_tok:
            return f"daily token cap {max_tok} exceeded"
    if cond.get("require_data_tag") and not ctx.has_data_tag:
        return "missing required data-classification tag"
    max_calls = int(cond.get("max_calls_per_hour", 0) or 0)
    if max_calls > 0 and usage.calls_last_hour(ctx) >= max_calls:
        return f"hourly rate limit {max_calls} reached"
    return None


# ── CRUD (for the Console) ──────────────────────────────────────────────
def _parse(row: dict) -> dict:
    d = dict(row)
    try:
        d["conditions"] = json.loads(d.get("conditions_json") or "{}")
    except (json.JSONDecodeError, TypeError):
        d["conditions"] = {}
    return d


def list_all() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM governance_policies ORDER BY created_at ASC").fetchall()
    return [_parse(r) for r in rows]


def create_policy(name: str, description: str, action_type: str, effect: str,
                  conditions: dict) -> str:
    pid = uuid.uuid4().hex
    now = _dt.datetime.now(_dt.UTC).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO governance_policies (id,name,description,enabled,action_type,"
            "effect,conditions_json,version,created_at,updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (pid, name, description, 1, action_type, effect,
             json.dumps(conditions or {}), 1, now, now),
        )
    return pid


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
