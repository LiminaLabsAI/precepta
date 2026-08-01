"""FEAT-003 — response cache: keying, safe-by-default gating, hit accounting,
and the governed pipeline hit path (served without calling a backend)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import cache, org
from app.main import app
from app.db import get_conn

client = TestClient(app)
ADMIN = {"Authorization": "Bearer dev-admin"}


def _reset():
    cache.clear()
    org.update({"cache_enabled": "false", "cache_semantic": "false", "cache_threshold": "1.0"})


# ── keying + gating ──────────────────────────────────────────────────────
def test_cache_key_depends_on_content():
    kw = {"temperature": 0, "max_tokens": 50, "top_p": None}
    a = cache.cache_key("auto", [{"role": "user", "content": "hi"}], kw)
    b = cache.cache_key("auto", [{"role": "user", "content": "bye"}], kw)
    same = cache.cache_key("auto", [{"role": "user", "content": "hi"}], kw)
    assert a != b and a == same


def test_is_cacheable_safe_by_default():
    _reset()
    kw0 = {"temperature": 0}
    assert cache.is_cacheable(kw0, sensitive=False) is False        # off by default
    org.update({"cache_enabled": "true"})
    try:
        assert cache.is_cacheable({"temperature": 0}, sensitive=False) is True
        assert cache.is_cacheable({"temperature": 0}, sensitive=True) is False   # sensitive never cached
        assert cache.is_cacheable({"temperature": 0.7}, sensitive=False) is False  # non-deterministic
        assert cache.is_cacheable({"temperature": None}, sensitive=False) is False
    finally:
        _reset()


# ── store / lookup / hit accounting ──────────────────────────────────────
def test_store_lookup_and_savings():
    _reset()
    org.update({"cache_enabled": "true"})
    try:
        kw = {"temperature": 0, "max_tokens": 50, "top_p": None}
        msgs = [{"role": "user", "content": "capital of France?"}]
        resp = {"choices": [{"message": {"role": "assistant", "content": "Paris"}}],
                "usage": {"prompt_tokens": 6, "completion_tokens": 1}}
        assert cache.lookup("auto", msgs, kw, team="") is None       # miss first
        cache.store("auto", msgs, kw, team="", response=resp,
                    tokens_in=6, tokens_out=1, backend="hf", model="m")
        entry = cache.lookup("auto", msgs, kw, team="")
        assert entry is not None and entry["response"]["choices"][0]["message"]["content"] == "Paris"
        assert entry["exact"] is True
        # different team can't see it (per-team scope)
        assert cache.lookup("auto", msgs, kw, team="other") is None
        saved = cache.record_hit(entry, team="")
        assert saved["tokens_saved"] == 7
        st = cache.stats()
        assert st["entries"] == 1 and st["hits"] == 1 and st["tokens_saved"] == 7
    finally:
        _reset()


# ── governed pipeline: a hit is served without calling any backend ───────
def test_pipeline_cache_hit_served_without_backend():
    _reset()
    org.update({"cache_enabled": "true"})
    try:
        kw = {"temperature": 0, "max_tokens": 50, "top_p": None}
        msgs = [{"role": "user", "content": "unique cache probe 42"}]
        resp = {"choices": [{"message": {"role": "assistant", "content": "cached answer"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2}}
        cache.store("auto", msgs, kw, team="", response=resp,
                    tokens_in=5, tokens_out=2, backend="ollama", model="llama3.2:3b")
        # dev-admin has team "" → same scope. A hit must NOT reach a live backend.
        r = client.post("/v1/chat/completions", headers=ADMIN, json={
            "model": "auto", "messages": msgs, "temperature": 0, "max_tokens": 50})
        assert r.status_code == 200
        body = r.json()
        assert body["choices"][0]["message"]["content"] == "cached answer"
        assert body["precepta"]["cache"] == "hit"
        assert body["precepta"]["tokens_saved"] == 7
    finally:
        _reset()


def test_pipeline_no_cache_when_disabled():
    _reset()  # cache off
    # a temp>0 or cache-off request must not be served from a pre-seeded entry
    kw = {"temperature": 0, "max_tokens": 50, "top_p": None}
    msgs = [{"role": "user", "content": "disabled cache probe"}]
    cache.clear()
    org.update({"cache_enabled": "true"})
    cache.store("auto", msgs, kw, team="", response={"choices": [], "usage": {}},
                tokens_in=0, tokens_out=0, backend="ollama", model="m")
    org.update({"cache_enabled": "false"})              # now disabled
    try:
        assert cache.lookup("auto", msgs, kw, team="") is not None   # entry exists
        assert cache.is_cacheable(kw, sensitive=False) is False       # but gating says no
    finally:
        _reset()


# ── stats endpoint is admin-only ─────────────────────────────────────────
def test_cache_stats_admin_only():
    assert client.get("/v1/cache/stats", headers={"Authorization": "Bearer dev-user"}).status_code == 403
    r = client.get("/v1/cache/stats", headers=ADMIN)
    assert r.status_code == 200 and "cost_saved_usd" in r.json()
