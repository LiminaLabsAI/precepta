---
type: PhasePlan
phase: 18
---

# Phase 18 — Implementation Plan

## Execution order
`Group 0 → (Groups 1 + 2 in parallel) → Group 3 → Group 4`

> **External deps:** a test SAML IdP (or a stubbed assertion) and a SCIM client
> (stubbed in tests); reuse the existing `IdentityPort` + `adapters/identity/`.

## Group 0 — Identity contracts (sequential, blocks all)
Extend the identity model for SAML + SCIM: user records with an external id +
IdP source, `deactivated` state, and a group→role map table. Config surface
(SAML metadata/cert, SCIM bearer token). *Commit: `feat(identity): SAML/SCIM contracts + storage`*

## Group 1 — SAML 2.0 sign-in (parallel w/ 2)
SAML adapter behind `IdentityPort`: SP metadata, AuthnRequest, assertion
signature + audience + expiry validation, JIT user create → session (reuse the
session flow from Phase 8/17). *Commit: `feat(identity): SAML 2.0 sign-in`*

## Group 2 — SCIM 2.0 provisioning (parallel w/ 1)
`/scim/v2/Users` (POST create, PATCH/PUT update, PATCH active=false / DELETE =
**deactivate**) + Groups read; token-authenticated; map to Precepta users +
roles; deactivate revokes access immediately. *Commit: `feat(identity): SCIM 2.0 Users provisioning`*

## Group 3 — Console Identity settings (sequential)
An **Identity** screen: configure SAML (paste IdP metadata) + SCIM (issue a
token), view provisioned users + their source, edit group→role mapping.
*Commit: `feat(console): Identity settings (SAML/SCIM/roles)`*

## Group 4 — Verification (sequential)
Unit + integration (assertion validation, SCIM create/deactivate, group→role);
live deprovision E2E (deactivate → access dies); full `./run.sh test`; SMOKE PASS.
*Commit: `test: enterprise identity E2E`*
