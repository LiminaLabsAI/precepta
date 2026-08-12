"""Ports (interfaces) for the control-plane domain core — the DIP boundary.

The domain never imports a concrete provider, store, or cloud. It depends only
on these Protocols; adapters (Phase 1+) implement them. Domain value types live
here too so both sides share one vocabulary.

See DESIGN.md §2 (ports & adapters) — this file is that table, as code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable, Callable, Any


# ─────────────────────────── domain value types ───────────────────────────

@dataclass(frozen=True)
class Price:
    """Per-1M-token pricing for a model (used by cheapest routing / cost-gating)."""
    input_per_1m: float
    output_per_1m: float


@dataclass(frozen=True)
class Principal:
    """An authenticated caller (result of authN)."""
    subject: str            # stable id / email / key name
    role: str               # "admin" | "user" | "auditor"
    display_name: str = ""
    team: str = ""          # org/team for attribution + scoping (Phase 7/9)
    scope: str = "inference"  # "inference" | "manage:ro" | "manage:rw" (Phase 15)


@dataclass
class PolicyCheckContext:
    """Input to governance evaluation for a single request."""
    action_type: str                 # "chat.completion" | "http_request" | "*" | ...
    principal: Principal | None = None
    backend: str | None = None       # resolved backend name, e.g. "vllm"
    in_boundary: bool = True
    url: str | None = None
    tokens_requested: int | None = None
    has_data_tag: bool = False
    workflow_id: str | None = None
    run_id: str | None = None
    step_name: str | None = None
    agent_id: str | None = None      # the agent/tool making the call (TD-005)
    end_user: str | None = None      # OpenAI `user` — the human the agent acts for


@dataclass(frozen=True)
class Decision:
    """Outcome of a policy evaluation. effect ∈ allow|warn|block."""
    effect: str
    reason: str = ""
    policy_id: str | None = None


@dataclass(frozen=True)
class RoutePlan:
    """What the router brain decided for an `auto`/intent request."""
    backend: str
    model: str
    technique: str = "passthrough"   # ReasoningPort adapter name
    reason: str = ""


@dataclass
class AuditEvent:
    """One row destined for the tamper-evident audit chain."""
    event_type: str
    actor: str
    resource: str
    action: str
    outcome: str
    metadata: dict[str, Any] = field(default_factory=dict)


# ─────────────────────────────── the ports ────────────────────────────────

@runtime_checkable
class ModelBackendPort(Protocol):
    """A place a model can run (Ollama, vLLM, Neysa, HF, …). Layer 1."""
    name: str
    in_boundary: bool
    def litellm_model(self, model: str) -> str: ...
    def price(self, model: str) -> Price: ...
    def health(self, timeout: float = 3.0) -> bool: ...


@runtime_checkable
class RouterBrainPort(Protocol):
    """Decides (backend × technique) for an auto/intent request. Swappable."""
    name: str
    def decide(self, query: str, intent: str, ctx: PolicyCheckContext,
               budget: dict | None) -> RoutePlan: ...


@runtime_checkable
class ReasoningPort(Protocol):
    """A reasoning technique. Each inner model call re-enters the governed
    pipeline via the injected `call_model`, keeping the sovereign loop closed."""
    name: str
    def estimate_calls(self, ctx: PolicyCheckContext) -> int: ...
    def run(self, messages: list[dict], ctx: PolicyCheckContext,
            call_model: Callable[[list[dict]], Any]) -> Any: ...


@runtime_checkable
class PolicyStorePort(Protocol):
    """CRUD + lookup over governance policies."""
    def list_policies(self) -> list[dict]: ...
    def enabled_for(self, action_type: str) -> list[dict]: ...


@runtime_checkable
class AuditSinkPort(Protocol):
    """Append-only, tamper-evident audit log."""
    def append(self, event: AuditEvent) -> str: ...
    def verify_chain(self) -> bool: ...


@runtime_checkable
class SecretStorePort(Protocol):
    """Where provider keys live — never plaintext in the DB."""
    def get(self, ref: str) -> str | None: ...
    def put(self, name: str, value: str) -> str: ...


@runtime_checkable
class InfraVisibilityPort(Protocol):
    """Live infra snapshot (GPU/VRAM/throughput/latency) — integrated, not built."""
    def snapshot(self) -> list[dict]: ...


@runtime_checkable
class IdentityPort(Protocol):
    """authN — proves *who* the caller is (the login)."""
    def authenticate(self, token: str) -> Principal | None: ...


@runtime_checkable
class AuthorizationPort(Protocol):
    """authZ — decides *what* a principal may do (roles/budgets)."""
    def can(self, principal: Principal, action: str, resource: str) -> bool: ...
    def budget(self, principal: Principal) -> dict: ...


class PricingPort(Protocol):
    """The single, versioned source of truth for per-token prices (TD-001).

    Every $ figure = tokens x price. `as_of` (ISO date) selects the price in
    effect then, so historical reports stay reproducible.
    """
    def price_of(self, backend: str, model: str = "", as_of: str | None = None) -> Price: ...
    def cost_of(self, backend: str, model: str, tokens_in: int, tokens_out: int,
                as_of: str | None = None) -> float: ...


__all__ = [
    "Price", "Principal", "PolicyCheckContext", "Decision", "RoutePlan", "AuditEvent",
    "ModelBackendPort", "RouterBrainPort", "ReasoningPort", "PolicyStorePort",
    "AuditSinkPort", "SecretStorePort", "InfraVisibilityPort", "IdentityPort",
    "AuthorizationPort", "PricingPort",
]
