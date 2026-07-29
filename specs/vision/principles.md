---
type: Vision
---

# Principles

> Guiding decisions throughout the project. When trade-offs arise, these resolve them.

## Core Principles
1. **Sovereign by default** — in-boundary routing + audit are on unless deliberately disabled; never route out-of-boundary in Sovereign Mode.
2. **Ports & adapters (DIP)** — the domain core never imports a provider/store/cloud; adding one is a single adapter, never a core change.
3. **Governance in the request path** — every call is authenticated, authorized, policy-checked, PII/injection-firewalled, and audited; no bypass. Backend failures are audited too.
4. **Integrate, don't build** — reuse vLLM/Ollama/metrics/optillm; never rebuild serving or observability, and stay out of the giants' lane.
5. **Provable over asserted** — sovereignty is an attestation an auditor independently verifies, not a claim; compliance maps to real control evidence.
6. **Evidence over intent** — nothing is "done" without a fresh passing verification (tests + browser-validated UI); the Console shows only real data, never mock, when served live.
7. **Attributed access** — every request is traceable to a real principal (per-team key or SSO identity) in the tamper-evident audit.
