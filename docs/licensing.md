# Precepta Licensing

How Precepta is licensed **without breaking the sovereignty promise.**

## The two surfaces

Precepta deliberately separates two things:

1. **The control plane** — the governed AI runtime — **self-hosts on the
   customer's own machine/server** (`deploy/`). Customer prompts and data never
   leave that boundary. This is the product.
2. **The licensing/onboarding service** (`licensing/`) — **the vendor's** control
   server. It records onboarding logins, issues license keys, and receives
   install heartbeats. It is **never** part of the self-host image.

A central server running everyone's control plane would itself violate
sovereignty — so it doesn't exist. The central domain is only a front door.

## The hybrid license model

- **Signed keys, verified locally.** A license key is an Ed25519-**signed** token
  (`base64url(payload).base64url(signature)`). The vendor signs with a private
  key; the self-host verifies with the embedded **public** key — **offline, no
  network**. This is what lets a sovereign, zero-egress install validate its
  license without phoning home.
- **A metadata-only heartbeat (Phase 17).** So the vendor has visibility, each
  install sends a small periodic heartbeat containing **only**:
  `license_id`, `install_id`, `plan`, `seats`, `version`. **No prompts, no
  customer data, ever** — the receiver whitelists these fields and drops anything
  else. This heartbeat is an allowlisted, **disclosed** egress; the Sovereignty
  Attestation separates *"customer data: zero egress"* from *"licensing: a
  metadata heartbeat to `<PRECEPTA_LICENSE_URL>`."* Honest by construction.

## License payload

| Field | Meaning |
|---|---|
| `license_id` | unique id |
| `subject` | who it's for (email/org) |
| `plan` | `trial` \| `subscription` |
| `issued_at` / `expires_at` | ISO-8601 UTC (trial = issued + 15 days) |
| `seats` | allowed installs (informational in v1) |
| `key_version` | signing-key version (rotation-ready) |

## Lifecycle

1. Sign in on the onboarding site → login recorded → a **15-day trial** key issued.
2. Install Precepta on your own box → **Settings → License** → paste the key →
   verified locally → trial active *(Phase 17)*.
3. Daily heartbeat → the vendor sees the install + its plan *(Phase 17)*.
4. **Expiry (Phase 17):** at day 15 a banner warns; a short **grace** (3 days);
   then the install goes **read-only** — console + audit stay viewable, but new
   inference is refused until a valid key. Moving to a subscription (an admin
   plan change) re-issues a key that clears the block.

## What ships in Phase 16 vs 17

- **Phase 16 (this):** the vendor side — signed-key contract, onboarding + login
  capture + trial issuance, admin visibility (logins/licenses/installs,
  plan-change, revoke), and the heartbeat **receiver**.
- **Phase 17:** the self-host side — the **License** screen + local verification,
  the heartbeat **client** (+ egress allowlist + attestation disclosure), and
  the **trial → read-only** enforcement in the governed pipeline. Then: payments,
  seat limits, notifications, key rotation.

## Transparency

The heartbeat payload is documented above and enforced by a field whitelist in
`licensing/store.record_heartbeat`. A determined self-hoster can inspect or
disable the client (it's their machine, open-core) — licensing here is honest
accounting for honest customers, not DRM.
