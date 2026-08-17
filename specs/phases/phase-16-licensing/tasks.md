---
type: PhaseTasks
phase: 16
---

# Phase 16 — Tasks

> Mirrors `plan.md`. `[ ]` todo · `[/]` in-progress · `[x]` done.

## Group 0 — License contract + signing lib (blocks all)
- [ ] Choose + record the signing primitive (Ed25519) and library
- [ ] Define the signed-key payload (license_id, subject, plan, issued/expires, seats, key_version)
- [ ] `licensing/core`: `issue()`, `verify()`, `status()` (active | grace | expired)
- [ ] Keypair handling: private via env `LICENSE_SIGNING_KEY`; **commit the public key** for Phase 17
- [ ] Tests: round-trip; tampered rejected; expired→expired; grace window

## Group 1 — Vendor backend (parallel w/ 2)
- [ ] `licensing/` FastAPI service + DB (logins, licenses, installs, heartbeats)
- [ ] `POST /onboard` — verify Google ID token, record login, issue 15-day trial, return key + steps
- [ ] `POST /license/heartbeat` — metadata-only upsert of an install; reject unexpected fields; return plan
- [ ] Admin: `GET /admin/{logins,licenses,installs}` + plan-change (re-sign) + revoke
- [ ] Admin dashboard HTML (owner-only) + config (`LICENSE_SIGNING_KEY`, `GOOGLE_CLIENT_ID`, `LICENSE_DB`)

## Group 2 — Onboarding site (parallel w/ 1)
- [ ] Landing + GIS Google Sign-In (Console design language)
- [ ] On credential → `POST /onboard` → render license key + copy-paste install steps (copy buttons)
- [ ] States: loading / signed-in / not-configured / no-JS

## Group 3 — Docs & deploy wiring
- [ ] `docs/licensing.md` (model, exact heartbeat payload, trial→grace→read-only [P17], transparency)
- [ ] Vendor-service deploy notes + `PRECEPTA_LICENSE_URL` convention
- [ ] Cross-link onboarding/licensing (vendor) vs self-hosted control plane

## Group 4 — Verification
- [ ] Unit + integration tests (onboard w/ mock Google verify, heartbeat, admin plan/revoke)
- [ ] Headless render of the onboarding site (pre/post sign-in)
- [ ] Live vendor E2E (onboard → admin → plan change → revoke → heartbeat shows install)
- [ ] Full `./run.sh test` green; confirm `app/` (sovereign core) unchanged
