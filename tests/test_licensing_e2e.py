"""Phase 16 · Group 4 — end-to-end vendor journey:
sign in (recorded) → trial key issued → install heartbeats in → admin sees it →
upgrade to subscription → key re-issued and verifies. Proves "see every login"
+ "control via keys" work together."""
from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from licensing import core, keys


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LICENSE_DB", str(tmp_path / "lic.db"))
    monkeypatch.setenv("LICENSE_ADMIN_TOKEN", "admintok")
    import licensing.service as svc
    importlib.reload(svc)
    monkeypatch.setattr(svc.google, "verify_id_token",
                        lambda credential, **kw: {"sub": "g-" + credential,
                                                  "email": credential + "@corp.com",
                                                  "name": credential.title()})
    return TestClient(svc.app)


ADMIN = {"Authorization": "Bearer admintok"}


def test_full_vendor_journey(client):
    # 1. two people sign in → both logins are visible; each gets a trial license
    for who in ("dana", "erin"):
        assert client.post("/onboard", json={"credential": who}).status_code == 200
    assert len(client.get("/admin/logins", headers=ADMIN).json()["data"]) == 2
    lics = client.get("/admin/licenses", headers=ADMIN).json()["data"]
    assert len(lics) == 2 and all(l["plan"] == "trial" and l["status"] == "active" for l in lics)

    dana = next(l for l in lics if l["subject"] == "dana@corp.com")
    lic_id = dana["license_id"]

    # 2. dana installs on two machines → both check in (metadata only)
    for inst in ("dana-laptop", "dana-server"):
        hb = client.post("/license/heartbeat", json={
            "license_id": lic_id, "install_id": inst, "plan": "trial",
            "seats": 1, "version": "0.3.0"})
        assert hb.status_code == 200 and hb.json()["state"] == "active"
    installs = client.get("/admin/installs", headers=ADMIN).json()["data"]
    assert {i["install_id"] for i in installs} >= {"dana-laptop", "dana-server"}

    # 3. dana takes a subscription → key re-issued, verifies, plan flips
    r = client.post(f"/admin/licenses/{lic_id}/plan", headers=ADMIN, json={"plan": "subscription"})
    assert r.status_code == 200
    payload = core.verify(r.json()["license"]["token"], keys.public_key())
    assert payload["plan"] == "subscription"
    # a fresh heartbeat now reports the subscription
    hb = client.post("/license/heartbeat", json={"license_id": lic_id,
                     "install_id": "dana-laptop", "plan": "subscription",
                     "seats": 1, "version": "0.3.0"}).json()
    assert hb["plan"] == "subscription" and hb["state"] == "active"

    # 4. revoke erin → shows revoked; a heartbeat still answers (client enforces in P17)
    erin = next(l for l in lics if l["subject"] == "erin@corp.com")
    assert client.post(f"/admin/licenses/{erin['license_id']}/revoke", headers=ADMIN).status_code == 200
    erin_now = next(l for l in client.get("/admin/licenses", headers=ADMIN).json()["data"]
                    if l["license_id"] == erin["license_id"])
    assert erin_now["status"] == "revoked"
