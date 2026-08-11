"""Phase 2 validation — intelligent router: brain, techniques, failover, cost-gating."""
from __future__ import annotations

import asyncio
import types

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.ports import Price, RoutePlan
from app.router import parse_intent, is_auto
from app.router import engine, state
from app.router.brain import RulesBrain, candidates
from app.adapters.reasoning import get_reasoner
from app.adapters.model.registry import get_registry
from app.settings import get_settings

client = TestClient(app)


class FakeBackend:
    def __init__(self, name, *, in_boundary=True, tier=1, in_price=0.0,
                 out_price=0.0, fail=False, default_model="m"):
        self.name = name
        self.in_boundary = in_boundary
        self.tier = tier
        self.in_price = in_price
        self.out_price = out_price
        self.fail = fail
        self.default_model = default_model
        self.calls = 0

    def litellm_model(self, m): return f"{self.name}/{m}"
    def price(self, m): return Price(self.in_price, self.out_price)
    def health(self, timeout: float = 3.0): return not self.fail

    async def complete(self, messages, model, **kw):
        if self.fail:
            raise httpx.ConnectError("boom")
        self.calls += 1
        return {"choices": [{"message": {"content": f"resp-from-{self.name}"}}], "usage": {}}


def _settings(sovereign=True):
    return types.SimpleNamespace(sovereign_mode=sovereign)


@pytest.fixture(autouse=True)
def _reset():
    state.reset_all()
    yield
    state.reset_all()


# ── intent parsing ──────────────────────────────────────────────────────
def test_intent_parsing():
    assert is_auto("auto") and is_auto("auto:cheapest")
    assert not is_auto("ollama/x")
    assert parse_intent("auto") == "automatic"
    assert parse_intent("auto:cheapest") == "cheapest"
    assert parse_intent("auto:fastest") == "fastest"
    assert parse_intent("auto:best-quality") == "best-quality"


# ── candidate selection respects sovereignty ────────────────────────────
def test_candidates_exclude_foreign_under_sovereign():
    reg = {"a": FakeBackend("a", in_boundary=True),
           "x": FakeBackend("x", in_boundary=False)}
    names_sov = {be.name for be, _ in candidates(reg, True)}
    names_open = {be.name for be, _ in candidates(reg, False)}
    assert names_sov == {"a"}
    assert names_open == {"a", "x"}


# ── rules brain ─────────────────────────────────────────────────────────
def test_rules_cheapest_picks_lowest_price():
    reg = {"cheap": FakeBackend("cheap", in_price=0.1),
           "pricey": FakeBackend("pricey", in_price=9.0)}
    brain = RulesBrain(lambda: reg, lambda: _settings(True))
    plan = brain.decide("hello", "cheapest")
    assert plan.backend == "cheap"
    assert plan.technique == "passthrough"


def test_rules_automatic_hard_uses_high_tier_and_bestofn():
    reg = {"small": FakeBackend("small", tier=1),
           "big": FakeBackend("big", tier=3)}
    brain = RulesBrain(lambda: reg, lambda: _settings(True))
    plan = brain.decide("Please analyze and reason step by step " * 20, "automatic")
    assert plan.backend == "big"
    assert plan.technique == "best_of_n"


# ── reasoning techniques call the model the right number of times ────────
def test_reasoning_call_counts():
    async def fake_call(msgs):
        fake_call.n += 1
        return ({"choices": [{"message": {"content": "x" * fake_call.n}}]}, "b")

    for name, expected in (("passthrough", 1), ("best_of_n", 3), ("self_consistency", 3)):
        fake_call.n = 0
        r = get_reasoner(name)
        asyncio.run(r.run([], None, fake_call))
        assert fake_call.n == expected, name


# ── engine: failover ────────────────────────────────────────────────────
def test_engine_failover_to_healthy_backend():
    reg = {"primary": FakeBackend("primary", fail=True),
           "backup": FakeBackend("backup")}
    plan = RoutePlan("primary", "m", "passthrough", "test")
    result, meta = asyncio.run(engine.execute(plan, [{"role": "user", "content": "hi"}],
                                              reg, _settings(True)))
    assert meta["backend_used"] == "backup"
    assert meta["fell_over"] is True


# ── engine: cost-gating downgrades an expensive technique ────────────────
def test_engine_cost_gating_downgrades():
    reg = {"b": FakeBackend("b", out_price=1000.0)}
    plan = RoutePlan("b", "m", "best_of_n", "hard")
    result, meta = asyncio.run(engine.execute(
        plan, [{"role": "user", "content": "hi"}], reg, _settings(True),
        budget_usd=0.01, max_tokens=500))
    assert meta["technique"] == "passthrough"   # downgraded
    assert meta["calls"] == 1


# ── circuit breaker opens after threshold ────────────────────────────────
def test_circuit_breaker_opens():
    b = state.breaker("z")
    assert not b.is_open()
    for _ in range(3):
        b.record_failure()
    assert b.is_open()
    b.record_success()
    assert not b.is_open()


# ── integration: auto:cheapest through the real gateway ──────────────────
def _ollama_up():
    s = get_settings()
    try:
        return httpx.get(f"http://127.0.0.1:{s.ollama_port}/v1/models", timeout=2.0).status_code < 500
    except httpx.HTTPError:
        return False


@pytest.mark.skipif(not _ollama_up(), reason="Ollama not running")
def test_auto_cheapest_integration():
    r = client.post("/v1/chat/completions", json={
        "model": "auto:cheapest",
        "messages": [{"role": "user", "content": "Reply with one word: pong"}],
        "max_tokens": 10,
    })
    assert r.status_code == 200, r.text
    p = r.json()["precepta"]
    assert p["route_mode"] == "cheapest"
    assert p["backend_used"] == "ollama"
    assert p["technique"] == "passthrough"
