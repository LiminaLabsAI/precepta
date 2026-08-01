"""Router quality eval harness (FEAT-006) — the locked scalar (Rule 11).

Drives the **real** routing path (`RouterBrain.decide` -> `engine.execute`) over
a frozen eval set, then scores each answer with an in-boundary judge. The single
scalar is **mean answer-quality (0..1)**; mean cost/req and p50 latency ride
along as guardrails so a router that buys quality with runaway cost/latency is
visible, not hidden (routing goal = balanced cost+speed).

LOCKED as `v1`. The eval set (`router_eval_v1.json`), the judge (`judge.py`), and
this aggregation are the evaluator. Do not mutate them to move a score — bump to
`v2` and re-baseline (Rule 11). Build the router loop AFTER this is committed.

`run_eval` takes an injected `judge` (and optional `brain`) so unit tests run
deterministically with stubs; the CLI (`__main__.py`) wires the live judge +
backends for the backend-real run.
"""
from __future__ import annotations

import json
import os
import statistics
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path

from app.router import engine
from app.router.brain import get_brain
from app.adapters.model.registry import get_registry
from app.settings import get_settings
from app import metering

EVAL_VERSION = "v1"
_EVAL_FILE = Path(__file__).with_name("router_eval_v1.json")
_MAX_TOKENS = 512


def load_cases() -> list[dict]:
    with _EVAL_FILE.open() as fh:
        return json.load(fh)["cases"]


def _answer_of(result: dict) -> str:
    try:
        return result["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        return ""


@dataclass
class CaseResult:
    id: str
    category: str
    backend_used: str
    technique: str
    quality: float
    cost_usd: float
    latency_ms: int
    tokens_in: int
    tokens_out: int
    reason: str
    answer: str


@dataclass
class EvalReport:
    version: str
    judge: str
    brain: str
    route_mode: str
    n: int
    scalar: float                       # mean answer-quality (0..1) — the number to move
    mean_cost_usd: float
    p50_latency_ms: int
    mean_latency_ms: int
    by_category: dict = field(default_factory=dict)
    cases: list = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            f"router-eval {self.version} · brain={self.brain} · route={self.route_mode} · judge={self.judge}",
            f"  SCALAR (mean quality): {self.scalar:.3f}   over {self.n} cases",
            f"  guardrails: mean_cost=${self.mean_cost_usd:.6f}/req · p50_latency={self.p50_latency_ms}ms",
        ]
        for cat, q in sorted(self.by_category.items()):
            lines.append(f"    {cat:<9} quality {q:.3f}")
        return "\n".join(lines)


async def run_eval(judge, *, brain=None, route_mode: str = "automatic",
                   cases: list[dict] | None = None,
                   registry_getter=get_registry) -> EvalReport:
    """Route each case for real, judge the answer, aggregate to the scalar."""
    cases = cases if cases is not None else load_cases()
    brain = brain or get_brain(os.environ.get("PRECEPTA_BRAIN", "rules"), registry_getter)
    settings = get_settings()
    reg = registry_getter()

    rows: list[CaseResult] = []
    for c in cases:
        query = c["prompt"]
        msgs = [{"role": "user", "content": query}]
        plan = brain.decide(query, route_mode)
        t0 = time.perf_counter()
        result, meta = await engine.execute(
            plan, msgs, reg, settings, temperature=0, max_tokens=_MAX_TOKENS)
        latency_ms = int((time.perf_counter() - t0) * 1000)

        answer = _answer_of(result)
        usage = result.get("usage") or {}
        t_in = int(usage.get("prompt_tokens") or 0)
        t_out = int(usage.get("completion_tokens") or 0)
        backend_used = meta["backend_used"]
        cost = metering.meter(backend_used, plan.model, t_in, t_out)["budget_charge_usd"]
        quality = float(judge.score(query, answer, c["reference"], c["rubric"]))

        rows.append(CaseResult(
            id=c["id"], category=c["category"], backend_used=backend_used,
            technique=meta["technique"], quality=quality, cost_usd=cost,
            latency_ms=latency_ms, tokens_in=t_in, tokens_out=t_out,
            reason=meta.get("reason", ""), answer=answer))

    qualities = [r.quality for r in rows] or [0.0]
    latencies = [r.latency_ms for r in rows] or [0]
    by_cat: dict[str, float] = {}
    for cat in {r.category for r in rows}:
        qs = [r.quality for r in rows if r.category == cat]
        by_cat[cat] = round(statistics.fmean(qs), 4)

    return EvalReport(
        version=EVAL_VERSION,
        judge=getattr(judge, "name", judge.__class__.__name__),
        brain=getattr(brain, "name", brain.__class__.__name__),
        route_mode=route_mode,
        n=len(rows),
        scalar=round(statistics.fmean(qualities), 4),
        mean_cost_usd=round(statistics.fmean([r.cost_usd for r in rows] or [0.0]), 6),
        p50_latency_ms=int(statistics.median(latencies)),
        mean_latency_ms=int(statistics.fmean(latencies)),
        by_category=by_cat,
        cases=[asdict(r) for r in rows],
    )
