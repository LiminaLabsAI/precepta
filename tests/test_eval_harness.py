"""FEAT-006 — router eval harness: deterministic logic tests (no live models).

The backend-real run (against Ollama) is `python -m tests.benchmarks`; here we
lock the aggregation, the scalar, and the frozen eval set so CI stays green
without a model. Rule 11: these guard that the evaluator's shape doesn't drift.
"""
from __future__ import annotations

import asyncio

import pytest

from tests.benchmarks import harness
from tests.benchmarks.judge import parse_score
from app.ports import RoutePlan


# ── the frozen eval set ──────────────────────────────────────────────────
def test_eval_set_is_wellformed_and_v1():
    import json
    from pathlib import Path
    data = json.loads((Path(harness.__file__).with_name("router_eval_v1.json")).read_text())
    assert data["version"] == "v1"
    cases = data["cases"]
    assert len(cases) >= 10
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids))                       # unique ids
    for c in cases:
        assert {"id", "category", "prompt", "reference", "rubric"} <= c.keys()
        assert c["prompt"] and c["reference"] and c["rubric"]
        assert c["category"] in {"easy", "hard", "latency"}


# ── judge score parsing ──────────────────────────────────────────────────
@pytest.mark.parametrize("text,expected", [
    ("100", 1.0), ("0", 0.0), ("85", 0.85), ("  score: 70  ", 0.70),
    ("120", 1.0), ("-5", 0.0), ("", 0.0), ("no number here", 0.0), ("42.5", 0.425),
])
def test_parse_score(text, expected):
    assert parse_score(text) == pytest.approx(expected)


# ── run_eval aggregation with stubs ──────────────────────────────────────
class _StubBrain:
    name = "stub-brain"
    def decide(self, query, mode, ctx=None, budget=None):
        return RoutePlan("ollama", "stub-model", "passthrough", "stub")


class _StubJudge:
    name = "stub-judge"
    def __init__(self, by_q):
        self._by_q = by_q
    def score(self, question, answer, reference, rubric):
        return self._by_q[question]


def _stub_execute_factory():
    async def _exec(plan, msgs, reg, settings, **kw):
        result = {"choices": [{"message": {"content": "stub answer"}}],
                  "usage": {"prompt_tokens": 8, "completion_tokens": 4}}
        meta = {"backend_used": "ollama", "technique": "passthrough", "reason": "stub"}
        return result, meta
    return _exec


def test_run_eval_scalar_and_by_category(monkeypatch):
    monkeypatch.setattr(harness.engine, "execute", _stub_execute_factory())
    cases = [
        {"id": "a1", "category": "easy", "prompt": "q1", "reference": "r", "rubric": "x"},
        {"id": "a2", "category": "easy", "prompt": "q2", "reference": "r", "rubric": "x"},
        {"id": "b1", "category": "hard", "prompt": "q3", "reference": "r", "rubric": "x"},
    ]
    judge = _StubJudge({"q1": 1.0, "q2": 0.0, "q3": 0.5})
    report = asyncio.run(harness.run_eval(
        judge, brain=_StubBrain(), route_mode="automatic", cases=cases,
        registry_getter=lambda: {}))

    assert report.version == "v1"
    assert report.n == 3
    assert report.judge == "stub-judge" and report.brain == "stub-brain"
    assert report.scalar == pytest.approx((1.0 + 0.0 + 0.5) / 3, abs=1e-4)   # mean quality
    assert report.by_category["easy"] == pytest.approx(0.5)
    assert report.by_category["hard"] == pytest.approx(0.5)
    assert report.mean_cost_usd >= 0.0
    assert len(report.cases) == 3
    assert {c["backend_used"] for c in report.cases} == {"ollama"}


def test_run_eval_handles_empty_answer(monkeypatch):
    async def _exec(plan, msgs, reg, settings, **kw):
        return {"choices": [], "usage": {}}, {"backend_used": "ollama",
                                              "technique": "passthrough", "reason": ""}
    monkeypatch.setattr(harness.engine, "execute", _exec)
    cases = [{"id": "x", "category": "easy", "prompt": "q", "reference": "r", "rubric": "x"}]
    report = asyncio.run(harness.run_eval(
        _StubJudge({"q": 0.0}), brain=_StubBrain(), cases=cases, registry_getter=lambda: {}))
    assert report.scalar == 0.0 and report.cases[0]["answer"] == ""
