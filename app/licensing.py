"""Self-host license — verify a signed key LOCALLY, track status, store activation.

This is the customer side. It carries its OWN Ed25519 verify + the embedded
public key and deliberately does NOT import the vendor `licensing/` package (that
package holds the private signing key + admin surface and is not in the app
image). A cross-check test proves the two agree on the token format.

Verification is fully offline — no network needed to validate a license — which
is what keeps the sovereign box's zero-egress guarantee intact. (The Phase-17
heartbeat is a separate, disclosed, metadata-only ping.)
"""
from __future__ import annotations

import base64
import datetime as _dt
import json
import os
import uuid

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .db import get_conn

GRACE_DAYS = 3

# The public key that licenses must be signed with. Production overrides via
# PRECEPTA_LICENSE_PUBLIC_KEY; the default is the committed dev key (matches the
# Phase-16 dev signer) so local/dev works out of the box.
_DEV_PUBLIC_KEY = "2-mX2RFERjZzJdsvPyN_Ju0fU--pnXJhOpVqsG_i5L4"


def public_key() -> str:
    return os.environ.get("PRECEPTA_LICENSE_PUBLIC_KEY", "").strip() or _DEV_PUBLIC_KEY


class InvalidLicense(Exception):
    """A malformed, tampered, or wrongly-signed license key."""


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def verify(token: str) -> dict:
    """Return the payload iff the token is well-formed and signed by public_key()."""
    try:
        body_b64, sig_b64 = (token or "").strip().split(".")
        body, sig = _b64d(body_b64), _b64d(sig_b64)
    except (ValueError, AttributeError, base64.binascii.Error) as exc:
        raise InvalidLicense("malformed license key") from exc
    try:
        Ed25519PublicKey.from_public_bytes(_b64d(public_key())).verify(sig, body)
    except (InvalidSignature, ValueError) as exc:
        raise InvalidLicense("license signature does not verify") from exc
    try:
        return json.loads(body)
    except ValueError as exc:
        raise InvalidLicense("license payload is not valid JSON") from exc


# ── storage (single-row table in the app DB) ───────────────────────────────
_DDL = """
CREATE TABLE IF NOT EXISTS app_license (
    id             INTEGER PRIMARY KEY CHECK (id = 1),
    token          TEXT,
    install_id     TEXT,
    activated_at   TEXT,
    last_heartbeat TEXT,
    server_plan    TEXT
)
"""


def ensure_table() -> None:
    with get_conn() as conn:
        conn.execute(_DDL)
        conn.execute("INSERT OR IGNORE INTO app_license (id, install_id) VALUES (1, ?)",
                     (uuid.uuid4().hex,))


def _row() -> dict:
    ensure_table()
    with get_conn() as conn:
        r = conn.execute("SELECT * FROM app_license WHERE id=1").fetchone()
    return dict(r) if r else {}


def install_id() -> str:
    return _row().get("install_id") or ""


def current() -> dict | None:
    """The stored, still-valid license payload — or None if none/invalid."""
    tok = _row().get("token")
    if not tok:
        return None
    try:
        return verify(tok)
    except InvalidLicense:
        return None


def activate(token: str) -> dict:
    """Verify a key and store it. Raises InvalidLicense on a bad key."""
    payload = verify(token)                       # raises if bad
    ensure_table()
    with get_conn() as conn:
        conn.execute("UPDATE app_license SET token=?, activated_at=? WHERE id=1",
                     (token.strip(), _dt.datetime.now(_dt.UTC).isoformat()))
    return payload


def record_heartbeat_result(server_plan: str | None) -> None:
    ensure_table()
    with get_conn() as conn:
        conn.execute("UPDATE app_license SET last_heartbeat=?, server_plan=? WHERE id=1",
                     (_dt.datetime.now(_dt.UTC).isoformat(), server_plan))


# ── status ─────────────────────────────────────────────────────────────────
def _parse(ts: str) -> _dt.datetime:
    d = _dt.datetime.fromisoformat(ts)
    return d if d.tzinfo else d.replace(tzinfo=_dt.UTC)


def status(now: _dt.datetime | None = None) -> dict:
    """Resolve the stored license + current time → {licensed, plan, state, days_left}.

    state: 'active' | 'grace' | 'expired' | 'unlicensed'."""
    now = now or _dt.datetime.now(_dt.UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=_dt.UTC)
    p = current()
    if p is None:
        return {"licensed": False, "plan": None, "state": "unlicensed",
                "days_left": None, "install_id": install_id()}
    plan = p.get("plan", "trial")
    exp_raw = p.get("expires_at")
    if not exp_raw:
        state, days_left = "active", None
    else:
        exp = _parse(exp_raw)
        days_left = (exp - now).days
        if now <= exp:
            state = "active"
        elif plan == "trial" and now <= exp + _dt.timedelta(days=GRACE_DAYS):
            state = "grace"
        else:
            state = "expired"
    return {"licensed": state != "expired", "plan": plan, "state": state,
            "days_left": days_left, "subject": p.get("subject"),
            "license_id": p.get("license_id"), "seats": p.get("seats"),
            "install_id": install_id()}


def enforcing() -> bool:
    """Enforcement is OFF by default so local/dev is never broken; production opts in."""
    return os.environ.get("PRECEPTA_LICENSE_ENFORCE", "0").lower() in ("1", "true", "yes", "on")


# ── heartbeat client (metadata only, disclosed, only when licensed) ─────────
def license_url() -> str:
    return os.environ.get("PRECEPTA_LICENSE_URL", "https://console.preceptaai.com").rstrip("/")


def heartbeat_body() -> dict | None:
    """The metadata-only payload — or None if unlicensed (then we don't phone home).
    NEVER contains prompts or customer data — just license/install identity."""
    from . import __version__
    p = current()
    if p is None:
        return None
    return {"license_id": p.get("license_id"), "install_id": install_id(),
            "plan": p.get("plan"), "seats": p.get("seats") or 1, "version": __version__}


async def heartbeat_once(*, poster=None) -> dict:
    """Send one metadata-only heartbeat to the vendor. Fail-soft. No-op (and no
    egress) when unlicensed — so an unlicensed/local box never phones home."""
    body = heartbeat_body()
    if body is None:
        return {"skipped": "unlicensed"}
    # open egress to the license host only now (a license is active), then send
    try:
        from .sovereign.egress import seed_license_egress, sync_allowfile
        seed_license_egress()
        sync_allowfile()
    except Exception:
        pass
    url = license_url() + "/license/heartbeat"
    try:
        if poster is not None:
            resp = await poster(url, body)
        else:
            import httpx
            async with httpx.AsyncClient(timeout=10.0) as client:
                r = await client.post(url, json=body)
                resp = r.json()
        record_heartbeat_result((resp or {}).get("plan"))
        return {"ok": True, "server": resp}
    except Exception as exc:                       # never break the app on a license ping
        return {"ok": False, "error": type(exc).__name__}
