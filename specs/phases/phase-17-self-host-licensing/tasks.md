---
type: PhaseTasks
phase: 17
---

# Phase 17 — Tasks

## Group 0 — app/licensing.py (contract + store)
- [ ] Embedded public key (`PRECEPTA_LICENSE_PUBLIC_KEY`, default committed) + own Ed25519 verify
- [ ] `verify()`, `status()` (active|grace|expired|unlicensed), `activate()`, `current()`, stable `install_id`
- [ ] Store activated key in the app DB
- [ ] Cross-check test: `licensing.core`-issued key verifies in `app.licensing`; tampered/expired/unlicensed
- [ ] Add `cryptography` to requirements.txt + deploy/Dockerfile

## Group 1 — License API + Console
- [ ] `GET /v1/license` (status) + `POST /v1/license/activate` (owner-gated)
- [ ] Console License screen (activate + plan/days/state) + status banner

## Group 2 — Heartbeat client + disclosure
- [ ] Metadata-only heartbeat body → daily POST to `{PRECEPTA_LICENSE_URL}/license/heartbeat` (fail-soft)
- [ ] Auto-approve the license host in egress + disclose in the attestation
- [ ] Store last-heartbeat + server-reported plan (propagate plan changes)

## Group 3 — Enforcement (flag-gated)
- [ ] `PRECEPTA_LICENSE_ENFORCE` (default off): expired/unlicensed → new inference 403 (read-only); grace warns
- [ ] Console/audit read paths unaffected; off = no effect (local unchanged)

## Group 4 — Verification
- [ ] Unit + integration (activate, status, heartbeat, enforcement on/off)
- [ ] Full `./run.sh test`; rebuild image; SMOKE PASS; local works with no key
