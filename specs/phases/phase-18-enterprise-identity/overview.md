---
type: Phase
phase: 18
name: Enterprise Identity & Access — SAML + SCIM
status: planned
tags: [identity, saml, scim, rbac, sso, enterprise, procurement]
---

# Phase 18 — Enterprise Identity & Access (SAML + SCIM)

> **Verification:** `./run.sh test` · **Build:** none
> **Backlog:** FEAT-023 · **Roadmap:** P0 (unblocks deals) · **Target:** Q4 2026

## Goal
Pass enterprise security review. Staff sign in with their normal corporate
account (**SAML**), the company directory **automatically creates and disables
users (SCIM)**, and directory groups map to Precepta roles — on top of the
OIDC/Google SSO and owner/admin/auditor/user role model already shipped.

## Why (plain English)
Big enterprises won't run a tool where you manage logins by hand, and an
ex-employee who still has access is a security incident. Without SAML + SCIM we
**fail the procurement security review** — a hard deal-blocker.

## Key decisions
| Decision | Choice |
|---|---|
| SSO protocol | Add **SAML 2.0** (Okta / Azure AD / Ping) alongside the existing OIDC — reuse the `IdentityPort` shape |
| Provisioning | **SCIM 2.0** Users endpoint (create / update / **deactivate**) driven by the customer's IdP |
| Role mapping | Directory **group → Precepta role** mapping (owner stays owner-only) |
| Sovereignty | All identity flows in-boundary; SAML/SCIM reach only the customer's own IdP (owner-approved egress if needed) |

## Scope — in
- SAML 2.0 sign-in adapter (metadata exchange, assertion validation, JIT user create).
- SCIM 2.0 `/scim/v2/Users` (+ Groups read) — create, update, **deactivate** (deprovision).
- Directory-group → role mapping + admin config.
- Console: an **Identity** settings screen (configure SAML/SCIM, view provisioned users, map groups).
- Tests + a live deprovision E2E.

## Scope — out
- Full IdP-side setup guides per vendor (docs only); fine-grained ABAC; passwordless/MFA (the IdP owns these).

## Deliverables & verification
| Deliverable | Verify |
|---|---|
| SAML sign-in | `./run.sh test`: a signed assertion → a session; a bad/expired assertion is rejected |
| SCIM Users provisioning | test: IdP creates a user → appears; IdP deactivates → access dies |
| Group → role mapping | test: a directory group maps to the right Precepta role |
| Identity settings screen | headless render: configure + provisioned-user list |
| Full suite | `./run.sh test` green; sovereign SMOKE PASS |

## Acceptance criteria
- A customer can wire their IdP: staff sign in via SAML; provisioning/deprovisioning
  happens automatically via SCIM; groups map to roles.
- Deactivating a user in the IdP removes their Precepta access without manual steps.
- Sovereignty unaffected (identity talks only to the customer's IdP); full suite green.
