# Open-core boundary — the Router (Apache-2.0)

Phase 12 decision (brainstorm 2026-08-09): the **router mechanics + hooks** are
intended to be open-sourced under **Apache-2.0**; the governance / audit /
attestation / sovereignty implementation stays commercial. The physical repo
split is deferred — for now the boundary is enforced *logically* (and by a test:
`tests/test_phase12_router_eval.py::test_oss_router_core_has_no_commercial_imports`).

## In the OSS boundary (Apache-2.0 candidates)
Pure routing mechanics — no imports of governance/sovereign/audit code:

- `intent_catalog.py` — the open intent registry
- `scoring.py` — the resolver (intent → scored candidates → target) + confidence floor
- `targets.py` — the `RouteTarget` contract + Agent Trace Contract
- `target_adapters.py` — `InferenceTarget` (LiteLLM, lazy) + `AgentTarget`
- `smart.py` — the two-stage decision
- `timing.py` — enforcement-timing map

The router depends only on ports and injected functions (pricing, latency,
registry) — never on the commercial side. That's what makes it extractable.

## Stays commercial (NOT open-sourced)
- `app/governance/*` (firewall, policy, sensitivity, toxicity)
- `app/sovereign/*` + the Sovereignty Attestation
- `app/adapters/audit/*` (tamper-evident chain), `app/adapters/authz/*`
- the Console, the learning loop, per-team keys

## Rule
Precepta depends on the OSS router, **never the reverse**. A commercial import
appearing in any file above is a boundary violation — the test fails.
