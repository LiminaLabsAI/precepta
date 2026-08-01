"""FEAT-007 (Rule C) — sensitive data → approved-backend-only routing (fail-closed)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.governance import sensitive
from app.db import get_conn

client = TestClient(app)
ADMIN = {"Authorization": "Bearer dev-admin"}


def _reset() -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM sensitive_backends")


def test_is_sensitive():
    assert sensitive.is_sensitive(1, False)          # firewall found PII
    assert sensitive.is_sensitive(0, True)           # caller tagged it
    assert not sensitive.is_sensitive(0, False)


def test_approve_list_unapprove_with_location():
    try:
        sensitive.approve("ollama", "Local GPU (Pune DC)", "admin@local")
        assert "ollama" in sensitive.approved_set()
        row = next(r for r in sensitive.list_approved() if r["backend"] == "ollama")
        assert row["location"] == "Local GPU (Pune DC)" and row["approved_by"] == "admin@local"
    finally:
        _reset()
        assert "ollama" not in sensitive.approved_set()


def test_filter_off_until_configured():
    _reset()
    # no approved backends yet → filter inactive → don't block (firewall still redacts)
    assert sensitive.block_reason(True, "hf") is None


def test_block_reason_fail_closed_once_active():
    try:
        _reset()
        sensitive.approve("ollama", "Local", "admin@local")       # activates the filter
        assert sensitive.block_reason(True, "hf") is not None      # hf not approved → blocked
        assert sensitive.block_reason(False, "hf") is None         # not sensitive → allowed
        assert sensitive.block_reason(True, None) is None          # auto → handled elsewhere
        assert sensitive.block_reason(True, "ollama") is None      # approved → allowed
    finally:
        _reset()


def test_endpoint_and_pipeline_enforcement():
    try:
        _reset()
        # approve only ollama
        r = client.post("/v1/routing/approved", headers=ADMIN,
                        json={"backend": "ollama", "location": "Local"})
        assert r.status_code == 201
        assert "ollama" in {a["backend"] for a in
                            client.get("/v1/routing/approved", headers=ADMIN).json()["approved"]}
        # a data-tagged (sensitive) request to hf (NOT approved) is blocked fail-closed
        resp = client.post("/v1/chat/completions", headers=ADMIN, json={
            "model": "hf/llama-3.1-70b-instruct",
            "messages": [{"role": "user", "content": "process this record"}],
            "data_tag": True})
        assert resp.status_code == 403
        assert "approved" in resp.json()["error"]["message"].lower()
    finally:
        _reset()
