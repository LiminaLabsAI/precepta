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
def candidates(registry: dict, sovereign: bool,
               allowed: set[str] | None = None) -> list[tuple]:
    """[(backend, model)] eligible to serve.

    In-boundary only under sovereign mode; and, when `allowed` is given (the
    governance filter for a sensitive auto request), restricted to that
    approved set — so a sensitive request can never be routed, or fail over,
    to an un-approved backend.
    """
    out = []
    for be in registry.values():
        if sovereign and not be.in_boundary:
            continue
        if allowed is not None and be.name not in allowed:
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


def _pick_cheapest(cands):
    return min(cands, key=lambda c: price_of(c[0].name, c[1]).input_per_1m)


def _pick_fastest(cands):
    return min(cands, key=lambda c: latency(c[0].name))


def _pick_strongest(cands):
    return max(cands, key=lambda c: c[0].tier)


class RulesBrain:
    """Deterministic, explainable routing over cheap signals."""

    name = "rules"

    def __init__(self, registry_getter, settings_getter=get_settings) -> None:
        self._registry_getter = registry_getter
        self._settings_getter = settings_getter

    def _candidates(self, allowed: set[str] | None):
        reg = self._registry_getter()
        sovereign = self._settings_getter().sovereign_mode
        cands = candidates(reg, sovereign, allowed)
        if not cands:
            raise LookupError("no eligible in-boundary backend")
        return cands

    def decide(self, query: str, intent: str,
               ctx: PolicyCheckContext | None = None,
               budget: dict | None = None,
               allowed: set[str] | None = None) -> RoutePlan:
        cands = self._candidates(allowed)

        if intent == "cheapest":
            be, model = _pick_cheapest(cands)
            return RoutePlan(be.name, model, "passthrough",
                             f"cheapest of {len(cands)} in-boundary backends")

        if intent == "fastest":
            be, model = _pick_fastest(cands)
            return RoutePlan(be.name, model, "passthrough", "lowest observed latency")

        # automatic / best-quality / auto → difficulty-aware
        diff = _difficulty(query)
        if diff == "hard":
            be, model = _pick_strongest(cands)
            technique = "best_of_n" if intent in ("best-quality", "auto", "automatic") else "passthrough"
            return RoutePlan(be.name, model, technique,
                             f"hard query → tier-{be.tier} backend, {technique}")
        be, model = _pick_cheapest(cands)
        return RoutePlan(be.name, model, "passthrough", "easy query → cheapest backend")


class LLMBrain:
    """Intent-aware routing (FEAT-007·A) — a small **in-boundary** model reads the
    request's goal (cost/speed/quality) + difficulty, then picks a backend
    balancing cost and speed. Bounded by the governance filter (`allowed`) and
    fail-soft: any classifier error falls back to RulesBrain, so inference never
    breaks. The classification is cached (see `app/router/intent.py`).
    """

    name = "llm-intent"

    def __init__(self, registry_getter, settings_getter=get_settings) -> None:
        self._rules = RulesBrain(registry_getter, settings_getter)

    def decide(self, query: str, intent: str,
               ctx: PolicyCheckContext | None = None,
               budget: dict | None = None,
               allowed: set[str] | None = None) -> RoutePlan:
        # Explicit intents (cheapest/fastest/best-quality) are already precise —
        # only the "automatic" family benefits from inferring the goal.
        if intent not in ("auto", "automatic"):
            return self._rules.decide(query, intent, ctx, budget, allowed)

        from .intent import classify
        cls = classify(query)
        if cls is None:                        # fail-soft → rules
            plan = self._rules.decide(query, intent, ctx, budget, allowed)
            return RoutePlan(plan.backend, plan.model, plan.technique,
                             f"[llm-intent unavailable → rules] {plan.reason}")

        cands = self._rules._candidates(allowed)
        goal, diff = cls["goal"], cls["difficulty"]

        # Balanced cost+speed: quality/hard → strongest tier; speed → fastest;
        # otherwise lean cheapest. Passthrough keeps it balanced (no extra calls).
        if goal == "quality" or diff == "hard":
            be, model = _pick_strongest(cands)
            why = f"goal={goal},difficulty={diff} → strongest tier-{be.tier}"
        elif goal == "speed":
            be, model = _pick_fastest(cands)
            why = f"goal=speed,difficulty={diff} → lowest latency"
        else:
            be, model = _pick_cheapest(cands)
            why = f"goal={goal},difficulty={diff} → cheapest"
        return RoutePlan(be.name, model, "passthrough", f"[llm-intent] {why}")


class ClassifierBrain:
    """Deferred: optillm-modernbert classifier (needs model download).

    Falls back to RulesBrain so the system stays functional; `decide` marks the
    plan reason so callers know it isn't the real classifier yet.
    """

    name = "classifier(stub→rules)"

    def __init__(self, registry_getter, settings_getter=get_settings) -> None:
        self._rules = RulesBrain(registry_getter, settings_getter)

    def decide(self, query, intent, ctx=None, budget=None, allowed=None) -> RoutePlan:
        plan = self._rules.decide(query, intent, ctx, budget, allowed)
        return RoutePlan(plan.backend, plan.model, plan.technique,
                         f"[classifier deferred → rules] {plan.reason}")


class LearnedBrain:
    """Learning loop (FEAT-008) — biases the LLM router toward the backend that
    has earned the best reward for this difficulty bucket (see app/learning.py).
    Falls back to the base plan when there isn't enough evidence, and never
    escapes the governance filter (`allowed`) or the eligible-candidate set.
    """

    name = "learned"

    def __init__(self, registry_getter, settings_getter=get_settings) -> None:
        self._base = LLMBrain(registry_getter, settings_getter)
        self._registry_getter = registry_getter
        self._settings_getter = settings_getter

    def decide(self, query: str, intent: str,
               ctx: PolicyCheckContext | None = None,
               budget: dict | None = None,
               allowed: set[str] | None = None) -> RoutePlan:
        plan = self._base.decide(query, intent, ctx, budget, allowed)
        if intent not in ("auto", "automatic"):
            return plan
        from .. import learning
        diff = _difficulty(query)              # same bucket used when recording traces
        pref = learning.preference(diff, allowed)
        if not pref or pref == plan.backend:
            return plan
        cands = candidates(self._registry_getter(),
                           self._settings_getter().sovereign_mode, allowed)
        match = next(((be, m) for be, m in cands if be.name == pref), None)
        if match is None:                      # learned pick not eligible → keep base
            return plan
        be, model = match
        return RoutePlan(be.name, model, plan.technique,
                         f"[learned] {diff} → {pref} (best historical reward); base: {plan.reason}")


def get_brain(name: str, registry_getter):
    if name == "learned":
        return LearnedBrain(registry_getter)
    if name == "llm":
        return LLMBrain(registry_getter)
    if name == "classifier":
        return ClassifierBrain(registry_getter)
    return RulesBrain(registry_getter)
