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
    """Cost + tokens spent by a key today and this month (org-timezone windows)."""
    ensure_table()
    day0, mon0 = _window_starts()
    with get_conn() as conn:
        d = conn.execute("SELECT COALESCE(SUM(cost_usd),0) c, COALESCE(SUM(billable_tokens),0) t "
                         "FROM key_usage WHERE key_name=? AND ts>=?", (key_name, day0)).fetchone()
        m = conn.execute("SELECT COALESCE(SUM(cost_usd),0) c, COALESCE(SUM(billable_tokens),0) t "
                         "FROM key_usage WHERE key_name=? AND ts>=?", (key_name, mon0)).fetchone()
    return {"day": round(d["c"], 6), "month": round(m["c"], 6),
            "tokens_day": int(d["t"]), "tokens_month": int(m["t"])}


_ADJ = {"day": "daily", "month": "monthly"}


def _fire(key_name: str, level: str, window: str, metric: str, capstr: str, usedstr: str) -> None:
    from . import notifications
    adj = _ADJ.get(window, window)
    verb = "blocked at" if level == "block" else "nearing"
    title = f"Key '{key_name}' {verb} its {adj} {metric} cap"
    tail = ("requests are now blocked until reset." if level == "block"
            else "warning threshold (80%) reached.")
    notifications.notify(
        f"budget_{level}", "critical" if level == "block" else "warning", title,
        f"{adj.capitalize()} {metric} usage {usedstr} of {capstr} — {tail}")


def check(key_name: str, projected_cost: float = 0.0, projected_tokens: int = 0,
          grace_pct: int = _DEFAULT_GRACE_PCT) -> dict:
    """Most-restrictive cost+token daily/monthly cap check. effect ∈ allow|warn|block.

    Fires a (deduped) bell notification on warn/block.
    """
    from .adapters.identity.keys import get_key_meta
    meta = get_key_meta(key_name)
    if not meta:
        return {"effect": "allow"}
    sp = spend(key_name)
    # (metric, window) → (cap, already-spent, projected, formatter)
    def money(v): return f"${v:.2f}"
    def toks(v): return f"{int(v):,} tokens"
    checks = [
        ("cost", "day", meta["cost_cap_daily"] or 0, sp["day"], projected_cost, money, lambda v: f"${v:.4f}"),
        ("cost", "month", meta["cost_cap_monthly"] or 0, sp["month"], projected_cost, money, lambda v: f"${v:.4f}"),
        ("token", "day", meta["token_cap_daily"] or 0, sp["tokens_day"], projected_tokens, toks, toks),
        ("token", "month", meta["token_cap_monthly"] or 0, sp["tokens_month"], projected_tokens, toks, toks),
    ]
    result = {"effect": "allow", "spend": sp}
    for metric, window, cap, used, proj, capfmt, usedfmt in checks:
        if not cap or cap <= 0:
            continue
        after = used + max(proj, 0)
        if after >= cap:
            _fire(key_name, "block", window, metric, capfmt(cap), usedfmt(used))
            return {"effect": "block", "metric": metric, "window": window, "spend": sp,
                    "reason": f"{_ADJ[window]} {metric} cap {capfmt(cap)} reached (used {usedfmt(used)})"}
        if after >= cap * (grace_pct / 100.0) and result["effect"] == "allow":
            _fire(key_name, "warn", window, metric, capfmt(cap), usedfmt(used))
            result = {"effect": "warn", "metric": metric, "window": window, "spend": sp,
                      "reason": f"{_ADJ[window]} {metric} at {int(after / cap * 100)}% of {capfmt(cap)}"}
    return result
