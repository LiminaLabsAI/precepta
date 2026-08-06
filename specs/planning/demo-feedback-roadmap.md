---
type: Roadmap
title: Demo-feedback roadmap
created: 2026-08-03
---

# Demo-feedback roadmap

Ten pieces of feedback from demos (multiple stakeholders, incl. investor signal).
They collapse into **four themes with one through-line**, sequenced into phases.

## Through-line
Precepta is a **runtime guardrail platform sold to AI companies** (not an end-user
AI product). A guardrail's value *is* showing what it guarded and why — so
**traces are the hero**, and everything else makes the surface match that framing.

## The four themes → feedback items

| Theme | Feedback items | Nature |
|---|---|---|
| **A · Positioning & vocabulary** | 1 (backend→inference), 5 (AI *platform*, not AI company), 6 (runtime guardrail), 7 (model plane→inference plane) | Naming + messaging |
| **B · Cache & compression, evolved** | 2 (two tabs), 3 (per-endpoint, not global), 4 (BYO algo/mechanism) | Architecture + UX |
| **C · Boundary clarity** | 8 (say *what* leaves — chose "intent" framing) | Copy/UX |
| **D · Traces & agent-workflow visibility** | 9 (traces = the missing hero, agent execution), 10 (simple/clear for investors) | New feature |

## Decisions locked (2026-08-03)
- **Renaming touches user-facing copy only** — never code/API/DB (`backend` stays the code term; `/v1/backends`, `state.backends` unchanged).
- **Boundary wording = "intent" framing:** "Intent within boundary" / "Intent crosses boundary".
- **`backend` → `inference endpoint`** in the UI; **`Model plane` → `Inference plane`**.
- **BYO cache/compression = design-for-now, build-later.**

## Phases (reordered 2026-08-03 per user: cache/compression UI → traces → rest)

### Phase 1 — Reframe (quick win) — ⏳
- ✅ **Naming pass** (A partial + C): Inference plane · inference endpoint · intent-boundary pills. *Done + landed 2026-08-03 (ENH-007).*
- ⚪ **Positioning & messaging** (A: items 5/6). *(ENH-006 — deferred to after Phase 3.)*

### Phase 2 — Cache & compression v2, UI-first — ⚪ **NEXT (user reordered up)**
- **Two tabs on one page** (Cache | Compression), each configured **per inference endpoint** (+ an "Auto (router)" row for `auto` requests) — replacing today's single global toggle.
- **Pluggable strategy selection, real for built-ins:** cache = exact / semantic (+ threshold); compression = baseline / aggressive. Shown as per-endpoint dropdowns.
- **BYO** (bring-your-own cache algo / compression method): surfaced in the UI as an honest "coming" option; **the real BYO engine → backlog** (FEAT-011 v2).
- Design decision: config key = the endpoint that serves the request (`req_backend`, or `auto`) — known pre-inference, so no pipeline reorder.
- **Why first now:** the user wants the UI/UX in front of demo audiences; it's contained; built-ins are already real.

### Phase 3 — Traces (design → build) — 🔵 **planned as `phase-11-traces`** (2026-08-06)
- The hero (FEAT-010). **Brainstormed + planned** — full spec in `specs/phases/phase-11-traces/`
  (overview · plan w/ M1–M5 implementation roadmap · tasks · history).
- **Locked scope:** trace = Precepta **ingress→egress** workflow with per-step reasoning;
  **L1** per-request journey (base) **+ L2** agent-run timeline (hero, stitched by run_id).
  Honest router labeling ("inferred"); dedicated in-boundary, team-scoped trace store.
- Mostly a **presentation** layer over existing audit + attribution data — additive. Run `/start-phase`.

### Phase 4 — the rest (as recommended)
- Positioning/messaging finish (ENH-006) · First-run setup copilot (FEAT-012) · real pluggable/BYO engine (FEAT-011 v2).

## Immediate move
Build **Phase 2** (cache/compression v2 UI, per-endpoint) now; BYO engine to backlog; then Phase 3 traces.
