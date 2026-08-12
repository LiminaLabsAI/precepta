"""Prompt compression (FEAT-005, per-endpoint in FEAT-011) — shorten prompts.

Configured PER inference endpoint (app/features.py): each endpoint (or the "auto"
row) chooses on/off and mode. **baseline** is quality-safe (whitespace only);
**aggressive** also strips conservative filler (lossy) and, when it shortens a
request, is surfaced in `precepta.compression` plus a deduped admin alert — never
a silent quality trade. Fail-soft (TD-006). Real semantic compression (LLMLingua)
and BYO methods are later additions behind the same shape.
"""
from __future__ import annotations

import datetime as _dt
import re

from .db import get_conn
from . import features

_DDL = """
CREATE TABLE IF NOT EXISTS compression_savings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT DEFAULT 'baseline',
    endpoint TEXT DEFAULT '',
    tokens_saved INTEGER DEFAULT 0,
    at TEXT NOT NULL
)
"""

_FILLER = {"please", "kindly", "just", "really", "very", "actually",
           "basically", "simply", "literally"}


def ensure_table() -> None:
    with get_conn() as conn:
        conn.execute(_DDL)
        try:
            conn.execute("ALTER TABLE compression_savings ADD COLUMN endpoint TEXT DEFAULT ''")
        except Exception:
            pass


def _now() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat()


def enabled(endpoint: str) -> bool:
    return features.compression_on(endpoint)


def aggressive_on(endpoint: str) -> bool:
    return features.compression_aggressive(endpoint)


def _user_len(messages: list[dict]) -> int:
    return sum(len(m.get("content") or "") for m in messages if m.get("role") == "user")


def decide_smart(messages: list[dict]) -> str:
    """For a 'smart' endpoint, pick 'skip' | 'baseline' | 'aggressive' for THIS
    request by how much there is to save:
    - skip: short prompt — nothing worth trimming.
    - aggressive: very long prompt — the lossy trim pays for itself.
    - baseline: everything in between (quality-safe, never changes meaning).
    """
    n = _user_len(messages)
    if n < 400:
        return "skip"
    if n > 4000:
        return "aggressive"
    return "baseline"


def effective_mode(endpoint: str, messages: list[dict]) -> str:
    """Resolve the endpoint's configured mode to a concrete per-request one."""
    mode = features.compression_mode(endpoint)
    if mode == "smart":
        return decide_smart(messages)
    return mode if mode in ("baseline", "aggressive") else "baseline"


def est_tokens(text: str) -> int:
    return max(0, round(len(text or "") / 4))


def _baseline(text: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", ln).rstrip() for ln in (text or "").split("\n")]
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()


def _aggressive(text: str) -> str:
    def strip_word(m: re.Match) -> str:
        return "" if m.group(0).lower() in _FILLER else m.group(0)
    trimmed = re.sub(r"[A-Za-z]+", strip_word, text or "")
    return _baseline(trimmed)


def compress(messages: list[dict], *, aggressive: bool = False) -> tuple[list[dict], dict]:
    """Return (compressed messages, stats). Only user-role content is touched.
    Fail-soft: on any error, the original messages pass through unchanged."""
    try:
        fn = _aggressive if aggressive else _baseline
        orig_tokens = 0
        new_tokens = 0
        out: list[dict] = []
        for m in messages:
            content = m.get("content") or ""
            orig_tokens += est_tokens(content)
            if m.get("role") == "user" and content:
                content = fn(content)
            new_tokens += est_tokens(content)
            out.append({**m, "content": content})
        saved = max(0, orig_tokens - new_tokens)
        return out, {"mode": "aggressive" if aggressive else "baseline",
                     "original_tokens": orig_tokens, "compressed_tokens": new_tokens,
                     "saved_tokens": saved}
    except Exception:
        return messages, {"mode": "off", "original_tokens": 0,
                          "compressed_tokens": 0, "saved_tokens": 0}


def record(stats: dict, endpoint: str = "") -> None:
    if not stats or stats.get("saved_tokens", 0) <= 0:
        return
    try:
        ensure_table()
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO compression_savings (mode,endpoint,tokens_saved,at) VALUES (?,?,?,?)",
                (stats.get("mode", "baseline"), endpoint or "", int(stats["saved_tokens"]), _now()))
    except Exception:
        pass


def notify_aggressive(saved: int) -> None:
    try:
        from . import notifications
        notifications.notify(
            "compression_aggressive", "info",
            "Aggressive compression is active",
            f"Cost-saving compression is shortening prompts (~{saved} tokens on the "
            "last request) before they reach a model. Adjust it in Cache & compression.")
    except Exception:
        pass


def stats(endpoint: str | None = None) -> dict:
    ensure_table()
    where = "WHERE endpoint=?" if endpoint is not None else ""
    args = (endpoint,) if endpoint is not None else ()
    with get_conn() as conn:
        row = conn.execute(f"SELECT COUNT(*) n, COALESCE(SUM(tokens_saved),0) t "
                           f"FROM compression_savings {where}", args).fetchone()
    return {"requests_compressed": row["n"], "tokens_saved": row["t"]}


def clear() -> None:
    ensure_table()
    with get_conn() as conn:
        conn.execute("DELETE FROM compression_savings")
