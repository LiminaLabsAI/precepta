"""Data access for the licensing service — logins, licenses, installs."""
from __future__ import annotations

import datetime as _dt
import uuid

from . import core, db, keys


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.UTC)


def _iso() -> str:
    return _now().isoformat()


# ── logins ─────────────────────────────────────────────────────────────────
def record_login(sub: str, email: str, name: str) -> None:
    db.ensure_schema()
    now = _iso()
    with db.get_conn() as conn:
        conn.execute(
            "INSERT INTO logins (sub,email,name,first_seen,last_seen,login_count) "
            "VALUES (?,?,?,?,?,1) ON CONFLICT(sub) DO UPDATE SET "
            "email=excluded.email, name=excluded.name, last_seen=excluded.last_seen, "
            "login_count=login_count+1",
            (sub, email, name, now, now))


def list_logins() -> list[dict]:
    db.ensure_schema()
    with db.get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM logins ORDER BY last_seen DESC")]


# ── licenses ───────────────────────────────────────────────────────────────
def create_or_get_trial(subject: str) -> dict:
    """One trial license per subject (email). Returns the license row (with token)."""
    db.ensure_schema()
    with db.get_conn() as conn:
        row = conn.execute("SELECT * FROM licenses WHERE subject=?", (subject,)).fetchone()
        if row is not None:
            return dict(row)
        now = _now()
        lic_id = "lic_" + uuid.uuid4().hex[:16]
        payload = core.trial_payload(lic_id, subject, now)
        token = core.issue(payload, keys.signing_key())
        conn.execute(
            "INSERT INTO licenses (license_id,subject,plan,issued_at,expires_at,seats,"
            "revoked,token,created_at,updated_at) VALUES (?,?,?,?,?,?,0,?,?,?)",
            (lic_id, subject, "trial", payload["issued_at"], payload["expires_at"],
             payload["seats"], token, now.isoformat(), now.isoformat()))
        return {"license_id": lic_id, "subject": subject, "plan": "trial",
                "issued_at": payload["issued_at"], "expires_at": payload["expires_at"],
                "seats": payload["seats"], "revoked": 0, "token": token}


def get_license(license_id: str) -> dict | None:
    db.ensure_schema()
    with db.get_conn() as conn:
        r = conn.execute("SELECT * FROM licenses WHERE license_id=?", (license_id,)).fetchone()
    return dict(r) if r else None


def list_licenses() -> list[dict]:
    db.ensure_schema()
    with db.get_conn() as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM licenses ORDER BY created_at DESC")]
    now = _now()
    for r in rows:                                   # attach live state (active/grace/expired)
        r["status"] = core.status(r, now)["state"] if not r["revoked"] else "revoked"
    return rows


def set_plan(license_id: str, plan: str, days: int | None = None) -> dict | None:
    """Change a license's plan and RE-ISSUE a fresh signed token."""
    db.ensure_schema()
    row = get_license(license_id)
    if row is None:
        return None
    now = _now()
    if plan == "subscription":
        expires = (now + _dt.timedelta(days=days or 365)).isoformat()
    else:                                            # trial (re-start or extend)
        expires = (now + _dt.timedelta(days=days or core.TRIAL_DAYS)).isoformat()
    payload = {"license_id": license_id, "subject": row["subject"], "plan": plan,
               "issued_at": now.isoformat(), "expires_at": expires,
               "seats": row["seats"], "key_version": core.KEY_VERSION}
    token = core.issue(payload, keys.signing_key())
    with db.get_conn() as conn:
        conn.execute("UPDATE licenses SET plan=?, expires_at=?, token=?, revoked=0, "
                     "updated_at=? WHERE license_id=?",
                     (plan, expires, token, now.isoformat(), license_id))
    return get_license(license_id)


def revoke(license_id: str) -> bool:
    db.ensure_schema()
    with db.get_conn() as conn:
        cur = conn.execute("UPDATE licenses SET revoked=1, updated_at=? WHERE license_id=?",
                           (_iso(), license_id))
    return cur.rowcount > 0


# ── installs (heartbeat receiver) ──────────────────────────────────────────
_INSTALL_FIELDS = ("install_id", "license_id", "plan", "seats", "version")


def record_heartbeat(payload: dict) -> dict:
    """Upsert an install from a METADATA-ONLY heartbeat. Ignores unexpected fields
    (never stores prompts/customer data). Returns the license's current state."""
    db.ensure_schema()
    p = {k: payload.get(k) for k in _INSTALL_FIELDS}   # whitelist — drop anything else
    if not p["install_id"] or not p["license_id"]:
        raise ValueError("install_id and license_id are required")
    now = _iso()
    with db.get_conn() as conn:
        conn.execute(
            "INSERT INTO installs (install_id,license_id,plan,seats,version,first_seen,"
            "last_seen,heartbeat_count) VALUES (?,?,?,?,?,?,?,1) "
            "ON CONFLICT(install_id) DO UPDATE SET license_id=excluded.license_id, "
            "plan=excluded.plan, seats=excluded.seats, version=excluded.version, "
            "last_seen=excluded.last_seen, heartbeat_count=heartbeat_count+1",
            (p["install_id"], p["license_id"], p["plan"], p["seats"], p["version"], now, now))
    lic = get_license(p["license_id"])
    if lic is None:
        return {"known": False, "state": "unknown", "revoked": False}
    st = core.status(lic, _now())
    return {"known": True, "plan": lic["plan"], "state": st["state"],
            "days_left": st["days_left"], "revoked": bool(lic["revoked"])}


def list_installs() -> list[dict]:
    db.ensure_schema()
    with db.get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM installs ORDER BY last_seen DESC")]
