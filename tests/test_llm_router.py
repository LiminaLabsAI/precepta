"""FEAT-007·A — LLM intent-router: classification, mapping, fail-soft, governance.

Deterministic (no live model): the classifier HTTP call and `classify` are
stubbed. The live behaviour is exercised by the eval harness run.
"""
from __future__ import annotations

import types

import httpx
import pytest
from fastapi.testclient import TestClient

from app.router import brain as brain_mod
from app.router import intent as intent_mod
from app.router.brain import LLMBrain, candidates, get_brain
from app.main import app
from app.db import get_conn

ADMIN = {"Authorization": "Bearer dev-admin"}


def _fake_be(name, tier, in_boundary=True):
    return types.SimpleNamespace(name=name, tier=tier, in_boundary=in_boundary,
                                 default_model=f"{name}-m")


def _registry():
    # insertion order matters: 'cheap' first (tie-break when prices are unknown=0)
    return {"cheap": _fake_be("cheap", 1), "strong": _fake_be("strong", 3)}


def _settings():
    return types.SimpleNamespace(sovereign_mode=True)


def _brain():
    return LLMBrain(_registry, _settings)


# ── candidate filtering (governance) ─────────────────────────────────────
def test_candidates_allowed_filter():
    reg = _registry()
    assert {c[0].name for c in candidates(reg, True)} == {"cheap", "strong"}
    assert {c[0].name for c in candidates(reg, True, {"strong"})} == {"strong"}
    assert candidates(reg, True, {"nope"}) == []


# ── classification parsing ───────────────────────────────────────────────
@pytest.mark.parametrize("text,expected", [
    ('{"goal":"cost","difficulty":"easy"}', {"goal": "cost", "difficulty": "easy"}),
    ('sure: {"goal":"quality","difficulty":"hard"} done', {"goal": "quality", "difficulty": "hard"}),
    ('{"goal":"speed","difficulty":"easy"}', {"goal": "speed", "difficulty": "easy"}),
    ('{"goal":"banana","difficulty":"easy"}', None),   # bad goal
    ('{"goal":"cost","difficulty":"medium"}', None),   # bad difficulty
    ('no json here', None),
    ('{broken', None),
])
def test_parse_classification(text, expected):
    assert intent_mod.parse_classification(text) == expected


# ── classify: caching + fail-soft ────────────────────────────────────────
def test_classify_caches_and_fails_soft(monkeypatch):
    intent_mod.clear_cache()
    calls = {"n": 0}

    class _Resp:
        def raise_for_status(self): pass
        def json(self):
            return {"choices": [{"message": {"content": '{"goal":"cost","difficulty":"easy"}'}}]}

    def _post(*a, **k):
        calls["n"] += 1
        return _Resp()

    monkeypatch.setattr(intent_mod.httpx, "post", _post)
    assert intent_mod.classify("hello world") == {"goal": "cost", "difficulty": "easy"}
    assert intent_mod.classify("hello world") == {"goal": "cost", "difficulty": "easy"}
    assert calls["n"] == 1                            # second call served from cache

    intent_mod.clear_cache()

    def _boom(*a, **k):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(intent_mod.httpx, "post", _boom)
    assert intent_mod.classify("something else") is None   # fail-soft → None


# ── LLMBrain mapping ─────────────────────────────────────────────────────
def test_llm_brain_maps_goal_to_backend(monkeypatch):
    def stub(cls):
        monkeypatch.setattr(intent_mod, "classify", lambda q: cls)

    stub({"goal": "quality", "difficulty": "hard"})
    p = _brain().decide("q", "automatic")
    assert p.backend == "strong" and p.technique == "passthrough" and "llm-intent" in p.reason

    stub({"goal": "cost", "difficulty": "easy"})
    assert _brain().decide("q", "automatic").backend == "cheap"

    stub({"goal": "quality", "difficulty": "easy"})     # quality wins even if easy
    assert _brain().decide("q", "automatic").backend == "strong"


def test_llm_brain_fail_soft_to_rules(monkeypatch):
    monkeypatch.setattr(intent_mod, "classify", lambda q: None)
    p = _brain().decide("q", "automatic")
    assert "rules" in p.reason.lower()                  # fell back, marked
    assert p.backend in {"cheap", "strong"}


def test_llm_brain_explicit_intent_delegates(monkeypatch):
    # explicit intents don't classify — should not even call classify
    monkeypatch.setattr(intent_mod, "classify",
                        lambda q: (_ for _ in ()).throw(AssertionError("should not classify")))
    p = _brain().decide("q", "cheapest")
    assert p.backend == "cheap" and "llm-intent" not in p.reason


def test_llm_brain_honors_allowed(monkeypatch):
    monkeypatch.setattr(intent_mod, "classify", lambda q: {"goal": "cost", "difficulty": "easy"})
    # cost wants 'cheap', but governance restricts to 'strong' → must pick strong
    p = _brain().decide("q", "automatic", allowed={"strong"})
    assert p.backend == "strong"


def test_get_brain_llm():
    assert get_brain("llm", _registry).__class__ is LLMBrain


# ── governance auto-path: fail-closed block (integration, no live backend) ──
def test_sensitive_auto_fail_closed(monkeypatch):
    client = TestClient(app)
    from app.governance import sensitive as _s
    with get_conn() as conn:
        conn.execute("DELETE FROM sensitive_backends")
    try:
        # approve only a backend that isn't in the registry → no approved candidate
        _s.approve("some-remote-gpu", "DC-1", "admin@local")
        resp = client.post("/v1/chat/completions", headers=ADMIN, json={
            "model": "auto",
            "messages": [{"role": "user", "content": "handle this record"}],
            "data_tag": True})
        assert resp.status_code == 403
        assert "approved" in resp.json()["error"]["message"].lower()
    finally:
        with get_conn() as conn:
            conn.execute("DELETE FROM sensitive_backends")
