"""FEAT-003/011 — per-endpoint response cache: keying, per-endpoint gating,
hit accounting, and the governed pipeline hit path (served without a backend)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import cache, features
from app.main import app

client = TestClient(app)
ADMIN = {"Authorization": "Bearer dev-admin"}
AUTO = "auto"


def _reset():
    cache.clear()
    features.clear()


# ── keying + gating (per endpoint) ────────────────────────────────────────
def test_cache_key_depends_on_content():
    kw = {"temperature": 0, "max_tokens": 50, "top_p": None}
    a = cache.cache_key("auto", [{"role": "user", "content": "hi"}], kw)
    b = cache.cache_key("auto", [{"role": "user", "content": "bye"}], kw)
    same = cache.cache_key("auto", [{"role": "user", "content": "hi"}], kw)
    assert a != b and a == same


def test_is_cacheable_per_endpoint():
    _reset()
    try:
        assert cache.is_cacheable({"temperature": 0}, False, AUTO) is False   # off by default
        features.set_config(AUTO, {"cache_enabled": True})
        assert cache.is_cacheable({"temperature": 0}, False, AUTO) is True
        assert cache.is_cacheable({"temperature": 0}, True, AUTO) is False     # sensitive never
        assert cache.is_cacheable({"temperature": 0.7}, False, AUTO) is False  # non-deterministic
        # a DIFFERENT endpoint is still off — config is per-endpoint
        assert cache.is_cacheable({"temperature": 0}, False, "ollama") is False
    finally:
        _reset()


def test_store_lookup_and_savings():
    _reset()
    features.set_config(AUTO, {"cache_enabled": True})
    try:
        kw = {"temperature": 0, "max_tokens": 50, "top_p": None}
        msgs = [{"role": "user", "content": "capital of France?"}]
        resp = {"choices": [{"message": {"role": "assistant", "content": "Paris"}}],
                "usage": {"prompt_tokens": 6, "completion_tokens": 1}}
        assert cache.lookup("auto", msgs, kw, "", AUTO) is None
        cache.store("auto", msgs, kw, "", AUTO, resp, 6, 1, "ollama", "m")
        entry = cache.lookup("auto", msgs, kw, "", AUTO)
        assert entry is not None and entry["response"]["choices"][0]["message"]["content"] == "Paris"
        assert cache.lookup("auto", msgs, kw, "other", AUTO) is None   # per-team scope
        saved = cache.record_hit(entry, "")
        assert saved["tokens_saved"] == 7
        st = cache.stats(AUTO)                                          # per-endpoint stats
        assert st["entries"] == 1 and st["hits"] == 1 and st["tokens_saved"] == 7
    finally:
        _reset()


# ── governed pipeline: a hit is served without calling any backend ────────
def test_pipeline_cache_hit_served_without_backend():
    _reset()
    features.set_config(AUTO, {"cache_enabled": True})
    try:
        kw = {"temperature": 0, "max_tokens": 50, "top_p": None}
        msgs = [{"role": "user", "content": "unique cache probe 42"}]
        resp = {"choices": [{"message": {"role": "assistant", "content": "cached answer"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2}}
        cache.store("auto", msgs, kw, "", AUTO, resp, 5, 2, "ollama", "llama3.2:3b")
        r = client.post("/v1/chat/completions", headers=ADMIN, json={
            "model": "auto", "messages": msgs, "temperature": 0, "max_tokens": 50})
        assert r.status_code == 200
        body = r.json()
        assert body["choices"][0]["message"]["content"] == "cached answer"
        assert body["precepta"]["cache"] == "hit" and body["precepta"]["tokens_saved"] == 7
    finally:
        _reset()


def test_pipeline_no_cache_when_endpoint_off():
    _reset()
    kw = {"temperature": 0, "max_tokens": 50, "top_p": None}
    msgs = [{"role": "user", "content": "disabled cache probe"}]
    features.set_config(AUTO, {"cache_enabled": True})
    cache.store("auto", msgs, kw, "", AUTO, {"choices": [], "usage": {}}, 0, 0, "ollama", "m")
    features.set_config(AUTO, {"cache_enabled": False})     # now off for this endpoint
    try:
        assert cache.lookup("auto", msgs, kw, "", AUTO) is not None   # entry still there
        assert cache.is_cacheable(kw, False, AUTO) is False           # but gating says no
    finally:
        _reset()


# ── per-endpoint config + stats endpoints are admin-only ──────────────────
def test_features_endpoint_admin_only():
    assert client.get("/v1/features", headers={"Authorization": "Bearer dev-user"}).status_code == 403
    r = client.get("/v1/features", headers=ADMIN)
    assert r.status_code == 200
    eps = {e["endpoint"] for e in r.json()["endpoints"]}
    assert "auto" in eps                                    # the router row is always present


def test_put_features_roundtrip():
    _reset()
    try:
        r = client.put("/v1/features/ollama", headers=ADMIN,
                       json={"cache_enabled": True, "cache_strategy": "semantic",
                             "cache_threshold": 0.9})
        assert r.status_code == 200
        cfg = r.json()
        assert cfg["cache_enabled"] is True and cfg["cache_strategy"] == "semantic"
        assert features.cache_on("ollama") is True and features.cache_threshold("ollama") == 0.9
    finally:
        _reset()
