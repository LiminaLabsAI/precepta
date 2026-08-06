---
type: Phase Tasks
phase: 11
name: traces
---

# Phase 11 — Traces · Tasks

Legend: `[ ]` todo · `[/]` in progress · `[x]` done

## Group 0 — Trace store + step contract
- [ ] `app/traces.py`: `traces` table (request_id PK + attribution + summary + steps_json)
- [ ] TraceStep contract: fixed step kinds + `{name, decision, reason, status, ms, inferred?}`
- [ ] `record_trace()`, `get_trace()`, `list_traces(filters)`, `get_run(run_id)` — team-scoped, migration-safe
- [ ] Fail-soft wrapper (capture never breaks inference)

## Group 1 — Pipeline instrumentation + reasons
- [ ] Instrument `governed_chat` — append a step at each stage with timing
- [ ] Persist the trace at end + on blocks; team from `principal.team`
- [ ] Reason enrichment helpers (firewall / sensitivity / routing / cache / compression / inference / output)
- [ ] Honest router labeling (`inferred: true` on smart-router reasons)

## Group 2 — Trace API
- [ ] `GET /v1/traces` (list + filters, admin-only, team-scoped)
- [ ] `GET /v1/traces/{request_id}` (one journey)
- [ ] `GET /v1/traces/runs/{run_id}` (run timeline)

## Group 3 — Console Traces screen
- [ ] Nav item **Traces** + `tracesView()` + `loadTraces()`
- [ ] List view (badges: allow/block, backend, pii, cache, latency)
- [ ] Level 1 — journey (step nodes: decision, plain reason, timing; blocks red; "inferred" tag)
- [ ] Level 2 — run timeline (grouped by run_id; step → its L1 journey; untagged = L1 only)
- [ ] Browser-validate (no JS errors)

## Group 4 — Verification
- [ ] Unit: capture (steps + reasons), stitching, API (admin/team), fail-soft
- [ ] Browser: L1 + L2 render
- [ ] Live end-to-end: single request journey + tagged multi-step run timeline
- [ ] Update HANDOFF + changelog; mark FEAT-010 resolved
