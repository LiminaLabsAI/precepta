"""Backend registry — builds the model plane from config/env.

V1 in-boundary backends: Ollama (local, always on), and — when their endpoint
env vars are set — vLLM, Neysa, HF dedicated endpoints. Foreign hosted
providers are intentionally absent (they would break the sovereign thesis);
they can be registered later behind the same port.
"""
from __future__ import annotations

import os
from functools import lru_cache

from ...settings import get_settings
from ...ports import Price
from .openai_compat import OpenAICompatBackend


def build_registry() -> dict[str, OpenAICompatBackend]:
    s = get_settings()
    reg: dict[str, OpenAICompatBackend] = {}

    # Ollama — local, in-boundary, no key, free. Always registered. Tier 1 (small/fast).
    _ollama = os.environ.get(
        "PRECEPTA_OLLAMA_URL", f"http://127.0.0.1:{s.ollama_port}").rstrip("/")
    reg["ollama"] = OpenAICompatBackend(
        "ollama", f"{_ollama}/v1", in_boundary=True,
        default_model=os.environ.get("OLLAMA_DEFAULT_MODEL", "llama3.2:3b"), tier=1,
    )

    # vLLM — your own GPU cluster (OpenAI-compatible server). Tier 3 (strong).
    if os.environ.get("VLLM_BASE_URL"):
        reg["vllm"] = OpenAICompatBackend(
            "vllm", os.environ["VLLM_BASE_URL"], in_boundary=True,
            api_key=os.environ.get("VLLM_API_KEY"),
            default_model=os.environ.get("VLLM_DEFAULT_MODEL", "mistral-large-2411"), tier=3,
        )

    # Neysa — sovereign cloud (in-region). In-boundary for the sovereign wedge. Tier 3.
    if os.environ.get("NEYSA_BASE_URL"):
        reg["neysa"] = OpenAICompatBackend(
            "neysa", os.environ["NEYSA_BASE_URL"], in_boundary=True,
            api_key=os.environ.get("NEYSA_API_KEY"),
            prices={"": Price(0.30, 0.30)},
            default_model=os.environ.get("NEYSA_DEFAULT_MODEL", "qwen2-72b"), tier=3,
        )

    # NOTE: the `.env` HF vars (HF_BASE_URL/HF_API_KEY/HF_DEFAULT_MODEL) are
    # **Precepta's own proprietary router model** (the app's IP), consumed by the
    # router/intent classifier (app/router/intent.py) — NOT a customer inference
    # backend. So they are deliberately NOT registered here; the customer's
    # models come only from the Console (registered_backends) below.

    # Persisted backends registered at runtime (Console/onboarding) — survive restart.
    from .store import load_backends
    try:
        for b in load_backends():
            reg[b["provider"]] = OpenAICompatBackend(
                b["provider"], b["base_url"], in_boundary=bool(b["in_boundary"]),
                api_key=b["api_key"] or None, default_model=b["model"] or "",
                tier=b["tier"] or 1)
    except Exception:  # pragma: no cover - table absent on first ever boot
        pass

    return reg


@lru_cache
def get_registry() -> dict[str, OpenAICompatBackend]:
    return build_registry()
