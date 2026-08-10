"""Intent catalog (Phase 12) — the open list of what a caller can want.

Stage 1 of the smart router classifies a request into an **intent** (cheapest,
smartest, accuracy, …). Stage 2 (``scoring.resolve``) maps that intent to a
target using the **weights** defined here. The router core never hard-codes
intents: adding one is a single ``register(Intent(...))`` entry, never a change
to the resolver.

Distinct from ``app/router/intent.py`` (plural vs singular): that module is the
in-boundary model that *guesses* the intent; this module is the catalog of
intents and their scoring weights. Weights are non-negative; higher weight =
that factor matters more for this intent.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Intent:
    key: str
    label: str
    description: str
    w_quality: float
    w_cost: float
    w_latency: float
    w_warm: float = 0.1


_REGISTRY: dict[str, Intent] = {}

# The intent the resolver falls back to for an unknown/empty intent.
DEFAULT = "balanced"


def register(intent: Intent) -> None:
    """Add or replace an intent. New intent = one call — no core change."""
    _REGISTRY[intent.key] = intent


def _norm_key(key: str | None) -> str:
    return (key or "").strip().lower()


def get(key: str | None) -> Intent | None:
    return _REGISTRY.get(_norm_key(key))


def is_known(key: str | None) -> bool:
    return get(key) is not None


def keys() -> list[str]:
    return sorted(_REGISTRY.keys())


def known() -> list[Intent]:
    return [_REGISTRY[k] for k in keys()]


def weights_for(key: str | None) -> Intent:
    """The intent to score by — the requested one, else the DEFAULT.

    Always returns an Intent (never None), so the resolver is total.
    """
    return get(key) or _REGISTRY[DEFAULT]


# ── seed the built-in intents (each is a single registry entry) ──────────────
for _it in (
    Intent("cheapest", "Cheapest", "Lowest cost that can still do the job",
           w_quality=0.30, w_cost=1.00, w_latency=0.20),
    Intent("fastest", "Fastest", "Lowest latency, cost secondary",
           w_quality=0.30, w_cost=0.20, w_latency=1.00),
    Intent("smartest", "Smartest", "Best quality regardless of cost",
           w_quality=1.00, w_cost=0.02, w_latency=0.02),
    Intent("accuracy", "Most accurate", "Highest quality — used when a weak "
           "intent guess is caught by the confidence floor",
           w_quality=1.00, w_cost=0.02, w_latency=0.02),
    Intent("balanced", "Balanced", "Sensible trade-off across quality, cost, latency",
           w_quality=0.60, w_cost=0.50, w_latency=0.40),
):
    register(_it)
