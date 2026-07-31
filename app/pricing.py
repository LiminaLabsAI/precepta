"""Pricing — the single, versioned source of truth for per-token prices (TD-001).

Every dollar figure in the product (budgets, cache/compression savings, routing
cost signal) is `tokens x price_per_token`. That price lives here, in one
admin-maintained, date-versioned table — never hardcoded in an adapter.

Lookup order for `price_of(backend, model)`:
  1. `model_prices` row for (backend, model) — newest `effective_date <= as_of`
  2. `model_prices` row for (backend, '')  — the backend default
  3. registry default (legacy hardcoded price on the adapter)
  4. $0 **with `missing=True`** — an unknown price is surfaced, never a silent $0.

`as_of` lets historical reports use the price that was in effect then.
"""
from __future__ import annotations

import datetime as _dt

from .db import get_conn
from .ports import Price
from .adapters.model.registry import get_registry

_DDL = """
CREATE TABLE IF NOT EXISTS model_prices (
    backend        TEXT NOT NULL,
    model          TEXT NOT NULL DEFAULT '',   -- '' = backend default
    input_per_1m   REAL NOT NULL,
    output_per_1m  REAL NOT NULL,
    currency       TEXT NOT NULL DEFAULT 'USD',
    effective_date TEXT NOT NULL,               -- ISO date; enables versioning
    source         TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL,
    created_by     TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (backend, model, effective_date)
)
"""

# Seed values (the previously-hardcoded registry prices, now owned data).
# Local in-boundary backends are explicitly $0 = "known free", not "unknown".
_SEED = {
    ("ollama", ""): (0.0, 0.0, "local — in-boundary, no per-token cost"),
    ("vllm", ""): (0.0, 0.0, "local — your GPU, no per-token cost"),
    ("neysa", ""): (0.30, 0.30, "Neysa list price (seed — verify & update)"),
    ("hf", ""): (0.60, 0.60, "HF dedicated endpoint (seed — verify & update)"),
}
_SEED_DATE = "2026-07-01"


def _today() -> str:
    return _dt.datetime.now(_dt.UTC).date().isoformat()


def ensure_table() -> None:
    with get_conn() as conn:
        conn.execute(_DDL)


def seed_defaults() -> None:
    """Insert the seed prices once (idempotent) so known backends have real prices."""
    ensure_table()
    now = _dt.datetime.now(_dt.UTC).isoformat()
    with get_conn() as conn:
        for (backend, model), (pin, pout, src) in _SEED.items():
            exists = conn.execute(
                "SELECT 1 FROM model_prices WHERE backend=? AND model=?",
                (backend, model)).fetchone()
            if not exists:
                conn.execute(
                    "INSERT INTO model_prices (backend,model,input_per_1m,output_per_1m,"
                    "currency,effective_date,source,created_at,created_by) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (backend, model, pin, pout, "USD", _SEED_DATE, src, now, "seed"))


def price_info(backend: str, model: str = "", as_of: str | None = None) -> tuple[Price, dict]:
    """Return (Price, meta) where meta = {source, effective_date, missing, currency}."""
    ensure_table()
    as_of = as_of or _today()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM model_prices WHERE backend=? AND model IN (?, '') "
            "AND effective_date<=? ORDER BY (model=?) DESC, effective_date DESC LIMIT 1",
            (backend, model, as_of, model)).fetchall()
    if rows:
        r = rows[0]
        return (Price(r["input_per_1m"], r["output_per_1m"]),
                {"source": r["source"], "effective_date": r["effective_date"],
                 "currency": r["currency"], "missing": False})
    # fallback: legacy registry default (hardcoded on the adapter)
    be = get_registry().get(backend)
    if be is not None:
        p = be.price(model)
        if p.input_per_1m or p.output_per_1m:
            return p, {"source": "registry-default", "effective_date": None,
                       "currency": "USD", "missing": False}
    # unknown — surface it, never a silent $0
    return Price(0.0, 0.0), {"source": "none", "effective_date": None,
                             "currency": "USD", "missing": True}


def price_of(backend: str, model: str = "", as_of: str | None = None) -> Price:
    """Just the Price (the PricingPort surface used by the router/gateway)."""
    return price_info(backend, model, as_of)[0]


def list_prices() -> list[dict]:
    """All current price rows (newest effective_date per backend/model), for the admin UI."""
    ensure_table()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT backend, model, input_per_1m, output_per_1m, currency, "
            "effective_date, source FROM model_prices ORDER BY backend, model, effective_date DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def upsert_price(backend: str, model: str, input_per_1m: float, output_per_1m: float,
                 *, source: str = "", currency: str = "USD",
                 effective_date: str | None = None, created_by: str = "") -> dict:
    """Add/replace a price row (a new effective_date creates a new version)."""
    ensure_table()
    eff = effective_date or _today()
    now = _dt.datetime.now(_dt.UTC).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO model_prices (backend,model,input_per_1m,output_per_1m,currency,"
            "effective_date,source,created_at,created_by) VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(backend,model,effective_date) DO UPDATE SET "
            "input_per_1m=excluded.input_per_1m, output_per_1m=excluded.output_per_1m, "
            "currency=excluded.currency, source=excluded.source",
            (backend, model or "", float(input_per_1m), float(output_per_1m), currency,
             eff, source, now, created_by))
    return {"backend": backend, "model": model or "", "input_per_1m": float(input_per_1m),
            "output_per_1m": float(output_per_1m), "currency": currency,
            "effective_date": eff, "source": source}


def cost_of(backend: str, model: str, tokens_in: int, tokens_out: int,
            as_of: str | None = None) -> float:
    """Real USD cost for a call: (tokens/1e6) x per-1M price. 0.0 for local/free."""
    p = price_of(backend, model, as_of)
    return (max(tokens_in, 0) / 1_000_000.0) * p.input_per_1m + \
           (max(tokens_out, 0) / 1_000_000.0) * p.output_per_1m
