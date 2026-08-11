"""Per-endpoint cache & compression configuration (FEAT-011).

Cache and compression are configured **per inference endpoint** (feedback #3 —
"not generic and global"). The config key is the endpoint that serves a request:
its name for a direct call, or ``"auto"`` for router-decided (`auto`) requests.
Each endpoint picks its own strategy — cache: ``exact`` | ``semantic`` (+
threshold); compression: ``baseline`` | ``aggressive``. Bring-your-own strategies
are a later addition behind the same shape (FEAT-011 v2).

Safe by default: every endpoint starts with cache and compression OFF.
"""
from __future__ import annotations

from .db import get_conn

AUTO = "auto"          # the config key for router-decided requests

_DDL = """
CREATE TABLE IF NOT EXISTS endpoint_features (
    endpoint            TEXT PRIMARY KEY,
    cache_enabled       INTEGER DEFAULT 0,
    cache_strategy      TEXT DEFAULT 'exact',     -- exact | semantic
    cache_threshold     REAL DEFAULT 1.0,
    compression_enabled INTEGER DEFAULT 0,
    compression_mode    TEXT DEFAULT 'baseline'   -- baseline | aggressive
)
"""

_DEFAULTS = {
    # Smart-by-default: the router auto-decides exact vs semantic vs skip per
    # request (threshold governs the semantic match). Matches the product design.
    "cache_enabled": 1, "cache_strategy": "smart", "cache_threshold": 0.9,
    "compression_enabled": 0, "compression_mode": "baseline",
}
_ALLOWED = set(_DEFAULTS)


def ensure_table() -> None:
    with get_conn() as conn:
        conn.execute(_DDL)


def get_config(endpoint: str) -> dict:
    ensure_table()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM endpoint_features WHERE endpoint=?",
                           (endpoint or AUTO,)).fetchone()
    if row is None:
        return {"endpoint": endpoint or AUTO, **_DEFAULTS}
    d = dict(row)
    d["cache_enabled"] = bool(d["cache_enabled"])
    d["compression_enabled"] = bool(d["compression_enabled"])
    return d


def set_config(endpoint: str, values: dict) -> dict:
    ensure_table()
    ep = endpoint or AUTO
    with get_conn() as conn:
        conn.execute("INSERT OR IGNORE INTO endpoint_features (endpoint) VALUES (?)", (ep,))
        for k, v in values.items():
            if k not in _ALLOWED or v is None:
                continue
            if k in ("cache_enabled", "compression_enabled"):
                v = 1 if (v is True or str(v).lower() in ("1", "true", "on", "yes")) else 0
            elif k == "cache_threshold":
                try:
                    v = float(v)
                except (ValueError, TypeError):
                    continue
            elif k == "cache_strategy":
                sv = str(v).lower()
                v = sv if sv in ("exact", "semantic", "smart") else "exact"
            elif k == "compression_mode":
                v = "aggressive" if str(v).lower() == "aggressive" else "baseline"
            conn.execute(f"UPDATE endpoint_features SET {k}=? WHERE endpoint=?", (v, ep))
    return get_config(ep)


# ── convenience accessors used by cache.py / compression.py ────────────────
def cache_on(endpoint: str) -> bool:
    return get_config(endpoint)["cache_enabled"]


def cache_semantic(endpoint: str) -> bool:
    return get_config(endpoint)["cache_strategy"] == "semantic"


def cache_strategy(endpoint: str) -> str:
    """Raw configured strategy: 'exact' | 'semantic' | 'smart'."""
    return get_config(endpoint)["cache_strategy"]


def cache_threshold(endpoint: str) -> float:
    return float(get_config(endpoint)["cache_threshold"])


def compression_on(endpoint: str) -> bool:
    return get_config(endpoint)["compression_enabled"]


def compression_aggressive(endpoint: str) -> bool:
    return get_config(endpoint)["compression_mode"] == "aggressive"


def clear() -> None:
    ensure_table()
    with get_conn() as conn:
        conn.execute("DELETE FROM endpoint_features")
