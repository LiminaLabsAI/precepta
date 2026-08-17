---
type: PhasePlan
phase: 17
---

# Phase 17 — Implementation Plan

## Execution order
```
Group 0 → Group 1 → Group 2 → Group 3 → Group 4
```
Sequential — enforcement (G3) depends on activation/status (G0/G1) and the
heartbeat plumbing (G2) shares the license host config.

> **External deps:** `cryptography` (Ed25519 verify) added to the app image;
> the Phase-16 licensing service reachable at `PRECEPTA_LICENSE_URL` (for the
> live heartbeat E2E; unit tests stub it).

## Group 0 — `app/licensing.py` (contract + store)  **(Sequential — blocks all)**
- Embedded public key `PRECEPTA_LICENSE_PUBLIC_KEY` (env; default the committed
  key — same value the Phase-16 dev signer uses).
- `verify(token)` (Ed25519, own impl — no import of the vendor `licensing/` pkg),
  `status(now)` (active|grace|expired|unlicensed), `activate(token)` (verify +
  store in the app DB), `current()`, stable `install_id` (persisted uuid).
- **Cross-check test:** a key issued by `licensing.core.issue` verifies in
  `app.licensing`; tampered/expired handled; unlicensed = no key.
- Add `cryptography` to `requirements.txt` + `deploy/Dockerfile`.
*Commit: `feat(app): license verify/status/activate + embedded public key`*

## Group 1 — License API + Console screen  **(Sequential)**
- `GET /v1/license` (status: plan, state, days_left, install_id, enforce flag).
- `POST /v1/license/activate` (owner-gated; body `{key}` → verify+store or 400).
- Console: **License** section (activate form + plan/days/state) + a header
  banner reflecting state (trial N days / grace / read-only / unlicensed).
*Commit: `feat(console): License screen + activate + status banner`*

## Group 2 — Heartbeat client + disclosure  **(Sequential)**
- Build a **metadata-only** heartbeat body (license_id, install_id, plan, seats,
  version) and POST to `{PRECEPTA_LICENSE_URL}/license/heartbeat` (daily; fail-soft).
- Auto-approve the `PRECEPTA_LICENSE_URL` host in the egress allowlist (like the
  Google-OIDC seed); **disclose it in the attestation** (a "licensing heartbeat"
  entry, separate from customer-data egress = zero).
- Store last-heartbeat + server-reported plan (so a vendor plan change propagates).
*Commit: `feat(app): license heartbeat client + attestation disclosure`*

## Group 3 — Enforcement (flag-gated)  **(Sequential)**
- `PRECEPTA_LICENSE_ENFORCE` (default off). When on and state ∈ {expired,
  unlicensed}: the governed pipeline refuses **new inference** with a clear
  `license_required`/`license_expired` 403; console + audit read paths unaffected.
  `grace` → allow + warn header. When off: no effect (local/dev unchanged).
*Commit: `feat(app): trial->read-only enforcement (flag-gated)`*

## Group 4 — Verification  **(Sequential)**
- Unit + integration (activate, status states, heartbeat body/disclosure,
  enforcement on/off).
- Live E2E against the running Phase-16 service if reachable (else stubbed).
- Full `./run.sh test`; rebuild image; **SMOKE PASS**; confirm **local works with
  no key** (enforcement off by default).
*Commit: `test: self-host licensing E2E + enforcement`*
