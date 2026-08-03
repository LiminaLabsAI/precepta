"""Execution engine — runs a RoutePlan with failover, circuit breaking and
cost-gating. The injected `call_model` is where inner technique calls route
through backends (and, from Phase 3, through governance)."""
from __future__ import annotations

import time

import httpx

from ..ports import RoutePlan
from ..pricing import price_info
from ..adapters.reasoning import get_reasoner, Passthrough
from .brain import candidates
from .state import breaker, record_latency

_CALL_KW = ("temperature", "max_tokens", "top_p")


async def execute(plan: RoutePlan, messages: list[dict], registry: dict,
                  settings, *, budget_usd: float | None = None,
                  allowed: set[str] | None = None, **kw) -> tuple[dict, dict]:
    # `allowed` (governance filter for a sensitive auto request) also bounds
    # failover — a sensitive request can never fail over to an un-approved backend.
    from ..controls import sovereign_enabled
    cands = candidates(registry, sovereign_enabled(), allowed)
    if not cands:
        raise LookupError("no eligible in-boundary backend")
    # primary (plan.backend) first, then the rest as failover targets.
    ordered = sorted(cands, key=lambda c: 0 if c[0].name == plan.backend else 1)
    primary_be, _ = ordered[0]

    reasoner = get_reasoner(plan.technique)

    # ── cost-gating: technique multiplies calls; downgrade if over budget ──
    downgraded = False
    cost_est: float | None = None
    if budget_usd is not None:
        approx_out = kw.get("max_tokens") or 500
        price, pmeta = price_info(primary_be.name, plan.model)
        if pmeta["missing"]:
            price = primary_be.price(plan.model)   # adapter-declared price as fallback
        per_call = (approx_out / 1_000_000) * price.output_per_1m
        cost_est = reasoner.estimate_calls() * per_call
        if cost_est > budget_usd and not isinstance(reasoner, Passthrough):
            reasoner = Passthrough()
            downgraded = True
            cost_est = per_call

    call_count = {"n": 0}
    call_kw = {k: v for k, v in kw.items() if k in _CALL_KW and v is not None}

    async def call_model(msgs):
        last_err: Exception | None = None
        for be, mdl in ordered:
            b = breaker(be.name)
            if b.is_open():
                continue
            t0 = time.perf_counter()
            try:
                res = await be.complete(msgs, mdl or be.default_model, **call_kw)
                record_latency(be.name, (time.perf_counter() - t0) * 1000)
                b.record_success()
                call_count["n"] += 1
                return res, be.name
            except httpx.HTTPError as exc:
                b.record_failure()
                last_err = exc
                continue
        raise last_err or RuntimeError("all in-boundary backends unavailable")

    result, backend_used = await reasoner.run(messages, None, call_model)
    reason = plan.reason + (" [cost-gated → passthrough]" if downgraded else "")
    meta = {
        "backend_used": backend_used,
        "technique": reasoner.name,
        "reason": reason,
        "fell_over": backend_used != plan.backend,
        "calls": call_count["n"],
        "cost_estimate_usd": cost_est,
    }
    return result, meta
