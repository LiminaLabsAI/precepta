---
type: Phase History
phase: 11
name: traces
---

# Phase 11 — Traces · History

### [DECISION] 2026-08-06 — Phase framed via FORGE + /brainstorm-phase
Topics: traces, observability, scope
Affects-phases: phase-11-traces
Affects-specs: specs/phases/phase-11-traces/overview.md
Detail: Brainstormed FEAT-010 as a design problem (past SIEVE — investors validated
demand; it's the product's own proof). Reframed from "pick an audience" to
**observability is the job** (user's correction): make the background visible +
understandable so anyone — investor or operator — sees what's happening and can improve.

---

### [SCOPE_CHANGE] 2026-08-06 — Trace boundary = Precepta ingress→egress
Topics: scope, gateway boundary
Affects-phases: phase-11-traces
Detail: Resolved the riskiest design assumption. Precepta is a gateway — it observes the
**requests that pass through it**, not the agent's private internals. Scope is therefore
**everything Precepta does from ingress to egress**, with the reasoning at each step —
NOT the agent's internal tool-calls (out of view unless proxied). This is fully within
what Precepta controls + already logs, so the "data exists" assumption holds for v1.

---

### [DECISION] 2026-08-06 — Two levels: L1 per-request + L2 agent-run timeline
Topics: levels, run stitching
Affects-phases: phase-11-traces
Detail: v1 = **Level 1** (per-request journey, always works, zero caller cooperation) +
**Level 2** (agent-run timeline — many tagged requests "stitched" into one workflow by
`run_id`/`workflow_id`/`step_name`, the attribution built in TD-005). L2 is the hero
("the agent's full workflow"); depends on the caller tagging its calls — fine for the
demo, a one-header ask for customers. Never a blank workflow: untagged → L1 only.

---

### [DECISION] 2026-08-06 — The "why" must be honest (no fabricated reasoning)
Topics: trust, router reasoning, backend-real
Affects-phases: phase-11-traces
Detail: The differentiator is the per-step *reasoning*, in plain language. But the Smart
router's "why" is itself an inference (`goal=cost` was guessed by a model) — showing a
confident "because cost" would build trust on a soft claim. Decision: router reasons are
labeled **"inferred"** (flag `inferred: true`); explicit reasons stated plainly. A fake
confident "why" is worse than none.

---

### [ARCH_CHANGE] 2026-08-06 — Dedicated in-boundary trace store (not derived from audit)
Topics: data model, sovereignty
Affects-phases: phase-11-traces
Affects-specs: specs/phases/phase-11-traces/plan.md
Detail: Capture a structured per-request trace **during the pipeline** into a dedicated
`traces` store, rather than deriving it from the audit chain (chain entries aren't
correlated per-request as ordered steps). The trace holds prompts + decisions → it is
sensitive data, so the store is **in-boundary, team-scoped, admin-only**;
encryption-at-rest deferred to TD-007/deploy. Audit chain stays the tamper-evident record;
the trace store is the observability/UX record.

---

### [NOTE] 2026-08-06 — v1 non-goals
Topics: scope discipline
Affects-phases: phase-11-traces
Detail: Explicitly out of v1 to avoid sprawl into an APM platform: agent internal
tool-calls · per-caller/end-user trace UI · real-time streaming · trace-store
encryption-at-rest · analytics dashboards · retention/sampling policy beyond a default.

---
