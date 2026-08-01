"""Persistence for runtime-registered backends.

Backends added via the Console/onboarding are saved here so they survive a
restart (the built-in env-configured ones are rebuilt from config each boot).

Note: api_key is stored in the local SQLite DB for V1 self-host simplicity.
Production should move this to the SecretStore/KMS (deferred — see DESIGN.md).
"""
from __future__ import annotations

import datetime as _dt

from ...db import get_conn

_DDL = """
CREATE TABLE IF NOT EXISTS registered_backends (
    provider    TEXT PRIMARY KEY,
    base_url    TEXT NOT NULL,
    api_key     TEXT,
    model       TEXT,
    in_boundary INTEGER DEFAULT 1,
    tier        INTEGER DEFAULT 1,
    created_at  TEXT NOT NULL
)
"""


def ensure_table() -> None:
    with get_conn() as conn:
        conn.execute(_DDL)


def save_backend(provider: str, base_url: str, api_key: str | None,
                 model: str, in_boundary: bool, tier: int = 1) -> None:
    ensure_table()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO registered_backends "
            "(provider,base_url,api_key,model,in_boundary,tier,created_at) "
            "VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(provider) DO UPDATE SET "
            "base_url=excluded.base_url, api_key=excluded.api_key, "
            "model=excluded.model, in_boundary=excluded.in_boundary, tier=excluded.tier",
            (provider, base_url, api_key, model, 1 if in_boundary else 0, tier,
             _dt.datetime.now(_dt.UTC).isoformat()),
        )


def delete_backend(provider: str) -> bool:
    ensure_table()
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM registered_backends WHERE provider=?", (provider,))
        return cur.rowcount > 0


def set_boundary(provider: str, in_boundary: bool) -> bool:
    """Correct a backend's in-boundary flag without a full re-register."""
    ensure_table()
    with get_conn() as conn:
        cur = conn.execute("UPDATE registered_backends SET in_boundary=? WHERE provider=?",
                           (1 if in_boundary else 0, provider))
        return cur.rowcount > 0


def load_backends() -> list[dict]:
    ensure_table()
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM registered_backends").fetchall()
    return [dict(r) for r in rows]
