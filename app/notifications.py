"""In-app notifications (the bell) — real, DB-backed (FEAT-001).

Fires on budget warn/block, sensitive-data blocks, aggressive compression, etc.
Deduped so a condition hit on every request produces ONE alert per day.

TD-008 — alerts config: which categories fire, and a minimum severity, are
admin-configurable (org settings). `notify()` consults that config first, so a
deployment can quiet categories it doesn't want without touching code.
"""
from __future__ import annotations

import datetime as _dt
import uuid

from .db import get_conn
from . import org

_SEVERITY_RANK = {"info": 0, "warning": 1, "critical": 2}


def _category(ntype: str) -> str:
    t = (ntype or "").lower()
    if t.startswith("budget"):
        return "budget"
    if "sensitive" in t:
        return "sensitive"
    if "compression" in t:
        return "compression"
    return "system"


def _should_fire(ntype: str, severity: str) -> bool:
    """Honor the admin's alerts config: master switch, per-category, min severity.
    `system` alerts follow only the master switch + severity (not silenceable)."""
    if org.get("alerts_enabled", "true") != "true":
        return False
    if _SEVERITY_RANK.get(severity, 0) < _SEVERITY_RANK.get(org.get("alert_min_severity", "info"), 0):
        return False
    cat = _category(ntype)
    if cat in ("budget", "sensitive", "compression"):
        return org.get(f"alert_{cat}", "true") == "true"
    return True

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
    """Create a notification. With dedup, skip if the same title already fired today.
    Respects the admin alerts config (TD-008) — a silenced category never fires."""
    if not _should_fire(ntype, severity):
        return
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
