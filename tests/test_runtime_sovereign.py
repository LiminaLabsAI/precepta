"""Runtime, owner-gated Sovereign Mode — the Console toggle must actually change
enforcement everywhere (gateway block, attestation, /health), and be audited."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app import controls
from app.main import app
from app.sovereign import enforce_backend
from app.adapters.audit.chain import get_chain
import types

client = TestClient(app)
OWNER = {"Authorization": "Bearer dev-admin"}      # admin@local ∈ platform owners
NON_OWNER = {"Authorization": "Bearer dev-user"}


def _ext():
    return types.SimpleNamespace(name="ext-backend", in_boundary=False)


def test_effective_mode_overrides_deploy_default():
    controls.clear_sovereign()
    try:
        # default (deploy) is on → an external backend is blocked
        assert controls.sovereign_enabled() is True
        assert enforce_backend(_ext()) is not None
        # owner turns it OFF at runtime → external routing now allowed
        controls.set_sovereign(False)
        assert controls.sovereign_enabled() is False
        assert enforce_backend(_ext()) is None
        # and back on
        controls.set_sovereign(True)
        assert enforce_backend(_ext()) is not None
    finally:
        controls.clear_sovereign()


def test_endpoint_owner_gated_and_audited():
    controls.clear_sovereign()
    try:
        # non-owner cannot flip it
        assert client.post("/v1/controls/sovereign", headers=NON_OWNER,
                           json={"enabled": False}).status_code == 403
        # owner disables it → state reflects, and an audit event is written
        r = client.post("/v1/controls/sovereign", headers=OWNER, json={"enabled": False})
        assert r.status_code == 200 and r.json()["in_boundary"] is False
        assert any(row.get("resource") == "controls.sovereign"
                   for row in get_chain().recent(limit=5))
        # attestation now reflects the runtime change
        att = client.get("/attestation").json()
        assert att["sovereign_mode"] is False and att["egress_test"]["result"] == "open"
    finally:
        controls.clear_sovereign()


def test_controls_state_and_can_edit():
    controls.clear_sovereign()
    try:
        owner = client.get("/v1/controls", headers=OWNER).json()
        assert owner["can_edit"] is True and owner["audit"] is True
        # egress mirrors in-boundary; both reflect effective sovereign mode
        assert owner["egress_lock"] == owner["in_boundary"]
        assert client.get("/v1/controls", headers=NON_OWNER).json()["can_edit"] is False
    finally:
        controls.clear_sovereign()
