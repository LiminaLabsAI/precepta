---
type: Phase Plan
phase: 11
name: traces
---

# Phase 11 — Traces · Implementation plan

## Execution order
```
Sequential:  Group 0 → Group 1 → Group 2 → Group 3 → Group 4
```
Largely sequential because the data flows **store → capture → API → UI → verify**.
Group 1 and Group 2 can overlap once Group 0's contract is fixed.

## Implementation roadmap (milestones)
| Milestone | Group | Outcome | Demo-able? |
|---|---|---|---|
| **M1 · Foundation** | G0 | Trace store + step contract exist | no |
| **M2 · Capture** | G1 | Every request writes a real, reasoned trace | via JSON |
| **M3 · Surface** | G2 | Traces queryable (list / one / run) | via API |
| **M4 · See it** | G3 | Console **Traces** screen — L1 + L2 render | **yes — the demo** |
| **M5 · Prove it** | G4 | Tested + browser + live end-to-end | yes |

Ship order optimizes for the demo: M4 is the payoff; M1–M3 are the substrate that make
M4 real (not a mock). Each milestone is independently verifiable.

---

## Group 0 — Trace store + step contract
**Sequential.** Blocks everything. No external deps.
- `app/traces.py`:
  - `traces` table — `request_id` (PK), `ts`, `team`, `run_id`, `workflow_id`,
    `step_name`, `agent_id`, `end_user`, `model_str`, `backend`, `in_boundary`,
    `blocked`, `latency_ms`, `steps_json`, `summary_json`.
  - **TraceStep contract** — the fixed step kinds: `firewall`, `policy`, `sensitivity`,
    `routing`, `cache`, `compression`, `inference`, `output_scan`; each step =
    `{name, decision, reason, status: pass|block|skip, ms, inferred?}`.
  - `record_trace(...)`, `get_trace(request_id)`, `list_traces(filters)` (team-scoped),
    `get_run(run_id)` (ordered steps across the run). Migration-safe (CREATE IF NOT EXISTS).
  - Fail-soft: capture must never break inference (TD-006).
- **Commit:** `feat(traces): trace store + step contract (Group 0)`

## Group 1 — Pipeline instrumentation + reason enrichment
**Sequential after G0.**
- Instrument `governed_chat` to assemble a trace as it runs — append a step at each stage
  (firewall PII/injection · policy decision · sensitivity/approved-filter · routing +
  why · cache lookup/hit · compression · inference backend · output scan), with per-step
  timing. Persist at the end (and on blocks). Team-scoped from `principal.team`.
- **Reason enrichment** (`app/traces.py` helpers) — plain-language per step, e.g.:
  - firewall → "Redacted 1 email (PII) before the model saw it" / "Blocked: prompt-injection detected"
  - sensitivity → "Sensitive (PII) → restricted to approved endpoints; ollama is approved"
  - routing (explicit) → "You named ollama" · (smart router) → "gemma-31b — **inferred** goal: quality, difficulty: hard → strongest endpoint" (`inferred: true`)
  - cache → "Served from cache (exact) — skipped the model, saved N tokens"
  - compression → "Compressed prompt (aggressive) — saved N tokens"
  - inference → "gemma-4-31b answered · 361ms · intent crossed boundary" (honest in/out-boundary)
  - output_scan → "Output scanned — no leak"
- **Honest router labeling:** inferred reasons carry `inferred: true` → the UI shows "inferred".
- **Commit:** `feat(traces): capture per-step trace with plain-language reasons (Group 1)`

## Group 2 — Trace API
**Sequential after G1** (may overlap once the G0 contract is fixed).
- `GET /v1/traces` — recent traces; filter by `run_id` / `agent_id` / decision / time. Admin-only, team-scoped.
- `GET /v1/traces/{request_id}` — one request's full step list.
- `GET /v1/traces/runs/{run_id}` — all steps in a run, ordered (the L2 timeline).
- Auth: `policy.update` / admin; results team-scoped.
- **Commit:** `feat(traces): trace API — list / one / run (Group 2)`

## Group 3 — Console Traces screen
**Sequential after G2.** Wiring.
- New nav item **Traces** + `tracesView()` in `web/console.html`; loader `loadTraces()`.
- **List:** recent requests/runs with badges (allow/block, backend, pii, cache, latency).
- **Level 1 — journey:** click a request → a vertical **workflow** of step nodes; each with
  icon, decision, plain-language reason, timing; blocks/redactions in red; cache/compression
  savings highlighted; an "inferred" tag on smart-router reasons.
- **Level 2 — run timeline:** requests grouped by `run_id` → a step-by-step timeline
  (step 1..N); click a step → its L1 journey. Untagged requests show only L1.
- Browser-validate (L1 + L2, no JS errors).
- **Commit:** `feat(traces): Console Traces screen — L1 journey + L2 run timeline (Group 3)`

## Group 4 — Verification
**Sequential.**
- Unit tests: capture (steps + reasons), stitching (run grouping), API (admin/team), fail-soft.
- Browser: Traces screen renders L1 + L2, no JS errors.
- Live end-to-end: one request → its journey; a tagged multi-step run → the stitched timeline.
- Update HANDOFF + changelog; mark FEAT-010 resolved; `/sync-docs` before `/complete-phase`.
- **Commit:** `test(traces): unit + browser + live end-to-end (Group 4)`

## Deferred (v2 / other phases)
Agent internal tool-calls · per-caller trace UI · real-time streaming · trace-store
encryption-at-rest (TD-007 / deploy) · analytics dashboards · retention/sampling policy.
