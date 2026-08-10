"""Phase 12 — Group 5 · LOCKED router-decision evaluator (Rule 11).

Runs the frozen 7-scenario set (tests/benchmarks/router_scenarios_v1.json)
through the resolver. The scalar is the fraction of scenarios routed to the
expected target; it must be 1.0. This is the evaluator that was frozen BEFORE
the router is tuned further — changing the scoring must not silently change
these outcomes (bump to v2 rather than editing v1).

Also checks the open-core boundary: the OSS router modules must not import the
commercial governance/sovereignty/audit code, so the router can be extracted as
an Apache-2.0 package (DIP boundary integrity).
"""
from __future__ import annotations

import json
import pathlib

from app.router import scoring

_EVAL = pathlib.Path(__file__).parent / "benchmarks" / "router_scenarios_v1.json"

# OSS router core (Apache-2.0 boundary) — must stay free of commercial imports.
_OSS_CORE = ["intent_catalog", "scoring", "targets", "smart", "timing",
             "target_adapters"]
_FORBIDDEN_IMPORTS = ("governance", "sovereign", "attestation",
                      "adapters.audit", "adapters.authz", "compliance")


def _load():
    return json.loads(_EVAL.read_text())


def _route(sc):
    # mirror the two stages: apply the confidence floor, then resolve.
    conf = sc.get("confidence")
    intent, _bumped, _ = scoring.apply_confidence_floor(sc["intent"], conf)
    return scoring.resolve(
        intent, sc["candidates"],
        forbidden=set(sc.get("forbidden") or []), confidence=conf)


def test_locked_router_scenarios_all_pass():
    data = _load()
    scenarios = data["scenarios"]
    assert len(scenarios) == 7, "the locked set is exactly 7 scenarios"
    correct = 0
    failures = []
    for sc in scenarios:
        d = _route(sc)
        if d.target == sc["expect_target"]:
            correct += 1
        else:
            failures.append(f"{sc['id']}: got {d.target!r}, expected {sc['expect_target']!r}")
    scalar = correct / len(scenarios)
    assert scalar == 1.0, f"router eval scalar {scalar} < 1.0; failures: {failures}"


def test_confidence_floor_scenario_bumps_intent():
    sc = next(s for s in _load()["scenarios"] if s["id"] == "low_confidence_cheap_caught_by_floor")
    intent2, bumped, _ = scoring.apply_confidence_floor(sc["intent"], sc["confidence"])
    assert bumped is True and intent2 == sc["expect_intent"]


def test_each_scenario_returns_full_candidate_set():
    # the candidate set (for the Traces Route tab) is always present for a routed decision
    for sc in _load()["scenarios"]:
        d = _route(sc)
        if d.target is not None:
            assert len(d.considered) == len([c for c in sc["candidates"]
                                             if c["target"] not in set(sc.get("forbidden") or [])])


def test_oss_router_core_has_no_commercial_imports():
    root = pathlib.Path(__file__).parent.parent / "app" / "router"
    offenders = []
    for mod in _OSS_CORE:
        src = (root / f"{mod}.py").read_text()
        for line in src.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                for bad in _FORBIDDEN_IMPORTS:
                    if bad in stripped:
                        offenders.append(f"{mod}.py: {stripped}")
    assert not offenders, f"OSS router core imports commercial code: {offenders}"
