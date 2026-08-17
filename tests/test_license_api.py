"""Phase 17 · Group 1 — /v1/license status + owner-gated activation."""
from __future__ import annotations

import datetime as dt

from fastapi.testclient import TestClient

from app.main import app
from app import licensing as al
from app.adapters.identity.keys import issue_key, revoke_key
from licensing import core, keys as vkeys

client = TestClient(app)
ADMIN = {"Authorization": "Bearer dev-admin"}


def _clear():
    al.ensure_table()
    from app.db import get_conn
    with get_conn() as conn:
        conn.execute("UPDATE app_license SET token=NULL, activated_at=NULL WHERE id=1")


def test_license_status_and_owner_activation():
    _clear()
    try:
        st = client.get("/v1/license", headers=ADMIN).json()
        assert st["state"] == "unlicensed" and "enforce" in st and st["install_id"]
        # activate a valid trial key (issued by the vendor lib)
        token = core.issue(core.trial_payload("lic_api", "buyer@corp.com", dt.datetime.now(dt.UTC)),
                           vkeys.signing_key())
        r = client.post("/v1/license/activate", headers=ADMIN, json={"key": token})
        assert r.status_code == 200 and r.json()["state"] == "active" and r.json()["plan"] == "trial"
        assert client.get("/v1/license", headers=ADMIN).json()["state"] == "active"
        # a bad key → 400
        assert client.post("/v1/license/activate", headers=ADMIN, json={"key": "nope"}).status_code == 400
    finally:
        _clear()


def test_activation_is_owner_only():
    kid, tok = issue_key(name="inf-lic", expires_in_days=None)
    try:
        h = {"Authorization": f"Bearer {tok}"}
        # a plain inference key can neither read nor activate
        assert client.get("/v1/license", headers=h).status_code == 403
        assert client.post("/v1/license/activate", headers=h, json={"key": "x"}).status_code == 403
    finally:
        revoke_key(kid)
