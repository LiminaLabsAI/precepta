"""Route-target adapters (Phase 12, Group 2) — the concrete models & agents.

Two implementations of the ``RouteTarget`` contract:

  * ``InferenceTarget`` — a model call. The actual call is injected; a LiteLLM
    factory (``make_litellm_call``) is provided with a **lazy** import so LiteLLM
    is never required unless used, and an **in-boundary allowlist** so a
    misconfigured base URL can never fall through to a public cloud (the
    sovereignty guard lives in the pure ``enforce_boundary``).

  * ``AgentTarget`` — dispatch to an in-premise agent. Runs under a **timeout**,
    is **fail-soft** (an error/timeout becomes a ``failed`` TargetResult, never a
    raise), passes a **gateway** handle so the agent's own model calls re-enter
    Precepta (governed egress, D2), and captures the agent's returned reasoning
    as a **sub-trace** via ``parse_agent_result`` (honest when absent, D1).

Everything network-touching is injected/lazy, so the adapters are unit-testable
without LiteLLM, a real agent, or the network.
"""
from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from .targets import (TargetResult, RouteTarget, parse_agent_result,
                      STATUS_OK, STATUS_FAILED, KIND_INFERENCE, KIND_AGENT)


# ── sovereignty guard (pure, fully testable) ─────────────────────────────────

def host_of(api_base: str) -> str:
    """The hostname of a base URL (no scheme/port/path). '' if unparseable."""
    if not api_base:
        return ""
    parsed = urlparse(api_base if "://" in api_base else "http://" + api_base)
    return (parsed.hostname or "").lower()


def enforce_boundary(api_base: str, allowlist: set[str] | None) -> str:
    """Return the host if this base URL may be dispatched to, else raise.

    * An explicit ``api_base`` is always required — never fall through to a
      provider default (which could be a public cloud).
    * When ``allowlist`` is provided, the host MUST be in it. ``None`` means no
      host restriction is configured (still requires an explicit api_base).
    """
    host = host_of(api_base)
    if not host:
        raise ValueError("in-boundary allowlist: an explicit api_base is required "
                         "(no provider fallthrough)")
    if allowlist is not None and host not in allowlist:
        raise ValueError(f"in-boundary allowlist: host '{host}' is not permitted")
    return host


def make_litellm_call(model: str, api_base: str, api_key: str | None,
                      allowlist: set[str] | None):
    """Return an async call_fn that dispatches via LiteLLM, boundary-enforced.

    LiteLLM is imported lazily inside the call so it is an optional dependency.
    """
    async def _call(messages: list[dict], opts: dict):
        enforce_boundary(api_base, allowlist)          # raises if not permitted
        import litellm                                  # lazy, optional dependency
        return await litellm.acompletion(
            model=model, messages=messages, api_base=api_base,
            api_key=api_key, **{k: v for k, v in (opts or {}).items()
                                if k not in ("gateway",)})
    return _call


# ── InferenceTarget ──────────────────────────────────────────────────────────

class InferenceTarget:
    kind = KIND_INFERENCE

    def __init__(self, id: str, call_fn, *, in_boundary: bool = True,
                 model: str = "") -> None:
        self.id = id
        self.in_boundary = in_boundary
        self.model = model
        self._call = call_fn

    async def execute(self, messages: list[dict], opts: dict) -> TargetResult:
        try:
            out = await self._call(messages, opts or {})
            return TargetResult(output=out, status=STATUS_OK,
                                meta={"target": self.id, "model": self.model})
        except Exception as exc:            # fail-soft — never break the pipeline
            return TargetResult(output=None, status=STATUS_FAILED,
                                reason=f"inference failed: {exc}",
                                meta={"target": self.id})


# ── AgentTarget ───────────────────────────────────────────────────────────────

class AgentTarget:
    kind = KIND_AGENT

    def __init__(self, id: str, dispatch_fn, *, in_boundary: bool = True,
                 timeout: float = 30.0, gateway=None) -> None:
        self.id = id
        self.in_boundary = in_boundary
        self.timeout = timeout
        self._dispatch = dispatch_fn
        self._gateway = gateway            # governed callback: agent's model calls re-enter Precepta

    async def execute(self, messages: list[dict], opts: dict) -> TargetResult:
        # the gateway is handed to the agent so its own model calls stay governed (D2)
        call_opts = {**(opts or {}), "gateway": self._gateway}
        try:
            raw = await asyncio.wait_for(
                self._dispatch(messages, call_opts), timeout=self.timeout)
        except asyncio.TimeoutError:
            return TargetResult(output=None, status=STATUS_FAILED,
                                reason=f"agent timed out after {self.timeout}s",
                                meta={"target": self.id})
        except Exception as exc:            # fail-soft
            return TargetResult(output=None, status=STATUS_FAILED,
                                reason=f"agent error: {exc}", meta={"target": self.id})
        result = parse_agent_result(raw)    # honest sub-trace capture (D1)
        result.meta = {**result.meta, "target": self.id}
        return result
