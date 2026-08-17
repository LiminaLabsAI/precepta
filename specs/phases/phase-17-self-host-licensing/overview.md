---
type: Phase
phase: 17
name: Self-host licensing — activation, heartbeat, trial enforcement
status: in-progress
tags: [licensing, self-host, activation, heartbeat, enforcement, attestation, ed25519, sovereignty]
---

# Phase 17 — Self-host licensing: activation, heartbeat & trial enforcement

> **Verification:** `./run.sh test` · **Build:** none
> **Depends on:** Phase 16 (vendor side — signed-key contract, heartbeat receiver).

## Goal

The self-hosted Precepta app becomes license-aware:
1. **Activate** a license key (paste it → **verify locally** with the embedded
   public key → store it). Console **License** screen + status banner.
2. **Heartbeat** — a daily, metadata-only check-in to the vendor
   (`PRECEPTA_LICENSE_URL`), **allowlisted egress + disclosed in the attestation**
   (customer data still never leaves).
3. **Enforce** trial → grace → **read-only** on expiry — but **gated by a flag so
   local/dev is never broken.**

## Key decisions

| Decision | Choice | Why |
|---|---|---|
| Verify | Local Ed25519 against an **embedded public key** (`PRECEPTA_LICENSE_PUBLIC_KEY`, default the committed key) | Offline, no phone-home to validate — preserves zero-egress |
| App independence | `app/licensing.py` carries its **own** verify + public key (does NOT import the vendor `licensing/` pkg) | The vendor package isn't in the app image; a cross-check test proves they agree |
| Enforcement | **Flag-gated**: `PRECEPTA_LICENSE_ENFORCE` (default **off**) | Local/dev keeps working with no key; production installs opt in |
| Expiry behavior | active → grace (3d) → **read-only** (new inference refused; console/audit still work) | Firm but non-destructive (Phase 16 decision) |
| Heartbeat egress | Auto-approve `PRECEPTA_LICENSE_URL` host + **disclose in the attestation** | Honest: customer data = zero egress; licensing = a named metadata heartbeat |
| New dep | Add `cryptography` to the app image (verify Ed25519) | Deferred here from Phase 16 as planned |

## Scope — in
- `app/licensing.py`: embedded public key; `verify()`, `status()`, `activate()`,
  `current()`, stable `install_id`, store in the app DB.
- API: `GET /v1/license` (status), `POST /v1/license/activate` (owner-gated).
- Console: **License** screen/section (activate + plan/days/state) + a status banner.
- Heartbeat client: daily metadata-only POST to `PRECEPTA_LICENSE_URL/license/heartbeat`;
  egress auto-approve of that host; attestation disclosure.
- Enforcement: pipeline refuses new inference when `enforce` and state is
  `expired`/`unlicensed`; `grace` warns; console/audit stay usable.
- Tests + live E2E + smoke; `cryptography` added to `requirements.txt` + Dockerfile.

## Scope — out (→ later)
- Payments/Stripe, trial→paid self-serve, seat *limits*, remote hard-kill,
  email notifications, key rotation.

## Deliverables & verification
| Deliverable | Verify |
|---|---|
| `app/licensing.py` verify/status/activate | `./run.sh test`: a key issued by `licensing/core` verifies here; tampered/expired handled |
| `GET/POST /v1/license` | test: activate a valid key → status active; bad key → 400 |
| Console License screen + banner | headless render: activate form + plan/days/state |
| Heartbeat client + disclosure | test: builds a metadata-only body; host auto-approved; attestation lists it |
| Enforcement (flag-gated) | test: enforce+expired → inference 403 read-only; console reads OK; enforce off → unaffected |
| Full suite + smoke | `./run.sh test` green; SMOKE PASS; local still works with no key |

## Acceptance criteria
- Paste a trial key issued by the Phase-16 service → the app verifies it locally,
  shows "trial — N days left", and (when egress is enabled) heartbeats to the vendor.
- With `PRECEPTA_LICENSE_ENFORCE=1` and an expired key past grace → new inference
  is refused (read-only) with a clear message; console + audit still load.
- With enforcement **off** (default), the app works fully regardless of license —
  **local is unaffected**. Attestation discloses the licensing heartbeat host;
  customer-data egress stays zero. Full suite green; SMOKE PASS.
