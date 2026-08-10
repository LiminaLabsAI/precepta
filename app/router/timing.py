"""Enforcement timing (Phase 12) — *when* each governed check runs.

Competitor-parity item (LiteLLM has pre-/during-/post-call guardrail modes). A
check declares whether it runs before the model call (pre), around it (during),
or on the result (post). This is the config scaffold the policy layer and the
Traces view read; the pipeline already runs the checks in this order.
"""
from __future__ import annotations

PRE = "pre-call"
DURING = "during-call"
POST = "post-call"
_STAGES = (PRE, DURING, POST)

# default stage for each governed check
_STAGE: dict[str, str] = {
    "firewall": PRE,
    "sensitivity": PRE,
    "policy": PRE,
    "routing": PRE,
    "cache": PRE,
    "compression": DURING,
    "inference": DURING,
    "output": POST,
    "toxicity": POST,
}


def stages() -> tuple[str, ...]:
    return _STAGES


def stage_of(check: str) -> str | None:
    return _STAGE.get(check)


def checks_at(stage: str) -> list[str]:
    return sorted(k for k, v in _STAGE.items() if v == stage)


def set_stage(check: str, stage: str) -> None:
    if stage not in _STAGES:
        raise ValueError(f"unknown stage '{stage}' (expected one of {_STAGES})")
    _STAGE[check] = stage


def as_map() -> dict[str, str]:
    """A copy of the current check→stage map (for the config/Traces UI)."""
    return dict(_STAGE)
