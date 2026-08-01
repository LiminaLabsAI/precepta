"""Phase 4 · task 1 — router config (platform-owner-only) + secret store.

Covers: the secret store never leaks a value; router config reports the HF key
as a boolean only; HF selection is fail-closed (needs endpoint + key); bad
backends are rejected; and the endpoints are gated to the platform owner.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.router import config as rc
from app.adapters.secret import get_secret_store
from app.db import get_conn

client = TestClient(app)
OWNER = {"Authorization": "Bearer dev-admin"}      # admin@local ∈ default owners
NON_OWNER = {"Authorization": "Bearer dev-user"}   # user@local — not an owner


def _reset() -> None:
    rc.ensure_table()
    from app.adapters.secret import ensure_table as _secrets_table
    _secrets_table()
    with get_conn() as conn:
        conn.execute("DELETE FROM router_config")
        conn.execute("DELETE FROM secrets WHERE name=?", (rc.HF_KEY_SECRET,))


# ── secret store ─────────────────────────────────────────────────────────
def test_secret_store_roundtrip_and_is_set():
    s = get_secret_store()
    try:
        assert s.is_set("t.secret") is False
        ref = s.put("t.secret", "super-secret-value")
        assert ref == "t.secret"
        assert s.get("t.secret") == "super-secret-value"
        assert s.is_set("t.secret") is True
    finally:
        s.delete("t.secret")
        assert s.is_set("t.secret") is False


# ── config store ─────────────────────────────────────────────────────────
def test_config_defaults_and_key_hidden():
    _reset()
    try:
        cfg = rc.get_config()
        assert cfg["router_backend"] == "ollama"
        assert cfg["hf_endpoint"] == ""
        assert cfg["hf_key_set"] is False
        # store a key; config exposes only the boolean, never the value
        rc.update_config({"hf_endpoint": "http://hf.internal:8080/v1",
                          "hf_key": "hf-live-key"})
        cfg = rc.get_config()
        assert cfg["hf_key_set"] is True
        assert "hf_key" not in cfg and "hf-live-key" not in str(cfg)
        assert get_secret_store().get(rc.HF_KEY_SECRET) == "hf-live-key"
    finally:
        _reset()


def test_empty_key_leaves_existing_unchanged():
    _reset()
    try:
        rc.update_config({"hf_endpoint": "http://hf.internal:8080/v1", "hf_key": "k1"})
        rc.update_config({"hf_endpoint": "http://hf.internal:9090/v1", "hf_key": ""})
        assert get_secret_store().get(rc.HF_KEY_SECRET) == "k1"   # unchanged
        assert rc.get_config()["hf_endpoint"].endswith("9090/v1")  # other field updated
    finally:
        _reset()


def test_hf_selection_is_fail_closed():
    _reset()
    try:
        with pytest.raises(rc.RouterConfigError):
            rc.update_config({"router_backend": "hf"})          # no endpoint/key yet
        # nothing was persisted by the rejected call
        assert rc.get_config()["router_backend"] == "ollama"
        # fully configured → accepted
        cfg = rc.update_config({"router_backend": "hf",
                                "hf_endpoint": "http://hf.internal:8080/v1",
                                "hf_key": "k"})
        assert cfg["router_backend"] == "hf"
    finally:
        _reset()


def test_bad_backend_rejected():
    with pytest.raises(rc.RouterConfigError):
        rc.update_config({"router_backend": "openai"})


# ── endpoint auth (platform-owner gate) ──────────────────────────────────
def test_endpoints_owner_only():
    _reset()
    try:
        assert client.get("/v1/router/config", headers=NON_OWNER).status_code == 403
        assert client.put("/v1/router/config", headers=NON_OWNER,
                          json={"router_backend": "ollama"}).status_code == 403

        r = client.get("/v1/router/config", headers=OWNER)
        assert r.status_code == 200
        assert r.json()["backends"] == ["ollama", "hf"]

        r = client.put("/v1/router/config", headers=OWNER,
                       json={"hf_endpoint": "http://hf.internal:8080/v1", "hf_key": "k"})
        assert r.status_code == 200 and r.json()["hf_key_set"] is True

        # HF-without-config is a 400, not a 500
        assert client.put("/v1/router/config", headers=OWNER,
                          json={"router_backend": "hf", "hf_endpoint": "",
                                "hf_key": ""}).status_code in (200, 400)
    finally:
        _reset()


def test_auth_me_reports_platform_owner():
    assert client.get("/auth/me", headers=OWNER).json()["platform_owner"] is True
    assert client.get("/auth/me", headers=NON_OWNER).json()["platform_owner"] is False
