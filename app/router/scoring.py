"""Router scoring resolver (Phase 12, stage 2) — intent → target.

Pure, deterministic, dependency-free: given an intent and a list of candidate
targets (each with quality / cost / latency / warm-cache flag), pick the best
one by ``w_quality·quality − w_cost·cost − w_latency·latency + w_warm·warm``,
with cost and latency **normalised across the candidates** so absolute scales
don't dominate. Returns a ``RouteDecision`` carrying the chosen target, the
plain reason, and the full **scored candidate set** — the exact data the Traces
"Route" tab shows ("what else was considered and how it scored").

Two honesty guards live here:
  * ``apply_confidence_floor`` — a weak intent guess is discarded and treated as
    the hard/``accuracy`` intent, so a hard question never rides a lucky match.
  * a "no allowed target" result when policy/sovereignty removes every
    candidate — the router blocks rather than inventing a route.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import intent_catalog as _intents

CONFIDENCE_FLOOR = 0.5
HARD_INTENT = "accuracy"


@dataclass
class ScoredTarget:
    target: str
    score: float
    quality: float
    cost: float
    latency: float
    warm: bool
    chosen: bool = False


@dataclass
class RouteDecision:
    target: str | None
    intent: str
    reason: str
    confidence: float | None = None
    inferred: bool = False
    considered: list[ScoredTarget] = field(default_factory=list)


def apply_confidence_floor(intent: str, confidence: float | None,
                           floor: float = CONFIDENCE_FLOOR) -> tuple[str, bool, str]:
    """If the intent guess is weak, treat the request as hard.

    Returns ``(intent, bumped, reason)``. A ``None`` confidence (e.g. an
    explicit intent, not a guess) is never floored.
    """
    if confidence is not None and confidence < floor:
        return (HARD_INTENT, True,
                f"low confidence ({confidence:.2f} < {floor:.2f}) — treated as "
                f"'{HARD_INTENT}' rather than trusting a weak guess")
    return (intent, False, "")


def _normalise(values: list[float]) -> list[float]:
    """Min-max to [0,1]; all-equal (or single) → all 0 (no penalty)."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi <= lo:
        return [0.0] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def resolve(intent: str, candidates: list[dict], *,
            forbidden: set[str] | None = None,
            confidence: float | None = None,
            inferred: bool = False) -> RouteDecision:
    """Pick the best target for ``intent`` from ``candidates``.

    Each candidate is a dict: ``{target, quality, cost, latency, warm}``.
    ``forbidden`` targets (policy/sovereignty) are removed first.
    """
    forbidden = forbidden or set()
    surv = [c for c in candidates if c.get("target") not in forbidden]
    if not surv:
        return RouteDecision(
            None, intent,
            "No allowed target — every candidate is blocked by policy or the "
            "sovereignty boundary.", confidence, inferred, [])

    w = _intents.weights_for(intent)
    costs = _normalise([float(c.get("cost", 0) or 0) for c in surv])
    lats = _normalise([float(c.get("latency", 0) or 0) for c in surv])

    scored: list[ScoredTarget] = []
    for c, cn, ln in zip(surv, costs, lats):
        q = float(c.get("quality", 0) or 0)
        warm = 1.0 if c.get("warm") else 0.0
        s = w.w_quality * q - w.w_cost * cn - w.w_latency * ln + w.w_warm * warm
        scored.append(ScoredTarget(
            target=c.get("target"), score=round(s, 4), quality=q,
            cost=float(c.get("cost", 0) or 0), latency=float(c.get("latency", 0) or 0),
            warm=bool(c.get("warm"))))

    # Deterministic ordering: score desc, then quality desc, then target name asc.
    scored.sort(key=lambda t: (-t.score, -t.quality, str(t.target)))
    best = scored[0]
    best.chosen = True

    label = (_intents.get(intent).label.lower() if _intents.is_known(intent)
             else str(intent))
    if len(scored) > 1:
        reason = (f"intent '{intent}' → {best.target}: best {label} score "
                  f"{best.score} of {len(scored)} candidates"
                  + (" (warm cache tipped it)" if best.warm else "") + ".")
    else:
        reason = f"intent '{intent}' → {best.target}: only eligible candidate."
    return RouteDecision(best.target, intent, reason, confidence, inferred, scored)
