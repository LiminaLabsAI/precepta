"""In-boundary model + provider catalog (Phase 15).

Mirrors LiteLLM's Model Catalog (models.litellm.ai) — a browsable catalog of
models with mode, context window, per-token cost, and capability flags — but
served **entirely in-boundary**: the data is a vendored snapshot
(`app/data/model_prices_litellm.json`, MIT-licensed reference data from
BerriAI/litellm), normalised at load; no external call at runtime. Falls back to
the small curated `model_catalog.json` if the snapshot is absent.

Also provides the provider-TYPE registry (what you need to connect each provider
Precepta can integrate) and a best-effort `catalog_lookup` used to enrich a live
endpoint's model — honest `None` when unmatched.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

_DIR = os.path.join(os.path.dirname(__file__), "data")
_LITELLM_PATH = os.path.join(_DIR, "model_prices_litellm.json")
_CURATED_PATH = os.path.join(_DIR, "model_catalog.json")

# Provider TYPES Precepta can *connect* (distinct from the browsable catalog's
# 100+ providers): the fields needed to register an inference endpoint.
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

_CAP_FLAGS = ("supports_function_calling", "supports_vision", "supports_reasoning",
              "supports_prompt_caching", "supports_audio_input", "supports_web_search",
              "supports_pdf_input", "supports_response_schema")


def _per_1m(per_token) -> float | None:
    try:
        return round(float(per_token) * 1_000_000, 4) if per_token is not None else None
    except (TypeError, ValueError):
        return None


def _normalize(model_id: str, raw: dict) -> dict:
    entry = {
        "id": model_id,
        "provider": raw.get("litellm_provider") or "unknown",
        "mode": raw.get("mode") or "chat",
        "max_input_tokens": raw.get("max_input_tokens") or raw.get("max_tokens"),
        "max_output_tokens": raw.get("max_output_tokens"),
        "input_cost_per_token": raw.get("input_cost_per_token"),
        "output_cost_per_token": raw.get("output_cost_per_token"),
        "input_cost_per_1m": _per_1m(raw.get("input_cost_per_token")),
        "output_cost_per_1m": _per_1m(raw.get("output_cost_per_token")),
        "deprecation_date": raw.get("deprecation_date"),
    }
    for flag in _CAP_FLAGS:
        entry[flag] = bool(raw.get(flag)) if raw.get(flag) is not None else False
    # convenience nested view (used by /v1/models enrichment + the Console)
    entry["capabilities"] = {
        "streaming": True if entry["mode"] == "chat" else False,
        "function_calling": entry["supports_function_calling"],
        "vision": entry["supports_vision"],
        "reasoning": entry["supports_reasoning"],
    }
    return entry


def _load_litellm() -> list[dict]:
    try:
        with open(_LITELLM_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        return [_normalize(k, v) for k, v in raw.items()
                if k != "sample_spec" and isinstance(v, dict)]
    except (OSError, ValueError):
        return []


def _load_curated() -> list[dict]:
    """Precepta's own curated entries — carry the exact ids of our in-boundary
    live models (e.g. `llama3.2:3b`, `nomic-embed-text`) that the broad LiteLLM
    snapshot keys differently, so live-endpoint enrichment stays exact."""
    try:
        with open(_CURATED_PATH, encoding="utf-8") as f:
            models = json.load(f).get("models", [])
    except (OSError, ValueError):
        return []
    out = []
    for m in models:
        caps = m.get("capabilities") or {}
        out.append(_normalize(m["id"], {
            "litellm_provider": m.get("provider"),
            "mode": m.get("mode", "chat"),
            "max_input_tokens": m.get("max_input_tokens"),
            "max_output_tokens": m.get("max_output_tokens"),
            "input_cost_per_token": (m.get("input_cost_per_1m") or 0) / 1e6 if m.get("input_cost_per_1m") is not None else None,
            "output_cost_per_token": (m.get("output_cost_per_1m") or 0) / 1e6 if m.get("output_cost_per_1m") is not None else None,
            "supports_function_calling": caps.get("function_calling"),
            "supports_vision": caps.get("vision"),
        }))
    return out


@lru_cache
def _all() -> list[dict]:
    by_id: dict[str, dict] = {}
    for m in _load_litellm():                 # base: the broad LiteLLM snapshot
        by_id[m["id"]] = m
    for m in _load_curated():                 # overlay: Precepta ids not already present
        by_id.setdefault(m["id"], m)
    return list(by_id.values())


def _basename(model: str) -> str:
    return (model or "").split("/")[-1].strip().lower()


def query_models(*, provider: str | None = None, mode: str | None = None,
                 model: str | None = None, supports_vision: bool | None = None,
                 supports_function_calling: bool | None = None,
                 supports_reasoning: bool | None = None,
                 page: int = 1, page_size: int = 100) -> dict:
    """LiteLLM-style filter + paginate. Returns {data,total_count,has_more,page,page_size}."""
    items = _all()
    if provider:
        items = [m for m in items if m["provider"] == provider]
    if mode:
        items = [m for m in items if m["mode"] == mode]
    if model:
        q = model.strip().lower()
        items = [m for m in items if q in m["id"].lower()]
    if supports_vision is not None:
        items = [m for m in items if m["supports_vision"] == supports_vision]
    if supports_function_calling is not None:
        items = [m for m in items if m["supports_function_calling"] == supports_function_calling]
    if supports_reasoning is not None:
        items = [m for m in items if m["supports_reasoning"] == supports_reasoning]
    items = sorted(items, key=lambda m: (m["provider"], m["id"]))
    total = len(items)
    page = max(1, int(page or 1))
    page_size = max(1, min(500, int(page_size or 100)))
    start = (page - 1) * page_size
    return {"data": items[start:start + page_size], "total_count": total,
            "has_more": start + page_size < total, "page": page, "page_size": page_size}


def get_model(model_id: str) -> dict | None:
    for m in _all():
        if m["id"] == model_id:
            return m
    return None


def list_models(provider: str | None = None, mode: str | None = None) -> list[dict]:
    """Simple unpaginated listing (used internally)."""
    return query_models(provider=provider, mode=mode, page=1, page_size=500)["data"]


def catalog_providers() -> list[dict]:
    """Distinct providers in the browsable catalog, with model counts (for the UI filter)."""
    counts: dict[str, int] = {}
    for m in _all():
        counts[m["provider"]] = counts.get(m["provider"], 0) + 1
    return [{"provider": p, "model_count": c}
            for p, c in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]


# ── connect-config provider TYPES (distinct from the browsable catalog) ─────
def list_providers() -> list[dict]:
    return list(PROVIDER_TYPES)


def get_provider(provider: str) -> dict | None:
    for p in PROVIDER_TYPES:
        if p["provider"] == provider:
            return {**p, "models": list_models(provider=provider)}
    return None


def catalog_lookup(provider_type: str | None, model: str) -> dict | None:
    """Best-effort match for a live endpoint's model. Exact id, then basename;
    provider is a tiebreak. Honest None when nothing matches."""
    if not model:
        return None
    models = _all()
    target = model.strip().lower()
    tb = _basename(model)
    untagged = tb.split(":")[0]               # ollama-style "llama3.2:3b" → "llama3.2"
    exact = [m for m in models if m["id"].lower() == target]
    if exact:
        same = [m for m in exact if provider_type and m["provider"] == provider_type]
        return same[0] if same else exact[0]
    for cand in (tb, untagged):               # basename, then tag-stripped basename
        base = [m for m in models if _basename(m["id"]) == cand]
        if base:
            same = [m for m in base if provider_type and m["provider"] == provider_type]
            return same[0] if same else base[0]
    return None
