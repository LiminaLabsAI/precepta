"""FEAT-001 (slice 1) — API key expiration: default 90d, never option, expired -> 401."""
from __future__ import annotations

import datetime as dt

from fastapi.testclient import TestClient

from app.main import app
from app.adapters.identity import keys
from app.db import get_conn

client = TestClient(app)
ADMIN = {"Authorization": "Bearer dev-admin"}


def _del(name: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM api_keys WHERE name=?", (name,))


def _row(name: str) -> dict:
    return next(k for k in keys.list_keys() if k["name"] == name)


def test_default_90_day_expiry_active_and_authenticates():
    try:
        _, tok = keys.issue_key("exp-90")
        r = _row("exp-90")
        assert r["expires_at"] is not None and r["active"] and not r["expired"]
        assert keys.get_api_identity().authenticate(tok) is not None
    finally:
        _del("exp-90")


def test_never_expires_option():
    try:
        _, tok = keys.issue_key("exp-never", expires_in_days=None)
        assert _row("exp-never")["expires_at"] is None
        assert keys.get_api_identity().authenticate(tok) is not None
    finally:
        _del("exp-never")


def test_expired_key_fails_auth_and_is_flagged():
    try:
        kid, tok = keys.issue_key("exp-past")
        past = (dt.datetime.now(dt.UTC) - dt.timedelta(days=1)).isoformat()
        with get_conn() as conn:
            conn.execute("UPDATE api_keys SET expires_at=? WHERE id=?", (past, kid))
        assert keys.get_api_identity().authenticate(tok) is None     # 401 path
        r = _row("exp-past")
        assert r["expired"] is True and r["active"] is False
    finally:
        _del("exp-past")


def test_endpoint_accepts_never_choice():
    try:
        r = client.post("/v1/keys", headers=ADMIN,
                        json={"name": "exp-ep", "expires_in_days": 0})
        assert r.status_code == 201
        assert r.json()["expires_in_days"] is None
        assert _row("exp-ep")["expires_at"] is None
    finally:
        _del("exp-ep")
