"""Activate smart router — intent mapping + trace-step candidate-set carrier.

Pure / in-memory (no DB writes, no deletes): verifies the raw→catalog intent
mapping and that a trace step carries the scored candidate set in ``extra``.
"""
from __future__ import annotations

from app.router import smart
from app import traces as tr


# ── raw intent → catalog intent ──────────────────────────────────────────────

def test_explicit_intents_map_directly_and_not_inferred():
    assert smart.catalog_intent_for("cheapest") == ("cheapest", None, False)
    assert smart.catalog_intent_for("fastest") == ("fastest", None, False)
    assert smart.catalog_intent_for("best-quality") == ("smartest", None, False)
    assert smart.catalog_intent_for("accuracy") == ("accuracy", None, False)


def test_auto_is_inferred_from_difficulty():
    assert smart.catalog_intent_for("auto", "hard") == ("smartest", None, True)
    assert smart.catalog_intent_for("auto", "easy") == ("cheapest", None, True)
    assert smart.catalog_intent_for("automatic", "easy")[2] is True   # inferred flag


def test_unknown_intent_is_treated_as_inferred_auto():
    key, conf, inferred = smart.catalog_intent_for("teleport", "hard")
    assert inferred is True and key == "smartest" and conf is None


# ── trace step carries the candidate set (in extra) ──────────────────────────

def test_routing_step_carries_candidate_set():
    t = tr.begin("team", "u@x", "admin", {})
    cands = [{"target": "ollama", "quality": 0.5, "cost": 0.0, "chosen": True},
             {"target": "hf", "quality": 0.95, "cost": 0.6, "chosen": False}]
    t.step("routing", "Routed to ollama", "easy → cheapest",
           inferred=True, extra={"candidates": cands, "intent": "cheapest"})
    s = t.steps[-1]
    assert s["extra"]["candidates"][0]["target"] == "ollama"
    assert s["extra"]["candidates"][0]["chosen"] is True
    assert s["extra"]["intent"] == "cheapest"
    assert s["inferred"] is True


def test_step_without_extra_omits_the_key():
    t = tr.begin("team", "u@x", "admin", {})
    t.step("firewall", "No sensitive data found", "scanned")
    assert "extra" not in t.steps[-1]
