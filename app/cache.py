"""Response cache (FEAT-003) — reuse a prior answer instead of re-calling a model.

Governing stance (safe by default, risk only by opt-in):
  - OFF until an admin enables it.
  - Only DETERMINISTIC requests are cached (temperature 0) — a temp>0 request is
    meant to vary, so caching it would be a surprise.
  - SENSITIVE requests (PII/PHI or data-tagged) are NEVER cached or served from
    cache — the same fence the router uses.
  - Cache hits are still governed: the input firewall + policy run BEFORE the
    cache is consulted, and every hit is audited as a cache hit.
  - Metering counts the request (usage) but charges the budget $0 — no inference
    ran (the one meter() definition, TD-002).
  - Scope is per-team; savings visibility is ADMIN-ONLY (invisible to end users).

Exact-match by default; semantic (opt-in) matches a near-duplicate via
**in-boundary** embeddings (Ollama nomic-embed-text) above a similarity
threshold (default 1.0 = exact). Every cache path is FAIL-SOFT (TD-006): any
error degrades to a cache miss / skipped store and never breaks inference.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import math

import httpx

from .db import get_conn
from . import org, pricing
from .settings import get_settings

_DDL_CACHE = """
CREATE TABLE IF NOT EXISTS response_cache (
    cache_key   TEXT NOT NULL,
    team        TEXT NOT NULL DEFAULT '',
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


# ── config (admin-set org settings) ──────────────────────────────────────
def enabled() -> bool:
    return org.get("cache_enabled", "false") == "true"


def semantic_enabled() -> bool:
    return org.get("cache_semantic", "false") == "true"


def threshold() -> float:
    try:
        return float(org.get("cache_threshold", "1.0"))
    except (ValueError, TypeError):
        return 1.0


# ── keying ───────────────────────────────────────────────────────────────
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


def is_cacheable(kw: dict, sensitive: bool) -> bool:
    """Deterministic + non-sensitive + cache enabled. Anything else → don't cache."""
    if not enabled() or sensitive:
        return False
    temp = kw.get("temperature")
    return temp == 0 or temp == 0.0


# ── embeddings (semantic, in-boundary) ───────────────────────────────────
def embed(text: str) -> list[float] | None:
    """In-boundary embedding via Ollama. Fail-soft → None."""
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


# ── lookup / store ───────────────────────────────────────────────────────
def lookup(model_str: str, messages: list[dict], kw: dict, team: str) -> dict | None:
    """Return the cached entry (dict incl. `response`) for a hit, else None. Fail-soft."""
    try:
        ensure_tables()
        key = cache_key(model_str, messages, kw)
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM response_cache WHERE cache_key=? AND team=?",
                (key, team)).fetchone()
        if row is not None:
            return _entry(row, exact=True)

        if not semantic_enabled():
            return None
        thr = threshold()
        if thr >= 1.0:                       # threshold 1.0 = exact only
            return None
        qvec = embed(_query_text(messages))
        if qvec is None:
            return None
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM response_cache WHERE team=? AND embedding IS NOT NULL",
                (team,)).fetchall()
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
    except Exception:                        # fail-soft: any error → cache miss
        return None


def _entry(row, *, exact: bool, similarity: float = 1.0) -> dict:
    return {
        "cache_key": row["cache_key"], "team": row["team"],
        "backend": row["backend"], "model": row["model"],
        "response": json.loads(row["response_json"]),
        "prompt_tokens": row["prompt_tokens"], "completion_tokens": row["completion_tokens"],
        "exact": exact, "similarity": similarity,
    }


def store(model_str: str, messages: list[dict], kw: dict, team: str,
          response: dict, tokens_in: int, tokens_out: int,
          backend: str, model: str) -> None:
    """Persist a fresh answer for reuse. Fail-soft (a store failure never surfaces)."""
    try:
        ensure_tables()
        key = cache_key(model_str, messages, kw)
        emb = None
        if semantic_enabled():
            vec = embed(_query_text(messages))
            emb = json.dumps(vec) if vec is not None else None
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO response_cache (cache_key,team,model,backend,response_json,"
                "prompt_tokens,completion_tokens,embedding,created_at,hit_count) "
                "VALUES (?,?,?,?,?,?,?,?,?,0) "
                "ON CONFLICT(cache_key,team) DO UPDATE SET response_json=excluded.response_json, "
                "prompt_tokens=excluded.prompt_tokens, completion_tokens=excluded.completion_tokens, "
                "embedding=excluded.embedding",
                (key, team, model or "", backend or "", json.dumps(response),
                 int(tokens_in or 0), int(tokens_out or 0), emb, _now()))
    except Exception:
        pass


def record_hit(entry: dict, team: str) -> dict:
    """Count the hit + log the savings (tokens + cost avoided). Returns the meter fields."""
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
                "INSERT INTO cache_savings (team,tokens_saved,cost_saved_usd,at) VALUES (?,?,?,?)",
                (team, saved_tokens, round(cost, 6), _now()))
    except Exception:
        pass
    return {"tokens_saved": saved_tokens, "cost_saved_usd": round(cost, 6)}


# ── stats (admin-only surface) ───────────────────────────────────────────
def stats() -> dict:
    ensure_tables()
    with get_conn() as conn:
        entries = conn.execute("SELECT COUNT(*) c, COALESCE(SUM(hit_count),0) h "
                               "FROM response_cache").fetchone()
        sv = conn.execute("SELECT COUNT(*) hits, COALESCE(SUM(tokens_saved),0) t, "
                          "COALESCE(SUM(cost_saved_usd),0) c FROM cache_savings").fetchone()
    return {
        "enabled": enabled(), "semantic": semantic_enabled(), "threshold": threshold(),
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
