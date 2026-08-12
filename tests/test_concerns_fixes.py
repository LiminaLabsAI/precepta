"""Regression tests for the batch of reported concerns (overnight fixes).

Backend-verifiable pieces of the concern list. UI-only fixes (markdown render,
timezone display, dynamic suggestions render) are covered by their endpoints
where they have one, and browser-validated separately.
"""
from __future__ import annotations

from app.router import config as router_config


# ── Phase 14 G3: real egress probe in the attestation ────────────────────────

def test_egress_probe_shape():
    from app.sovereign.probe import egress_probe
    r = egress_probe(timeout=1.0)
    assert r["result"] in ("blocked", "open", "unknown")
    assert isinstance(r["targets"], list) and len(r["targets"]) >= 1
    assert "reachable" in r


def test_attestation_includes_real_egress_test():
    from app.sovereign.attestation import build_attestation
    from app.adapters.model.registry import get_registry
    from app.settings import get_settings
    att = build_attestation(get_settings(), get_registry())
    et = att["egress_test"]
    assert et["result"] in ("blocked", "open", "unknown")
    assert "verified" in et and "targets" in et


# ── concern #8: router settings — atomic switch to HF endpoint ───────────────

def test_router_hf_atomic_switch():
    """Sending endpoint + model + key + backend together switches to HF in one
    step (the old flow forced a fragile multi-step save that could get stuck)."""
    before = router_config.get_config()["router_backend"]
    try:
        cfg = router_config.update_config({
            "router_backend": "hf",
            "hf_endpoint": "http://hf.internal:8080/v1",
            "hf_model": "llama-3.1-8b-instruct",
            "hf_key": "test-router-key",
        })
        assert cfg["router_backend"] == "hf"
        assert cfg["hf_endpoint"] == "http://hf.internal:8080/v1"
        assert cfg["hf_key_set"] is True
        # blank key on a later edit keeps the stored key
        cfg2 = router_config.update_config({"hf_model": "other"})
        assert cfg2["hf_key_set"] is True and cfg2["hf_model"] == "other"
    finally:
        router_config.update_config({"router_backend": before})


def test_router_hf_rejected_without_endpoint_or_key():
    before = router_config.get_config()["router_backend"]
    try:
        # switching to hf with neither endpoint nor key must be rejected clearly
        import pytest
        with pytest.raises(router_config.RouterConfigError):
            router_config.update_config({"router_backend": "hf", "hf_endpoint": "",
                                         "hf_model": "", "hf_key": ""})
    finally:
        router_config.update_config({"router_backend": before})
