"""Organization settings (real, persisted key/value).

Replaces the hardcoded Settings-modal displays with editable, stored values:
org name, default model, declared data-residency, audit retention. Read at
runtime by the top bar, the gateway (default model), and the compliance report.
"""
from __future__ import annotations

from .db import get_conn

_DDL = "CREATE TABLE IF NOT EXISTS org_settings (key TEXT PRIMARY KEY, value TEXT)"

_DEFAULTS = {
    "org_name": "My Organization",
    "default_model": "ollama/llama3.2:3b",
    "data_residency": "India (Mumbai)",
    "audit_retention_years": "7",
}

_ALLOWED = set(_DEFAULTS)


def ensure_table() -> None:
    with get_conn() as conn:
        conn.execute(_DDL)


def get(key: str, default: str | None = None) -> str:
    ensure_table()
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM org_settings WHERE key=?", (key,)).fetchone()
    if row is not None:
        return row["value"]
    return default if default is not None else _DEFAULTS.get(key, "")


def all_settings() -> dict:
    return {k: get(k) for k in _DEFAULTS}


def update(values: dict) -> dict:
    ensure_table()
    with get_conn() as conn:
        for k, v in values.items():
            if k in _ALLOWED and v is not None:
                conn.execute(
                    "INSERT INTO org_settings (key,value) VALUES (?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (k, str(v)))
    return all_settings()
