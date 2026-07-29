"""Phase 9 validation — compliance evidence, audit export, team-scoped authZ."""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.compliance import build_report
from app.adapters.authz import scopes
from app.adapters.identity.keys import issue_key
from app.ports import Principal
from app.db import get_conn

client = TestClient(app)
ADMIN = {"Authorization": "Bearer dev-admin"}


# ── compliance evidence ──────────────────────────────────────────────────
def test_build_report():
    rep = build_report()
    assert 0 <= rep["score"] <= 100
    frameworks = {c["framework"] for c in rep["controls"]}
    assert {"DPDP", "SOC2", "HIPAA", "GDPR"} <= frameworks
    chain_ctrl = next(c for c in rep["controls"] if c["id"] == "SOC2 CC7.2")
    assert chain_ctrl["status"] in ("met", "failed")


def test_compliance_endpoint():
    r = client.get("/compliance/report")
    assert r.status_code == 200
    assert "controls" in r.json() and r.json()["controls_total"] == 6


def test_audit_export_endpoint():
    r = client.get("/audit/export")
    assert r.status_code == 200
    body = r.json()
    assert "chain" in body and "head" in body and "verified" in body


# ── team scopes ──────────────────────────────────────────────────────────
def test_team_scope_check():
    scopes.set_scope("t9", ["neysa"], 1000)
    try:
        p = Principal("svc", "user", team="t9")
        assert scopes.check_backend(p, "ollama") is not None   # not allowed
        assert scopes.check_backend(p, "neysa") is None        # allowed
        assert scopes.budget(p)["max_tokens_per_day"] == 1000
        # no team → unrestricted
        assert scopes.check_backend(Principal("x", "user"), "ollama") is None
    finally:
        with get_conn() as conn:
            conn.execute("DELETE FROM team_scopes WHERE team=?", ("t9",))


def test_team_scope_enforced_via_api():
    r = client.post("/v1/keys", headers=ADMIN,
                    json={"name": "svc-scoped", "role": "user", "team": "risk9"})
    kid, token = r.json()["id"], r.json()["key"]
    client.post("/v1/team-scopes", headers=ADMIN,
                json={"team": "risk9", "allowed_backends": ["neysa"], "max_tokens_per_day": 500})
    try:
        # ollama is not in the team's allowed backends → blocked (before inference)
        rr = client.post("/v1/chat/completions",
                         headers={"Authorization": f"Bearer {token}"},
                         json={"model": "ollama/llama3.2:3b",
                               "messages": [{"role": "user", "content": "hi"}]})
        assert rr.status_code == 403
        assert "scoped" in rr.json()["error"]["message"]
    finally:
        with get_conn() as conn:
            conn.execute("DELETE FROM api_keys WHERE id=?", (kid,))
            conn.execute("DELETE FROM team_scopes WHERE team=?", ("risk9",))


def test_team_scope_endpoint_admin_only():
    r = client.post("/v1/team-scopes", json={"team": "x"})
    assert r.status_code == 403
