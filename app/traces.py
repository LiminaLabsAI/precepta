"""Traces (FEAT-010 / Phase 11) — a visible, reasoned record of what the
guardrail did to each request, ingress→egress.

Distinct from the learning loop's ``route_traces`` (which stores only a reward
signal): this store captures the **full per-request journey** — one ordered list
of steps, each with a plain-language decision, the *why*, its status and timing —
so a human can *see* how a request flowed and why it was allowed, blocked or
rerouted. Requests tagged with a ``run_id`` stitch into an agent-run timeline (L2).

Sovereignty & safety:
  - The store is **in-boundary** (the same local SQLite as everything else) and
    **team-scoped** — reads are filtered by the caller's team; cross-team traces
    are never returned.
  - Capture is **fail-soft** (TD-006): a failure to record a step or persist a
    trace never breaks inference. Every public function swallows its own errors.
  - Reasons are **honest**: the router's inferred intent is flagged ``inferred``;
    we never fabricate a confident "why". The request preview stored here is the
    **already-PII-redacted** text (the firewall runs first), never the raw prompt.
"""
from __future__ import annotations

import datetime as _dt
import json
import time
import uuid

from .db import get_conn

# Fixed step kinds (the ordered spine of the governed loop).
STEP_KINDS = ("firewall", "sensitivity", "policy", "cache",
              "compression", "routing", "inference", "output")

_DDL = """
CREATE TABLE IF NOT EXISTS traces (
    request_id    TEXT PRIMARY KEY,
    ts            TEXT NOT NULL,
    team          TEXT,
    principal     TEXT,
    role          TEXT,
    workflow_id   TEXT,
    run_id        TEXT,
    step_name     TEXT,
    agent_id      TEXT,
    end_user      TEXT,
    backend       TEXT,
    model         TEXT,
    outcome       TEXT,
    total_ms      INTEGER DEFAULT 0,
    pii_redacted  INTEGER DEFAULT 0,
    cost_usd      REAL DEFAULT 0,
    tokens_in     INTEGER DEFAULT 0,
    tokens_out    INTEGER DEFAULT 0,
    request_preview TEXT,
    steps_json    TEXT NOT NULL
)
"""


def ensure_table() -> None:
    with get_conn() as conn:
        conn.execute(_DDL)


def _now() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat()


class Trace:
    """Accumulator built up as ``governed_chat`` runs, then persisted once.

    All mutation is best-effort and never raises — capture must not break the
    request path.
    """

    def __init__(self, team: str, principal: str, role: str,
                 attribution: dict | None, request_preview: str = "") -> None:
        self.request_id = uuid.uuid4().hex
        self.team = team or ""
        self.principal = principal or ""
        self.role = role or ""
        a = attribution or {}
        self.workflow_id = a.get("workflow_id")
        self.run_id = a.get("run_id")
        self.step_name = a.get("step_name")
        self.agent_id = a.get("agent_id")
        self.end_user = a.get("end_user")
        self.request_preview = (request_preview or "")[:280]
        self.backend = None
        self.model = None
        self.outcome = "allowed"
        self.pii_redacted = 0
        self.cost_usd = 0.0
        self.tokens_in = 0
        self.tokens_out = 0
        self.steps: list[dict] = []
        self._t0 = time.perf_counter()
        self._last = self._t0

    def step(self, name: str, decision: str, reason: str, *, status: str = "ok",
             inferred: bool = False) -> None:
        """Append one governed step. ``status`` ∈ ok|blocked|warn|hit|failed|skipped."""
        try:
            now = time.perf_counter()
            ms = int((now - self._last) * 1000)
            self._last = now
            s = {"name": name, "decision": decision, "reason": reason,
                 "status": status, "ms": ms}
            if inferred:
                s["inferred"] = True
            self.steps.append(s)
        except Exception:
            pass


def begin(team: str, principal: str, role: str, attribution: dict | None,
          request_preview: str = "") -> Trace | None:
    """Start a trace. Returns None on any failure (capture stays optional)."""
    try:
        return Trace(team, principal, role, attribution, request_preview)
    except Exception:
        return None


def save(tr: Trace | None, outcome: str, *, backend: str | None = None,
         model: str | None = None, pii: int = 0, cost_usd: float = 0.0,
         tokens_in: int = 0, tokens_out: int = 0) -> None:
    """Persist the accumulated trace. Fail-soft — never raises."""
    if tr is None:
        return
    try:
        tr.outcome = outcome
        tr.backend = backend or tr.backend
        tr.model = model or tr.model
        tr.pii_redacted = pii
        tr.cost_usd = float(cost_usd or 0)
        tr.tokens_in = int(tokens_in or 0)
        tr.tokens_out = int(tokens_out or 0)
        total_ms = int((time.perf_counter() - tr._t0) * 1000)
        ensure_table()
        with get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO traces (request_id,ts,team,principal,role,"
                "workflow_id,run_id,step_name,agent_id,end_user,backend,model,outcome,"
                "total_ms,pii_redacted,cost_usd,tokens_in,tokens_out,request_preview,"
                "steps_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (tr.request_id, _now(), tr.team, tr.principal, tr.role,
                 tr.workflow_id, tr.run_id, tr.step_name, tr.agent_id, tr.end_user,
                 tr.backend, tr.model, tr.outcome, total_ms, int(tr.pii_redacted or 0),
                 tr.cost_usd, tr.tokens_in, tr.tokens_out, tr.request_preview,
                 json.dumps(tr.steps)))
    except Exception:
        pass


# ── reads (team-scoped) ──────────────────────────────────────────────────────

def _row_summary(r) -> dict:
    return {
        "request_id": r["request_id"], "ts": r["ts"],
        "principal": r["principal"], "role": r["role"],
        "run_id": r["run_id"], "step_name": r["step_name"],
        "agent_id": r["agent_id"], "end_user": r["end_user"],
        "backend": r["backend"], "model": r["model"], "outcome": r["outcome"],
        "total_ms": r["total_ms"], "pii_redacted": r["pii_redacted"],
        "cost_usd": r["cost_usd"], "tokens_in": r["tokens_in"],
        "tokens_out": r["tokens_out"], "request_preview": r["request_preview"],
        "step_count": _count(r["steps_json"]),
    }


def _count(steps_json: str) -> int:
    try:
        return len(json.loads(steps_json or "[]"))
    except Exception:
        return 0


def list_traces(team: str, limit: int = 50, run_id: str | None = None,
                outcome: str | None = None) -> list[dict]:
    try:
        ensure_table()
        q = "SELECT * FROM traces WHERE team=?"
        args: list = [team or ""]
        if run_id:
            q += " AND run_id=?"; args.append(run_id)
        if outcome:
            q += " AND outcome=?"; args.append(outcome)
        q += " ORDER BY ts DESC LIMIT ?"; args.append(int(limit))
        with get_conn() as conn:
            rows = conn.execute(q, tuple(args)).fetchall()
        return [_row_summary(r) for r in rows]
    except Exception:
        return []


def get_trace(request_id: str, team: str) -> dict | None:
    try:
        ensure_table()
        with get_conn() as conn:
            r = conn.execute(
                "SELECT * FROM traces WHERE request_id=? AND team=?",
                (request_id, team or "")).fetchone()
        if r is None:
            return None
        out = _row_summary(r)
        try:
            out["steps"] = json.loads(r["steps_json"] or "[]")
        except Exception:
            out["steps"] = []
        return out
    except Exception:
        return None


def get_run(run_id: str, team: str) -> dict:
    """The agent-run timeline (L2): every trace tagged with this run_id, in order."""
    try:
        ensure_table()
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM traces WHERE run_id=? AND team=? ORDER BY ts ASC",
                (run_id, team or "")).fetchall()
        traces = []
        for r in rows:
            t = _row_summary(r)
            try:
                t["steps"] = json.loads(r["steps_json"] or "[]")
            except Exception:
                t["steps"] = []
            traces.append(t)
        return {"run_id": run_id, "count": len(traces), "traces": traces}
    except Exception:
        return {"run_id": run_id, "count": 0, "traces": []}


def stats(team: str) -> dict:
    """KPI aggregates for the Traces overview — all real, team-scoped.

    ``escalation_rate`` is intentionally ``None`` until the smart router (Phase
    12) exists to escalate; the UI shows "—" rather than a fabricated number.
    """
    try:
        ensure_table()
        with get_conn() as conn:
            tot = conn.execute(
                "SELECT COUNT(*) n, "
                "COALESCE(SUM(outcome IN ('allowed','warn')),0) accepted, "
                "COALESCE(SUM(cost_usd),0) cost "
                "FROM traces WHERE team=?", (team or "",)).fetchone()
            mix = conn.execute(
                "SELECT backend, COUNT(*) n FROM traces WHERE team=? AND backend IS NOT NULL "
                "GROUP BY backend ORDER BY n DESC", (team or "",)).fetchall()
        n = tot["n"] or 0
        accepted = tot["accepted"] or 0
        cost = tot["cost"] or 0.0
        return {
            "total": n,
            "accepted": accepted,
            "acceptance_rate": round(100.0 * accepted / n, 1) if n else None,
            "cost_per_accepted": round(cost / accepted, 6) if accepted else None,
            "route_mix": [{"backend": r["backend"], "count": r["n"]} for r in mix],
            "escalation_rate": None,   # arrives with the smart router (Phase 12)
        }
    except Exception:
        return {"total": 0, "accepted": 0, "acceptance_rate": None,
                "cost_per_accepted": None, "route_mix": [], "escalation_rate": None}


def clear(team: str | None = None) -> None:
    try:
        ensure_table()
        with get_conn() as conn:
            if team is None:
                conn.execute("DELETE FROM traces")
            else:
                conn.execute("DELETE FROM traces WHERE team=?", (team,))
    except Exception:
        pass
