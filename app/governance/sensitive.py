"""Governance routing filter (FEAT-007 / Rule C) — sensitive data → approved backends only.

Sensitivity is auto-derived from the Stage-1 firewall (PII/PHI) plus an explicit
data-tag. A sensitive request may only be served by a backend an admin has
approved for sensitive data; if none is available it is blocked (fail-closed) and
an admin notification fires. Approval records where the backend is hosted, so the
consent is a deliberate, audited decision.
"""
from __future__ import annotations

import datetime as _dt

from ..db import get_conn

_DDL = """
CREATE TABLE IF NOT EXISTS sensitive_backends (
    backend     TEXT PRIMARY KEY,
    location    TEXT DEFAULT '',
    approved_by TEXT DEFAULT '',
    approved_at TEXT NOT NULL
)
"""


def ensure_table() -> None:
    with get_conn() as conn:
        conn.execute(_DDL)


def approve(backend: str, location: str, approved_by: str) -> None:
    ensure_table()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO sensitive_backends (backend,location,approved_by,approved_at) "
            "VALUES (?,?,?,?) ON CONFLICT(backend) DO UPDATE SET "
            "location=excluded.location, approved_by=excluded.approved_by, "
            "approved_at=excluded.approved_at",
            (backend, location or "", approved_by or "",
             _dt.datetime.now(_dt.UTC).isoformat()))


def unapprove(backend: str) -> None:
    ensure_table()
    with get_conn() as conn:
        conn.execute("DELETE FROM sensitive_backends WHERE backend=?", (backend,))


def list_approved() -> list[dict]:
    ensure_table()
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT backend,location,approved_by,approved_at FROM sensitive_backends "
            "ORDER BY backend").fetchall()]


def approved_set() -> set[str]:
    ensure_table()
    with get_conn() as conn:
        return {r["backend"] for r in conn.execute(
            "SELECT backend FROM sensitive_backends").fetchall()}


def is_sensitive(pii_count: int, data_tag: bool) -> bool:
    """A request is sensitive if the firewall found PII/PHI or the caller tagged it."""
    return (pii_count or 0) > 0 or bool(data_tag)


def block_reason(sensitive: bool, backend_name: str | None) -> str | None:
    """Reason a sensitive request must be blocked for this backend, else None.

    backend_name None (auto, backend not yet chosen) → the router restricts to the
    approved set instead; nothing to block here.
    """
    if not sensitive or backend_name is None:
        return None
    approved = approved_set()
    if not approved:                    # feature not configured → don't enforce (firewall still redacts)
        return None
    if backend_name not in approved:
        return ("sensitive data (PII/PHI detected) may only be routed to a backend "
                f"approved for sensitive data; {backend_name!r} is not approved")
    return None


def notify_block(key_name: str, backend_name: str | None) -> None:
    """Alert an admin that sensitive requests are being blocked (deduped)."""
    from .. import notifications
    tgt = f" to {backend_name!r}" if backend_name else ""
    notifications.notify(
        "sensitive_block", "critical",
        "Sensitive request blocked — no approved backend",
        f"A request with sensitive data was blocked{tgt} because no approved-for-"
        f"sensitive backend was available. Approve a backend in Policies → Advanced routing.")
