"""FEAT-001 — per-key scope (team/role/agent/backend/model) + daily/monthly cost caps."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.adapters.identity import keys
from app import budgets
from app.db import get_conn

client = TestClient(app)
ADMIN = {"Authorization": "Bearer dev-admin"}


def _cleanup(name: str) -> None:
    budgets.ensure_table()
    with get_conn() as conn:
        conn.execute("DELETE FROM api_keys WHERE name=?", (name,))
        conn.execute("DELETE FROM key_usage WHERE key_name=?", (name,))


def test_provisioning_stores_scope_and_caps():
    try:
        keys.issue_key("scoped-key", role="user", team="Payments",
                       subject_type="agent", allowed_backends=["ollama"],
                       allowed_models=["ollama/llama3.2:3b"],
                       cost_cap_daily=2.0, cost_cap_monthly=40.0)
        m = keys.get_key_meta("scoped-key")
        assert m["team"] == "Payments" and m["subject_type"] == "agent"
        assert m["allowed_backends"] == "ollama"
        assert m["cost_cap_daily"] == 2.0 and m["cost_cap_monthly"] == 40.0
        row = next(k for k in keys.list_keys() if k["name"] == "scoped-key")
        assert row["backends_list"] == ["ollama"]
    finally:
        _cleanup("scoped-key")


def test_scope_blocks_disallowed_backend_and_model():
    try:
        keys.issue_key("be-scoped", allowed_backends=["ollama"], allowed_models=["ollama/m1"])
        assert keys.scope_violation("be-scoped", "ollama", "ollama/m1") is None      # allowed
        assert keys.scope_violation("be-scoped", "hf", "hf/x") is not None           # backend blocked
        assert keys.scope_violation("be-scoped", "ollama", "ollama/m2") is not None  # model blocked
    finally:
        _cleanup("be-scoped")


def test_cost_cap_warns_then_blocks():
    try:
        keys.issue_key("cap-key", cost_cap_daily=1.0)
        assert budgets.check("cap-key")["effect"] == "allow"
        budgets.record_usage("cap-key", "", 1000, 0.90)          # 90% of $1
        assert budgets.check("cap-key")["effect"] == "warn"      # >= 80%
        budgets.record_usage("cap-key", "", 1000, 0.20)          # now $1.10 > cap
        assert budgets.check("cap-key")["effect"] == "block"
    finally:
        _cleanup("cap-key")


def test_no_cap_is_unlimited():
    try:
        keys.issue_key("free-key")                               # no caps
        budgets.record_usage("free-key", "", 10_000, 999.0)
        assert budgets.check("free-key")["effect"] == "allow"
    finally:
        _cleanup("free-key")


def test_endpoints_create_scoped_key_and_report_usage():
    try:
        r = client.post("/v1/keys", headers=ADMIN, json={
            "name": "ep-scoped", "team": "Risk", "subject_type": "service",
            "allowed_backends": ["ollama"], "cost_cap_daily": 5, "cost_cap_monthly": 100})
        assert r.status_code == 201
        budgets.record_usage("ep-scoped", "Risk", 500, 0.33)
        u = client.get("/v1/usage", headers=ADMIN).json()["usage"]
        row = next(x for x in u if x["key"] == "ep-scoped")
        assert row["spent_day"] == 0.33 and row["cap_day"] == 5 and row["cap_month"] == 100
    finally:
        _cleanup("ep-scoped")
