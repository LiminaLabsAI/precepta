---
type: PhaseOverview
phase: 16
name: Licensing v1 (vendor side) — onboarding, login capture, key issuance & visibility
status: planned
---

# Phase 16 — Licensing v1 (vendor side): onboarding, login capture, key issuance & visibility

> **Verification:** `./run.sh test` (pytest) · **Build:** none
> **Brainstormed:** 2026-08-17

## Goal

Stand up **the vendor side** of Precepta licensing:

1. **`console.preceptaai.com` onboarding site (with a small backend):** a Google
   login is **recorded** → a **15-day trial signed key** is issued → copy-paste
   self-host install steps are shown.
2. **Vendor admin view:** see **every login** and every issued **license** —
   subject (email/org), plan, trial days left, created/expiry — and
   issue / upgrade / revoke.
3. **Heartbeat receiver ready:** the `/license/heartbeat` endpoint + install list
   exist and are tested, so when Phase 17 ships the self-host heartbeat client,
   installs appear automatically.

## Why now

This session proved the central domain should **not** run the sovereign control
plane (Vercel's read-only disk fails the DB write; and a central server running
everyone's control plane would violate sovereignty anyway). The correct split:
the control plane **self-hosts** on each customer's machine; the central domain
is a **distribution + licensing front door**. This phase builds that front door
and gives the founder the commercial visibility/control asked for (who signed in,
what key, trial vs subscription) — **without touching the sovereign core**. The
Ed25519 signing scheme built here is the foundation Phase 17's in-app activation
verifies against.

## Key decisions

| Decision | Choice | Why |
|---|---|---|
| License model | **Hybrid** — Ed25519-signed keys (issued here; verified locally in Phase 17) + a heartbeat receiver ready now | Preserves zero-egress for customer data; only a metadata heartbeat will phone home (Phase 17), disclosed in the attestation |
| Trial default | 15 days, `plan="trial"` | Subscription = a plan change made in admin |
| Onboarding auth | Client Google Sign-In → **server-verifies** the Google ID token → records login + issues key | Must record logins, so server-side verification (supersedes the earlier pure-client-static plan) |
| Vendor service | New `licensing/` service, **own DB**; private signing key = **vendor env only**, never in the app image | The self-host image must never contain the private key; it embeds only the public key |
| Trim boundary | **Vendor side only.** Self-host activation + heartbeat client + trial→read-only enforcement = **Phase 17** | De-risk: deliver login visibility + issuance first |

## Scope — in

- **License contract + lib** (`licensing/core`): signed-key format
  (`license_id`, `subject`, `plan`, `issued_at`, `expires_at`, `seats`,
  `key_version`); `issue()`, `verify()`, `status()` (`active` | `grace` |
  `expired`); tamper + expiry rejection. Keypair: private → env, public →
  committed constant (for Phase 17 to verify against).
- **Vendor backend** (`licensing/`): `POST /onboard` (verify Google ID token,
  record login, issue trial key, return key + install steps),
  `POST /license/heartbeat` (record install last-seen, return current plan),
  **admin dashboard** (logins, licenses, installs; issue/upgrade/revoke), own DB.
- **Onboarding site**: landing + Google Sign-In → shows the issued key +
  copy-paste self-host install steps.
- **Docs**: `docs/licensing.md` (model, what's stored, how the heartbeat will
  work, transparency) + vendor-service deploy notes.
- Tests + a live E2E of the vendor loop.

## Scope — out (→ Phase 17)

- Self-host **activation** (`app/licensing.py`, Console License screen),
  **heartbeat client**, **attestation disclosure + egress auto-approve**, and
  **trial → read-only enforcement** in the governed pipeline.
- Later: payments/Stripe + trial→paid conversion, seat limits, remote hard-kill,
  email notifications, key rotation, multi-org hierarchies, CRM-grade admin.

## Deliverables & verification

| Deliverable | Verify |
|---|---|
| `licensing/core` sign/verify lib | `./run.sh test`: valid verifies; tampered/expired rejected; status states correct |
| `/onboard` + login capture | Live: Google ID token → login recorded → trial key + steps returned |
| `/license/heartbeat` receiver | Test: synthetic ping upserts an install + returns plan; **no customer-data fields accepted** |
| Admin dashboard | Live: lists logins + licenses + installs; issue/upgrade/revoke works |
| Onboarding site | Headless render + live: sign-in reveals the key + copy-paste steps |
| `docs/licensing.md` | Present + accurate |
| Full suite | `./run.sh test` green; **sovereign control plane untouched** |

## Acceptance criteria

- Sign in on the onboarding site → the admin view shows that login, and a
  15-day trial key is issued with copy-paste install steps.
- An admin can change a license's plan (trial → subscription) and revoke it.
- The signed key **verifies** with the committed public key and is **rejected**
  if tampered or expired (proven in tests — the contract Phase 17 relies on).
- The heartbeat endpoint accepts a metadata-only ping and lists the install;
  no customer-data fields are stored.
- Full test suite green; the self-hosted control plane is unchanged.
