"""Phase 12 — Smart Router · Group 0 unit tests.

Pure, deterministic tests for the intent catalog and the scoring resolver,
including edge cases (empty/forbidden candidates, ties, missing fields,
confidence floor boundaries, normalisation when all values are equal).
"""
from __future__ import annotations

import pytest

from app.router import intent_catalog as cat
from app.router import scoring


# ── intent catalog ───────────────────────────────────────────────────────────

def test_builtin_intents_present():
    for k in ("cheapest", "fastest", "smartest", "accuracy", "balanced"):
        assert cat.is_known(k), f"missing built-in intent {k}"
    assert cat.DEFAULT == "balanced"
    assert set(("cheapest", "balanced")).issubset(set(cat.keys()))


def test_get_is_case_insensitive_and_trims():
    assert cat.get("  CHEAPEST ").key == "cheapest"
    assert cat.get("Smartest").key == "smartest"


def test_unknown_intent_is_none():
    assert cat.get("nonsense") is None
    assert cat.get("") is None
    assert cat.get(None) is None
    assert cat.is_known("nonsense") is False


def test_weights_for_falls_back_to_default():
    assert cat.weights_for("nonsense").key == cat.DEFAULT
    assert cat.weights_for(None).key == cat.DEFAULT
    assert cat.weights_for("cheapest").key == "cheapest"


def test_register_adds_new_intent_without_core_change():
    cat.register(cat.Intent("greenest", "Greenest", "Lowest carbon",
                            w_quality=0.4, w_cost=0.3, w_latency=0.3))
    try:
        assert cat.is_known("greenest")
        assert cat.weights_for("greenest").label == "Greenest"
    finally:
        cat._REGISTRY.pop("greenest", None)   # keep the catalog clean for other tests


# ── confidence floor ─────────────────────────────────────────────────────────

def test_confidence_floor_bumps_weak_guess_to_accuracy():
    intent, bumped, reason = scoring.apply_confidence_floor("cheapest", 0.30)
    assert intent == "accuracy" and bumped is True and "low confidence" in reason


def test_confidence_floor_keeps_confident_guess():
    intent, bumped, _ = scoring.apply_confidence_floor("cheapest", 0.80)
    assert intent == "cheapest" and bumped is False


def test_confidence_floor_boundary_is_not_bumped():
    # exactly at the floor is NOT below it → kept
    intent, bumped, _ = scoring.apply_confidence_floor("cheapest", scoring.CONFIDENCE_FLOOR)
    assert intent == "cheapest" and bumped is False


def test_confidence_floor_ignores_none_confidence():
    intent, bumped, _ = scoring.apply_confidence_floor("cheapest", None)
    assert intent == "cheapest" and bumped is False


def test_confidence_floor_custom_threshold():
    intent, bumped, _ = scoring.apply_confidence_floor("fastest", 0.7, floor=0.9)
    assert intent == "accuracy" and bumped is True


# ── resolver: intent → target ────────────────────────────────────────────────

def _cands():
    return [
        {"target": "haiku", "quality": 0.80, "cost": 0.004, "latency": 300},
        {"target": "sonnet", "quality": 0.93, "cost": 0.021, "latency": 900},
        {"target": "mini", "quality": 0.72, "cost": 0.003, "latency": 250},
    ]


def test_cheapest_picks_lowest_cost():
    d = scoring.resolve("cheapest", _cands())
    assert d.target == "mini"          # lowest cost
    assert d.intent == "cheapest"


def test_smartest_picks_highest_quality():
    d = scoring.resolve("smartest", _cands())
    assert d.target == "sonnet"        # highest quality


def test_fastest_picks_lowest_latency():
    d = scoring.resolve("fastest", _cands())
    assert d.target == "mini"          # lowest latency (250)


def test_warm_cache_bonus_breaks_a_tie():
    cands = [
        {"target": "cold", "quality": 0.5, "cost": 5, "latency": 50, "warm": False},
        {"target": "warm", "quality": 0.5, "cost": 5, "latency": 50, "warm": True},
    ]
    d = scoring.resolve("balanced", cands)
    assert d.target == "warm"          # identical except warm → warm wins
    assert "warm cache tipped it" in d.reason


def test_forbidden_target_is_excluded():
    d = scoring.resolve("smartest", _cands(), forbidden={"sonnet"})
    assert d.target == "haiku"         # sonnet removed → next-best quality


def test_all_candidates_forbidden_yields_no_target():
    d = scoring.resolve("smartest", _cands(), forbidden={"haiku", "sonnet", "mini"})
    assert d.target is None
    assert "No allowed target" in d.reason


def test_empty_candidates_yields_no_target():
    d = scoring.resolve("cheapest", [])
    assert d.target is None and d.considered == []


def test_single_candidate_is_chosen():
    d = scoring.resolve("cheapest", [{"target": "solo", "quality": 0.1, "cost": 9, "latency": 9}])
    assert d.target == "solo" and "only eligible candidate" in d.reason


def test_considered_set_has_exactly_one_chosen():
    d = scoring.resolve("smartest", _cands())
    chosen = [c for c in d.considered if c.chosen]
    assert len(chosen) == 1 and chosen[0].target == d.target
    assert len(d.considered) == 3      # full scored candidate set returned


def test_resolver_is_deterministic():
    a = scoring.resolve("balanced", _cands())
    b = scoring.resolve("balanced", _cands())
    assert a.target == b.target
    assert [c.score for c in a.considered] == [c.score for c in b.considered]


def test_equal_costs_do_not_dominate():
    # all same cost/latency → smartest still tracks quality, no divide-by-zero
    cands = [
        {"target": "a", "quality": 0.6, "cost": 5, "latency": 100},
        {"target": "b", "quality": 0.9, "cost": 5, "latency": 100},
    ]
    d = scoring.resolve("smartest", cands)
    assert d.target == "b"


def test_missing_fields_default_to_zero():
    # a candidate with only a target must not crash; missing quality/cost/latency → 0.
    # (Which one wins depends on weights; the invariant is: no exception, valid target,
    #  deterministic, and every candidate scored.)
    cands = [{"target": "bare"}, {"target": "full", "quality": 0.9, "cost": 1, "latency": 1}]
    d = scoring.resolve("balanced", cands)
    assert d.target in ("bare", "full")
    assert len(d.considered) == 2
    assert scoring.resolve("balanced", cands).target == d.target   # deterministic


def test_smartest_prefers_quality_even_when_pricier():
    # explicit guard on the weight tuning: "regardless of cost" must actually hold.
    d = scoring.resolve("smartest", _cands())
    assert d.target == "sonnet"           # highest quality despite highest cost/latency


def test_unknown_intent_uses_default_weights_and_still_routes():
    d = scoring.resolve("teleport", _cands())
    assert d.target is not None           # total function — always resolves
    assert d.intent == "teleport"


def test_confidence_and_inferred_pass_through():
    d = scoring.resolve("cheapest", _cands(), confidence=0.62, inferred=True)
    assert d.confidence == 0.62 and d.inferred is True
