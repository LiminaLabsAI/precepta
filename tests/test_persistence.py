"""Validation — backend persistence (survive restart) + clean-slate reset."""
from __future__ import annotations

from app.adapters.model import store
from app.adapters.model.registry import build_registry
from app.admin_ops import reset_activity
from app.adapters.audit import get_audit
from app.ports import PolicyCheckContext, Decision
from app.db import get_conn


def test_backend_persistence_roundtrip():
    store.save_backend("testprov", "http://x/v1", "k", "gpt-oss-120b", True, tier=2)
    try:
        loaded = {b["provider"]: b for b in store.load_backends()}
        assert "testprov" in loaded
        assert loaded["testprov"]["model"] == "gpt-oss-120b"
        # a freshly built registry (as on restart) includes the persisted backend
        reg = build_registry()
        assert "testprov" in reg
        assert reg["testprov"].default_model == "gpt-oss-120b"
        assert reg["testprov"].in_boundary is True
    finally:
        assert store.delete_backend("testprov") is True
        assert "testprov" not in {b["provider"] for b in store.load_backends()}


def test_reset_clears_activity():
    # seed a row so the reset has something to clear
    get_audit().append_check(
        PolicyCheckContext(action_type="chat.completion"),
        Decision("allow"), tokens=1, pii_count=0, blocked=False)
    with get_conn() as conn:
        assert conn.execute("SELECT COUNT(*) c FROM audit_log").fetchone()["c"] > 0

    cleared = reset_activity()
    assert set(cleared) == {"audit_log", "tamper_evident_audit_log", "telemetry"}

    with get_conn() as conn:
        for t in ("audit_log", "tamper_evident_audit_log", "telemetry"):
            assert conn.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"] == 0
