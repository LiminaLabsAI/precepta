"""Secret store adapter (SecretStorePort) — where provider keys live.

A named secret is written once and read back only by the server that needs it to
make an outbound call; it is **never returned over the API** (callers get a
boolean "is it set", never the value). This is the seam the DESIGN calls out
(SecretStorePort → customer KMS/Vault in production). For V1 self-host the store
is a dedicated SQLite table, kept separate from application data so the move to
Vault/KMS is a single adapter swap and nothing else changes.

Note (honest limitation): V1 stores the value at rest in the local DB. That is
no weaker than the existing `registered_backends.api_key` column it supersedes,
and it is deliberately behind this port so production can bind a real KMS
without touching callers. Encryption-at-rest / external KMS is deferred
(DESIGN.md §SecretStorePort).
"""
from __future__ import annotations

import datetime as _dt

from ...db import get_conn

_DDL = """
CREATE TABLE IF NOT EXISTS secrets (
    name       TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


def ensure_table() -> None:
    with get_conn() as conn:
        conn.execute(_DDL)


class SqliteSecretStore:
    """Local-DB implementation of SecretStorePort (get/put) + set-check helpers."""

    def put(self, name: str, value: str) -> str:
        """Store (or replace) the secret under `name`; returns the ref (the name)."""
        ensure_table()
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO secrets (name,value,updated_at) VALUES (?,?,?) "
                "ON CONFLICT(name) DO UPDATE SET value=excluded.value, "
                "updated_at=excluded.updated_at",
                (name, value, _dt.datetime.now(_dt.UTC).isoformat()))
        return name

    def get(self, ref: str) -> str | None:
        """Read the secret value for internal use only (outbound calls) — never over the API."""
        ensure_table()
        with get_conn() as conn:
            row = conn.execute("SELECT value FROM secrets WHERE name=?", (ref,)).fetchone()
        return row["value"] if row is not None else None

    def is_set(self, name: str) -> bool:
        """True if a non-empty secret exists — safe to surface (no value leaked)."""
        v = self.get(name)
        return bool(v)

    def delete(self, name: str) -> bool:
        ensure_table()
        with get_conn() as conn:
            cur = conn.execute("DELETE FROM secrets WHERE name=?", (name,))
            return cur.rowcount > 0


_store = SqliteSecretStore()


def get_secret_store() -> SqliteSecretStore:
    return _store
