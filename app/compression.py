"""Prompt compression (FEAT-005) — shorten prompts before they reach a model.

Governing stance (never surprise the user):
  - OFF by default. When enabled, the **baseline** mode is quality-safe:
    whitespace/formatting normalization only — it does not change meaning.
  - **Aggressive** mode is a separate opt-in ("cost-saving mode"): it also strips
    politeness filler. It is lossy, so every time it actually shortens a request
    the caller sees it in the response (`precepta.compression`) and an admin
    notification fires (deduped) — no silent quality trade.
  - Metering bills on the COMPRESSED prompt automatically (we send the shortened
    messages to the model); `tokens_saved` here is the visible savings.

Real semantic compression (LLMLingua) is deferred until it can be gated by the
eval harness (Rule 11) — this module is the safe baseline + the framework it
plugs into. Token counts are an estimate (~4 chars/token); the authoritative
billing number is the model's own usage on the compressed prompt.
"""
from __future__ import annotations

import datetime as _dt
import re

from .db import get_conn
from . import org

_DDL = """
CREATE TABLE IF NOT EXISTS compression_savings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mode TEXT DEFAULT 'baseline',
    tokens_saved INTEGER DEFAULT 0,
    at TEXT NOT NULL
)
"""

# Politeness filler removed only in aggressive mode — words whose absence does
# not change an instruction's meaning. Deliberately tiny and conservative.
_FILLER = {"please", "kindly", "just", "really", "very", "actually",
           "basically", "simply", "literally"}


def ensure_table() -> None:
    with get_conn() as conn:
        conn.execute(_DDL)


def _now() -> str:
    return _dt.datetime.now(_dt.UTC).isoformat()


def enabled() -> bool:
    return org.get("compression_enabled", "false") == "true"


def aggressive_on() -> bool:
    return org.get("compression_aggressive", "false") == "true"


def est_tokens(text: str) -> int:
    return max(0, round(len(text or "") / 4))


def _baseline(text: str) -> str:
    """Quality-safe: collapse intra-line whitespace, trim lines, cap blank runs."""
    lines = [re.sub(r"[ \t]+", " ", ln).rstrip() for ln in (text or "").split("\n")]
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out)          # cap consecutive blank lines
    return out.strip()


def _aggressive(text: str) -> str:
    """Baseline + drop conservative politeness filler (lossy, opt-in)."""
    def strip_word(m: re.Match) -> str:
        return "" if m.group(0).lower() in _FILLER else m.group(0)
    trimmed = re.sub(r"[A-Za-z]+", strip_word, text or "")
    return _baseline(trimmed)


def compress(messages: list[dict], *, aggressive: bool = False) -> tuple[list[dict], dict]:
    """Return (compressed messages, stats). Only user-role content is touched;
    system/assistant messages are left intact. Fail-soft: on any error, the
    original messages pass through unchanged."""
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
    except Exception:                              # fail-soft — never break inference
        return messages, {"mode": "off", "original_tokens": 0,
                          "compressed_tokens": 0, "saved_tokens": 0}


def record(stats: dict) -> None:
    if not stats or stats.get("saved_tokens", 0) <= 0:
        return
    try:
        ensure_table()
        with get_conn() as conn:
            conn.execute("INSERT INTO compression_savings (mode,tokens_saved,at) VALUES (?,?,?)",
                         (stats.get("mode", "baseline"), int(stats["saved_tokens"]), _now()))
    except Exception:
        pass


def notify_aggressive(saved: int) -> None:
    """Never-surprise: a deduped admin heads-up that aggressive mode is trimming."""
    try:
        from . import notifications
        notifications.notify(
            "compression_aggressive", "info",
            "Aggressive compression is active",
            f"Cost-saving compression is shortening prompts (~{saved} tokens on the "
            "last request) before they reach a model. Turn it off in Cache & compression.")
    except Exception:
        pass


def stats() -> dict:
    ensure_table()
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) n, COALESCE(SUM(tokens_saved),0) t "
                           "FROM compression_savings").fetchone()
    return {"enabled": enabled(), "aggressive": aggressive_on(),
            "requests_compressed": row["n"], "tokens_saved": row["t"]}


def clear() -> None:
    ensure_table()
    with get_conn() as conn:
        conn.execute("DELETE FROM compression_savings")
