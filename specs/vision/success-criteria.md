---
type: Success Criteria
---

# Success Criteria

> Measurable targets. When all are met, the project has achieved its goals.

## V1 Targets (Phases 0–9 — MET)
| Criterion | Target | How to Measure |
|-----------|--------|----------------|
| Real governed inference | A prompt routes in-boundary, governed, audited | `./run.sh test` (88 pass) + live Playground |
| Provable sovereignty | Attestation verifiable: 0 external calls, chain verified | `GET /attestation`, `GET /audit/verify` |
| Governance enforced | Injection/PII/policy blocks work; every call audited | `POST /v1/chat/completions` (block cases) |
| Enterprise access | Per-team keys attributed; MCP works; SSO/Google login | `/v1/keys`, `/mcp`, Google sign-in |
| Compliance evidence | Controls mapped (DPDP/SOC2/HIPAA/GDPR/ISO), scored | `GET /compliance/report` |
| No fake UI | Console shows only real backend data when served live | Browser: Audit/Overview reflect real state |

## Long-Term Targets
| Criterion | Target | How to Measure |
|-----------|--------|----------------|
| Willingness to pay | ≥1 regulated design partner runs a paid pilot | Signed pilot + budget line |
| Trust proof | SOC2/ISO, pen test, DPA | Certification artifacts |
| Auditor-grade evidence | Per-control evidence bundles an auditor accepts | Auditor sign-off |
| Performance | Sub-second p50 for in-boundary requests | `telemetry` p50 |
