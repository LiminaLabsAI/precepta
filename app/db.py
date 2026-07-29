"""SQLite access over the existing `preceptaai.db`.

Phase 0 only needs connectivity + a health snapshot; later phases add the
PolicyStore / AuditSink adapters on top of the same connection helper.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from collections.abc import Iterator

from .settings import get_settings


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    """Yield a configured connection (row access by name, WAL, FK enforcement)."""
    settings = get_settings()
    conn = sqlite3.connect(settings.db_path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def list_tables() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    return [r["name"] for r in rows]


def health() -> dict:
    """Return a DB health snapshot: reachable, path, table count."""
    settings = get_settings()
    try:
        tables = list_tables()
        return {"ok": True, "path": str(settings.db_path), "tables": len(tables)}
    except sqlite3.Error as exc:  # pragma: no cover - surfaced via /health
        return {"ok": False, "path": str(settings.db_path), "error": str(exc)}
