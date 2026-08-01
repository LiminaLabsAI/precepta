"""FEAT-002 — policy scope (key/backend/model) + editable policies with version bump."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.governance import policy
from app.db import get_conn

client = TestClient(app)
ADMIN = {"Authorization": "Bearer dev-admin"}


def _del(pid: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM governance_policies WHERE id=?", (pid,))


def test_empty_scope_applies_to_all():
    assert policy.scope_matches({}, "anykey", "ollama", "ollama/m")


def test_scope_by_key():
    sc = {"keys": ["payments-app"]}
    assert policy.scope_matches(sc, "payments-app", None, None)
    assert not policy.scope_matches(sc, "other-app", None, None)


def test_scope_unknown_value_with_restriction_is_no_match():
    sc = {"backends": ["ollama"]}
    assert policy.scope_matches(sc, "k", "ollama", None)
    assert not policy.scope_matches(sc, "k", "hf", None)
    assert not policy.scope_matches(sc, "k", None, None)      # can't confirm in-scope


def test_scope_is_and_across_dimensions():
    sc = {"keys": ["k1"], "models": ["ollama/m"]}
    assert policy.scope_matches(sc, "k1", None, "ollama/m")
    assert not policy.scope_matches(sc, "k1", None, "ollama/other")
    assert not policy.scope_matches(sc, "k2", None, "ollama/m")


def test_create_with_scope_then_edit_bumps_version():
    pid = policy.create_policy("t", "d", "*", "audit", {}, scope={"keys": ["k1"]})
    try:
        p = next(x for x in policy.list_all() if x["id"] == pid)
        assert p["scope"] == {"keys": ["k1"]} and p["version"] == 1
        ver = policy.update_policy(pid, effect="block", scope={"backends": ["ollama"]})
        assert ver == 2
        p = next(x for x in policy.list_all() if x["id"] == pid)
        assert p["effect"] == "block" and p["scope"] == {"backends": ["ollama"]}
        assert p["version"] == 2
    finally:
        _del(pid)


def test_edit_endpoint_bumps_version():
    pid = client.post("/v1/policies", headers=ADMIN, json={
        "name": "ep", "action_type": "*", "effect": "audit",
        "scope": {"keys": ["k1"]}}).json()["id"]
    try:
        r = client.put(f"/v1/policies/{pid}", headers=ADMIN, json={"effect": "warn"})
        assert r.status_code == 200 and r.json()["version"] == 2
    finally:
        _del(pid)
