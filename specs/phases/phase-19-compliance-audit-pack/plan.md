---
type: PhasePlan
phase: 19
---

# Phase 19 — Implementation Plan

## Execution order
`Group 0 → (Groups 1 + 2 + 3 + 4 in parallel) → Group 5`

> Group 0 (the control catalog) unblocks the export labels. Change-control,
> incident register and retention are independent feature areas.

## Group 0 — Control catalog + mapping (sequential, blocks export labels) · FEAT-025
Load the **NIST AI RMF** control set (then EU AI Act articles, ISO 42001);
tag each Precepta capability (PII redaction, policy checks, audit chain, egress
attestation, …) to the controls it satisfies; a coverage report + a compliance
view. *Commit: `feat(compliance): control catalog + capability→control mapping (NIST first)`*

## Group 1 — Policy change-control (parallel) · FEAT-026
Version every policy (keep all versions); require a second approver for flagged
policies (four-eyes); full who/when/before/after history in the audit chain.
*Commit: `feat(policies): versioning + four-eyes + change history`*

## Group 2 — Evidence export pack (parallel) · FEAT-024
Query the audit chain by time / system / policy; render a **signed PDF + JSON**
bundle labelled by control (from Group 0). *Commit: `feat(compliance): auditor evidence export pack`*

## Group 3 — Incident register + regulator export (parallel) · FEAT-030
Incident records linked to the audit trail; export templates shaped to EU AI Act
Art. 73 / US state law. *Commit: `feat(compliance): incident register + regulator-shaped export`*

## Group 4 — Long-horizon retention & archive (parallel) · FEAT-031
Export records to an open, self-describing, integrity-checked archive; retention
policy; verify-on-read. *Commit: `feat(compliance): 10-year retention + portable archive`*

## Group 5 — Verification (sequential)
Unit + integration across all five; export/verify round-trips; full `./run.sh test`;
SMOKE PASS. *Commit: `test: compliance & audit-readiness E2E`*
