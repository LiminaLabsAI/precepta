"""Metering — the ONE definition of how tokens & cost are counted (TD-002).

Budgets (FEAT-001), cache (FEAT-003) and compression (FEAT-005) all touch the
same token/cost counters. If each counted differently, the dashboards would
disagree. So they all call `meter()` here — defined once, up front.

Definitions (per request):
  - billable_tokens : tokens actually sent to + returned from the model,
                      AFTER compression. **0 on a cache hit** (no inference ran).
  - budget_charge   : billable_tokens x price  — the one money number a budget spends.
  - usage_volume    : 1 per request, counted for EVERY request incl. cache hits (visibility).
  - tokens_saved    : compression savings + cache-avoided tokens (for the savings view).

Canonical pipeline order (features slot in here, nowhere else):
  firewall -> policy -> budget pre-check -> cache -> compress -> inference
           -> measure actuals -> budget commit -> audit

Today only inference exists; cache/compression pass their extra fields when built.
"""
from __future__ import annotations

from . import pricing


def meter(backend: str, model: str, tokens_in: int, tokens_out: int, *,
          cache_hit: bool = False, original_tokens: int | None = None,
          compressed_tokens: int | None = None, as_of: str | None = None) -> dict:
    """Return {billable_tokens, budget_charge_usd, usage_volume, tokens_saved}."""
    billable_in = 0 if cache_hit else max(tokens_in or 0, 0)
    billable_out = 0 if cache_hit else max(tokens_out or 0, 0)
    billable_tokens = billable_in + billable_out

    # a cache hit ran no inference -> costs the budget nothing
    budget_charge = 0.0 if cache_hit else pricing.cost_of(
        backend, model, billable_in, billable_out, as_of)

    saved = 0
    if cache_hit and original_tokens:
        saved += max(original_tokens, 0)                       # tokens the model would have processed
    if original_tokens and compressed_tokens is not None:
        saved += max(original_tokens - compressed_tokens, 0)   # trimmed by compression

    return {
        "billable_tokens": billable_tokens,
        "budget_charge_usd": round(budget_charge, 6),
        "usage_volume": 1,
        "tokens_saved": saved,
    }
