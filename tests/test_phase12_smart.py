"""Phase 12 — Group 1 · two-stage smart decision tests.

Uses fake backends + injected pricing/latency so the decision is pure and
network-free. Covers intent selection, the confidence floor bumping a weak
guess, sovereignty/allowed filtering, warm bonus, and the no-candidate case.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.router import smart


@dataclass
class FakeBackend:
    name: str
    tier: int
    in_boundary: bool = True
    default_model: str = "m"


@dataclass
class FakePrice:
    input_per_1m: float
    output_per_1m: float


# a small fleet: cheap-small in-boundary, mid in-boundary, strong-pricey in-boundary,
# and one out-of-boundary strong backend.
def _registry():
    return {
        "small": FakeBackend("small", tier=1),
        "mid": FakeBackend("mid", tier=2),
        "strong": FakeBackend("strong", tier=3),
        "external": FakeBackend("external", tier=3, in_boundary=False),
    }


_PRICES = {"small": FakePrice(0.1, 0.1), "mid": FakePrice(0.5, 0.5),
           "strong": FakePrice(3.0, 3.0), "external": FakePrice(2.0, 2.0)}
_LAT = {"small": 250, "mid": 500, "strong": 900, "external": 400}


def _price_fn(be, model):
    return _PRICES.get(be, FakePrice(0, 0))


def _lat_fn(be):
    return _LAT.get(be, 0)


def _decide(intent, **kw):
    return smart.decide(intent, _registry(), sovereign=True,
                        price_fn=_price_fn, latency_fn=_lat_fn, **kw)


def test_quality_for_tier():
    assert smart.quality_for_tier(1) < smart.quality_for_tier(2) < smart.quality_for_tier(3)
    assert smart.quality_for_tier(None) == smart.quality_for_tier(1)
    assert smart.quality_for_tier("bad") == 0.50


def test_score_candidates_shape_and_boundary_filter():
    cands = smart.score_candidates(_registry(), sovereign=True,
                                   price_fn=_price_fn, latency_fn=_lat_fn)
    names = {c["target"] for c in cands}
    assert "external" not in names          # out-of-boundary excluded under sovereign
    assert names == {"small", "mid", "strong"}
    strong = next(c for c in cands if c["target"] == "strong")
    assert strong["quality"] == smart.quality_for_tier(3)
    assert strong["cost"] == 3.0            # (3+3)/2
    assert strong["latency"] == 900


def test_cheapest_picks_lowest_cost():
    d = _decide("cheapest")
    assert d.target == "small"


def test_smartest_picks_strongest():
    d = _decide("smartest")
    assert d.target == "strong"


def test_fastest_picks_lowest_latency():
    d = _decide("fastest")
    assert d.target == "small"              # 250ms


def test_confidence_floor_bumps_weak_cheapest_to_accuracy():
    # a weak 'cheapest' guess must NOT send a hard request to the tiny model
    d = _decide("cheapest", confidence=0.20)
    assert d.intent == "accuracy"           # bumped
    assert d.inferred is True
    assert d.target == "strong"             # accuracy → highest quality
    assert "low confidence" in d.reason


def test_confident_cheapest_stays_cheapest():
    d = _decide("cheapest", confidence=0.90)
    assert d.intent == "cheapest" and d.target == "small"


def test_allowed_set_restricts_candidates():
    d = _decide("smartest", allowed={"small", "mid"})
    assert d.target == "mid"                # strong excluded by allowed set


def test_no_eligible_candidate_returns_none():
    d = _decide("smartest", allowed={"nonexistent"})
    assert d.target is None and "No allowed target" in d.reason


def test_warm_bonus_influences_choice():
    # give the small backend a warm prefix; balanced routing should prefer it on a tie-ish call
    warm = lambda be, model: be == "small"
    d = smart.decide("balanced", _registry(), sovereign=True,
                     price_fn=_price_fn, latency_fn=_lat_fn, warm_fn=warm)
    small = next(c for c in d.considered if c.target == "small")
    assert small.warm is True


def test_non_sovereign_includes_external():
    d = smart.decide("smartest", _registry(), sovereign=False,
                     price_fn=_price_fn, latency_fn=_lat_fn)
    names = {c.target for c in d.considered}
    assert "external" in names              # boundary filter off → external eligible


def test_decision_is_deterministic():
    a, b = _decide("balanced"), _decide("balanced")
    assert a.target == b.target
