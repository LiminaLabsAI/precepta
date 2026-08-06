---
type: Phase Overview
phase: 11
name: traces
status: planned
created: 2026-08-06
backlog: FEAT-010
---

# Phase 11 — Traces (request-lifecycle observability)

## Goal
Make Precepta's governance **visible and trustworthy**: a clear, reasoned workflow of
everything the guardrail does to a request from **ingress to egress** — per request
(Level 1) and stitched into **agent-run timelines** (Level 2) — so a privacy-sensitive
enterprise can *see* that their data is governed correctly and stays in-boundary.

> A guardrail you can't see is a guardrail you can't trust. This phase turns Precepta's
> invisible governance into **visible, explained evidence on every request**.

## Problem statement
Enterprises running AI on sensitive data **cannot see or verify what happens to that
data inside an AI gateway** — which model saw it, whether it left the network, what was
redacted, why a request was blocked/rerouted, why a model was chosen. Invisible
governance is indistinguishable from no governance: they can't trust it, debug it, or
prove compliance.

## Who is suffering · Why now
- **Compliance/security leads** at regulated (DPDP / privacy-sensitive) enterprises whose
  data legally cannot leave the network — they carry the risk and need proof.
- **Platform/dev teams** who need to understand *why* the guardrail acted.
- **The founder**, needing the guardrail's value legible in investor / design-partner demos.
- **Why now:** the guardrail machinery is built (Phases 4–7) — it makes these decisions on
  every request; the data exists but isn't shown. Investors named traces as the missing
  piece — it's the demonstration of everything already built, and the proof of the
  "runtime guardrail platform" positioning.

## Key decisions
| Decision | Choice |
|---|---|
| Trace boundary | Precepta **ingress→egress** (NOT the agent's internal tool-calls) |
| Levels | **L1** per-request journey (base, always works) + **L2** agent-run timeline (hero) |
| Run stitching | By `run_id` / `workflow_id` / `step_name` attribution (already captured, TD-005) |
| The "why" | Real, **plain-language** reasons per step; router inferences labeled **"inferred"** (not definitive) |
| Store | New **in-boundary, team-scoped** trace store; captured **during the pipeline** (not derived from the audit chain) |
| Audience (v1) | Admin/team in the Console; per-caller (end-user) access = later |
| Trust guardrails | Never show a fake/confident "why"; never a blank "workflow" for untagged callers |

## Scope
**In:**
- Trace data model + in-boundary, team-scoped store (migration).
- Pipeline instrumentation: capture a per-step trace during `governed_chat`, with enriched
  plain-language reasons + honest router labeling.
- API: `GET /v1/traces` (list/filter) · `GET /v1/traces/{id}` (one journey) ·
  `GET /v1/traces/runs/{run_id}` (stitched run timeline) — admin-only, team-scoped.
- Console **Traces** screen: L1 workflow view + L2 run timeline.

**Out (v1):**
- The agent's internal (non-model) tool-calls — only Precepta's ingress→egress.
- End-user / per-caller trace UI (admin/team for now).
- Real-time streaming trace updates (historical view first).
- Trace-store encryption-at-rest (→ TD-007 / deploy, Phase 8).
- Analytics / aggregation dashboards.
- Retention/sampling policy beyond a basic default.

## Deliverables & verification
Test command: `./run.sh test` · no build.

| Deliverable | Verification |
|---|---|
| Trace store + per-request capture | Unit: a request yields a trace with the right ordered steps + reasons |
| Run stitching by `run_id` | Unit: tagged requests group into one run timeline |
| Trace API (list / one / run) | Tests: admin-only, team-scoped |
| Trace store governed (team-scoped, in-boundary) | Test: cross-team isolation |
| Console **Traces** screen | **Browser-validated**: L1 journey + L2 run timeline render, no JS errors |
| End-to-end | **Live**: one request shows its journey; a tagged multi-step run shows the stitched timeline |

## Acceptance criteria
- Every governed request produces a **queryable trace** whose steps + reasons match what
  actually happened (backend-real — **no fabricated reasoning**).
- A run of tagged requests renders as **one step-by-step timeline** (Level 2).
- **Level 1 works for any caller with zero cooperation**; Level 2 renders when tags are
  present, never a blank workflow otherwise.
- Router reasoning is shown **honestly** (inferred vs. explicit).
- The trace store is **team-scoped and in-boundary**.
- The Traces screen reads clearly to a **non-technical viewer**.

## Pre-mortem (risks the plan must handle)
1. **Fake/confident "why" → trust backfires.** → reasons derived from real decisions; router inferences labeled "inferred".
2. **Trace store becomes the leak** (holds prompts + decisions). → in-boundary, team-scoped, admin-only; encryption-at-rest → TD-007/deploy.
3. **Level 2 looks broken for untagged callers.** → L1 always works; L2 only when tags present; never a blank workflow.
4. **Sprawl into a full APM platform.** → v1 is trace + run-timeline, ingress→egress only.
