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

## Guiding Principles
1. Ship working software in every phase.
2. Each phase leaves the project in a releasable state.
3. Defer scope, not quality. Every UI surface is browser-validated against the live backend.
