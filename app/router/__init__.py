"""Router (Layer 2).

Phase 1: explicit routing only — resolve a `provider/model` string to a
concrete backend. `auto:` intent modes, cost/latency selection and failover
arrive in Phase 2.
"""
from __future__ import annotations

from ..adapters.model.openai_compat import OpenAICompatBackend


class RouteError(Exception):
    """Raised when a model string cannot be resolved to a backend."""


# intent routing (Phase 2)
_INTENTS = {"cheapest", "fastest", "best-quality", "automatic"}


def is_auto(model_str: str) -> bool:
    return bool(model_str) and (model_str == "auto" or model_str.startswith("auto:"))


def parse_intent(model_str: str) -> str:
    """`auto` → automatic; `auto:cheapest|fastest|best-quality|automatic` → that intent."""
    if model_str == "auto":
        return "automatic"
    suffix = model_str.split(":", 1)[1] if ":" in model_str else "automatic"
    return suffix if suffix in _INTENTS else "automatic"


def resolve(model_str: str, registry: dict[str, OpenAICompatBackend]):
    """Resolve explicit `"provider/model"` → (backend, model_name).

    `auto:*` is handled by the brain/engine, not here.
    """
    if is_auto(model_str):
        raise RouteError(f"{model_str!r} is an intent — route via the brain, not resolve()")
    if not model_str or "/" not in model_str:
        raise RouteError(f"model must be 'provider/model', got {model_str!r}")
    provider, model = model_str.split("/", 1)
    backend = registry.get(provider)
    if backend is None:
        available = ", ".join(sorted(registry)) or "(none)"
        raise RouteError(f"unknown backend {provider!r}; available: {available}")
    return backend, model
