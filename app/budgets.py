"""Per-key cost budgets — usage recording + daily/monthly cap enforcement (FEAT-001).

Spend is recorded per request (real cost from metering x pricing) into `key_usage`,
then checked against the key's daily/monthly USD caps. Window boundaries honor the
org timezone (Settings), so "today" resets at local midnight, not UTC.
"""
from __future__ import annotations

import datetime as _dt
import uuid
from zoneinfo import ZoneInfo

from .db import get_conn
from . import org

_DDL = """
CREATE TABLE IF NOT EXISTS key_usage (
    id              TEXT PRIMARY KEY,
    key_name        TEXT NOT NULL,
    team            TEXT DEFAULT '',
    billable_tokens INTEGER DEFAULT 0,
    cost_usd        REAL DEFAULT 0,
    ts              TEXT NOT NULL
)
"""

_DEFAULT_GRACE_PCT = 80


def ensure_table() -> None:
    with get_conn() as conn:
        conn.execute(_DDL)


def _tz() -> ZoneInfo:
    try:
        return ZoneInfo(org.get("timezone", "UTC") or "UTC")
    except Exception:
        return ZoneInfo("UTC")


def _window_starts() -> tuple[str, str]:
    """(day_start, month_start) as UTC-ISO, computed at local midnight in the org tz."""
    now = _dt.datetime.now(_tz())
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month = day.replace(day=1)
    return day.astimezone(_dt.UTC).isoformat(), month.astimezone(_dt.UTC).isoformat()


def record_usage(key_name: str, team: str, billable_tokens: int, cost_usd: float) -> None:
    if not key_name:
        return
    ensure_table()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO key_usage (id,key_name,team,billable_tokens,cost_usd,ts) "
            "VALUES (?,?,?,?,?,?)",
            (uuid.uuid4().hex, key_name, team or "", int(billable_tokens or 0),
             float(cost_usd or 0), _dt.datetime.now(_dt.UTC).isoformat()))


def spend(key_name: str) -> dict:
    """Cost spent by a key today and this month (org-timezone windows)."""
    ensure_table()
    day0, mon0 = _window_starts()
    with get_conn() as conn:
        d = conn.execute("SELECT COALESCE(SUM(cost_usd),0) c FROM key_usage "
                         "WHERE key_name=? AND ts>=?", (key_name, day0)).fetchone()["c"]
        m = conn.execute("SELECT COALESCE(SUM(cost_usd),0) c FROM key_usage "
                         "WHERE key_name=? AND ts>=?", (key_name, mon0)).fetchone()["c"]
    return {"day": round(d, 6), "month": round(m, 6)}


def check(key_name: str, projected_cost: float = 0.0,
          grace_pct: int = _DEFAULT_GRACE_PCT) -> dict:
    """Most-restrictive daily/monthly cost-cap check. effect ∈ allow|warn|block."""
    from .adapters.identity.keys import get_key_meta
    meta = get_key_meta(key_name)
    if not meta:
        return {"effect": "allow"}
    caps = {"day": meta["cost_cap_daily"] or 0, "month": meta["cost_cap_monthly"] or 0}
    sp = spend(key_name)
    result = {"effect": "allow", "spend": sp, "caps": caps}
    for window in ("day", "month"):
        cap = caps[window]
        if not cap or cap <= 0:
            continue
        after = sp[window] + max(projected_cost, 0)
        if after >= cap:
            return {"effect": "block", "window": window, "spend": sp, "caps": caps,
                    "reason": f"{window}ly cost cap ${cap:.2f} reached "
                              f"(spent ${sp[window]:.4f})"}
        if after >= cap * (grace_pct / 100.0) and result["effect"] == "allow":
            result = {"effect": "warn", "window": window, "spend": sp, "caps": caps,
                      "reason": f"{window}ly cost at {int(after / cap * 100)}% of "
                                f"${cap:.2f} cap"}
    return result
