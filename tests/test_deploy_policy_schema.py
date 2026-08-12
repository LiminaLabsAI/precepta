"""Deploy regression: the policy table is created on a FRESH database.

A fresh deploy (empty preceptaai.db) exposed that `governance_policies` had no
CREATE — only an ALTER — so the first governed request 500'd. This guards the
DDL and that it matches what create_policy inserts.
"""
from __future__ import annotations

import sqlite3

from app.governance import policy as P

_INSERT_COLS = ["id", "name", "description", "enabled", "action_type", "effect",
                "conditions_json", "scope_json", "version", "created_at", "updated_at"]


def test_policy_ddl_creates_full_table():
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute(P._DDL)                      # fresh DB path
        cols = [r[1] for r in conn.execute("PRAGMA table_info(governance_policies)")]
        for c in _INSERT_COLS:
            assert c in cols, f"DDL missing column {c}"
    finally:
        conn.close()


def test_policy_ddl_matches_create_policy_insert():
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute(P._DDL)
        placeholders = ",".join("?" * len(_INSERT_COLS))
        conn.execute(
            f"INSERT INTO governance_policies ({','.join(_INSERT_COLS)}) VALUES ({placeholders})",
            ("id1", "n", "d", 1, "chat", "block", "{}", "{}", 1, "t", "t"))
        assert conn.execute("SELECT COUNT(*) FROM governance_policies").fetchone()[0] == 1
    finally:
        conn.close()


def test_ddl_is_idempotent():
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute(P._DDL)
        conn.execute(P._DDL)                      # CREATE TABLE IF NOT EXISTS — no error
    finally:
        conn.close()
