"""Validation — real org settings, CSV export, /auth/me (Settings modal fixes)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app import org
from app.db import get_conn

client = TestClient(app)
ADMIN = {"Authorization": "Bearer dev-admin"}


def test_get_settings_defaults():
    r = client.get("/v1/settings")
    assert r.status_code == 200
    body = r.json()
    for k in ("org_name", "default_model", "data_residency", "audit_retention_years"):
        assert k in body


def test_update_settings_admin_and_persist():
    try:
        r = client.put("/v1/settings", headers=ADMIN,
                       json={"org_name": "Acme Regulated Ltd", "audit_retention_years": "5"})
        assert r.status_code == 200
        assert r.json()["org_name"] == "Acme Regulated Ltd"
        assert org.get("org_name") == "Acme Regulated Ltd"        # persisted
        assert org.get("audit_retention_years") == "5"
    finally:
        with get_conn() as conn:
            conn.execute("DELETE FROM org_settings")


def test_update_settings_non_admin_forbidden():
    r = client.put("/v1/settings", json={"org_name": "x"})   # anonymous → user
    assert r.status_code == 403


def test_settings_reflected_in_compliance():
    try:
        client.put("/v1/settings", headers=ADMIN, json={"data_residency": "EU (Frankfurt)"})
        rep = client.get("/compliance/report").json()
        assert rep["data_residency"] == "EU (Frankfurt)"
        dpdp = next(c for c in rep["controls"] if c["id"] == "DPDP §8")
        assert "EU (Frankfurt)" in dpdp["evidence"]
    finally:
        with get_conn() as conn:
            conn.execute("DELETE FROM org_settings")


def test_csv_export():
    r = client.get("/audit/export.csv", headers=ADMIN)
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert r.text.splitlines()[0].startswith("timestamp,")


def test_whoami():
    r = client.get("/auth/me", headers=ADMIN)
    assert r.status_code == 200
    assert r.json()["role"] == "admin"
    assert r.json()["name"]
