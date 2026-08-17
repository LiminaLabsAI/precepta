---
type: PhasePlan
phase: 16
---

# Phase 16 — Implementation Plan

## Execution order

```
Group 0 → (Groups 1 + 2 in parallel) → Group 3 → Group 4
```

- **Group 0** — license contract + signing lib (blocks everything; both the
  backend and Phase 17 depend on the format).
- **Groups 1 + 2** — vendor backend and onboarding site (parallel; the site
  calls the `/onboard` contract fixed in Group 0/1).
- **Group 3** — docs + deploy wiring (sequential).
- **Group 4** — verification (sequential).

> **External dependencies:** Ed25519 signing (`cryptography` or PyNaCl — pick in
> Group 0 and record it); a live Google OAuth client (client id already exists)
> for ID-token verification; the vendor service needs a persistent DB (SQLite for
> the pilot, Postgres-ready).

---

## Group 0 — License contract + signing lib  **(Sequential — blocks all)**

**Deliver the signed-key format and the issue/verify/status library.**

- Choose the signing primitive (Ed25519) and library; record the choice.
- Define the key payload: `license_id`, `subject` (email/org), `plan`
  (`trial` | `subscription`), `issued_at`, `expires_at`, `seats`, `key_version`.
- Encode as a compact token: `base64url(payload_json).base64url(signature)`.
- `licensing/core`:
  - `issue(payload, private_key) -> token`
  - `verify(token, public_key) -> payload | raises InvalidLicense`
  - `status(payload, now) -> {plan, days_left, state}` where
    `state ∈ {active, grace, expired}` (grace window is a constant, e.g. 3 days).
- Keypair handling: private key read from a vendor env var (`LICENSE_SIGNING_KEY`,
  never committed); **commit the public key** as a constant the app will embed in
  Phase 17.
- Tests: round-trip issue→verify; **tampered token rejected**; **expired payload
  → `expired`**; trial within window → `active`; within grace → `grace`.

*Commit: `feat(licensing): signed-key contract + verify/status lib`*

---

## Group 1 — Vendor backend  **(Parallel with Group 2)**

**The vendor control server: onboarding, issuance, heartbeat receiver, admin.**

External deps: Google JWKS (verify ID tokens); the Group 0 lib; a DB.

- New `licensing/` FastAPI service with its own DB (tables: `logins`,
  `licenses`, `installs`, `heartbeats`).
- `POST /onboard` — body: Google ID-token (credential from GIS). Verify the
  token server-side (signature + `aud` = our client id + `exp`); record the
  login (email, name, sub, first/last seen); create-or-get a **trial** license
  (15 days) for that subject; return `{ key, subject, plan, expires_at, steps }`.
- `POST /license/heartbeat` — body: `{ license_id, install_id, plan, seats,
  version }` (metadata only — **reject/ignore any unexpected fields; never store
  prompt/customer data**). Upsert the install, record last-seen, return the
  license's current plan/status.
- **Admin dashboard** (owner-only — gate to the founder's email/an admin token):
  `GET /admin/logins`, `GET /admin/licenses`, `GET /admin/installs`;
  `POST /admin/licenses/{id}/plan` (trial↔subscription, re-sign + re-issue),
  `POST /admin/licenses/{id}/revoke`. A simple server-rendered HTML admin view.
- Config: `LICENSE_SIGNING_KEY`, `GOOGLE_CLIENT_ID`, `LICENSE_DB`, admin auth.

*Commit: `feat(licensing): onboarding, issuance, heartbeat receiver, admin`*

---

## Group 2 — Onboarding site  **(Parallel with Group 1)**

**The public "Get Precepta" page for `console.preceptaai.com`.**

- Landing (what Precepta is, 1–2 lines) in the Console's design language.
- **Google Sign-In** (GIS button) → on credential, `POST /onboard` → render the
  issued **license key** + the **copy-paste self-host install steps** (clone,
  `cp .env`, `./deploy/up.sh`, open the console) with copy buttons.
- Honest states: loading / signed-in / sign-in-not-configured / no-JS.
- Served by the vendor backend (or as static assets it hosts) so `/onboard`
  is same-origin.

*Commit: `feat(licensing): Get-Precepta onboarding site`*

---

## Group 3 — Docs & deploy wiring  **(Sequential)**

- `docs/licensing.md`: the hybrid model, the key format, exactly **what the
  heartbeat will send** (license id, install id, plan, seats, version — no
  customer data), trial→grace→read-only (enforced in Phase 17), transparency.
- Vendor-service deploy notes (own DB; `LICENSE_SIGNING_KEY` as a secret; the
  onboarding domain); the `PRECEPTA_LICENSE_URL` convention Phase 17's client
  will call.
- Cross-link: onboarding/licensing (vendor) vs the self-hosted control plane.

*Commit: `docs: licensing model + vendor deploy`*

---

## Group 4 — Verification  **(Sequential)**

- Unit: Group 0 lib (already) + `/onboard` (mock Google verify), heartbeat
  upsert (metadata-only), admin plan-change re-signs a valid key, revoke.
- Headless render of the onboarding site (pre/post sign-in).
- Live vendor E2E: onboard (mock/real token) → admin lists the login + license →
  change plan → revoke → heartbeat ping shows the install.
- Full `./run.sh test` green; confirm **no change to `app/`** (sovereign core).

*Commit: `test: licensing vendor-side E2E`*
