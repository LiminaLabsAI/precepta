"""Learning loop (FEAT-008) — route smarter over time from real outcomes.

Every auto-routed request leaves a **trace** (which backend served which kind of
request, how it went). A reward is derived from an **explicit** signal (a
Playground thumbs-up/down) and **implicit** ones (did it fail over?). Over time
the router prefers, for each difficulty bucket, the backend with the best average
reward — evidence replacing the hand-tuned heuristic.

Governing stance:
  - OFF by default (safe); enabling it only *biases* routing — it never escapes
    the governance filter or the sovereign/in-boundary constraint (the learned
    backend must still be an eligible candidate).
  - Requires evidence before it acts: a backend needs at least ``MIN_TRACES``
    rewarded traces in a bucket before it can be preferred, and only if its mean
    reward is positive. Otherwise the router falls back to its base decision.
  - Fully explainable: the plan reason says exactly why (bucket → backend, mean
    reward, n).
  - Traces are per-deployment and in-boundary — never pooled across customers.

The router quality this optimises is measured by the LOCKED eval harness (Rule
11): the evaluator was frozen before this loop was built.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import uuid

from .db import get_conn
from . import org, pricing

MIN_TRACES = 3          # evidence bar before a backend can be preferred in a bucket

_DDL = """
CREATE TABLE IF NOT EXISTS route_traces (
    id          TEXT PRIMARY KEY,
    ts          TEXT NOT NULL,
    query_hash  TEXT,
    difficulty  TEXT,
    backend     TEXT,
    technique   TEXT,
    latency_ms  INTEGER,
    cost_usd    REAL DEFAULT 0,
    fell_over   INTEGER DEFAULT 0,
    rating      INTEGER DEFAULT 0,
    reward      REAL DEFAULT 0
)
"""


def ensure_table() -> None:
    with get_conn() as conn:
        conn.execute(_DDL)


def _now() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat()


def enabled() -> bool:
    return org.get("learning_enabled", "false") == "true"


def _reward(rating: int, fell_over: bool) -> float:
    """Explicit rating dominates; a clean completion is mildly positive; a
    failover is penalised. Bounded to [-1, 1]."""
    base = 1.0 if rating > 0 else (-1.0 if rating < 0 else 0.1)
    if fell_over:
        base -= 0.5
    return max(-1.0, min(1.0, base))


def record_trace(query: str, difficulty: str, backend: str, technique: str,
                 latency_ms: int, cost_usd: float, fell_over: bool) -> str:
    """Persist one routing outcome; returns the trace id (attach feedback to it). Fail-soft."""
    tid = uuid.uuid4().hex
    try:
        ensure_table()
        qh = hashlib.sha256((query or "").encode()).hexdigest()[:16]
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO route_traces (id,ts,query_hash,difficulty,backend,technique,"
                "latency_ms,cost_usd,fell_over,rating,reward) VALUES (?,?,?,?,?,?,?,?,?,0,?)",
                (tid, _now(), qh, difficulty, backend, technique, int(latency_ms or 0),
                 float(cost_usd or 0), 1 if fell_over else 0, _reward(0, bool(fell_over))))
    except Exception:
        pass
    return tid


def apply_feedback(trace_id: str, rating: int) -> bool:
    """Attach an explicit thumbs rating (+1/-1) and recompute the trace reward."""
    rating = 1 if rating > 0 else (-1 if rating < 0 else 0)
    try:
        ensure_table()
        with get_conn() as conn:
            row = conn.execute("SELECT fell_over FROM route_traces WHERE id=?",
                               (trace_id,)).fetchone()
            if row is None:
                return False
            reward = _reward(rating, bool(row["fell_over"]))
            conn.execute("UPDATE route_traces SET rating=?, reward=? WHERE id=?",
                         (rating, reward, trace_id))
        return True
    except Exception:
        return False


def preference(difficulty: str, allowed: set[str] | None = None) -> str | None:
    """Best backend for this difficulty bucket by mean reward, if there is enough
    evidence and it is positive. `allowed` restricts to eligible backends."""
    try:
        ensure_table()
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT backend, COUNT(*) n, AVG(reward) avg_r FROM route_traces "
                "WHERE difficulty=? GROUP BY backend", (difficulty,)).fetchall()
    except Exception:
        return None
    best, best_r = None, 0.0
    for r in rows:
        if r["n"] < MIN_TRACES:
            continue
        if allowed is not None and r["backend"] not in allowed:
            continue
        if r["avg_r"] > best_r:
            best, best_r = r["backend"], r["avg_r"]
    return best


def stats() -> dict:
    ensure_table()
    with get_conn() as conn:
        tot = conn.execute("SELECT COUNT(*) n, COALESCE(SUM(rating<>0),0) rated FROM route_traces").fetchone()
        rows = conn.execute(
            "SELECT difficulty, backend, COUNT(*) n, ROUND(AVG(reward),3) avg_r "
            "FROM route_traces GROUP BY difficulty, backend ORDER BY difficulty, avg_r DESC"
        ).fetchall()
    return {
        "enabled": enabled(), "traces": tot["n"], "rated": tot["rated"],
        "min_traces": MIN_TRACES,
        "buckets": [dict(r) for r in rows],
    }


def clear() -> None:
    ensure_table()
    with get_conn() as conn:
        conn.execute("DELETE FROM route_traces")
