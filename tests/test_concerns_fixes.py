"""Regression tests for the batch of reported concerns (overnight fixes).

Backend-verifiable pieces of the concern list. UI-only fixes (markdown render,
timezone display, dynamic suggestions render) are covered by their endpoints
where they have one, and browser-validated separately.
"""
from __future__ import annotations

from app.router import config as router_config


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
