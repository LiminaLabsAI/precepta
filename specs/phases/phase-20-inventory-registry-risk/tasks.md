---
type: PhaseTasks
phase: 20
---

# Phase 20 — Tasks

## Group 0 — Registry model + auto-capture (FEAT-027)
- [ ] Registry table (system id, kind, owner, first-seen, source, risk)
- [ ] Auto-create an entry on first sight of a model/agent in the governed path

## Group 1 — Registry UI (FEAT-027)
- [ ] Registry screen (list + owner + risk + last-seen); manual add/edit

## Group 2 — Risk scoring (FEAT-028)
- [ ] Rules-based scorer (sensitivity + use-case + autonomy) → level + reasons
- [ ] Recompute from live traces (dynamic)

## Group 3 — Eval + red-team gate (FEAT-029)
- [ ] Fixed eval test-set + thresholds + red-team library
- [ ] Block go-live until pass; attach results to the registry entry

## Group 4 — Verification
- [ ] Unit + integration; live E2E; full `./run.sh test`; SMOKE PASS
