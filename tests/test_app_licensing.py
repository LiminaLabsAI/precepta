"""Phase 17 · Group 0 — self-host license verify/status/activate (app side).

Cross-checks that a key issued by the vendor `licensing.core` verifies in
`app.licensing` — the two must agree on the token format & keypair."""
from __future__ import annotations

import datetime as dt

import pytest

from app import licensing as al
from licensing import core, keys as vkeys


@pytest.fixture(autouse=True)
def _clean_license():
    al.ensure_table()
    from app.db import get_conn
    with get_conn() as conn:                       # reset the single-row license
        conn.execute("UPDATE app_license SET token=NULL, activated_at=NULL WHERE id=1")
    yield
    with get_conn() as conn:
        conn.execute("UPDATE app_license SET token=NULL, activated_at=NULL WHERE id=1")


def _issue(plan="trial", days=15, now=None):
    now = now or dt.datetime.now(dt.UTC)
    if plan == "trial":
        payload = core.trial_payload("lic_x", "buyer@corp.com", now, days=days)
    else:
        payload = {"license_id": "lic_x", "subject": "buyer@corp.com", "plan": plan,
                   "issued_at": now.isoformat(),
                   "expires_at": (now + dt.timedelta(days=days)).isoformat(),
                   "seats": 1, "key_version": core.KEY_VERSION}
    return core.issue(payload, vkeys.signing_key())


def test_vendor_key_verifies_in_app():
    # the committed dev keypair must line up: app public key == vendor public key
    assert al.public_key() == vkeys.public_key()
    token = _issue()
    payload = al.verify(token)
    assert payload["subject"] == "buyer@corp.com" and payload["plan"] == "trial"


def test_activate_and_status_trial_active():
    al.activate(_issue())
    st = al.status()
    assert st["licensed"] and st["state"] == "active" and st["plan"] == "trial"
    assert st["install_id"]                         # stable install id assigned


def test_status_grace_then_expired():
    now = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    al.activate(_issue(days=15, now=now))
    assert al.status(now + dt.timedelta(days=16))["state"] == "grace"
    exp = al.status(now + dt.timedelta(days=19))
    assert exp["state"] == "expired" and exp["licensed"] is False


def test_unlicensed_when_no_key():
    st = al.status()
    assert st["state"] == "unlicensed" and st["licensed"] is False


def test_tampered_and_forged_keys_rejected():
    with pytest.raises(al.InvalidLicense):
        al.verify("garbage")
    other_priv, _ = core.generate_keypair()          # signed by a different key
    forged = core.issue(core.trial_payload("l", "x@y.com", dt.datetime.now(dt.UTC)), other_priv)
    with pytest.raises(al.InvalidLicense):
        al.verify(forged)


def test_enforcing_defaults_off(monkeypatch):
    monkeypatch.delenv("PRECEPTA_LICENSE_ENFORCE", raising=False)
    assert al.enforcing() is False                   # local/dev never broken by default
    monkeypatch.setenv("PRECEPTA_LICENSE_ENFORCE", "1")
    assert al.enforcing() is True
