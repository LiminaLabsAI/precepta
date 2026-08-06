"""FEAT-005 — prompt compression: safe baseline, opt-in aggressive, fail-soft,
and the governed pipeline path (compressed prompt reaches the model, transparently)."""
from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from app import compression as comp, features
from app.main import app

client = TestClient(app)
ADMIN = {"Authorization": "Bearer dev-admin"}


def _reset():
    comp.clear()
    features.clear()


# ── baseline is quality-safe ─────────────────────────────────────────────
def test_baseline_normalizes_whitespace_only():
    msgs = [{"role": "user", "content": "hello    world\n\n\n\nfoo   bar   "}]
    out, st = comp.compress(msgs, aggressive=False)
    assert out[0]["content"] == "hello world\n\nfoo bar"
    assert st["mode"] == "baseline" and st["saved_tokens"] >= 0


def test_baseline_leaves_system_messages_untouched():
    msgs = [{"role": "system", "content": "keep    this   exact"},
            {"role": "user", "content": "trim    me"}]
    out, _ = comp.compress(msgs, aggressive=False)
    assert out[0]["content"] == "keep    this   exact"       # system untouched
    assert out[1]["content"] == "trim me"


# ── aggressive drops conservative filler (opt-in, lossy) ─────────────────
def test_aggressive_drops_filler():
    msgs = [{"role": "user", "content": "Please just really summarize this very simply"}]
    out, st = comp.compress(msgs, aggressive=True)
    low = out[0]["content"].lower()
    assert "please" not in low and "really" not in low and "very" not in low
    assert "summarize" in low                                # meaning-bearing words kept
    assert st["mode"] == "aggressive" and st["saved_tokens"] > 0


def test_compress_fail_soft(monkeypatch):
    # a broken transform must pass the original through, not raise
    monkeypatch.setattr(comp, "_baseline", lambda t: (_ for _ in ()).throw(RuntimeError()))
    msgs = [{"role": "user", "content": "unchanged please"}]
    out, st = comp.compress(msgs, aggressive=False)
    assert out == msgs and st["mode"] == "off"


# ── governed pipeline: compressed prompt reaches the model, shown transparently ──
def test_pipeline_compresses_and_reports(monkeypatch):
    _reset()
    features.set_config("auto", {"compression_enabled": True})   # auto row (req_backend None)
    seen = {}

    async def fake_infer(msgs, route_ctx=None):
        seen["content"] = msgs[-1]["content"]
        return ({"choices": [{"message": {"role": "assistant", "content": "ok"}}],
                 "usage": {"prompt_tokens": 3, "completion_tokens": 1}},
                {"backend_used": "ollama", "in_boundary": True, "route_mode": "explicit",
                 "technique": "passthrough", "model": "m"})

    from app.gateway import pipeline
    try:
        with patch.object(pipeline, "governed_chat", wraps=pipeline.governed_chat):
            # drive governed_chat directly to avoid a live backend
            import asyncio
            from app.ports import Principal
            status, payload = asyncio.run(pipeline.governed_chat(
                [{"role": "user", "content": "hello     world    extra   spaces"}],
                {"temperature": 0.5}, Principal("u@x", "user"), False, fake_infer))
        assert status == 200
        assert seen["content"] == "hello world extra spaces"      # model saw compressed
        assert payload["precepta"]["compression"]["saved_tokens"] > 0
    finally:
        _reset()


def test_compression_stats_admin_only():
    assert client.get("/v1/compression/stats",
                      headers={"Authorization": "Bearer dev-user"}).status_code == 403
    assert client.get("/v1/compression/stats", headers=ADMIN).status_code == 200
