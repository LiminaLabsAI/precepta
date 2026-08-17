---
type: PhaseTasks
phase: 17
---

# Phase 17 — Tasks

## Group 0 — app/licensing.py (contract + store)
- [x] Embedded public key (`PRECEPTA_LICENSE_PUBLIC_KEY`, default committed) + own Ed25519 verify
- [x] `verify()`, `status()` (active|grace|expired|unlicensed), `activate()`, `current()`, stable `install_id`
- [x] Store activated key in the app DB (single-row `app_license`)
- [x] Cross-check test: `licensing.core`-issued key verifies in `app.licensing`; tampered/forged/expired/unlicensed (6 tests)
- [x] Add `cryptography` to requirements.txt (Dockerfile installs from it)

## Group 1 — License API + Console
- [x] `GET /v1/license` (manage-gated) + `POST /v1/license/activate` (owner-gated)
- [x] Console License screen (nav item, activate + plan/days/state) — 3 states render

## Group 2 — Heartbeat client + disclosure
- [x] Metadata-only `heartbeat_body()` + `heartbeat_once(poster)` → POST `{PRECEPTA_LICENSE_URL}/license/heartbeat` (fail-soft; no-op when unlicensed)
- [x] Lazy egress auto-approve (`seed_license_egress`, only when licensed) + attestation `licensing` disclosure
- [x] Store last-heartbeat + server-reported plan (`record_heartbeat_result`)

## Group 3 — Enforcement (flag-gated)
- [x] `PRECEPTA_LICENSE_ENFORCE` (default off): expired→`license_expired` / unlicensed→`license_required` 403 on new inference (chat+embeddings)
- [x] Console/audit/models read paths unaffected; off = no effect (local unchanged) — 3 tests

## Group 4 — Verification
- [x] Unit + integration (activate, status, heartbeat, enforcement on/off) — 21 licensing tests
- [x] Full suite 425 green; image rebuilt with cryptography; SMOKE PASS; local works with no key (enforce off) + activation live-verified
