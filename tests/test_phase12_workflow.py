"""Phase 12 — Group 4 · /v1/workflow endpoint (read-only config projection)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
H = {"Authorization": "Bearer dev-admin"}


def test_workflow_returns_fixed_rails_intents_targets_controls():
    r = client.get("/v1/workflow", headers=H)
    assert r.status_code == 200
    d = r.json()

    # fixed governance rails, in order
    names = [s["name"] for s in d["stages"]]
    assert names == ["firewall", "sensitivity", "policy", "cache",
                     "compression", "routing", "inference", "output"]
    assert all(s["fixed"] for s in d["stages"])

    # routing layer: intents from the catalog
    keys = {i["key"] for i in d["intents"]}
    assert {"cheapest", "smartest", "balanced"}.issubset(keys)

    # targets from the live registry — ollama is always in-boundary
    ids = {t["id"] for t in d["targets"]}
    assert "ollama" in ids
    ollama = next(t for t in d["targets"] if t["id"] == "ollama")
    assert ollama["in_boundary"] is True

    # controls reflect real config
    assert set(("sovereign", "toxicity_filter", "smart_router", "learning")).issubset(
        set(d["controls"].keys()))


def test_workflow_stage_timings():
    d = client.get("/v1/workflow", headers=H).json()
    fw = next(s for s in d["stages"] if s["name"] == "firewall")
    out = next(s for s in d["stages"] if s["name"] == "output")
    assert fw["timing"] == "pre-call"
    assert out["timing"] == "post-call"


def test_workflow_requires_auth():
    # no bearer → unauthenticated
    r = client.get("/v1/workflow")
    assert r.status_code in (401, 403)
