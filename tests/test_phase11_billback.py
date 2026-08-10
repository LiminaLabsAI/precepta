"""Phase 11 — bill-back (chargeback): cost + requests per app / agent, team-scoped."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import traces
from app.main import app

client = TestClient(app)
H = {"Authorization": "Bearer dev-admin"}
_TEAM = "__test_billback_team"


def _seed():
    traces.clear(_TEAM)
    rows = [("app-a", None, 0.10), ("app-a", None, 0.20),
            ("app-b", "crm-agent", 0.05), ("app-b", "crm-agent", 0.15)]
    for principal, agent, cost in rows:
        tr = traces.begin(_TEAM, principal, "user",
                          {"agent_id": agent} if agent else None)
        tr.step("inference", "ok", "x")
        traces.save(tr, "allowed", backend="ollama", cost_usd=cost)


def test_billback_aggregates_by_app_and_agent():
    _seed()
    try:
        bb = traces.billback(_TEAM)
        apps = {a["app"]: a for a in bb["by_app"]}
        assert apps["app-a"]["requests"] == 2 and round(apps["app-a"]["cost_usd"], 2) == 0.30
        assert apps["app-b"]["requests"] == 2 and round(apps["app-b"]["cost_usd"], 2) == 0.20
        agents = {a["agent"]: a for a in bb["by_agent"]}
        assert agents["crm-agent"]["requests"] == 2
        assert round(agents["crm-agent"]["cost_usd"], 2) == 0.20
        assert bb["total_requests"] == 4
        assert round(bb["total_cost_usd"], 2) == 0.50
    finally:
        traces.clear(_TEAM)


def test_billback_empty_team():
    bb = traces.billback("__nonexistent_team__")
    assert bb["by_app"] == [] and bb["by_agent"] == []
    assert bb["total_requests"] == 0 and bb["total_cost_usd"] == 0


def test_billback_endpoint_shape_and_auth():
    r = client.get("/v1/billback", headers=H)
    assert r.status_code == 200
    d = r.json()
    assert set(("by_app", "by_agent", "total_requests", "total_cost_usd")).issubset(d.keys())
    assert client.get("/v1/billback").status_code in (401, 403)
