"""SQLite store for the vendor licensing service (its OWN database, separate from
the sovereign app's DB). Path from `LICENSE_DB` (default `licensing/data/licensing.db`)."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS logins (
    sub         TEXT PRIMARY KEY,          -- Google subject id
    email       TEXT,
    name        TEXT,
    first_seen  TEXT,
    last_seen   TEXT,
    login_count INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS licenses (
    license_id  TEXT PRIMARY KEY,
    subject     TEXT UNIQUE,               -- one license per subject (email) in v1
    plan        TEXT,                      -- trial | subscription
    issued_at   TEXT,
    expires_at  TEXT,
    seats       INTEGER DEFAULT 1,
    revoked     INTEGER DEFAULT 0,
    token       TEXT,                      -- the signed key (re-issued on plan change)
    created_at  TEXT,
    updated_at  TEXT
);
CREATE TABLE IF NOT EXISTS installs (
    install_id      TEXT PRIMARY KEY,
    license_id      TEXT,
    plan            TEXT,
    seats           INTEGER,
    version         TEXT,
    first_seen      TEXT,
    last_seen       TEXT,
    heartbeat_count INTEGER DEFAULT 0
);
"""


def _path() -> str:
    return os.environ.get("LICENSE_DB", "licensing/data/licensing.db")


def get_conn() -> sqlite3.Connection:
    p = _path()
    if p != ":memory:":
        Path(p).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(p)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema() -> None:
    with get_conn() as conn:
        conn.executescript(_SCHEMA)
