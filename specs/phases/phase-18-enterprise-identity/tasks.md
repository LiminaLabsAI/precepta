---
type: PhaseTasks
phase: 18
---

# Phase 18 — Tasks

## Group 0 — Identity contracts
- [ ] User model: external id + IdP source + `deactivated`; group→role map table
- [ ] Config surface (SAML metadata/cert, SCIM bearer token)

## Group 1 — SAML sign-in
- [ ] SAML adapter behind IdentityPort (SP metadata, AuthnRequest)
- [ ] Assertion validation (signature, audience, expiry) → JIT user → session
- [ ] Tests: valid assertion → session; bad/expired → rejected

## Group 2 — SCIM provisioning
- [ ] `/scim/v2/Users`: create / update / deactivate (+ Groups read), token-auth
- [ ] Deactivate revokes access immediately
- [ ] Tests: create → appears; deactivate → access dies

## Group 3 — Console Identity settings
- [ ] Configure SAML + SCIM; view provisioned users; group→role mapping

## Group 4 — Verification
- [ ] Unit + integration; live deprovision E2E; full `./run.sh test`; SMOKE PASS
