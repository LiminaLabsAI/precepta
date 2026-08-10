"""Two-stage smart routing (Phase 12) — intent → scored candidates → target.

This ties Group 0 together without disturbing the existing brains:

  Stage 1  an intent (explicit, or a classifier's guess + confidence)
           → the confidence floor bumps a weak guess to 'accuracy'.
  Stage 2  the eligible in-boundary backends are turned into **scored
           candidates** (quality from tier, cost from pricing, latency from
           observed state, warm from a prefix-cache hook) and handed to
           ``scoring.resolve`` → a ``RouteDecision`` with the full candidate set.

Everything external (pricing, latency, warm) is injected, so the decision is
pure and fully unit-testable. The real inference wiring (engine) happens in a
later group; this module is the decision, not the dispatch.
"""
from __future__ import annotations

import math

from . import scoring
from .scoring import RouteDecision

# tier (1 small / 2 mid / 3 strong) → a quality prior in [0,1]
_TIER_QUALITY = {1: 0.50, 2: 0.75, 3: 0.95}


def _finite(v, default: float = 0.0) -> float:
    """Coerce to a finite float — state.latency() returns inf for unobserved
    backends, which breaks both normalisation (nan) and JSON (inf)."""
    try:
        v = float(v)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def quality_for_tier(tier: int | None) -> float:
    try:
        return _TIER_QUALITY.get(int(tier or 1), 0.50)
    except (TypeError, ValueError):
        return 0.50


def score_candidates(registry: dict, *, allowed=None, sovereign: bool = True,
                     price_fn=None, latency_fn=None, warm_fn=None) -> list[dict]:
    """Turn the eligible backends into scored-candidate dicts for the resolver."""
    from .brain import candidates as _eligible
    if price_fn is None:
        from ..pricing import price_of as _price_of
        price_fn = _price_of
    if latency_fn is None:
        from .state import latency as _latency
        latency_fn = _latency
    if warm_fn is None:
        warm_fn = lambda be, model: False   # no prefix-cache tracking yet (placeholder)

    out: list[dict] = []
    for be, model in _eligible(registry, sovereign, allowed):
        p = price_fn(be.name, model)
        cost = _finite((getattr(p, "input_per_1m", 0.0)
                        + getattr(p, "output_per_1m", 0.0)) / 2.0)
        out.append({
            "target": be.name,
            "model": model,
            "quality": quality_for_tier(getattr(be, "tier", 1)),
            "cost": cost,
            "latency": _finite(latency_fn(be.name)),
            "warm": bool(warm_fn(be.name, model)),
        })
    return out


# map the gateway's raw intent (parse_intent output) to a catalog intent.
_DIRECT_INTENT = {
    "cheapest": "cheapest", "fastest": "fastest", "smartest": "smartest",
    "best-quality": "smartest", "quality": "smartest", "accuracy": "accuracy",
    "balanced": "balanced",
}


def catalog_intent_for(intent_raw: str, difficulty: str = "easy") -> tuple[str, float | None, bool]:
    """Map a raw request intent to a catalog intent.

    Returns ``(intent_key, confidence, inferred)``. An explicit intent maps
    directly (not inferred, no confidence → no floor). ``auto``/unknown is
    *inferred* from the difficulty heuristic (hard → smartest, else cheapest).
    """
    key = (intent_raw or "").strip().lower()
    if key in _DIRECT_INTENT:
        return _DIRECT_INTENT[key], None, False
    inferred = "smartest" if difficulty == "hard" else "cheapest"
    return inferred, None, True


def decide(intent: str, registry: dict, *, allowed=None, sovereign: bool = True,
           confidence: float | None = None, inferred: bool = False,
           price_fn=None, latency_fn=None, warm_fn=None) -> RouteDecision:
    """Full two-stage decision. Returns a ``RouteDecision`` (target may be None
    if policy/sovereignty leaves no eligible candidate)."""
    intent2, bumped, floor_reason = scoring.apply_confidence_floor(intent, confidence)
    cands = score_candidates(registry, allowed=allowed, sovereign=sovereign,
                             price_fn=price_fn, latency_fn=latency_fn, warm_fn=warm_fn)
    d = scoring.resolve(intent2, cands, confidence=confidence,
                        inferred=(inferred or bumped))
    if bumped and floor_reason:
        d.reason = f"{floor_reason}; {d.reason}"
    return d
