"""Phase 0 validation — scaffold, config, DB layer, ports, /health."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.settings import get_settings
from app import ports
from app import db

client = TestClient(app)


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["db"]["ok"] is True
    # the existing preceptaai.db ships 15 tables — the DB layer must read it.
    assert body["db"]["tables"] >= 15


def test_root_serves_console_directly():
    # The Console is served on its own subdomain (console.<domain>), so "/" IS the
    # Console — no /console redirect. /console stays as a back-compat alias.
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 200
    assert "function apiView(" in r.text            # it's the Console SPA, served inline
    assert client.get("/console").status_code == 200  # alias still works


def test_api_info():
    r = client.get("/api")
    assert r.status_code == 200
    assert r.json()["name"] == "preceptaai"
    assert r.json()["console"] == "/"


def test_settings_sovereign_by_default():
    s = get_settings()
    assert s.sovereign_mode is True
    assert s.db_path.name == "preceptaai.db"


def test_db_reads_governance_tables():
    tables = db.list_tables()
    for required in ("governance_policies", "audit_log", "tamper_evident_audit_log"):
        assert required in tables


def test_ports_are_defined():
    for name in (
        "ModelBackendPort", "RouterBrainPort", "ReasoningPort", "PolicyStorePort",
        "AuditSinkPort", "SecretStorePort", "InfraVisibilityPort",
        "IdentityPort", "AuthorizationPort",
    ):
        assert hasattr(ports, name), f"missing port: {name}"
