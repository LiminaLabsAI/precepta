"""Router brain (RouterBrainPort) — decides (backend × technique) for auto/intent.

Adapters (DIP): `rules` is the working V1 default. `classifier`
(optillm-modernbert, self-hosted) is the intended default but needs a model
download, so it is deferred — the stub falls back to rules and says so.
"""
from __future__ import annotations

from ..ports import RoutePlan, PolicyCheckContext
from ..pricing import price_of
from ..settings import get_settings
from .state import latency


# ── candidate selection ─────────────────────────────────────────────────
def candidates(registry: dict, sovereign: bool) -> list[tuple]:
    """[(backend, model)] eligible to serve — in-boundary only under sovereign mode."""
    out = []
    for be in registry.values():
        if sovereign and not be.in_boundary:
            continue
        model = be.default_model or ""
        out.append((be, model))
    return out


def _difficulty(query: str) -> str:
    """Cheap heuristic: long / analytical prompts → hard."""
    q = (query or "").lower()
    hard_words = ("analyze", "prove", "derive", "step by step", "reason", "plan",
                  "restructure", "compare", "evaluate", "explain why")
    if len(query or "") > 400 or any(w in q for w in hard_words):
        return "hard"
    return "easy"


class RulesBrain:
    """Deterministic, explainable routing over cheap signals."""

    name = "rules"

    def __init__(self, registry_getter, settings_getter=get_settings) -> None:
        self._registry_getter = registry_getter
        self._settings_getter = settings_getter

    def decide(self, query: str, intent: str,
               ctx: PolicyCheckContext | None = None,
               budget: dict | None = None) -> RoutePlan:
        reg = self._registry_getter()
        sovereign = self._settings_getter().sovereign_mode
        cands = candidates(reg, sovereign)
        if not cands:
            raise LookupError("no eligible in-boundary backend")

        if intent == "cheapest":
            be, model = min(cands, key=lambda c: price_of(c[0].name, c[1]).input_per_1m)
            return RoutePlan(be.name, model, "passthrough",
                             f"cheapest of {len(cands)} in-boundary backends")

        if intent == "fastest":
            be, model = min(cands, key=lambda c: latency(c[0].name))
            return RoutePlan(be.name, model, "passthrough", "lowest observed latency")

        # automatic / best-quality / auto → difficulty-aware
        diff = _difficulty(query)
        if diff == "hard":
            be, model = max(cands, key=lambda c: c[0].tier)     # strongest tier
            technique = "best_of_n" if intent in ("best-quality", "auto", "automatic") else "passthrough"
            return RoutePlan(be.name, model, technique,
                             f"hard query → tier-{be.tier} backend, {technique}")
        be, model = min(cands, key=lambda c: price_of(c[0].name, c[1]).input_per_1m)
        return RoutePlan(be.name, model, "passthrough", "easy query → cheapest backend")


class ClassifierBrain:
    """Deferred: optillm-modernbert classifier (needs model download).

    Falls back to RulesBrain so the system stays functional; `decide` marks the
    plan reason so callers know it isn't the real classifier yet.
    """

    name = "classifier(stub→rules)"

    def __init__(self, registry_getter, settings_getter=get_settings) -> None:
        self._rules = RulesBrain(registry_getter, settings_getter)

    def decide(self, query, intent, ctx=None, budget=None) -> RoutePlan:
        plan = self._rules.decide(query, intent, ctx, budget)
        return RoutePlan(plan.backend, plan.model, plan.technique,
                         f"[classifier deferred → rules] {plan.reason}")


def get_brain(name: str, registry_getter):
    if name == "classifier":
        return ClassifierBrain(registry_getter)
    return RulesBrain(registry_getter)
