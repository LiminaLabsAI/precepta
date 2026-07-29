"""Phase 6 validation — Console serving + policy CRUD + audit-log endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.db import get_conn

client = TestClient(app)
ADMIN = {"Authorization": "Bearer dev-admin"}


def test_console_served():
    r = client.get("/console")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "preceptaai" in r.text
    assert "Sovereignty Attestation" in r.text   # the money view is present


def test_policies_list():
    r = client.get("/v1/policies")
    assert r.status_code == 200
    assert isinstance(r.json()["policies"], list)


def test_policy_create_requires_admin():
    # anonymous resolves to role 'user' → cannot create policies
    r = client.post("/v1/policies", json={"name": "x", "effect": "audit"})
    assert r.status_code == 403


def test_policy_crud_as_admin():
    r = client.post("/v1/policies", headers=ADMIN, json={
        "name": "phase6 test policy", "description": "d", "action_type": "*",
        "effect": "warn", "conditions": {"max_calls_per_hour": 5}})
    assert r.status_code == 201
    pid = r.json()["id"]
    try:
        listed = client.get("/v1/policies").json()["policies"]
        row = next(p for p in listed if p["id"] == pid)
        assert row["enabled"] is True and row["effect"] == "warn"
        assert row["conditions"]["max_calls_per_hour"] == 5
        # toggle off
        t = client.post(f"/v1/policies/{pid}/toggle", headers=ADMIN)
        assert t.status_code == 200 and t.json()["enabled"] is False
    finally:
        with get_conn() as conn:
            conn.execute("DELETE FROM governance_policies WHERE id=?", (pid,))


def test_toggle_missing_404():
    r = client.post("/v1/policies/nonexistent/toggle", headers=ADMIN)
    assert r.status_code == 404


def test_audit_log_endpoint():
    r = client.get("/audit/log?limit=5")
    assert r.status_code == 200
    assert isinstance(r.json()["log"], list)
