---
type: Status
---

# Project Status

> **Last Updated**: 2026-07-30
> **Current Phase**: Between phases — Phases 0–9 complete; **Phase 10 brainstorm 6 of 7 items scoped, ready for design** (Item 6 deploy still pending)
> **Latest Release**: v0.2.0 (Enterprise access — Phases 7–9)
> **Health**: On Track

## Summary

preceptaai is a **self-hosted, governed control plane for open-source AI models** — routing,
governance, tamper-evident audit, Sovereign Mode + attestation, a Console, per-team API keys, an
MCP server, and Google/OIDC SSO. Built and validated across Phases 0–9 (88 tests; every UI surface
browser-validated against the live backend). Founded retroactively on 2026-07-29 — the code
predates momentum founding; foundation docs were authored from the existing root docs
(`VISION.md`, `DESIGN.md`, `IMPLEMENTATION_PLAN.md`, `DECISIONS.md`).

## Completed Phases

| Phase | Name | Status | Released |
|-------|------|--------|---------|
| 0 | Scaffold + ports | ✅ | v0.1.0 |
| 1 | Model plane + gateway | ✅ | v0.1.0 |
| 2 | Intelligent router | ✅ | v0.1.0 |
| 3 | Governance + identity | ✅ | v0.1.0 |
| 4 | Sovereign Mode + Attestation | ✅ | v0.1.0 |
| 5 | Infra visibility | ✅ | v0.1.0 |
| 6 | Precepta Console | ✅ | v0.1.0 |
| 7 | Enterprise access (per-team keys) | ✅ | v0.2.0 |
| 8 | Reach & identity (MCP + SSO) | ✅ | v0.2.0 |
| 9 | Hardening & tenancy | ✅ | v0.2.0 |

## Active Phase

| Phase | Branch | Status | Progress |
|-------|--------|--------|----------|
| _(none — Phase 10 to be planned)_ | | | |

## Upcoming Phases

| Phase | Name | Status | Key Deliverables |
|-------|------|--------|-----------------|
| 10 | Cost/quality/governance controls | Brainstorm scoped (6/7); design next | Foundations: pricing (TD-001) · counting rules (TD-002) · quality/eval harness (FEAT-006) · sensitivity quality (TD-004). Features: budgets (FEAT-001) · policy scope (FEAT-002) · cache (FEAT-003) · compression (FEAT-005) · advanced routing (FEAT-007) · traces→learning (FEAT-008). Pending brainstorm: deploy (FEAT-009). |

## Blockers
| ID | Description | Severity |
|----|-------------|----------|
| _(none)_ | | |

## Critical Items (P0)
| ID | Type | Description |
|----|------|-------------|
| _(none)_ | | |

## Next Actions
1. **Enter the design phase** for Phase 10 using the scoped brainstorm (`BRAINSTORM.md`) + build order.
2. Brainstorm the one remaining item — Item 6 self-hosting/deploy (FEAT-009) — when ready.
3. Design foundations first (pricing, counting rules, eval harness, sensitivity), then the features.

## Key Decisions Made
- Product = self-hosted governed control plane (router is a feature). Self-hosted first, both doors (API + Console).
- Ports & adapters; Sovereign Mode + attestation as the provable core; per-team keys + MCP + SSO for enterprise access.
- Deferred: real IdP certs, SOC2/ISO certification, retention pruning (archive-and-anchor), foreign providers in the sovereign core.

## Recent Changes
- Founded the project (authored foundation docs from root docs). See `DECISIONS.md` for the full journey.
