"""Phase 4 validation — tamper-evident chain, Sovereign Mode, attestation."""
from __future__ import annotations

import types

from fastapi.testclient import TestClient

from app.main import app
from app.adapters.audit.chain import _hash, verify_rows, GENESIS, get_chain, _FIELDS
from app.adapters.model.registry import get_registry
from app.adapters.model.openai_compat import OpenAICompatBackend
from app.sovereign import enforce_backend
from app.sovereign.attestation import build_attestation
from app.settings import get_settings

client = TestClient(app)


def _mkrow(prev, **f):
    row = {"event_id": f["event_id"], "timestamp": f["timestamp"],
           "event_type": "t", "actor": "a", "resource": "chat.completion",
           "action": "allow", "outcome": "allowed", "metadata": "{}",
           "previous_hash": prev}
    row["event_hash"] = _hash(row)
    return row


# ── pure chain verifier ────────────────────────────────────────────────
def test_verify_rows_valid_chain():
    r1 = _mkrow(GENESIS, event_id="e1", timestamp=1)
    r2 = _mkrow(r1["event_hash"], event_id="e2", timestamp=2)
    assert verify_rows([r1, r2]) is True


def test_verify_rows_detects_tamper():
    r1 = _mkrow(GENESIS, event_id="e1", timestamp=1)
    r2 = _mkrow(r1["event_hash"], event_id="e2", timestamp=2)
    r2_tampered = dict(r2, outcome="blocked")   # content changed, hash now stale
    assert verify_rows([r1, r2_tampered]) is False


def test_verify_rows_detects_broken_link():
    r1 = _mkrow(GENESIS, event_id="e1", timestamp=1)
    r2 = _mkrow("f" * 64, event_id="e2", timestamp=2)   # wrong previous_hash
    assert verify_rows([r1, r2]) is False


# ── real chain stays valid after appends ───────────────────────────────
def test_real_chain_append_and_verify():
    chain = get_chain()
    before = chain.count()
    chain.append("test.event", "tester", "unit", "noop", "allowed", {"k": "v"})
    assert chain.count() == before + 1
    assert chain.verify() is True


# ── sovereign enforcement ──────────────────────────────────────────────
def test_enforce_backend():
    # Sovereign Mode is now the EFFECTIVE runtime value (controls), not a passed
    # settings object — so the owner's Console toggle actually takes effect.
    from app import controls
    foreign = types.SimpleNamespace(name="x", in_boundary=False)
    local = types.SimpleNamespace(name="ollama", in_boundary=True)
    controls.clear_sovereign()
    try:
        assert enforce_backend(foreign) is not None   # deploy default (on) → blocked
        assert enforce_backend(local) is None
        controls.set_sovereign(False)                 # runtime off → foreign allowed
        assert enforce_backend(foreign) is None
    finally:
        controls.clear_sovereign()


def test_sovereign_blocks_foreign_route_e2e():
    reg = get_registry()
    reg["foreignx"] = OpenAICompatBackend(
        "foreignx", "http://example.invalid/v1", in_boundary=False, default_model="m")
    try:
        r = client.post("/v1/chat/completions", json={
            "model": "foreignx/m", "messages": [{"role": "user", "content": "hi"}]})
        assert r.status_code == 403
        body = r.json()
        assert body["error"]["type"] == "policy_block"
        assert body["precepta"]["in_boundary"] is False
    finally:
        reg.pop("foreignx", None)


# ── attestation ────────────────────────────────────────────────────────
def test_build_attestation_shape():
    reg = get_registry()
    att = build_attestation(get_settings(), reg)
    assert att["sovereign_mode"] is True
    # all_in_boundary must reflect the ACTUAL registry (a customer may register
    # an external backend; sovereign mode blocks routing to it). Test the
    # computation, not a fixed value.
    assert att["config"]["all_in_boundary"] is all(b.in_boundary for b in reg.values())
    assert att["audit"]["chain_verified"] is True
    assert att["audit"]["external_calls"] == 0
    assert att["egress_test"]["result"] == "blocked"
    assert len(att["signature"]) == 64
    # TD-007: data stores are enumerated and all in-boundary
    assert att["data_stores"]["all_in_boundary"] is True
    assert all(s["location"] == "local (in-boundary)" for s in att["data_stores"]["stores"])


def test_attestation_endpoint():
    r = client.get("/attestation")
    assert r.status_code == 200
    assert isinstance(r.json()["config"]["all_in_boundary"], bool)
    assert r.json()["data_stores"]["all_in_boundary"] is True   # stores are always local


def test_audit_verify_endpoint():
    r = client.get("/audit/verify")
    assert r.status_code == 200
    assert r.json()["verified"] is True
