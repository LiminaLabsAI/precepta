"""Signed-license contract — issue, verify, and read the status of a license key.

A license key is a compact, offline-verifiable token:

    base64url(canonical_json_payload) + "." + base64url(ed25519_signature)

The vendor signs with a private Ed25519 key (kept server-side); anyone with the
public key can verify **locally, with no network** — which is exactly what lets a
sovereign self-host validate its license without phoning home (the heartbeat in
Phase 17 is metadata-only and separate).

Payload fields:
    license_id   str    unique id
    subject      str    who it's for (email / org)
    plan         str    "trial" | "subscription"
    issued_at    str    ISO-8601 (UTC)
    expires_at   str    ISO-8601 (UTC)  — trial = issued + 15d
    seats        int    allowed installs (informational in v1)
    key_version  int    signing-key version (rotation-ready)
"""
from __future__ import annotations

import base64
import datetime as _dt
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization as _ser
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey, Ed25519PublicKey)

TRIAL_DAYS = 15
GRACE_DAYS = 3
KEY_VERSION = 1


class InvalidLicense(Exception):
    """A key that is malformed, tampered, or not signed by the trusted key."""


# ── base64url without padding ──────────────────────────────────────────────
def _b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


# ── keys ───────────────────────────────────────────────────────────────────
def generate_keypair() -> tuple[str, str]:
    """Return (private_b64, public_b64) for a fresh Ed25519 keypair."""
    sk = Ed25519PrivateKey.generate()
    priv = sk.private_bytes(_ser.Encoding.Raw, _ser.PrivateFormat.Raw,
                            _ser.NoEncryption())
    pub = sk.public_key().public_bytes(_ser.Encoding.Raw, _ser.PublicFormat.Raw)
    return _b64e(priv), _b64e(pub)


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


# ── issue / verify ─────────────────────────────────────────────────────────
def issue(payload: dict, private_b64: str) -> str:
    """Sign a payload → a license-key token. Vendor-only (needs the private key)."""
    body = _canonical(payload)
    sk = Ed25519PrivateKey.from_private_bytes(_b64d(private_b64))
    sig = sk.sign(body)
    return _b64e(body) + "." + _b64e(sig)


def verify(token: str, public_b64: str) -> dict:
    """Return the payload iff the token is well-formed AND signed by the key.

    Raises InvalidLicense on any tampering / bad format / wrong signer. Does NOT
    check expiry — call status() for that (a signed-but-expired key is still
    authentic; expiry is a separate, time-based decision)."""
    try:
        body_b64, sig_b64 = token.strip().split(".")
        body, sig = _b64d(body_b64), _b64d(sig_b64)
    except (ValueError, AttributeError, base64.binascii.Error) as exc:
        raise InvalidLicense("malformed license key") from exc
    try:
        pk = Ed25519PublicKey.from_public_bytes(_b64d(public_b64))
        pk.verify(sig, body)          # raises InvalidSignature on mismatch
    except (InvalidSignature, ValueError) as exc:
        raise InvalidLicense("license signature does not verify") from exc
    try:
        return json.loads(body)
    except ValueError as exc:
        raise InvalidLicense("license payload is not valid JSON") from exc


# ── status (time-based state) ──────────────────────────────────────────────
def _parse(ts: str) -> _dt.datetime:
    d = _dt.datetime.fromisoformat(ts)
    return d if d.tzinfo else d.replace(tzinfo=_dt.UTC)


def status(payload: dict, now: _dt.datetime, grace_days: int = GRACE_DAYS) -> dict:
    """Resolve a payload + the current time → {plan, state, days_left}.

    state: 'active' (in force) | 'grace' (trial past expiry, within grace) |
           'expired' (past grace / subscription lapsed)."""
    plan = payload.get("plan", "trial")
    exp_raw = payload.get("expires_at")
    if not exp_raw:                                  # perpetual (rare) — always active
        return {"plan": plan, "state": "active", "days_left": None}
    exp = _parse(exp_raw)
    if now.tzinfo is None:
        now = now.replace(tzinfo=_dt.UTC)
    days_left = (exp - now).days
    if plan == "subscription":
        return {"plan": plan, "state": "active" if now <= exp else "expired",
                "days_left": days_left}
    # trial: active → grace → expired
    if now <= exp:
        state = "active"
    elif now <= exp + _dt.timedelta(days=grace_days):
        state = "grace"
    else:
        state = "expired"
    return {"plan": plan, "state": state, "days_left": days_left}


# ── convenience: build a trial payload ─────────────────────────────────────
def trial_payload(license_id: str, subject: str, now: _dt.datetime,
                  days: int = TRIAL_DAYS, seats: int = 1) -> dict:
    if now.tzinfo is None:
        now = now.replace(tzinfo=_dt.UTC)
    return {"license_id": license_id, "subject": subject, "plan": "trial",
            "issued_at": now.isoformat(),
            "expires_at": (now + _dt.timedelta(days=days)).isoformat(),
            "seats": seats, "key_version": KEY_VERSION}
