---
type: Status
---

# Project Status

> **Last Updated**: 2026-08-03
> **Current Phase**: **Phase 10 — building.** Sub-phases 1–7 (money foundations · access & keys · policy
> governance · smart routing · cost optimization · learning loop · enterprise hardening) ✅ done + LANDED on
> `main`. Sub-phase 8 (deploy) needs a brainstorm; sub-phase 9 (validation) is business. Full details:
> **read `HANDOFF.md` first.**
> **Main @ `53a160d` (pushed to GitHub) · 205 tests passing.**

> 📌 **NEXT-SESSION START HERE:** read `HANDOFF.md` (repo root) — it has full context, what's built, what's
> next (router config → eval harness → LLM router → cache → compression), the locked decisions, and how to run/verify.
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
| 12 — Smart Router (+ workflow view) | `main` | ✅ Built + tested + **merged to `main`** 2026-08-10; **activated** in the live path (candidate set in traces) | Done |
| 11 — Traces (request-lifecycle observability) | `main` | ✅ Built + tested + merged 2026-08-10 (L1 + L2 agent sub-trace + bill-back) | Done |
| 14 — Deploy: Sovereign Pilot (self-host) | `phase-14-deploy-pilot` | **Complete 2026-08-11** — SMOKE PASS (provable zero-egress); + copilot(+nav), egress allowlist+broker, endpoint edit/delete, smart cache+compression, demo seed; 354 tests green | 100% |
| 15 — AI Provider Integration API | `phase-15-provider-api` | **Built G0–G5 2026-08-11** — providers + in-boundary catalog, `/v1/endpoints` (renamed, aliased), governed `/v1/inference`+`/v1/embeddings`, keys+`manage` scope, OpenAPI `/docs` + API page. Live-verified; 376 tests; SMOKE PASS. Remaining: in-modal management-key toggle | ~95% |
| 16 — Licensing v1 (vendor side) | `phase-16-licensing` | **Started 2026-08-17** — onboarding site + login capture + Ed25519 signed-key issuance + admin visibility + heartbeat receiver. Self-host activation/enforcement = Phase 17. | In progress |

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
1. **`/start-phase`** for **Phase 15 — AI Provider Integration API** (brainstormed 2026-08-11; spec in `specs/phases/phase-15-provider-api/`, groups G0–G5 in its `plan.md`).
2. Land the pilot: merge `phase-14-deploy-pilot` → `main` (blocked only by the local safety gate; branch is pushed and green).
3. Later: **Phase 13 — Workflow builder** (FEAT-021) · production hardening (Postgres/Helm/Vault/HA/SCIM) · key-hygiene ENHs (rotation, usage page, per-key rate-limit) · Overview per-hour chart (ENH-009).

## Key Decisions Made
- Product = self-hosted governed control plane (router is a feature). Self-hosted first, both doors (API + Console).
- Ports & adapters; Sovereign Mode + attestation as the provable core; per-team keys + MCP + SSO for enterprise access.
- Deferred: real IdP certs, SOC2/ISO certification, retention pruning (archive-and-anchor), foreign providers in the sovereign core.

## Recent Changes
- Founded the project (authored foundation docs from root docs). See `DECISIONS.md` for the full journey.
