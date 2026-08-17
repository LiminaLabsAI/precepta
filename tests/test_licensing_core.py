"""Phase 16 · Group 0 — the signed-license contract: issue, verify, status."""
from __future__ import annotations

import datetime as dt

import pytest

from licensing import core, keys


def test_issue_and_verify_roundtrip():
    priv, pub = core.generate_keypair()
    now = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    payload = core.trial_payload("lic_1", "a@corp.com", now)
    token = core.issue(payload, priv)
    got = core.verify(token, pub)
    assert got["license_id"] == "lic_1" and got["plan"] == "trial"
    assert got["expires_at"] == (now + dt.timedelta(days=15)).isoformat()


def test_tampered_token_is_rejected():
    priv, pub = core.generate_keypair()
    token = core.issue(core.trial_payload("lic", "a@corp.com", dt.datetime(2026, 1, 1, tzinfo=dt.UTC)), priv)
    body, sig = token.split(".")
    # flip a byte in the payload → signature no longer matches
    bad_body = core._b64e(core._b64d(body).replace(b"trial", b"suber"))
    with pytest.raises(core.InvalidLicense):
        core.verify(bad_body + "." + sig, pub)
    # a key signed by a DIFFERENT keypair must not verify against our public key
    other_priv, _ = core.generate_keypair()
    forged = core.issue(core.trial_payload("lic", "a@corp.com", dt.datetime(2026, 1, 1, tzinfo=dt.UTC)), other_priv)
    with pytest.raises(core.InvalidLicense):
        core.verify(forged, pub)
    # garbage input
    with pytest.raises(core.InvalidLicense):
        core.verify("not-a-token", pub)


def test_status_trial_active_grace_expired():
    now = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    p = core.trial_payload("lic", "a@corp.com", now)          # expires day 15
    assert core.status(p, now)["state"] == "active"
    assert core.status(p, now)["days_left"] == 15
    assert core.status(p, now + dt.timedelta(days=14))["state"] == "active"
    # day 16 → within 3-day grace
    assert core.status(p, now + dt.timedelta(days=16))["state"] == "grace"
    # day 19 → past grace → expired
    assert core.status(p, now + dt.timedelta(days=19))["state"] == "expired"


def test_status_subscription():
    now = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    p = {"plan": "subscription", "expires_at": (now + dt.timedelta(days=30)).isoformat()}
    assert core.status(p, now)["state"] == "active"
    assert core.status(p, now + dt.timedelta(days=31))["state"] == "expired"   # no grace for subs


def test_dev_keys_are_a_valid_pair():
    # the committed dev keypair must actually verify (used by the vendor service
    # + Phase 17 in dev). Production overrides both via env.
    now = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    token = core.issue(core.trial_payload("lic", "a@corp.com", now), keys.signing_key())
    got = core.verify(token, keys.public_key())
    assert got["license_id"] == "lic"
