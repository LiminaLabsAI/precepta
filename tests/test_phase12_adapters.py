"""Phase 12 — Group 2 · target adapter tests.

Covers the pure in-boundary allowlist guard, the InferenceTarget (success +
fail-soft), and the AgentTarget (sub-trace capture, timeout, fail-soft, and the
governed gateway hand-off). Async is driven with asyncio.run — no extra deps.
"""
from __future__ import annotations

import asyncio

import pytest

from app.router import target_adapters as ta
from app.router import targets as T


def run(coro):
    return asyncio.run(coro)


# ── sovereignty guard (pure) ─────────────────────────────────────────────────

def test_host_of_parses_variants():
    assert ta.host_of("https://10.0.4.12:8000/v1") == "10.0.4.12"
    assert ta.host_of("http://vllm.internal/v1") == "vllm.internal"
    assert ta.host_of("localhost:11434") == "localhost"     # no scheme
    assert ta.host_of("HTTPS://Host.Example/v1") == "host.example"  # lower-cased
    assert ta.host_of("") == ""


def test_enforce_boundary_allows_permitted_host():
    assert ta.enforce_boundary("http://10.0.0.1:8000/v1", {"10.0.0.1"}) == "10.0.0.1"


def test_enforce_boundary_rejects_unlisted_host():
    with pytest.raises(ValueError):
        ta.enforce_boundary("https://router.huggingface.co/v1", {"10.0.0.1"})


def test_enforce_boundary_requires_explicit_base_url():
    with pytest.raises(ValueError):
        ta.enforce_boundary("", {"10.0.0.1"})       # no fallthrough to a provider default
    with pytest.raises(ValueError):
        ta.enforce_boundary("", None)


def test_enforce_boundary_none_allowlist_permits_explicit_base():
    # no allowlist configured → any explicit in-boundary base is allowed
    assert ta.enforce_boundary("http://my-vllm:8000/v1", None) == "my-vllm"


def test_litellm_call_enforces_boundary_before_importing_litellm():
    # a disallowed host must be rejected by the guard, never reaching `import litellm`
    call = ta.make_litellm_call("hf/x", "https://router.huggingface.co/v1", None, {"10.0.0.1"})
    with pytest.raises(ValueError):
        run(call([{"role": "user", "content": "hi"}], {}))
    call2 = ta.make_litellm_call("m", "", None, None)
    with pytest.raises(ValueError):
        run(call2([], {}))


# ── InferenceTarget ──────────────────────────────────────────────────────────

def test_inference_target_success():
    async def ok(messages, opts):
        return {"choices": [{"message": {"content": "hi"}}]}
    t = ta.InferenceTarget("ollama", ok, in_boundary=True, model="llama")
    r = run(t.execute([{"role": "user", "content": "hi"}], {}))
    assert r.status == T.STATUS_OK
    assert r.output["choices"][0]["message"]["content"] == "hi"
    assert r.meta["target"] == "ollama"
    assert t.kind == T.KIND_INFERENCE
    assert isinstance(t, T.RouteTarget)


def test_inference_target_is_fail_soft():
    async def boom(messages, opts):
        raise RuntimeError("backend down")
    t = ta.InferenceTarget("vllm", boom)
    r = run(t.execute([], {}))
    assert r.status == T.STATUS_FAILED
    assert "backend down" in r.reason
    assert r.output is None      # did not raise


# ── AgentTarget ──────────────────────────────────────────────────────────────

def test_agent_target_captures_sub_trace():
    async def agent(messages, opts):
        return {"output": {"reply": "done"}, "status": "ok",
                "steps": [{"decision": "looked up order"}, {"decision": "drafted reply"}]}
    t = ta.AgentTarget("crm", agent)
    r = run(t.execute([], {}))
    assert r.status == T.STATUS_OK
    assert len(r.steps) == 2 and r.reported_reasoning is True
    assert r.meta["target"] == "crm"
    assert t.kind == T.KIND_AGENT and isinstance(t, T.RouteTarget)


def test_agent_target_honest_when_no_reasoning():
    async def silent(messages, opts):
        return {"output": "answer"}
    r = run(ta.AgentTarget("cs", silent).execute([], {}))
    assert r.reported_reasoning is False
    assert r.reason == "agent reported no reasoning"


def test_agent_target_passes_gateway_for_governed_egress():
    seen = {}
    sentinel = object()
    async def agent(messages, opts):
        seen["gateway"] = opts.get("gateway")
        return {"output": "ok", "steps": [{"decision": "x"}]}
    run(ta.AgentTarget("crm", agent, gateway=sentinel).execute([], {"foo": 1}))
    assert seen["gateway"] is sentinel     # agent's model calls re-enter Precepta


def test_agent_target_times_out_fail_soft():
    async def slow(messages, opts):
        await asyncio.sleep(0.2)
        return {"output": "late"}
    r = run(ta.AgentTarget("slow", slow, timeout=0.05).execute([], {}))
    assert r.status == T.STATUS_FAILED and "timed out" in r.reason


def test_agent_target_dispatch_error_fail_soft():
    async def boom(messages, opts):
        raise ValueError("tool exploded")
    r = run(ta.AgentTarget("crm", boom).execute([], {}))
    assert r.status == T.STATUS_FAILED and "tool exploded" in r.reason


def test_agent_target_none_return_is_failed():
    async def nothing(messages, opts):
        return None
    r = run(ta.AgentTarget("crm", nothing).execute([], {}))
    assert r.status == T.STATUS_FAILED and r.reason == "agent returned nothing"
