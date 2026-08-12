"""Audit adapter (AuditSinkPort) — Phase 3 writes governance checks to
`audit_log`. Phase 4 adds the tamper-evident SHA-256 hash chain in
`tamper_evident_audit_log` + verify_chain()."""
from __future__ import annotations

import datetime as _dt
import uuid

from ...db import get_conn
from ...ports import Decision, PolicyCheckContext
from .chain import get_chain


def _now() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat()


_DDL = """
CREATE TABLE IF NOT EXISTS audit_log (
    id                 TEXT PRIMARY KEY,
    timestamp          TEXT,
    workflow_id        TEXT,
    run_id             TEXT,
    step_name          TEXT,
    action_type        TEXT,
    policy_id          TEXT,
    policy_name        TEXT,
    decision           TEXT,
    reason             TEXT,
    context_url        TEXT,
    tokens_requested   INTEGER,
    pii_detected_count INTEGER,
    execution_blocked  INTEGER
)
"""


def ensure_table() -> None:
    with get_conn() as conn:
        conn.execute(_DDL)


class SqliteAudit:
    def append_check(self, ctx: PolicyCheckContext, decision: Decision, *,
                     tokens: int | None, pii_count: int, blocked: bool) -> str:
        aid = uuid.uuid4().hex
        actor = ctx.principal.subject if ctx.principal else "anonymous"
        ensure_table()
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO audit_log (id,timestamp,workflow_id,run_id,step_name,"
                "action_type,policy_id,policy_name,decision,reason,context_url,"
                "tokens_requested,pii_detected_count,execution_blocked) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                # workflow_id/run_id columns are FK-constrained to real workflow
                # rows; free-form agent attribution lives in the chain metadata
                # below instead, so these stay null (their prior behaviour).
                (aid, _now(), None, None, actor,
                 ctx.action_type, decision.policy_id, None, decision.effect,
                 decision.reason, ctx.url, tokens, pii_count, 1 if blocked else 0),
            )
        # Also anchor the decision into the tamper-evident chain (Phase 4).
        # Agent attribution (TD-005): who/what made the call — only non-empty
        # fields are recorded, so ordinary human requests stay clean.
        meta = {"reason": decision.reason, "pii": pii_count, "audit_id": aid,
                "backend": ctx.backend}
        for k, v in (("workflow_id", ctx.workflow_id), ("run_id", ctx.run_id),
                     ("step_name", ctx.step_name), ("agent_id", ctx.agent_id),
                     ("end_user", ctx.end_user)):
            if v:
                meta[k] = v
        get_chain().append(
            event_type="governance.check", actor=actor, resource=ctx.action_type,
            action=decision.effect, outcome="blocked" if blocked else "allowed",
            metadata=meta,
        )
        return aid

    def recent(self, limit: int = 20) -> list[dict]:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]


_audit = SqliteAudit()


def get_audit() -> SqliteAudit:
    return _audit
