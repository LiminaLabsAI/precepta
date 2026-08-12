"""'Smart router (auto-decide)' cache strategy: per-request exact vs semantic vs
skip, config round-trip, and lookup/store honoring the decision."""
from __future__ import annotations

from app import cache, features


def _msg(text):
    return [{"role": "user", "content": text}]


def test_config_accepts_smart():
    features.set_config("smart-ep", {"cache_enabled": True, "cache_strategy": "smart"})
    assert features.cache_strategy("smart-ep") == "smart"
    # unknown values still fall back to exact
    features.set_config("smart-ep2", {"cache_strategy": "bogus"})
    assert features.cache_strategy("smart-ep2") == "exact"


def test_decide_smart_skip_exact_semantic():
    assert cache.decide_smart(_msg("What's the weather today?")) == "skip"
    assert cache.decide_smart(_msg("latest news on rates")) == "skip"
    assert cache.decide_smart(_msg("2+2")) == "exact"                 # short → exact
    assert cache.decide_smart(_msg("ping")) == "exact"
    long_q = "Explain in detail how our data-retention policy applies to archived customer records"
    assert cache.decide_smart(_msg(long_q)) == "semantic"            # long NL → semantic


def test_effective_strategy_resolves_smart(monkeypatch):
    features.set_config("smart-ep3", {"cache_enabled": True, "cache_strategy": "smart"})
    assert cache.effective_strategy("smart-ep3", _msg("today's price")) == "skip"
    assert cache.effective_strategy("smart-ep3", _msg("hi")) == "exact"
    # a non-smart endpoint just returns its configured strategy
    features.set_config("exact-ep", {"cache_enabled": True, "cache_strategy": "exact"})
    assert cache.effective_strategy("exact-ep", _msg("anything at all here")) == "exact"


def test_smart_skip_means_no_store_no_lookup():
    features.set_config("smart-skip", {"cache_enabled": True, "cache_strategy": "smart"})
    msgs = _msg("what is the weather today in Mumbai")   # → skip
    cache.store("m", msgs, {}, "teamX", "smart-skip",
                {"choices": []}, 1, 1, "ollama", "m")
    # skip means it was never stored, so a lookup is a miss
    assert cache.lookup("m", msgs, {}, "teamX", "smart-skip") is None


def test_smart_exact_roundtrip():
    features.set_config("smart-exact", {"cache_enabled": True, "cache_strategy": "smart"})
    msgs = _msg("2+2")                                   # short → exact
    cache.store("m", msgs, {}, "teamY", "smart-exact",
                {"choices": [{"message": {"content": "4"}}]}, 1, 1, "ollama", "m")
    hit = cache.lookup("m", msgs, {}, "teamY", "smart-exact")
    assert hit is not None and hit["exact"] is True
