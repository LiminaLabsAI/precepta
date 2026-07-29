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


class SqliteAudit:
    def append_check(self, ctx: PolicyCheckContext, decision: Decision, *,
                     tokens: int | None, pii_count: int, blocked: bool) -> str:
        aid = uuid.uuid4().hex
        actor = ctx.principal.subject if ctx.principal else "anonymous"
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO audit_log (id,timestamp,workflow_id,run_id,step_name,"
                "action_type,policy_id,policy_name,decision,reason,context_url,"
                "tokens_requested,pii_detected_count,execution_blocked) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (aid, _now(), ctx.workflow_id, ctx.run_id, actor,
                 ctx.action_type, decision.policy_id, None, decision.effect,
                 decision.reason, ctx.url, tokens, pii_count, 1 if blocked else 0),
            )
        # Also anchor the decision into the tamper-evident chain (Phase 4).
        get_chain().append(
            event_type="governance.check", actor=actor, resource=ctx.action_type,
            action=decision.effect, outcome="blocked" if blocked else "allowed",
            metadata={"reason": decision.reason, "pii": pii_count, "audit_id": aid,
                      "backend": ctx.backend},
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
