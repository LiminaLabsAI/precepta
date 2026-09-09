---
type: Roadmap
---

# Roadmap

> **Start Date**: 2026-07-20 · **Founded**: 2026-07-29

## Vision
preceptaai becomes the neutral, self-hosted control plane between a regulated enterprise and every
open-source AI model it runs — routed, governed, attributed, and provably in-boundary by default.

## Timeline
| Phase | Name | Status | Key Deliverables |
|-------|------|--------|------------------|
| 0 | Scaffold + ports | ✅ Done (v0.1.0) | FastAPI, DB layer, ports, `/health` |
| 1 | Model plane + gateway | ✅ Done | OpenAI-compatible API; Ollama/vLLM/Neysa/HF adapters |
| 2 | Intelligent router | ✅ Done | RouterBrain, route modes, failover, ReasoningPort, cost-gating |
| 3 | Governance + identity | ✅ Done | authN→authZ, policy engine, firewall, audit per check |
| 4 | Sovereign Mode + Attestation | ✅ Done | in-boundary enforcement, SHA-256 chain, attestation |
| 5 | Infra visibility | ✅ Done | vLLM/Ollama metrics → telemetry → `/infra` |
| 6 | Precepta Console | ✅ Done | ChatGPT-style Console wired to the live backend |
| 7 | Enterprise access | ✅ Done | Per-team API keys (attributed), zero-code adoption |
| 8 | Reach & identity | ✅ Done (v0.2.0) | MCP server; SSO/OIDC + Google login + sessions |
| 9 | Hardening & tenancy | ✅ Done | Team-scoped authZ, compliance evidence, audit export |
| 10 | Cost / quality / governance controls | Scoped (design next) | Foundations (pricing TD-001, counting TD-002, eval harness FEAT-006, sensitivity TD-004) → budgets+key-expiry (FEAT-001), policy scope (FEAT-002), cache (FEAT-003), compression (FEAT-005), advanced routing (FEAT-007), traces→learning (FEAT-008); refreshed Precepta Console; OpenGuard authZ (FEAT-004). Pending brainstorm: deploy (FEAT-009). See `BRAINSTORM.md`. |
| 12 | **Smart Router (+ workflow view)** | ✅ **Built + tested 2026-08-10** (branch `phase-12-smart-router`, +90 tests) | Two-stage intent router (model brain + config resolver); unified `RouteTarget` for models **and** in-premise agents; LiteLLM inference adapter (in-boundary allowlist); BUG-001 guard; toxicity filter + enforcement-timing; read-only workflow view; open-core (Apache-2.0); locked router eval (Rule 11). Deferred: live pipeline swap to the two-stage brain; full agent dispatch (contract + adapters ready). |
| 11 | Traces (request-lifecycle observability) | ✅ **Built + tested 2026-08-10** (FEAT-010) | L1 every-step traces + **L2 agent sub-trace** + live request log + **bill-back** (cost by app/agent). Learning-loop reward capture via FEAT-008. |
| 13 | Workflow builder | Planned (outline) | Editable canvas → writes resolver config, validation-gated (no orphan intents; every intent reaches an allowed target; no rule fights a sovereignty policy); versioning; trace-backed preview. Governance rails fixed. |
| 14 | **Deploy: Sovereign Pilot (self-host)** | ✅ **Done 2026-08-11** (branch `phase-14-deploy-pilot`) | Single-node egress-locked **docker-compose** bundle; **in-boundary helper models** (bundled Ollama serves router + embeddings — closes TD-009); egress-lock by construction + **egress probe in the attestation** (SMOKE PASS: provable zero-egress); one-command up + `doctor` + runbook + in-product Deployment screen. **Also shipped in-lane:** grounded in-boundary **copilot** (+ navigation), **approved-egress allowlist + broker** (restricted egress opt-in), endpoint edit/delete, **smart cache + compression**, demo seed. Pilot slice — defers Helm/Postgres/Vault/air-gap/HA/SCIM. |
| 15 | **AI Provider Integration API** | Planned (brainstormed 2026-08-11) | Governed provider-integration API: `GET /v1/providers` + **in-boundary model catalog** (`/v1/catalog/models` — capabilities/context/pricing, LiteLLM-style) → register an **inference endpoint** (`/v1/endpoints`, renames `backends` +alias) → **governed `/v1/inference` + `/v1/embeddings`** (`chat/completions` kept as OpenAI-compat alias). Auth = keys + **`manage` scope** (sovereignty stays owner-only); typed OpenAPI at `/docs`; in-product API page. Vocabulary: drops "backend"→endpoint, "chat"→inference. Spec: `specs/phases/phase-15-provider-api/`. |
| 18 | **Enterprise Identity & Access** | Planned 2026-09-09 (FEAT-023) | SAML 2.0 SSO + SCIM 2.0 auto-provisioning/deprovisioning + directory-group→role mapping, on top of shipped OIDC/RBAC. Roadmap P0 · Q4 2026. Deal-blocker (enterprise security review). Spec: `specs/phases/phase-18-enterprise-identity/`. |
| 19 | **Compliance & Audit-Readiness Pack** | Planned 2026-09-09 (FEAT-024/025/026/030/031) | Control-framework mapping (NIST→EU AI Act→ISO 42001), one-click evidence export, policy change-control (versioning+four-eyes), incident register w/ regulator export, 10-year retention. Roadmap P0/P1 · Q4 2026–Q2 2027. Spec: `specs/phases/phase-19-compliance-audit-pack/`. |
| 20 | **AI Inventory, Registry & Risk** | Planned 2026-09-09 (FEAT-027/028/029) | Auto-built AI registry, per-system risk classification + dynamic scoring, pre-deployment eval + red-team gate — the missing 'Know/Decide' jobs. Roadmap P1 · Q1–Q2 2027. Spec: `specs/phases/phase-20-inventory-registry-risk/`. |

## Smart-Router initiative — execution order (2026-08-09)
`Phase 12 Smart Router + read-only view → Phase 11 Traces (extended) → Phase 13 Workflow builder`
Foundations across all three: open-core (Apache-2.0) · in-boundary helper models (TD-009, at deploy) · locked eval set (Rule 11).
> Numbers are IDs, not execution order — Phase 12 runs **before** Phase 11 (traces builds on the router).

## Guiding Principles
1. Ship working software in every phase.
2. Each phase leaves the project in a releasable state.
3. Defer scope, not quality. Every UI surface is browser-validated against the live backend.
