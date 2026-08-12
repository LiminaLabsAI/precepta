"""'Smart router (auto-decide)' compression: per-request skip/baseline/aggressive."""
from __future__ import annotations

from app import compression, features


def _msg(text):
    return [{"role": "user", "content": text}]


def test_config_accepts_smart_compression():
    features.set_config("cmp-smart", {"compression_enabled": True, "compression_mode": "smart"})
    assert features.compression_mode("cmp-smart") == "smart"
    features.set_config("cmp-x", {"compression_mode": "bogus"})
    assert features.compression_mode("cmp-x") == "baseline"


def test_decide_smart_by_length():
    assert compression.decide_smart(_msg("hi there")) == "skip"          # short → nothing to save
    assert compression.decide_smart(_msg("word " * 120)) == "baseline"   # ~600 chars → baseline
    assert compression.decide_smart(_msg("word " * 1000)) == "aggressive"  # ~5000 chars → aggressive


def test_effective_mode_resolves_smart():
    features.set_config("cmp-ep", {"compression_enabled": True, "compression_mode": "smart"})
    assert compression.effective_mode("cmp-ep", _msg("short")) == "skip"
    assert compression.effective_mode("cmp-ep", _msg("word " * 1000)) == "aggressive"
    # a non-smart endpoint returns its configured mode
    features.set_config("cmp-base", {"compression_enabled": True, "compression_mode": "baseline"})
    assert compression.effective_mode("cmp-base", _msg("word " * 1000)) == "baseline"
