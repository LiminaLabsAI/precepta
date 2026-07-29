"""Team scopes & budgets (Phase 9) — open-guard-style authorization.

Beyond role, a team can be restricted to specific backends and given a daily
token budget. Stored in SQLite; enforced in the request path for explicit routes
(and reported via budget()).
"""
from __future__ import annotations

import datetime as _dt

from ...db import get_conn
from ...ports import Principal

_DDL = """
CREATE TABLE IF NOT EXISTS team_scopes (
    team              TEXT PRIMARY KEY,
    allowed_backends  TEXT,
    max_tokens_per_day INTEGER DEFAULT 0,
    created_at        TEXT NOT NULL
)
"""


def ensure_table() -> None:
    with get_conn() as conn:
        conn.execute(_DDL)


def set_scope(team: str, allowed_backends: list[str] | None, max_tokens_per_day: int = 0) -> None:
    ensure_table()
    ab = ",".join(a.strip() for a in (allowed_backends or []) if a.strip())
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO team_scopes (team,allowed_backends,max_tokens_per_day,created_at) "
            "VALUES (?,?,?,?) ON CONFLICT(team) DO UPDATE SET "
            "allowed_backends=excluded.allowed_backends, max_tokens_per_day=excluded.max_tokens_per_day",
            (team, ab, int(max_tokens_per_day), _dt.datetime.now(_dt.UTC).isoformat()))


def get_scope(team: str) -> dict | None:
    if not team:
        return None
    ensure_table()
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM team_scopes WHERE team=?", (team,)).fetchone()
    return dict(row) if row else None


def list_scopes() -> list[dict]:
    ensure_table()
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM team_scopes").fetchall()]


def check_backend(principal: Principal, backend_name: str) -> str | None:
    """Return a block reason if the principal's team may not use this backend."""
    sc = get_scope(getattr(principal, "team", "") or "")
    if not sc:
        return None
    allowed = [a for a in (sc.get("allowed_backends") or "").split(",") if a]
    if allowed and backend_name not in allowed:
        return (f"team {principal.team!r} is scoped to {allowed} and may not use "
                f"backend {backend_name!r}")
    return None


def budget(principal: Principal) -> dict:
    sc = get_scope(getattr(principal, "team", "") or "")
    return {"max_tokens_per_day": sc["max_tokens_per_day"] if sc else 0}
