---
type: Vision
---

# Project Charter

> **Project**: preceptaai
> **Created**: 2026-07-20 (founded retroactively 2026-07-29 — built before momentum founding)

## Problem Statement
Regulated and data-sensitive enterprises want to use AI, but (1) they can't send data to
third-party clouds (DPDP/HIPAA/GDPR/SOC2 + sovereignty), (2) they have no easy way to route to the
cheapest capable open-source model on their own infra, and (3) their AI usage is ungoverned — no
enforced policy, no PII controls, no audit trail an auditor accepts. In one sentence: **they don't
control their own AI access.**

## Solution
A **self-hosted control plane** for running open-source AI models on the customer's own
infrastructure — with routing, governance, and tamper-evident audit built in. **Sovereign Mode +
Sovereignty Attestation** make "data never leaves" *provable*, not just claimed. The intelligence
router is a feature; the product is the governed control plane.

## Stakeholders
| Role | Name / Team | Responsibility |
|------|-------------|----------------|
| Owner | sarang | Final decisions, direction |
| Buyer | Compliance / security lead (CISO) | Purchases; governs |
| Users | Developers, apps/services, agents (via API/MCP), business staff (Console) | Consume governed inference |

## Scope
### In
- Model plane (Ollama, vLLM, Neysa, HF dedicated endpoints), intelligent router, governance
  (policy engine + firewall + tamper-evident audit), Sovereign Mode + attestation, infra
  visibility, the Console, per-team API keys, MCP server, SSO/OIDC, compliance evidence.
### Out
- Foreign hosted providers in the sovereign core; a public hosted SaaS (self-hosted first);
  reselling tokens; SOC2/ISO *certification* (that's an audit process, not code).

## Success
See `success-criteria.md`. In short: a regulated buyer runs a real workload in-boundary, governed
and audited, and can produce a Sovereignty Attestation their security team independently verifies.
