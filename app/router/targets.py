"""Route targets (Phase 12) — one socket for models AND in-premise agents.

The router doesn't care whether it dispatches to an inference model or to an
agent: both satisfy ``RouteTarget``. This module defines that contract plus the
**Agent Trace Contract** — the ``TargetResult`` envelope an agent returns
(``output``, ``status``, ``reason``, ``steps``). ``parse_agent_result`` accepts
whatever an agent hands back and normalises it **honestly**: when an agent
reports no reasoning steps, we say so rather than inventing a workflow.

The concrete adapters (a LiteLLM ``InferenceTarget`` and a dispatching
``AgentTarget``) are built in Group 2; here we define only the shared shapes so
everything above and below depends on the contract, not the implementation (DIP).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

# status vocabulary for a dispatched target
STATUS_OK = "ok"
STATUS_FAILED = "failed"
STATUS_BLOCKED = "blocked"
_VALID_STATUS = {STATUS_OK, STATUS_FAILED, STATUS_BLOCKED}

# target kinds
KIND_INFERENCE = "inference"
KIND_AGENT = "agent"


@dataclass
class TargetResult:
    """What a dispatched target returns, normalised.

    ``output`` is the raw response (an OpenAI-style dict for a model, or an
    agent's result). ``steps`` is the agent's own reasoning sub-trace (empty for
    a plain model call, or when an agent reports nothing). ``reported_reasoning``
    is the honest flag the Traces UI uses.
    """
    output: Any
    status: str = STATUS_OK
    reason: str = ""
    steps: list[dict] = field(default_factory=list)
    reported_reasoning: bool = False
    meta: dict = field(default_factory=dict)


@runtime_checkable
class RouteTarget(Protocol):
    """A routing destination — a model or an agent. ``kind`` distinguishes them.

    ``execute`` is async and MUST NOT raise for an expected failure (timeout,
    agent error): it returns a ``TargetResult`` with ``status='failed'`` so the
    pipeline can trace it and fail soft.
    """
    id: str
    kind: str          # KIND_INFERENCE | KIND_AGENT
    in_boundary: bool

    async def execute(self, messages: list[dict], opts: dict) -> TargetResult: ...


def _coerce_steps(raw: Any) -> list[dict]:
    if not isinstance(raw, list):
        return []
    out: list[dict] = []
    for s in raw:
        if isinstance(s, dict):
            out.append(s)
        else:                       # tolerate a bare string step ("did X")
            out.append({"decision": str(s)})
    return out


def parse_agent_result(raw: Any) -> TargetResult:
    """Normalise whatever an agent returned into a ``TargetResult``. Never raises.

    Rules (honest by construction):
      * ``None`` → a failed result ("agent returned nothing").
      * a non-dict value → treated as the output, status ok, no steps.
      * a dict without our envelope keys → treated as the output (e.g. a raw
        completion), status ok, no steps.
      * an unknown status → coerced to ``ok`` (we don't guess failure).
      * missing/!list steps → ``[]`` and ``reported_reasoning=False`` with a
        note; a non-empty ``steps`` → ``reported_reasoning=True``.
    """
    if raw is None:
        return TargetResult(output=None, status=STATUS_FAILED,
                            reason="agent returned nothing", steps=[],
                            reported_reasoning=False)

    if not isinstance(raw, dict):
        return TargetResult(output=raw, status=STATUS_OK, reason="",
                            steps=[], reported_reasoning=False)

    envelope_keys = {"output", "status", "reason", "steps"}
    has_envelope = bool(envelope_keys & set(raw.keys()))
    if not has_envelope:
        # a raw response object (e.g. a completion dict) — treat as the output
        return TargetResult(output=raw, status=STATUS_OK, reason="",
                            steps=[], reported_reasoning=False)

    output = raw.get("output", raw)
    status = raw.get("status", STATUS_OK)
    if status not in _VALID_STATUS:
        status = STATUS_OK
    steps = _coerce_steps(raw.get("steps"))
    reported = len(steps) > 0
    reason = raw.get("reason") or ("" if reported else "agent reported no reasoning")
    return TargetResult(output=output, status=status, reason=reason, steps=steps,
                        reported_reasoning=reported)


def agent_reported_reasoning(result: TargetResult) -> bool:
    return bool(result.reported_reasoning and result.steps)
