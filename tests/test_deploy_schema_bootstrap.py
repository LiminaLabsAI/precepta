"""Deploy: the startup schema bootstrap creates every table on a fresh DB.

Guards the fresh-deploy 500s (governance_policies / audit_log / telemetry /
chain missing on a brand-new database).
"""
from __future__ import annotations

from app import schema
from app.db import get_conn

_CORE_TABLES = [
    "governance_policies", "audit_log", "tamper_evident_audit_log", "telemetry",
    "traces", "api_keys", "org_settings",
]


def test_ensure_all_idempotent_and_creates_core_tables():
    schema.ensure_all()
    schema.ensure_all()          # idempotent — no error on a second call
    with get_conn() as conn:
        tables = {r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
    missing = [t for t in _CORE_TABLES if t not in tables]
    assert not missing, f"tables missing after ensure_all: {missing}"
