"""FEAT-008 — learning loop: trace → reward → learned preference → biased routing.

Deterministic (no live model): the learned preference is seeded from traces and
the brain is driven with a fake registry, so the *mechanism* is proven; live
improvement accrues as real feedback arrives.
"""
from __future__ import annotations

import types

from fastapi.testclient import TestClient

from app import learning, org
from app.router.brain import LearnedBrain, get_brain
from app.main import app

client = TestClient(app)
ADMIN = {"Authorization": "Bearer dev-admin"}
USER = {"Authorization": "Bearer dev-user"}


def _fake_be(name, tier):
    return types.SimpleNamespace(name=name, tier=tier, in_boundary=True,
                                 default_model=f"{name}-m")


def _registry():
    return {"cheap": _fake_be("cheap", 1), "strong": _fake_be("strong", 3)}


def _settings():
    return types.SimpleNamespace(sovereign_mode=True)


# ── reward + preference ──────────────────────────────────────────────────
def test_reward_and_preference_needs_evidence():
    learning.clear()
    # 2 traces for 'strong' on hard, both thumbs-up → but below MIN_TRACES(3)
    for _ in range(2):
        tid = learning.record_trace("q", "hard", "strong", "passthrough", 100, 0.0, False)
        learning.apply_feedback(tid, +1)
    assert learning.preference("hard") is None            # not enough evidence yet
    # a 3rd positive trace crosses the bar
    tid = learning.record_trace("q", "hard", "strong", "passthrough", 100, 0.0, False)
    learning.apply_feedback(tid, +1)
    assert learning.preference("hard") == "strong"
    learning.clear()


def test_preference_ignores_negative_and_respects_allowed():
    learning.clear()
    for _ in range(4):                                    # 'cheap' rewarded on hard
        learning.apply_feedback(
            learning.record_trace("q", "hard", "cheap", "passthrough", 50, 0.0, False), +1)
    for _ in range(4):                                    # 'strong' punished on hard
        learning.apply_feedback(
            learning.record_trace("q", "hard", "strong", "passthrough", 50, 0.0, False), -1)
    assert learning.preference("hard") == "cheap"
    # governance filter: if only 'strong' is allowed, no positive-reward option → None
    assert learning.preference("hard", allowed={"strong"}) is None
    learning.clear()


# ── learned brain biases routing, bounded by candidates ──────────────────
def test_learned_brain_routes_to_preferred(monkeypatch):
    learning.clear()
    from app.router import intent as intent_mod
    monkeypatch.setattr(intent_mod, "classify", lambda q: None)   # base falls to rules
    # a long/analytical query → _difficulty == 'hard'
    hard_q = "analyze and prove step by step why this holds " + "x" * 420
    for _ in range(4):
        learning.apply_feedback(
            learning.record_trace(hard_q, "hard", "cheap", "passthrough", 50, 0.0, False), +1)
    brain = LearnedBrain(_registry, _settings)
    plan = brain.decide(hard_q, "automatic")
    assert plan.backend == "cheap" and "[learned]" in plan.reason
    # honors governance: if 'cheap' is not allowed, no learned override
    plan2 = brain.decide(hard_q, "automatic", allowed={"strong"})
    assert plan2.backend == "strong" and "[learned]" not in plan2.reason
    learning.clear()


def test_get_brain_learned():
    assert get_brain("learned", _registry).__class__ is LearnedBrain


# ── feedback + stats endpoints ───────────────────────────────────────────
def test_feedback_endpoint_and_stats():
    learning.clear()
    try:
        tid = learning.record_trace("q", "easy", "cheap", "passthrough", 20, 0.0, False)
        r = client.post("/v1/feedback", headers=USER, json={"trace_id": tid, "rating": 1})
        assert r.status_code == 200 and r.json()["rating"] == 1
        assert client.post("/v1/feedback", headers=USER,
                           json={"trace_id": "nope", "rating": 1}).status_code == 404
        # stats is admin-only
        assert client.get("/v1/learning/stats", headers=USER).status_code == 403
        st = client.get("/v1/learning/stats", headers=ADMIN).json()
        assert st["traces"] == 1 and st["rated"] == 1 and st["min_traces"] == 3
    finally:
        learning.clear()
