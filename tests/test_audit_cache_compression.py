"""Cache hits and compression must be auditable — visible under the audit view's
'Cache & compression' filter (which matches events whose resource contains
'cache'/'compression'). Previously nothing wrote such events (filter was dead)."""
from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from app import cache, org
from app.gateway import pipeline
from app.ports import Principal
from app.adapters.audit.chain import get_chain
from app.main import app

client = TestClient(app)
ADMIN = {"Authorization": "Bearer dev-admin"}


def _resources(limit=15):
    return [r.get("resource") for r in get_chain().recent(limit=limit)]


async def _fake_infer(msgs, route_ctx=None):
    return ({"choices": [{"message": {"role": "assistant", "content": "ok"}}],
             "usage": {"prompt_tokens": 3, "completion_tokens": 1}},
            {"backend_used": "ollama", "in_boundary": True, "route_mode": "explicit",
             "technique": "passthrough", "model": "m"})


def test_cache_hit_writes_a_cache_event():
    cache.clear()
    org.update({"cache_enabled": "true"})
    try:
        kw = {"temperature": 0, "max_tokens": 50, "top_p": None}
        msgs = [{"role": "user", "content": "audit cache probe"}]
        cache.store("auto", msgs, kw, team="",
                    response={"choices": [{"message": {"role": "assistant", "content": "x"}}],
                              "usage": {"prompt_tokens": 2, "completion_tokens": 1}},
                    tokens_in=2, tokens_out=1, backend="ollama", model="m")
        r = client.post("/v1/chat/completions", headers=ADMIN, json={
            "model": "auto", "messages": msgs, "temperature": 0, "max_tokens": 50})
        assert r.status_code == 200 and r.json()["precepta"]["cache"] == "hit"
        assert "cache.hit" in _resources()          # filterable as Cache & compression
    finally:
        cache.clear()
        org.update({"cache_enabled": "false"})


def test_compression_writes_a_compression_event():
    org.update({"compression_enabled": "true", "compression_aggressive": "true"})
    try:
        status, _ = asyncio.run(pipeline.governed_chat(
            [{"role": "user", "content": "please just really trim   this   very simply"}],
            {"temperature": 0.5}, Principal("u@x", "user"), False, _fake_infer))
        assert status == 200
        assert "compression" in _resources()        # filterable as Cache & compression
    finally:
        org.update({"compression_enabled": "false", "compression_aggressive": "false"})
