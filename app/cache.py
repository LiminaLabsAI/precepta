"""Response cache (FEAT-003, per-endpoint in FEAT-011) — reuse a prior answer.

Configured PER inference endpoint (see app/features.py): each endpoint (or the
"auto" router row) has its own on/off, strategy (exact | semantic) and threshold.

Governing stance (unchanged): only DETERMINISTIC requests are cached
(temperature 0); SENSITIVE requests (PII/PHI or data-tagged) are never cached or
served; hits stay governed (firewall + policy run first, hit is audited) and are
metered as usage with $0 budget charge (TD-002). Per-team scope; savings are
admin-only. Every path is FAIL-SOFT (TD-006).
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math

import httpx

from .db import get_conn
from . import pricing, features
from .settings import get_settings

_DDL_CACHE = """
CREATE TABLE IF NOT EXISTS response_cache (
    cache_key   TEXT NOT NULL,
    team        TEXT NOT NULL DEFAULT '',
    endpoint    TEXT DEFAULT '',
    model       TEXT DEFAULT '',
    backend     TEXT DEFAULT '',
    response_json TEXT NOT NULL,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    embedding   TEXT,
    created_at  TEXT NOT NULL,
    hit_count   INTEGER DEFAULT 0,
    last_hit_at TEXT,
    PRIMARY KEY (cache_key, team)
)
"""
_DDL_SAVINGS = """
CREATE TABLE IF NOT EXISTS cache_savings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team TEXT DEFAULT '',
    endpoint TEXT DEFAULT '',
    tokens_saved INTEGER DEFAULT 0,
    cost_saved_usd REAL DEFAULT 0,
    at TEXT NOT NULL
)
"""
_EMBED_MODEL = "nomic-embed-text"


def _now() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat()


def ensure_tables() -> None:
    with get_conn() as conn:
        conn.execute(_DDL_CACHE)
        conn.execute(_DDL_SAVINGS)
        for tbl in ("response_cache", "cache_savings"):   # migrate older DBs
            try:
                conn.execute(f"ALTER TABLE {tbl} ADD COLUMN endpoint TEXT DEFAULT ''")
            except Exception:
                pass


# ── per-endpoint gating ───────────────────────────────────────────────────
def is_cacheable(kw: dict, sensitive: bool, endpoint: str) -> bool:
    """Deterministic + non-sensitive + this endpoint has caching on."""
    if sensitive or not features.cache_on(endpoint):
        return False
    temp = kw.get("temperature")
    return temp == 0 or temp == 0.0


# ── keying ────────────────────────────────────────────────────────────────
def _norm(model_str: str, messages: list[dict], kw: dict) -> str:
    payload = {
        "model": model_str or "",
        "messages": [{"role": m.get("role"), "content": m.get("content")} for m in messages],
        "temperature": kw.get("temperature"),
        "max_tokens": kw.get("max_tokens"),
        "top_p": kw.get("top_p"),
    }
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def cache_key(model_str: str, messages: list[dict], kw: dict) -> str:
    return hashlib.sha256(_norm(model_str, messages, kw).encode()).hexdigest()


# ── embeddings (semantic, in-boundary) ────────────────────────────────────
def embed(text: str) -> list[float] | None:
    try:
        port = get_settings().ollama_port
        r = httpx.post(f"http://127.0.0.1:{port}/api/embeddings", timeout=10.0,
                       json={"model": _EMBED_MODEL, "prompt": text or ""})
        r.raise_for_status()
        vec = r.json().get("embedding")
        return vec if isinstance(vec, list) and vec else None
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        return None


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _query_text(messages: list[dict]) -> str:
    return next((m.get("content", "") for m in reversed(messages)
                 if m.get("role") == "user"), "")


# ── "smart" strategy: auto-decide exact vs semantic vs skip, per request ─────
# Time-sensitive / personalized phrasings where reusing a prior answer risks
# serving something stale — so the smart strategy SKIPS the cache for these.
_SKIP_HINTS = (
    "today", "right now", "as of", "currently", "current ", "latest",
    "this week", "this month", "this year", "breaking", "live ", "just now",
    "stock price", "weather", "news",
)


def decide_smart(messages: list[dict]) -> str:
    """For a 'smart' endpoint, pick 'exact' | 'semantic' | 'skip' for THIS request.

    - skip: the ask looks time-sensitive/personalized — don't reuse a stale answer.
    - exact: short/lookup-style — only reuse an identical request (semantic could
      confidently return a wrong near-match).
    - semantic: a longer natural-language question — a close match is worth reusing.
    """
    q = _query_text(messages).strip().lower()
    if not q:
        return "exact"
    if any(h in q for h in _SKIP_HINTS):
        return "skip"
    if len(q) < 40:
        return "exact"
    return "semantic"


def effective_strategy(endpoint: str, messages: list[dict]) -> str:
    """Resolve the endpoint's configured strategy to a concrete per-request one."""
    strat = features.cache_strategy(endpoint)
    if strat == "smart":
        return decide_smart(messages)
    return strat if strat in ("exact", "semantic") else "exact"


# ── lookup / store ────────────────────────────────────────────────────────
def lookup(model_str: str, messages: list[dict], kw: dict, team: str, endpoint: str) -> dict | None:
    """Return the cached entry for a hit, else None. Strategy is per endpoint. Fail-soft."""
    try:
        eff = effective_strategy(endpoint, messages)
        if eff == "skip":                       # smart decided this request shouldn't reuse
            return None
        ensure_tables()
        key = cache_key(model_str, messages, kw)
        with get_conn() as conn:
            row = conn.execute("SELECT * FROM response_cache WHERE cache_key=? AND team=?",
                               (key, team)).fetchone()
        if row is not None:
            return _entry(row, exact=True)

        if eff != "semantic":
            return None
        thr = features.cache_threshold(endpoint)
        if thr >= 1.0:
            return None
        qvec = embed(_query_text(messages))
        if qvec is None:
            return None
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM response_cache WHERE team=? AND endpoint=? AND embedding IS NOT NULL",
                (team, endpoint)).fetchall()
        best, best_sim = None, 0.0
        for r in rows:
            try:
                vec = json.loads(r["embedding"])
            except (ValueError, TypeError):
                continue
            sim = _cosine(qvec, vec)
            if sim > best_sim:
                best, best_sim = r, sim
        if best is not None and best_sim >= thr:
            return _entry(best, exact=False, similarity=round(best_sim, 4))
        return None
    except Exception:
        return None


def _entry(row, *, exact: bool, similarity: float = 1.0) -> dict:
    return {
        "cache_key": row["cache_key"], "team": row["team"],
        "endpoint": (row["endpoint"] if "endpoint" in row.keys() else "") or "",
        "backend": row["backend"], "model": row["model"],
        "response": json.loads(row["response_json"]),
        "prompt_tokens": row["prompt_tokens"], "completion_tokens": row["completion_tokens"],
        "exact": exact, "similarity": similarity,
    }


def store(model_str: str, messages: list[dict], kw: dict, team: str, endpoint: str,
          response: dict, tokens_in: int, tokens_out: int, backend: str, model: str) -> None:
    """Persist a fresh answer for reuse under this endpoint's config. Fail-soft."""
    try:
        eff = effective_strategy(endpoint, messages)
        if eff == "skip":                       # smart decided not to cache this one
            return
        ensure_tables()
        key = cache_key(model_str, messages, kw)
        emb = None
        if eff == "semantic":                   # store an embedding only when semantic reuse is on
            vec = embed(_query_text(messages))
            emb = json.dumps(vec) if vec is not None else None
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO response_cache (cache_key,team,endpoint,model,backend,response_json,"
                "prompt_tokens,completion_tokens,embedding,created_at,hit_count) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,0) "
                "ON CONFLICT(cache_key,team) DO UPDATE SET response_json=excluded.response_json, "
                "endpoint=excluded.endpoint, prompt_tokens=excluded.prompt_tokens, "
                "completion_tokens=excluded.completion_tokens, embedding=excluded.embedding",
                (key, team, endpoint, model or "", backend or "", json.dumps(response),
                 int(tokens_in or 0), int(tokens_out or 0), emb, _now()))
    except Exception:
        pass


def record_hit(entry: dict, team: str) -> dict:
    tokens_in = int(entry.get("prompt_tokens") or 0)
    tokens_out = int(entry.get("completion_tokens") or 0)
    saved_tokens = tokens_in + tokens_out
    try:
        cost = pricing.cost_of(entry.get("backend") or "", entry.get("model") or "",
                               tokens_in, tokens_out)
    except Exception:
        cost = 0.0
    try:
        ensure_tables()
        with get_conn() as conn:
            conn.execute(
                "UPDATE response_cache SET hit_count=hit_count+1, last_hit_at=? "
                "WHERE cache_key=? AND team=?", (_now(), entry["cache_key"], team))
            conn.execute(
                "INSERT INTO cache_savings (team,endpoint,tokens_saved,cost_saved_usd,at) "
                "VALUES (?,?,?,?,?)",
                (team, entry.get("endpoint") or "", saved_tokens, round(cost, 6), _now()))
    except Exception:
        pass
    return {"tokens_saved": saved_tokens, "cost_saved_usd": round(cost, 6)}


# ── stats (admin-only) — overall or per endpoint ──────────────────────────
def stats(endpoint: str | None = None) -> dict:
    ensure_tables()
    where = "WHERE endpoint=?" if endpoint is not None else ""
    args = (endpoint,) if endpoint is not None else ()
    with get_conn() as conn:
        entries = conn.execute(f"SELECT COUNT(*) c, COALESCE(SUM(hit_count),0) h "
                               f"FROM response_cache {where}", args).fetchone()
        sv = conn.execute(f"SELECT COUNT(*) hits, COALESCE(SUM(tokens_saved),0) t, "
                          f"COALESCE(SUM(cost_saved_usd),0) c FROM cache_savings {where}",
                          args).fetchone()
    return {
        "entries": entries["c"], "hits": sv["hits"],
        "tokens_saved": sv["t"], "cost_saved_usd": round(sv["c"] or 0.0, 6),
    }


def clear() -> int:
    ensure_tables()
    with get_conn() as conn:
        n = conn.execute("SELECT COUNT(*) c FROM response_cache").fetchone()["c"]
        conn.execute("DELETE FROM response_cache")
        conn.execute("DELETE FROM cache_savings")
    return n
