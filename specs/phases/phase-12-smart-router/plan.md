---
type: Phase Plan
phase: 12
name: smart-router
---

# Phase 12 — Smart Router · Implementation Plan

Execution order:
`Group 0 → (Groups 1 + 2 in parallel) → Group 3 → Group 4 → Group 5`

- **Group 0** blocks everything (contracts + migrations).
- **Groups 1 + 2** are independent (brain/resolver vs targets) — parallel candidates.
- **Group 3** wires into the governed pipeline (sequential).
- **Group 4** is the read-only workflow view (sequential, after wiring).
- **Group 5** verifies (sequential, last).

> DIP throughout: the core depends only on ports; a new model, agent, or store is a new
> adapter, never a core change. Governance runs **before** the router — always.

---

## Group 0 — Contracts, ports, migrations
**Sequential.** Blocks all. Commit: `feat(router): ports + contracts + backend id migration`

- `app/router/ports.py`: `RouterBrain`, `TargetResolver`, `RouteTarget` (`InferenceTarget` | `AgentTarget`).
- `RouteDecision {target, intent, reason, confidence, inferred}`.
- Intent registry — open list (cheapest / smartest / accuracy / …); new intent = one row.
- `AgentTraceContract`: `TargetResult {output, status, reason, steps[]}`.
- **BUG-001 migration:** backend **unique id** (slug of Name) as the key across
  registry/store/pricing/routing/scopes — two same-provider backends coexist.

## Group 1 — Brain + resolver
**Parallel with Group 2.** Commit: `feat(router): model brain + intent resolver`

- `ModelRouterBrain` adapter — single classify call; **in-boundary** target
  (Console router_config → `.env` → Ollama); fail-soft.
- **Confidence floor** — weak intent match discarded → treated as hard (bump min-tier);
  reason printed; router inferences flagged `inferred: true`.
- `TargetResolver` (config, not a prompt): filter targets by policy (force_model /
  min_tier / sensitive→approved-only) → score `quality − cost − latency + warm-bonus`
  → pick; **"no target" → blocked + traced**.
- **Warm-prefix bonus** as a scoring input (prefer a model that already has the opening loaded).

## Group 2 — Targets (models + agents)
**Parallel with Group 1.** Commit: `feat(router): inference + agent targets`

- `InferenceTarget` via **LiteLLM** adapter: `litellm.completion(model, api_base, api_key)`;
  **MIT core only** (never `enterprise/`); **in-boundary allowlist** — explicit `api_base`,
  no provider fallthrough. Gives **many providers + load balancing** across model copies.
- Keep existing thin adapters working behind the same port (two-way door).
- `AgentTarget`: dispatch to an in-premise agent; **timeout + fail-soft**; agent's own
  model calls **re-enter Precepta**; **capture** the sub-trace per `AgentTraceContract`
  (missing → honest "agent reported no reasoning").
- **Usage-by-tool/agent** captured on dispatch (shown later in Traces).

## Group 3 — Governance-first wiring
**Sequential.** Commit: `feat(router): wire into governed pipeline`

- Insert the router **after** firewall + policy in `governed_chat`:
  `firewall → policy → ROUTER → cache → compression → dispatch → output-firewall`.
- Cache/compression apply to **model targets only**; **off by default** for agents.
- **Enforcement-timing modes** — each safety check declares pre-call / during-call /
  post-call (config).
- **Toxicity output filter** in the output firewall.
- The `RouteDecision` is **audited** (intent · target · why · inferred · rule that fired).

## Group 4 — Read-only workflow view
**Sequential.** Commit: `feat(console): read-only workflow view`

- Console **Workflow** screen: render the governed path + routing rules **auto-generated
  from the live config** (a projection — never a second source).
- Governance rails shown as fixed; routing layer shown as the composable middle (read-only for now).
- Browser-validate (no JS errors); the view matches the live config.

## Group 5 — Verification
**Sequential.** Commit: `test(router): unit + eval + live`

- Unit: brain + floor, resolver filter/score/pick, targets (model + agent + timeout),
  BUG-001 coexistence, enforcement modes, toxicity filter, fail-soft.
- **Lock the router eval set** — the 7 scenarios (cheap→small, min-tier forced, exact
  cache, approx cache, confidence-floor catch, sensitive→guarded) in `tests/benchmarks`
  (Rule 11 — freeze before any optimization).
- **Live end-to-end:** a tagged request routes to a model **and** to an agent, governed
  first, audited with a plain reason; workflow view reflects it.
- OSS: router package builds standalone under Apache-2.0; core imports no commercial code.
- Update HANDOFF + changelog; mark FEAT-013/014/015/020 + BUG-001 resolved.

---

## Deferred out of this phase (tracked)
- **Traces / phase-11:** live request log · bill-back (cost by team/app) · render agent sub-traces · learning-loop reward capture.
- **Deploy phase (FEAT-009):** easy-install packages (Helm/offline) · auto-provision users · move router model in-boundary (TD-009).
- **Phase 13:** the workflow **builder** (editable canvas → writes resolver config, validation-gated).
- **Backlog:** per-app speed limits (ENH-003) · faster gateway (ENH-008).
