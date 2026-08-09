---
type: Phase Overview
phase: 12
name: smart-router
status: planned
created: 2026-08-09
backlog: FEAT-013, FEAT-014, FEAT-015, FEAT-020, BUG-001
runs-before: phase-11-traces
---

# Phase 12 — Smart Router (+ read-only workflow view)

## Goal
Every request — from an agent, the API, or an agent's prompt — is understood by
**intent** and routed to the right target (an inference **model** *or* an in-premise
**agent**), **governed first**, and shown as a **read-only workflow** the operator can
see. Ship the router as an **open-core** package.

> The routing brain is a **model** that only reads *what the caller wants*. Plain,
> auditable **rules** pick the actual target. Governance always runs first.

## Problem statement
Requests arrive from many places with different goals (cheapest, smartest, accuracy).
Today there is no single, intent-aware, **governed** path that can send a request to a
model *or* an agent while proving nothing left the boundary — and the operator can't
*see* how routing works. Competitors (LiteLLM) already do cost-routing; our edge must be
**sovereignty + readable reasoning + governed agents**, not routing alone.

## Who is suffering · Why now
- **Compliance/security leads** — need every route decision governed and provable.
- **Platform/dev teams** — need one intent-aware entry point for models *and* agents.
- **The founder** — needs a demoable, differentiated router (not a me-too gateway).
- **Why now:** the governed pipeline exists; the router is the missing brain that ties
  sources → governance → targets, and the wedge against LiteLLM.

## Key decisions (locked in brainstorm 2026-08-09)
| Decision | Choice |
|---|---|
| Router brain | A **model** (single classify call), behind a `RouterBrain` port |
| Routing shape | **Two-stage (Option B):** brain picks **intent** → resolver maps intent→target (config) |
| Targets | One `RouteTarget` socket: `InferenceTarget` **and** `AgentTarget` |
| Inference dispatch | **LiteLLM** adapter (MIT core only), **in-boundary allowlist** enforced |
| Agent trace | **Mandate** the contract `{output, status, reason, steps[]}` (third-party degrades honestly) |
| Agent egress | Agent's own model calls **re-enter Precepta** (governed) |
| Cache/compress on agents | **Off by default** (opt-in for read-only agents) |
| Order | Governance runs **before** routing (unchanged) |
| Open-core | Router mechanics + governance **hooks** open (Apache-2.0); governance impl stays commercial; **carve into a package** first |
| Router model | Right-size (small model for intent); **in-boundary** in production (TD-009) |

## Positioning correction (from competitor research)
Cost-routing is **table stakes** (LiteLLM has it). Do **not** headline "smart router."
Headline: **sovereign control plane with observability that never leaves your network.**
Routing is a feature; **governed agents + in-boundary reasoning-traces** are the moat.

## Competitor parity — "must-add" items in THIS phase
(From the LiteLLM neck-to-neck list; the rest are split to Traces / Deploy / backlog.)
- Work with many more models out of the box (via the LiteLLM adapter)
- Spread load across copies of a model (load balancing)
- Track usage by **tool and agent** (capture here; shown in Traces)
- Choose **when** each safety check runs — before / during / after the model call
- Toxic-content filter (output guardrail)

## Scope
**In:** the ports/contracts; the model brain + confidence floor; the resolver + scoring
(`quality − cost − latency + warm-bonus`); LiteLLM inference adapter (allowlist);
`AgentTarget` (dispatch + timeout + fail-soft + egress re-entry + sub-trace **capture**);
BUG-001 unique-id onboarding fix; governance-first wiring; enforcement-timing modes;
toxicity output filter; load balancing; usage-by-tool/agent capture; the **read-only
workflow view**; the **locked router eval set** (7 scenarios); the OSS package boundary.

**Out (this phase):**
- The workflow **editor/builder** (→ Phase 13).
- **Rendering** agent sub-traces + the live request log + bill-back in the UI (→ Traces / phase-11).
- Model **hosting / deploy** + moving the router model in-boundary (→ deploy phase, TD-009).
- Model **retraining** (Traces captures reward; retrain is later).
- Auto-provisioning users, easy-install packages (→ deploy phase).

## Deliverables & verification
Test command: `./run.sh test` · no build.

| Deliverable | Verification |
|---|---|
| Ports + contracts (`RouterBrain`, `TargetResolver`, `RouteTarget`, `AgentTraceContract`) | Unit: a request produces a `RouteDecision` with intent + target + reason |
| Model brain + confidence floor | Unit: weak intent match is discarded → treated as hard |
| Resolver: filter-by-policy → score → pick | Unit: forbidden targets dropped; best chosen; "no target" → blocked |
| LiteLLM `InferenceTarget` (allowlist) | Test: dispatch to an in-boundary model; a non-allowlisted host is refused |
| `AgentTarget` (timeout, fail-soft, egress, sub-trace capture) | Test: agent result captured; timeout → traced failure; missing steps → honest note |
| BUG-001 unique-id onboarding | Test: two backends of the same provider coexist (no overwrite) |
| Enforcement-timing modes + toxicity filter | Test: a check fires at the configured stage; toxic output blocked |
| Read-only workflow view | **Browser-validated**: view matches live config; no JS errors |
| Locked router eval (7 scenarios) | `tests/benchmarks` green (Rule 11) |
| End-to-end | **Live**: a tagged request routes by intent to a model **and** to an agent, governed first, audited with a plain reason |

## Acceptance criteria
- A tagged request routes **by intent** to a model or agent, **governed first**, with an
  audited plain-language reason (router inferences labeled **"inferred"**).
- Governance cannot be bypassed by the router; blocks are still traced.
- An agent target's own model calls **re-enter Precepta**; the agent emits a sub-trace
  (or an honest "no reasoning reported").
- Two backends of the same provider **coexist** (BUG-001 closed).
- The read-only workflow view is a **projection of config** (no second source of truth).
- The 7-scenario router eval passes; the router package builds standalone under Apache-2.0.

## Pre-mortem (risks the plan must handle)
1. **Router becomes a governance bypass.** → router runs after firewall/policy; governance rails are fixed.
2. **LiteLLM leaks to a cloud provider.** → explicit `api_base` + in-boundary allowlist; no default fallthrough; MIT-only (never `enterprise/`).
3. **Agent hangs/fails in the hot path.** → timeout + fail-soft; partial/failed runs traced with a reason.
4. **Router model on a public endpoint (TD-009).** → dev only; in-boundary before any customer.
5. **"Smart router" reads as me-too.** → position on sovereignty + reasoning-traces, not routing.
6. **Phase too big.** → G0 blocks; G1–G4 independent; may split 12a (models+view) / 12b (agents) if a smaller sprint is wanted.
