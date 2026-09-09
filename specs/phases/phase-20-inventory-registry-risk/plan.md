---
type: PhasePlan
phase: 20
---

# Phase 20 — Implementation Plan

## Execution order
`Group 0 → Group 1 → Group 2 → Group 3 → Group 4`

> Registry (G0/G1) is the foundation; risk scoring (G2) reads it; the eval gate
> (G3) attaches to it. Draws on the existing traces/audit signals.

## Group 0 — Registry data model + auto-capture (sequential) · FEAT-027
Registry table (system id, kind model/agent, owner, first-seen, source, risk);
auto-create an entry the first time a model/agent is seen in the governed path.
*Commit: `feat(registry): AI inventory model + auto-capture from traffic`*

## Group 1 — Registry UI + manual entries (sequential) · FEAT-027
A **Registry** console screen: list with owner + risk + last-seen; add/edit
entries for AI that doesn't route through us. *Commit: `feat(console): AI registry screen`*

## Group 2 — Risk classification & dynamic scoring (sequential) · FEAT-028
Rules-based scorer (data sensitivity + use-case + autonomy) producing a level +
reasons; recompute from live traces so the score moves with behaviour.
*Commit: `feat(registry): risk classification + dynamic scoring`*

## Group 3 — Pre-deployment eval + red-team gate (sequential) · FEAT-029
A fixed eval test-set with pass thresholds + a red-team prompt library; block
go-live until pass; attach results to the registry entry.
*Commit: `feat(registry): pre-deployment eval + red-team gate`*

## Group 4 — Verification (sequential)
Unit + integration; live E2E (route → auto-registered → scored → gated); full
`./run.sh test`; SMOKE PASS. *Commit: `test: inventory, registry & risk E2E`*
