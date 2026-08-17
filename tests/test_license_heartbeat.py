"""Phase 17 · Group 2 — heartbeat client (metadata only) + attestation disclosure."""
from __future__ import annotations

import asyncio
import datetime as dt

import pytest

from app import licensing as al
from app.sovereign import attestation, egress as eg
from licensing import core, keys as vkeys


@pytest.fixture(autouse=True)
def _clean():
    al.ensure_table()
    from app.db import get_conn
    with get_conn() as conn:
        conn.execute("UPDATE app_license SET token=NULL, activated_at=NULL WHERE id=1")
    eg.ensure_table()
    for h in list(eg.list_hosts()):
        eg.remove_host(h["host"])
    yield
    with get_conn() as conn:
        conn.execute("UPDATE app_license SET token=NULL, activated_at=NULL WHERE id=1")
    for h in list(eg.list_hosts()):
        eg.remove_host(h["host"])


def _activate():
    al.activate(core.issue(core.trial_payload("lic_hb", "buyer@corp.com", dt.datetime.now(dt.UTC)),
                           vkeys.signing_key()))


def test_heartbeat_body_is_metadata_only():
    assert al.heartbeat_body() is None                 # unlicensed → no phone-home
    _activate()
    b = al.heartbeat_body()
    assert set(b.keys()) == {"license_id", "install_id", "plan", "seats", "version"}
    # not a single field carries prompt/customer content
    assert b["license_id"] == "lic_hb" and b["plan"] == "trial" and b["install_id"]


def test_heartbeat_once_unlicensed_is_noop(monkeypatch):
    called = []
    async def poster(url, body): called.append(body); return {}
    res = asyncio.run(al.heartbeat_once(poster=poster))
    assert res == {"skipped": "unlicensed"} and not called   # never phones home unlicensed
    assert eg.list_hosts() == []                             # and never opens egress


def test_heartbeat_once_licensed_sends_and_opens_egress(monkeypatch):
    monkeypatch.setenv("PRECEPTA_LICENSE_URL", "https://license.example.com")
    _activate()
    sent = {}
    async def poster(url, body): sent["url"], sent["body"] = url, body; return {"plan": "subscription"}
    res = asyncio.run(al.heartbeat_once(poster=poster))
    assert res["ok"] and sent["url"].endswith("/license/heartbeat")
    assert "prompt" not in sent["body"]                      # metadata only
    # egress to the license host is now approved (disclosed, system:license)
    hosts = {h["host"]: h for h in eg.list_hosts()}
    assert "license.example.com" in hosts and hosts["license.example.com"]["added_by"] == "system:license"


def test_attestation_discloses_licensing():
    # unlicensed: heartbeat disabled, customer data egress none
    d = attestation._licensing_disclosure()
    assert d["customer_data_egress"] == "none" and d["heartbeat"]["enabled"] is False
    _activate()
    d2 = attestation._licensing_disclosure()
    assert d2["license_active"] is True and d2["heartbeat"]["enabled"] is True
    assert d2["heartbeat"]["contains_customer_data"] is False
    assert d2["heartbeat"]["sends"] == ["license_id", "install_id", "plan", "seats", "version"]
