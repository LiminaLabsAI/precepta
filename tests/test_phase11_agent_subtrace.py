"""Phase 11 — agent sub-trace nesting (L2).

An agent target returns its own reasoning steps (Agent Trace Contract); those
nest under the inference checkpoint of the request trace. Tests the store
(substeps persist/return) and the pipeline (agent_steps from route_meta →
'Agent responded' with substeps; plain model call stays 'Model responded').
"""
from __future__ import annotations

import asyncio

from app import traces


_TEAM = "__test_subtrace_team"


def test_substeps_persist_and_return():
    traces.clear(_TEAM)
    try:
        tr = traces.begin(_TEAM, "u@x", "user", None)
        tr.step("firewall", "clean", "scanned")
        tr.step("inference", "Agent responded", "agent handled it",
                substeps=[{"decision": "looked up order"},
                          {"decision": "drafted reply", "reason": "used the CRM record"}])
        traces.save(tr, "allowed", backend="crm-agent")
        got = traces.get_trace(tr.request_id, _TEAM)
        inf = next(s for s in got["steps"] if s["name"] == "inference")
        assert inf["decision"] == "Agent responded"
        assert len(inf["substeps"]) == 2
        assert inf["substeps"][0]["decision"] == "looked up order"
        assert inf["substeps"][1]["reason"] == "used the CRM record"
        # a plain step has no substeps key
        fw = next(s for s in got["steps"] if s["name"] == "firewall")
        assert "substeps" not in fw
    finally:
        traces.clear(_TEAM)


def _run(route_meta_extra):
    from app.gateway import pipeline
    from app.ports import Principal
    captured = {}

    def fake_save(tr, outcome, **kw):
        captured["tr"] = tr

    async def fake_infer(msgs, route_ctx=None):
        return ({"choices": [{"message": {"role": "assistant", "content": "done"}}],
                 "usage": {"prompt_tokens": 3, "completion_tokens": 2}},
                {"backend_used": "crm-agent", "in_boundary": True, "model": "agent",
                 **route_meta_extra})

    import unittest.mock as _m
    with _m.patch.object(pipeline._traces, "save", fake_save):
        status, _ = asyncio.run(pipeline.governed_chat(
            [{"role": "user", "content": "where is my order"}], {"temperature": 0.5},
            Principal("u@x", "user"), False, fake_infer))
    return status, captured.get("tr")


def test_pipeline_nests_agent_substeps():
    status, tr = _run({"agent": True,
                       "agent_steps": [{"decision": "looked up order"},
                                       {"decision": "drafted reply"}]})
    assert status == 200
    inf = next(s for s in tr.steps if s["name"] == "inference")
    assert inf["decision"] == "Agent responded"
    assert inf["substeps"][0]["decision"] == "looked up order"


def test_agent_without_reasoning_is_honest():
    status, tr = _run({"agent": True})     # agent, but no steps reported
    inf = next(s for s in tr.steps if s["name"] == "inference")
    assert inf["decision"] == "Agent responded"
    assert "no reasoning" in inf["reason"]
    assert "substeps" not in inf


def test_plain_model_call_has_no_substeps():
    status, tr = _run({})                  # ordinary model, no agent
    inf = next(s for s in tr.steps if s["name"] == "inference")
    assert inf["decision"] == "Model responded"
    assert "substeps" not in inf
