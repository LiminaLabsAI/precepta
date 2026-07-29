"""Admin operations — clean-slate reset of activity data.

Clears the audit log, the tamper-evident chain, and telemetry (a fresh
control plane reads 0 everywhere). Policies and registered backends are kept.
"""
from __future__ import annotations

from .db import get_conn

_ACTIVITY_TABLES = ("audit_log", "tamper_evident_audit_log", "telemetry")


def reset_activity() -> dict[str, int]:
    """Delete all rows from activity tables; return how many were cleared each."""
    cleared: dict[str, int] = {}
    with get_conn() as conn:
        for table in _ACTIVITY_TABLES:
            n = conn.execute(f"SELECT COUNT(*) c FROM {table}").fetchone()["c"]
            conn.execute(f"DELETE FROM {table}")
            cleared[table] = int(n)
    return cleared
