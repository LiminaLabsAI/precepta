---
type: Phase
phase: 19
name: Compliance & Audit-Readiness Pack
status: planned
tags: [compliance, audit, nist, eu-ai-act, iso-42001, evidence-export, policy-versioning, incident, retention]
---

# Phase 19 — Compliance & Audit-Readiness Pack

> **Verification:** `./run.sh test` · **Build:** none
> **Backlog:** FEAT-024, FEAT-025, FEAT-026, FEAT-030, FEAT-031
> **Roadmap:** P0/P1 · **Target:** Q4 2026 – Q2 2027

## Goal
Turn the tamper-evident audit chain (already built) into the things auditors,
legal and regulators actually accept: **control-framework mapping** (NIST first,
then EU AI Act & ISO 42001), a **one-click evidence export pack**, **policy
change-control**, an **incident register with regulator-shaped export**, and
**10-year integrity-preserving retention**.

## Why (plain English)
We already record everything, but an auditor won't read a database, and legal
buys when a feature maps to a named obligation. This phase produces the report,
the mapping and the change-history that convert a technical product into a
governance purchase — the review's highest-leverage cluster.

## Key decisions
| Decision | Choice |
|---|---|
| Mapping order | **NIST AI RMF first** (affirmative legal defence under US state law), then EU AI Act, then ISO 42001 |
| Export shape | Signed PDF **+** machine-readable bundle, labelled by control + regulation |
| Change-control | Policy **versioning + four-eyes approval + full history** (separation of duties) |
| Incident export | EU AI Act **Art. 73** and US state law (e.g. CA SB 53) shaped |
| Retention | Open, self-describing, integrity-checked archive (EU AI Act **Art. 18**, 10-year) |

## Scope — in
- Control catalog + capability→control mapping (NIST → EU → ISO) + coverage view. (FEAT-025)
- Evidence export pack (query audit chain by time/system/policy → signed PDF + JSON). (FEAT-024)
- Policy change-control: versioning, four-eyes approval, change history. (FEAT-026)
- Incident register + regulator-shaped export. (FEAT-030)
- Long-horizon retention & portable archive + verify-on-read. (FEAT-031)

## Scope — out
- Full risk-register/scoring (Phase 20); per-vendor legal templates beyond NIST/EU/ISO; automated regulator submission.

## Deliverables & verification
| Deliverable | Verify |
|---|---|
| Control mapping + coverage | `./run.sh test`: capabilities map to NIST controls; coverage report renders |
| Evidence export pack | test: export by time/system/policy → signed, verifiable bundle |
| Policy change-control | test: version bump + four-eyes required + history recorded |
| Incident register + export | test: incident → Art. 73-shaped export |
| Retention/archive | test: archive round-trips + integrity verify-on-read |
| Full suite | `./run.sh test` green; SMOKE PASS |

## Acceptance criteria
- An auditor's request ("every decision in Q2 + the policy in force") produces a
  clean, signed, framework-labelled export in minutes.
- A sensitive policy change requires a second approver and is fully logged.
- An incident exports in the regulator's shape; records survive 10-year retention
  with integrity verifiable. Full suite green; sovereignty unaffected.
