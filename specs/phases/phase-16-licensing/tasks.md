---
type: PhaseTasks
phase: 16
---

# Phase 16 — Tasks

> Mirrors `plan.md`. `[ ]` todo · `[/]` in-progress · `[x]` done.

## Group 0 — License contract + signing lib (blocks all)
- [x] Choose + record the signing primitive (Ed25519 via `cryptography`) and library
- [x] Define the signed-key payload (license_id, subject, plan, issued/expires, seats, key_version)
- [x] `licensing/core`: `issue()`, `verify()`, `status()` (active | grace | expired)
- [x] Keypair handling: private via env `LICENSE_SIGNING_KEY`; **committed dev public key** for Phase 17 (`licensing/keys.py`)
- [x] Tests: round-trip; tampered/forged/garbage rejected; trial active→grace→expired; subscription

## Group 1 — Vendor backend (parallel w/ 2)
- [x] `licensing/` FastAPI service + DB (logins, licenses, installs)
- [x] `POST /onboard` — verify Google ID token, record login, issue 15-day trial, return key + steps
- [x] `POST /license/heartbeat` — metadata-only upsert (whitelist fields, drops customer data); return plan/state
- [x] Admin: `GET /admin/{logins,licenses,installs}` + plan-change (re-sign) + revoke (bearer `LICENSE_ADMIN_TOKEN`)
- [x] Admin dashboard HTML (owner-only) + config (`LICENSE_SIGNING_KEY`, `GOOGLE_CLIENT_ID`, `LICENSE_DB`)

## Group 2 — Onboarding site (parallel w/ 1)
- [x] Landing + GIS Google Sign-In (Console design language) — `licensing/site/index.html`
- [x] On credential → `POST /onboard` → render license key + copy-paste install steps (copy buttons)
- [x] States: loading / signed-in / not-configured / no-JS; served at `GET /` + `/onboard/config` for the client id

## Group 3 — Docs & deploy wiring
- [x] `docs/licensing.md` (model, exact heartbeat payload, trial→grace→read-only [P17], transparency)
- [x] Vendor-service deploy notes (`licensing/README.md`) + `PRECEPTA_LICENSE_URL` convention + keypair-gen (verified)
- [x] Cross-link onboarding/licensing (vendor) vs self-hosted control plane

## Group 4 — Verification
- [x] Unit + integration tests (onboard w/ mock Google verify, heartbeat, admin plan/revoke) — 12 licensing tests
- [x] Onboarding site served + structure checks (GIS, steps, states) + live uvicorn smoke
- [x] Full vendor E2E (2 logins → trials → 2 installs heartbeat → subscription re-issue → revoke)
- [x] Full suite green (410); confirmed `app/`, `web/`, `deploy/` unchanged; SMOKE PASS
