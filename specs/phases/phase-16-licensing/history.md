---
type: PhaseHistory
phase: 16
---

# Phase 16 — History (append-only)

### [DECISION] 2026-08-17 — Licensing model = hybrid (signed key + future heartbeat)
Topics: licensing, sovereignty, egress
Affects-phases: phase-16-licensing, phase-17 (self-host activation/enforcement)
Affects-specs: none (planning)
Detail: A self-hosted install will verify an Ed25519-**signed** license locally
(customer prompts/data never leave), plus a small **disclosed metadata heartbeat**
(license id, install id, plan, seats — no customer data) so the vendor gets
visibility. Chosen over pure-online (dents zero-egress) and pure-offline (no live
visibility). Phase 16 builds the vendor side + the signing scheme; the self-host
client + enforcement are Phase 17.

---

### [DECISION] 2026-08-17 — Trial = 15 days; expiry → grace, then read-only
Topics: licensing, trial, enforcement
Affects-phases: phase-16-licensing, phase-17
Affects-specs: none (planning)
Detail: Default plan is a 15-day trial. On expiry: a banner + short grace, then
the install goes **read-only** (console/audit viewable; new inference refused
until a valid key). The behavior is **defined here but enforced in Phase 17**
(self-host side).

---

### [ARCH_CHANGE] 2026-08-17 — New vendor `licensing/` service (separate from the app)
Topics: architecture, licensing, key-management
Affects-phases: phase-16-licensing, phase-17
Affects-specs: specs/architecture/*
Detail: Licensing/onboarding is a **separate vendor service** (`licensing/`) with
its own DB and the **private signing key (env only, never committed, never in the
self-host image)**. The self-hosted app will embed only the **public** verify key.
This keeps the sovereign control plane clean and the signing key off customer
machines.

---

### [SCOPE_CHANGE] 2026-08-17 — Onboarding site gains a backend (records logins, issues keys)
Topics: onboarding, scope
Affects-phases: phase-16-licensing
Affects-specs: none (planning)
Detail: Earlier the onboarding page was scoped as pure-static with client-side
Google Sign-In. The requirement to **see every login** and **issue license keys**
requires a small backend + DB, so the onboarding site is now server-backed
(client GIS → server verifies the Google ID token → records login → issues key).

---

### [SCOPE_CHANGE] 2026-08-17 — Phase 16 trimmed to the vendor side
Topics: scope, phasing
Affects-phases: phase-16-licensing, phase-17
Affects-specs: none (planning)
Detail: Phase 16 = vendor side only (onboarding, login capture, key issuance,
admin visibility, heartbeat **receiver**). Self-host **activation + heartbeat
client + trial→read-only enforcement + attestation disclosure** move to Phase 17;
payments/seats/hard-kill follow after.

---

### [NOTE] 2026-08-17 — Context: this replaces the failed Vercel deployment attempt
Topics: deployment, sovereignty
Affects-phases: phase-16-licensing
Affects-specs: none
Detail: `console.preceptaai.com` was wrongly running the heavy control plane on
Vercel (read-only serverless disk → "unable to open database file"). The correct
model — the control plane self-hosts on the customer's box; the central domain is
an onboarding/licensing front door — is what this phase implements.

---
