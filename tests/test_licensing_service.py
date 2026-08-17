"""Phase 16 · Group 1 — vendor backend: onboarding, issuance, heartbeat, admin."""
from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient

from licensing import core, keys


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LICENSE_DB", str(tmp_path / "lic.db"))
    monkeypatch.setenv("LICENSE_ADMIN_TOKEN", "admintok")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid.apps.googleusercontent.com")
    # fresh app bound to the temp DB
    import licensing.service as svc
    importlib.reload(svc)
    # stub Google verification so no network is needed
    monkeypatch.setattr(svc.google, "verify_id_token",
                        lambda credential, **kw: {"sub": "g-" + credential,
                                                  "email": credential + "@corp.com",
                                                  "name": "User " + credential})
    return TestClient(svc.app)


ADMIN = {"Authorization": "Bearer admintok"}


def test_onboard_records_login_and_issues_verifiable_trial(client):
    r = client.post("/onboard", json={"credential": "alice"})
    assert r.status_code == 200
    b = r.json()
    assert b["subject"] == "alice@corp.com" and b["plan"] == "trial"
    assert b["steps"] and b["steps"][0]["cmd"].startswith("git clone")
    # the issued key VERIFIES with the public key (the Phase-17 contract)
    payload = core.verify(b["key"], keys.public_key())
    assert payload["subject"] == "alice@corp.com" and payload["plan"] == "trial"
    # the login shows up in admin; re-onboard keeps ONE license, bumps login_count
    client.post("/onboard", json={"credential": "alice"})
    logins = client.get("/admin/logins", headers=ADMIN).json()["data"]
    assert len(logins) == 1 and logins[0]["login_count"] == 2
    lics = client.get("/admin/licenses", headers=ADMIN).json()["data"]
    assert len(lics) == 1 and lics[0]["status"] == "active"


def test_onboard_rejects_bad_google_token(client, monkeypatch):
    import licensing.service as svc
    def boom(credential, **kw):
        raise svc.google.GoogleAuthError("bad token")
    monkeypatch.setattr(svc.google, "verify_id_token", boom)
    assert client.post("/onboard", json={"credential": "x"}).status_code == 401


def test_heartbeat_is_metadata_only_and_upserts_install(client):
    key = client.post("/onboard", json={"credential": "bob"}).json()
    lic_id = key["license_id"]
    # a heartbeat with an extra 'prompt' field — must be ignored, never stored
    hb = client.post("/license/heartbeat", json={
        "license_id": lic_id, "install_id": "inst-1", "plan": "trial",
        "seats": 1, "version": "0.3", "prompt": "SECRET CUSTOMER DATA"})
    assert hb.status_code == 200 and hb.json()["state"] == "active"
    installs = client.get("/admin/installs", headers=ADMIN).json()["data"]
    assert len(installs) == 1 and installs[0]["install_id"] == "inst-1"
    assert "prompt" not in installs[0]                       # customer data never stored
    # second heartbeat from the same install bumps the count, not a new row
    client.post("/license/heartbeat", json={"license_id": lic_id, "install_id": "inst-1",
                                            "plan": "trial", "seats": 1, "version": "0.3"})
    assert client.get("/admin/installs", headers=ADMIN).json()["data"][0]["heartbeat_count"] == 2
    # missing required ids → 400
    assert client.post("/license/heartbeat", json={"install_id": "x"}).status_code == 400


def test_admin_plan_change_reissues_valid_key_and_revoke(client):
    key = client.post("/onboard", json={"credential": "carol"}).json()
    lic_id = key["license_id"]
    r = client.post(f"/admin/licenses/{lic_id}/plan", headers=ADMIN, json={"plan": "subscription"})
    assert r.status_code == 200
    newkey = r.json()["license"]["token"]
    p = core.verify(newkey, keys.public_key())               # re-issued key still verifies
    assert p["plan"] == "subscription" and newkey != key["key"]
    # revoke
    assert client.post(f"/admin/licenses/{lic_id}/revoke", headers=ADMIN).status_code == 200
    assert client.get("/admin/licenses", headers=ADMIN).json()["data"][0]["status"] == "revoked"


def test_admin_requires_token(client):
    assert client.get("/admin/logins").status_code == 401
    assert client.get("/admin/licenses", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/admin", headers={"Authorization": "Bearer wrong"}).status_code == 401
