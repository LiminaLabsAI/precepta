"""Phase 12 — Group 0 · RouteTarget + Agent Trace Contract tests.

Covers the honest normalisation of whatever an agent returns, plus the
RouteTarget protocol recognising both a model-like and an agent-like target.
"""
from __future__ import annotations

from app.router import targets as T


# ── parse_agent_result — the honest normaliser ───────────────────────────────

def test_wellformed_agent_result():
    r = T.parse_agent_result({
        "output": {"answer": "done"}, "status": "ok", "reason": "looked it up",
        "steps": [{"decision": "queried CRM"}, {"decision": "drafted reply"}],
    })
    assert r.output == {"answer": "done"}
    assert r.status == T.STATUS_OK
    assert r.reason == "looked it up"
    assert len(r.steps) == 2
    assert r.reported_reasoning is True
    assert T.agent_reported_reasoning(r) is True


def test_missing_status_defaults_ok():
    r = T.parse_agent_result({"output": "x", "steps": [{"decision": "a"}]})
    assert r.status == T.STATUS_OK


def test_invalid_status_coerced_to_ok():
    r = T.parse_agent_result({"output": "x", "status": "weird", "steps": [{"decision": "a"}]})
    assert r.status == T.STATUS_OK


def test_failed_status_preserved():
    r = T.parse_agent_result({"output": None, "status": "failed", "reason": "tool crashed"})
    assert r.status == T.STATUS_FAILED and r.reason == "tool crashed"


def test_missing_steps_is_honest_no_reasoning():
    r = T.parse_agent_result({"output": "answer", "status": "ok"})
    assert r.steps == []
    assert r.reported_reasoning is False
    assert r.reason == "agent reported no reasoning"
    assert T.agent_reported_reasoning(r) is False


def test_empty_steps_list_is_no_reasoning():
    r = T.parse_agent_result({"output": "answer", "steps": []})
    assert r.reported_reasoning is False and r.reason == "agent reported no reasoning"


def test_reason_kept_when_steps_present():
    r = T.parse_agent_result({"output": "a", "reason": "because", "steps": [{"decision": "s"}]})
    assert r.reason == "because" and r.reported_reasoning is True


def test_none_result_is_failed():
    r = T.parse_agent_result(None)
    assert r.status == T.STATUS_FAILED
    assert r.reason == "agent returned nothing"
    assert r.reported_reasoning is False


def test_bare_string_result_is_output():
    r = T.parse_agent_result("just an answer")
    assert r.output == "just an answer" and r.status == T.STATUS_OK and r.steps == []


def test_raw_completion_dict_without_envelope_is_output():
    completion = {"choices": [{"message": {"content": "hi"}}], "usage": {"total_tokens": 5}}
    r = T.parse_agent_result(completion)
    assert r.output == completion and r.status == T.STATUS_OK and r.steps == []


def test_steps_not_a_list_is_coerced_empty():
    r = T.parse_agent_result({"output": "x", "steps": "oops"})
    assert r.steps == [] and r.reported_reasoning is False


def test_bare_string_steps_are_coerced_to_dicts():
    r = T.parse_agent_result({"output": "x", "steps": ["looked up order", "sent email"]})
    assert all(isinstance(s, dict) for s in r.steps)
    assert r.steps[0]["decision"] == "looked up order"
    assert r.reported_reasoning is True


# ── RouteTarget protocol ─────────────────────────────────────────────────────

class _InferenceLike:
    id = "ollama"
    kind = T.KIND_INFERENCE
    in_boundary = True
    async def execute(self, messages, opts):  # pragma: no cover - shape only
        return T.TargetResult(output={})


class _AgentLike:
    id = "crm-agent"
    kind = T.KIND_AGENT
    in_boundary = True
    async def execute(self, messages, opts):  # pragma: no cover - shape only
        return T.TargetResult(output={})


class _NotATarget:
    id = "nope"     # missing kind / in_boundary / execute


def test_both_model_and_agent_satisfy_route_target():
    assert isinstance(_InferenceLike(), T.RouteTarget)
    assert isinstance(_AgentLike(), T.RouteTarget)
    assert _InferenceLike().kind == T.KIND_INFERENCE
    assert _AgentLike().kind == T.KIND_AGENT


def test_non_conforming_object_is_not_a_route_target():
    assert not isinstance(_NotATarget(), T.RouteTarget)
