"""TD-005 — agent attribution: who/what made the call is recorded in the audit
chain and echoed to the caller, while ordinary human requests stay clean."""
from __future__ import annotations

import asyncio
import json

from fastapi.testclient import TestClient

from app.gateway import pipeline
from app.ports import Principal
from app.adapters.audit.chain import get_chain
from app.main import app
from app import cache, org

client = TestClient(app)
ADMIN = {"Authorization": "Bearer dev-admin"}


async def _fake_infer(msgs, route_ctx=None):
    return ({"choices": [{"message": {"role": "assistant", "content": "ok"}}],
             "usage": {"prompt_tokens": 2, "completion_tokens": 1}},
            {"backend_used": "ollama", "in_boundary": True, "route_mode": "explicit",
             "technique": "passthrough", "model": "m"})


def _latest_governance_meta():
    for row in get_chain().recent(limit=10):
        if row.get("event_type") == "governance.check":
            return json.loads(row["metadata"])
    return {}


def test_attribution_recorded_and_echoed():
    attribution = {"workflow_id": "wf-1", "run_id": "run-9",
                   "agent_id": "agent-x", "end_user": "u@co"}
    status, payload = asyncio.run(pipeline.governed_chat(
        [{"role": "user", "content": "hi"}], {"temperature": 0.5},
        Principal("svc@x", "user"), False, _fake_infer, attribution=attribution))
    assert status == 200
    assert payload["precepta"]["attribution"]["agent_id"] == "agent-x"      # echoed
    meta = _latest_governance_meta()
    assert meta.get("agent_id") == "agent-x" and meta.get("workflow_id") == "wf-1"  # audited


def test_human_request_stays_clean():
    status, payload = asyncio.run(pipeline.governed_chat(
        [{"role": "user", "content": "hi"}], {"temperature": 0.5},
        Principal("person@x", "user"), False, _fake_infer))
    assert "attribution" not in payload["precepta"]                         # no noise
    meta = _latest_governance_meta()
    assert "agent_id" not in meta and "workflow_id" not in meta


def test_endpoint_accepts_attribution():
    # cache-hit path → no live backend; attribution still flows to the audit chain
    cache.clear()
    org.update({"cache_enabled": "true"})
    try:
        kw = {"temperature": 0, "max_tokens": 50, "top_p": None}
        msgs = [{"role": "user", "content": "attrib probe"}]
        cache.store("auto", msgs, kw, team="",
                    response={"choices": [{"message": {"role": "assistant", "content": "x"}}],
                              "usage": {"prompt_tokens": 1, "completion_tokens": 1}},
                    tokens_in=1, tokens_out=1, backend="ollama", model="m")
        r = client.post("/v1/chat/completions", headers=ADMIN, json={
            "model": "auto", "messages": msgs, "temperature": 0, "max_tokens": 50,
            "agent_id": "billing-bot", "user": "customer-42"})
        assert r.status_code == 200
        assert _latest_governance_meta().get("agent_id") == "billing-bot"
    finally:
        cache.clear()
        org.update({"cache_enabled": "false"})
