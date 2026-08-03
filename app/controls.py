"""Runtime sovereignty controls — owner-gated overrides of the deploy config.

Sovereign Mode (in-boundary-only routing) is set at deploy time
(`PRECEPTA_SOVEREIGN`), but the **platform owner** may override it at runtime.
The override lives here and is consulted by every enforcement path — the
gateway's backend check, the router's candidate filter, the attestation, and
`/health` — so toggling it genuinely changes behaviour (unlike the old
display-only switch).

Turning it OFF disables the zero-egress guarantee, so the Console gates the
change behind a confirmation and writes it to the tamper-evident audit chain.

Scope note: **in-boundary routing** is the one control with independent runtime
enforcement. *Egress lock* is the same guarantee (egress is blocked by
in-boundary routing), so it mirrors this. *Audit logging* is always on
(non-disableable — it's the tamper-evident record). *Residency* is a declared
label edited under Data controls. `controls_state()` reports all four honestly.
"""
from __future__ import annotations

from .db import get_conn
from .settings import get_settings

_DDL = "CREATE TABLE IF NOT EXISTS runtime_controls (key TEXT PRIMARY KEY, value TEXT)"


def ensure_table() -> None:
    with get_conn() as conn:
        conn.execute(_DDL)


def _get(key: str) -> str | None:
    ensure_table()
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM runtime_controls WHERE key=?", (key,)).fetchone()
    return row["value"] if row is not None else None


def sovereign_enabled() -> bool:
    """Effective Sovereign Mode: the runtime override if set, else the deploy default."""
    v = _get("sovereign_mode")
    if v == "on":
        return True
    if v == "off":
        return False
    return get_settings().sovereign_mode


def sovereign_overridden() -> bool:
    return _get("sovereign_mode") in ("on", "off")


def set_sovereign(on: bool) -> None:
    ensure_table()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO runtime_controls (key,value) VALUES ('sovereign_mode',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", ("on" if on else "off",))


def clear_sovereign() -> None:
    ensure_table()
    with get_conn() as conn:
        conn.execute("DELETE FROM runtime_controls WHERE key='sovereign_mode'")


def controls_state() -> dict:
    from . import org
    sov = sovereign_enabled()
    return {
        "in_boundary": sov,          # real, runtime-toggleable
        "egress_lock": sov,          # same guarantee as in-boundary routing
        "audit": True,               # always on (non-disableable)
        "residency": org.get("data_residency"),
        "overridden": sovereign_overridden(),
        "deploy_default": get_settings().sovereign_mode,
    }
