"""Phase 17 · Group 3 — trial→read-only enforcement (flag-gated, off by default)."""
from __future__ import annotations

import datetime as dt

from fastapi.testclient import TestClient

from app.main import app
from app import licensing as al
from licensing import core, keys as vkeys

client = TestClient(app)
ADMIN = {"Authorization": "Bearer dev-admin"}
CHAT = {"model": "auto", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 4}


def _set(token):
    al.ensure_table()
    from app.db import get_conn
    with get_conn() as conn:
        conn.execute("UPDATE app_license SET token=?, activated_at=? WHERE id=1",
                     (token, dt.datetime.now(dt.UTC).isoformat() if token else None))


def _clear():
    _set(None)


def test_enforcement_off_by_default_does_not_block(monkeypatch):
    # No license at all + enforcement OFF → the request is NOT license-blocked.
    monkeypatch.delenv("PRECEPTA_LICENSE_ENFORCE", raising=False)
    _clear()
    r = client.post("/v1/chat/completions", headers=ADMIN, json=CHAT)
    assert r.status_code != 403 or r.json().get("error", {}).get("type") not in (
        "license_required", "license_expired")


def test_enforcement_on_unlicensed_blocks_inference(monkeypatch):
    monkeypatch.setenv("PRECEPTA_LICENSE_ENFORCE", "1")
    _clear()
    try:
        r = client.post("/v1/chat/completions", headers=ADMIN, json=CHAT)
        assert r.status_code == 403 and r.json()["error"]["type"] == "license_required"
        e = client.post("/v1/embeddings", headers=ADMIN, json={"input": "x"})
        assert e.status_code == 403 and e.json()["error"]["type"] == "license_required"
        # console/read paths stay available (read-only, not bricked)
        assert client.get("/v1/license", headers=ADMIN).status_code == 200
        assert client.get("/v1/models").status_code == 200
    finally:
        _clear()


def test_enforcement_on_expired_blocks_but_active_allows(monkeypatch):
    monkeypatch.setenv("PRECEPTA_LICENSE_ENFORCE", "1")
    try:
        # an expired trial (issued 30 days ago, 15-day trial, past grace) → blocked
        old = dt.datetime.now(dt.UTC) - dt.timedelta(days=30)
        _set(core.issue(core.trial_payload("lic", "b@corp.com", old), vkeys.signing_key()))
        r = client.post("/v1/chat/completions", headers=ADMIN, json=CHAT)
        assert r.status_code == 403 and r.json()["error"]["type"] == "license_expired"
        # a fresh, active key → NOT license-blocked (may still 200/other, just not our 403)
        _set(core.issue(core.trial_payload("lic", "b@corp.com", dt.datetime.now(dt.UTC)), vkeys.signing_key()))
        r2 = client.post("/v1/chat/completions", headers=ADMIN, json=CHAT)
        assert not (r2.status_code == 403 and r2.json().get("error", {}).get("type", "").startswith("license"))
    finally:
        _clear()
