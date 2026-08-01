"""In-app notifications (the bell) — real, DB-backed (FEAT-001).

Fires on budget warn/block (extensible later). Deduped so a cap that's hit on
every request produces ONE alert per day, not a flood.
"""
from __future__ import annotations

import datetime as _dt
import uuid

from .db import get_conn

_DDL = """
CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY, type TEXT NOT NULL, severity TEXT NOT NULL,
    workflow_id TEXT, run_id TEXT, title TEXT NOT NULL, body TEXT NOT NULL,
    sent_at TEXT NOT NULL, read_at TEXT, action_taken TEXT
)
"""


def ensure_table() -> None:
    with get_conn() as conn:
        conn.execute(_DDL)


def _today_start() -> str:
    now = _dt.datetime.now(_dt.UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def notify(ntype: str, severity: str, title: str, body: str, *, dedup: bool = True) -> None:
    """Create a notification. With dedup, skip if the same title already fired today."""
    ensure_table()
    with get_conn() as conn:
        if dedup:
            hit = conn.execute(
                "SELECT 1 FROM notifications WHERE title=? AND sent_at>=?",
                (title, _today_start())).fetchone()
            if hit:
                return
        conn.execute(
            "INSERT INTO notifications (id,type,severity,title,body,sent_at) "
            "VALUES (?,?,?,?,?,?)",
            (uuid.uuid4().hex, ntype, severity, title, body,
             _dt.datetime.now(_dt.UTC).isoformat()))


def list_recent(limit: int = 30) -> list[dict]:
    ensure_table()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id,type,severity,title,body,sent_at,read_at FROM notifications "
            "ORDER BY sent_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) | {"read": r["read_at"] is not None} for r in rows]


def unread_count() -> int:
    ensure_table()
    with get_conn() as conn:
        return conn.execute(
            "SELECT COUNT(*) n FROM notifications WHERE read_at IS NULL").fetchone()["n"]


def mark_all_read() -> None:
    ensure_table()
    with get_conn() as conn:
        conn.execute("UPDATE notifications SET read_at=? WHERE read_at IS NULL",
                     (_dt.datetime.now(_dt.UTC).isoformat(),))
