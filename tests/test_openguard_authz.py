"""FEAT-004 — OpenGuard authZ: configurable RBAC, ABAC conditions, agent budgets."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.adapters.authz import openguard as og
from app.adapters.authz import get_authz
from app.ports import Principal
from app.main import app
from app.db import get_conn

client = TestClient(app)
ADMIN = {"Authorization": "Bearer dev-admin"}
USER = {"Authorization": "Bearer dev-user"}


def _reset():
    og.ensure_tables()
    with get_conn() as conn:
        conn.execute("DELETE FROM authz_roles")
        conn.execute("DELETE FROM agent_budgets")
        conn.execute("DELETE FROM agent_usage")


# ── RBAC defaults preserve prior behaviour ───────────────────────────────
def test_default_rbac_matches_rolecheck():
    _reset()
    az = get_authz()
    assert az.can(Principal("a", "admin"), "policy.update") is True
    assert az.can(Principal("u", "user"), "chat.completion") is True
    assert az.can(Principal("u", "user"), "policy.update") is False
    assert az.can(Principal("x", "auditor"), "audit.read") is True
    assert az.can(Principal("x", "auditor"), "chat.completion") is False


# ── RBAC is configurable ─────────────────────────────────────────────────
def test_rbac_configurable():
    _reset()
    try:
        og.set_role_permissions("user", ["chat.completion", "policy.update"])
        assert get_authz().can(Principal("u", "user"), "policy.update") is True
    finally:
        _reset()
        assert get_authz().can(Principal("u", "user"), "policy.update") is False   # back to default


# ── ABAC condition (attribute-scoped permission) ─────────────────────────
def test_abac_team_condition():
    _reset()
    try:
        og.set_role_permissions("user", [{"action": "reports.read", "when": {"team": "finance"}}])
        az = get_authz()
        assert az.can(Principal("u", "user", team="finance"), "reports.read") is True
        assert az.can(Principal("u", "user", team="sales"), "reports.read") is False
    finally:
        _reset()


# ── agent budgets ────────────────────────────────────────────────────────
def test_agent_budget_enforced():
    _reset()
    try:
        assert og.check_and_record_agent("free-agent") == (True, None)   # no budget → unbounded
        og.set_agent_budget("bot-1", 2)
        assert og.check_and_record_agent("bot-1")[0] is True             # 1
        assert og.check_and_record_agent("bot-1")[0] is True             # 2
        ok, why = og.check_and_record_agent("bot-1")                     # 3 → blocked
        assert ok is False and "cap" in why
        rows = {r["agent_id"]: r for r in og.list_agent_budgets()}
        assert rows["bot-1"]["used_today"] == 2                          # blocked call not counted
    finally:
        _reset()


def test_agent_budget_via_chat_endpoint():
    _reset()
    try:
        og.set_agent_budget("probe-bot", 1)
        # first call may hit a live backend; we only care it's not 429
        r1 = client.post("/v1/chat/completions", headers=ADMIN, json={
            "model": "auto", "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 4, "agent_id": "probe-bot"})
        assert r1.status_code != 429
        # second call is over cap regardless of backend → 429 before inference
        r2 = client.post("/v1/chat/completions", headers=ADMIN, json={
            "model": "auto", "messages": [{"role": "user", "content": "hi again"}],
            "max_tokens": 4, "agent_id": "probe-bot"})
        assert r2.status_code == 429 and "cap" in r2.json()["error"]["message"]
    finally:
        _reset()


# ── management endpoints admin-only ──────────────────────────────────────
def test_authz_endpoints_admin_only():
    _reset()
    try:
        assert client.get("/v1/authz/roles", headers=USER).status_code == 403
        assert client.get("/v1/authz/roles", headers=ADMIN).json()["roles"]["admin"] == ["*"]
        r = client.post("/v1/authz/agent-budgets", headers=ADMIN,
                        json={"agent_id": "ep-bot", "daily_request_cap": 5})
        assert r.status_code == 201
        assert any(a["agent_id"] == "ep-bot" for a in r.json()["agents"])
    finally:
        _reset()
