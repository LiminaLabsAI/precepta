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

## Phases

### Phase 1 — Reframe (quick win) — ⏳ in progress
- ✅ **Naming pass** (A partial + C): Inference plane · inference endpoint · Endpoint column · Add inference endpoint · intent-boundary pills. *Done + landed 2026-08-03 (ENH-007).*
- ⚪ **Positioning & messaging** (A: items 5/6) — taglines, screen intros, "runtime guardrail platform for AI companies" voice. *(ENH-006)*
- **Why first:** fast, improves every demo, low risk.

### Phase 2 — Traces (design) — ⚪ next
- Brainstorm + design the trace/workflow model + UI. *(FEAT-010, design)*
- **Open questions to settle:**
  1. Is a "trace" a **single request's journey**, an **agent run across many requests**, or **both**? (leaning: both — request trace nested inside an agent-run timeline.)
  2. **Who sees it** — every caller their own, or admin-only? (guardrail transparency argues for broad visibility, tenant-isolated.)
  3. Live vs. historical; how much per-step detail; retention.
- **What already exists to build on:** tamper-evident audit chain (every firewall/policy/routing decision), `route_traces`, agent attribution (workflow/run/agent id, TD-005), `precepta.*` per-response metadata. Mostly a **presentation** layer — additive, no core rewrite.
- **Why here:** investor-critical hero; needs design before code.

### Phase 3 — Traces (build) — ⚪
- Per-request **journey view** (firewall → policy → route decision + why → cache/compress → endpoint → output check → result, each with timing + pass/block).
- Agent-run **timeline** grouped by workflow/run/agent id; expandable into per-request traces.
- Simple, visual, "investor-clear." *(FEAT-010, build)*

### Phase 4 — Cache & compression v2 — ⚪
- Two tabs on one page; **per-endpoint** config; pluggable strategy registry; design toward **BYO**. *(FEAT-011)*
- **Why last:** deepest refactor; renames backend→endpoint (do after Phase 1); changes the metering/savings model.

### Parallel backlog
- **First-run setup copilot** — agent-assisted vs manual onboarding. *(FEAT-012)*

## Recommended immediate move
Kick off the **Phase 2 traces brainstorm** (the hero, needs design) while Phase 1
naming is already done and the messaging pass is a quick follow-up.
