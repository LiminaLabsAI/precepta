"""In-boundary model + provider catalog (Phase 15).

Ships a curated `app/data/model_catalog.json` (no runtime external call). Provides
the provider-type registry (what you need to connect each provider), the model
catalog listing, and a best-effort `catalog_lookup` used to enrich a live
endpoint's model with capabilities/context — honest `None` when unmatched.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

_CATALOG_PATH = os.path.join(os.path.dirname(__file__), "data", "model_catalog.json")

# Provider TYPES Precepta can integrate + the fields needed to connect each.
# Boundary is the default posture; a specific endpoint can still be marked
# in/out of boundary at registration.
PROVIDER_TYPES: list[dict] = [
    {"provider": "ollama", "name": "Ollama", "boundary": "in-boundary",
     "requires_egress_approval": False,
     "config_schema": [
         {"field": "base_url", "label": "Endpoint URL", "required": True, "example": "http://ollama:11434/v1"},
         {"field": "model", "label": "Model", "required": True, "example": "llama3.2:3b"}]},
    {"provider": "vllm", "name": "vLLM cluster", "boundary": "in-boundary",
     "requires_egress_approval": False,
     "config_schema": [
         {"field": "base_url", "label": "Endpoint URL", "required": True, "example": "http://vllm:8000/v1"},
         {"field": "api_key", "label": "API key", "required": False, "secret": True},
         {"field": "model", "label": "Model", "required": True, "example": "mistral-large-2411"}]},
    {"provider": "neysa", "name": "Neysa", "boundary": "in-boundary (sovereign cloud)",
     "requires_egress_approval": True,
     "config_schema": [
         {"field": "base_url", "label": "Endpoint URL", "required": True},
         {"field": "api_key", "label": "API key", "required": True, "secret": True},
         {"field": "model", "label": "Model", "required": True, "example": "qwen2-72b"}]},
    {"provider": "hf", "name": "Hugging Face endpoint", "boundary": "cloud",
     "requires_egress_approval": True,
     "config_schema": [
         {"field": "base_url", "label": "Endpoint URL", "required": True, "example": "https://router.huggingface.co/v1"},
         {"field": "api_key", "label": "API key", "required": True, "secret": True},
         {"field": "model", "label": "Model", "required": True}]},
    {"provider": "openai-compatible", "name": "OpenAI-compatible endpoint", "boundary": "cloud",
     "requires_egress_approval": True,
     "config_schema": [
         {"field": "base_url", "label": "Endpoint URL", "required": True, "example": "https://api.example.com/v1"},
         {"field": "api_key", "label": "API key", "required": True, "secret": True},
         {"field": "model", "label": "Model", "required": True}]},
]

_PROVIDER_IDS = {p["provider"] for p in PROVIDER_TYPES}


@lru_cache
def _load() -> list[dict]:
    try:
        with open(_CATALOG_PATH, encoding="utf-8") as f:
            return json.load(f).get("models", [])
    except (OSError, ValueError):
        return []


def _basename(model: str) -> str:
    return (model or "").split("/")[-1].strip().lower()


def list_models(provider: str | None = None, mode: str | None = None) -> list[dict]:
    out = _load()
    if provider:
        out = [m for m in out if m.get("provider") == provider]
    if mode:
        out = [m for m in out if m.get("mode") == mode]
    return out


def list_providers() -> list[dict]:
    return list(PROVIDER_TYPES)


def get_provider(provider: str) -> dict | None:
    for p in PROVIDER_TYPES:
        if p["provider"] == provider:
            return {**p, "models": list_models(provider=provider)}
    return None


def catalog_lookup(provider_type: str | None, model: str) -> dict | None:
    """Best-effort catalog match for a live endpoint's model. Matches on the
    model id (exact, then basename); provider is only a tiebreaker. Honest None
    when nothing matches — callers surface 'unknown' rather than a guess."""
    if not model:
        return None
    models = _load()
    target = model.strip().lower()
    tb = _basename(model)
    # 1) exact id, preferring same provider family
    exact = [m for m in models if m.get("id", "").lower() == target]
    if exact:
        same = [m for m in exact if provider_type and m.get("provider") in (provider_type,)]
        return same[0] if same else exact[0]
    # 2) basename match (e.g. "hf-llama/…/Llama-3.1-8B-Instruct" ~ catalog id basename)
    base = [m for m in models if _basename(m.get("id", "")) == tb]
    if base:
        same = [m for m in base if provider_type and m.get("provider") in (provider_type,)]
        return same[0] if same else base[0]
    return None
