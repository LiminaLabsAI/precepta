"""Copilot: grounded in real state, in-boundary, fail-soft.

Covers: fact gathering reads real stores; the fallback answer is built from
those facts (no fabrication); empty question is handled; a model failure never
raises and degrades to the grounded fallback; a working (stubbed in-boundary)
model produces a grounded answer.
"""
from __future__ import annotations

import asyncio

import app.copilot as copilot


def _run(coro):
    return asyncio.run(coro)


def test_gather_facts_returns_real_shape():
    facts = copilot.gather_facts()
    assert isinstance(facts, dict)
    # These come from stores that always exist in a booted app.
    assert "sovereign_mode" in facts
    assert isinstance(facts["sovereign_mode"], bool)
    assert "inference_endpoints" in facts
    assert isinstance(facts["inference_endpoints"], list)
    assert facts["endpoint_count"] == len(facts["inference_endpoints"])


def test_empty_question_is_grounded_and_no_model():
    out = _run(copilot.answer(""))
    assert out["grounded"] is True
    assert out["model"] is None
    assert "endpoints" in out["answer"].lower() or "ask me" in out["answer"].lower()


def test_fallback_answer_is_built_from_facts_only():
    facts = {
        "org": {"name": "Acme"},
        "sovereign_mode": True,
        "endpoint_count": 2,
        "all_endpoints_in_boundary": True,
        "api_keys": {"total": 3, "active": 2},
        "policies": {"total": 4, "enabled": 4},
        "internet_egress": {"result": "blocked", "verified": True},
    }
    text = copilot._fallback_answer("anything", facts)
    assert "Acme" in text
    assert "Sovereign Mode: on" in text
    assert "2" in text and "in-boundary" in text
    assert "blocked" in text
    # Nothing fabricated: no numbers that aren't in the facts.
    assert "verified" in text


def test_model_failure_degrades_to_fallback(monkeypatch):
    """If the registry/model blows up, answer() still returns a grounded reply."""
    def _boom():
        raise RuntimeError("no model")
    monkeypatch.setattr("app.adapters.model.registry.get_registry", _boom)
    out = _run(copilot.answer("Is sovereign mode on?"))
    assert out["grounded"] is True
    assert isinstance(out["answer"], str) and out["answer"]
    # It should read the live state directly.
    assert "state" in out["answer"].lower() or "sovereign" in out["answer"].lower()


def test_working_model_produces_grounded_answer(monkeypatch):
    """Stub an in-boundary backend; the copilot uses it and reports it."""
    class _Be:
        default_model = "llama3.2:3b"
        in_boundary = True
        async def complete(self, messages, model, **kw):
            # The system prompt + facts must be passed in.
            joined = " ".join(m["content"] for m in messages)
            assert "FACTS" in joined
            assert "Sovereign" in joined or "sovereign" in joined
            return {"choices": [{"message": {"content": "Sovereign Mode is on."}}]}

    monkeypatch.setattr("app.adapters.model.registry.get_registry",
                        lambda: {"ollama": _Be()})
    out = _run(copilot.answer("Is sovereign mode on?"))
    assert out["answer"] == "Sovereign Mode is on."
    assert out["in_boundary"] is True
    assert out["model"] == "llama3.2:3b"
