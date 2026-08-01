"""Precepta's proprietary router model (.env HF) vs the customer's Model Plane
backends — they must not be conflated. The .env HF feeds the router only; it is
never a customer inference backend."""
from __future__ import annotations

import app.adapters.model.store as store
from app.adapters.model.registry import build_registry
from app.router import intent
from app.db import get_conn


def _clear_router_config():
    with get_conn() as c:
        c.execute("CREATE TABLE IF NOT EXISTS router_config (key TEXT PRIMARY KEY, value TEXT)")
        c.execute("DELETE FROM router_config")


def test_env_hf_is_not_a_customer_backend(monkeypatch):
    monkeypatch.setenv("HF_BASE_URL", "https://precepta-router.internal/v1")
    monkeypatch.setenv("HF_DEFAULT_MODEL", "precepta/router-model")
    monkeypatch.setenv("HF_API_KEY", "k")
    monkeypatch.setattr(store, "load_backends", lambda: [])      # no customer backends registered
    reg = build_registry()
    assert "hf" not in reg                                        # .env HF is NOT in the customer registry
    assert "ollama" in reg                                        # local dev backend still present


def test_router_model_uses_env_hf(monkeypatch):
    _clear_router_config()
    monkeypatch.setenv("HF_BASE_URL", "https://precepta-router.internal/v1")
    monkeypatch.setenv("HF_DEFAULT_MODEL", "precepta/router-model")
    monkeypatch.setenv("HF_API_KEY", "k")
    base, model, key = intent._target()                          # the router's own model
    assert base == "https://precepta-router.internal/v1"
    assert model == "precepta/router-model" and key == "k"


def test_router_model_falls_back_to_ollama(monkeypatch):
    _clear_router_config()
    monkeypatch.delenv("HF_BASE_URL", raising=False)
    monkeypatch.delenv("HF_DEFAULT_MODEL", raising=False)
    base, model, key = intent._target()
    assert "127.0.0.1" in base and key is None                   # in-boundary local Ollama
