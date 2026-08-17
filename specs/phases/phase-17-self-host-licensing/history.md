---
type: PhaseHistory
phase: 17
---

# Phase 17 — History (append-only)

### [DECISION] 2026-08-17 — Enforcement is flag-gated (default off) so local never breaks
Topics: licensing, enforcement, dx
Affects-phases: phase-17-self-host-licensing
Affects-specs: none
Detail: `PRECEPTA_LICENSE_ENFORCE` defaults OFF — the app works fully regardless
of license in dev/local (honouring "local should work as it was"). Production
installs opt in; then expired/unlicensed → read-only (new inference refused;
console/audit still load), grace → warn.

---

### [DECISION] 2026-08-17 — app carries its OWN verify + public key (no vendor import)
Topics: architecture, licensing, key-management
Affects-phases: phase-17-self-host-licensing
Affects-specs: specs/architecture/*
Detail: `app/licensing.py` implements Ed25519 verify + the embedded public key
directly — it must NOT import the vendor `licensing/` package (not in the app
image, and it holds the admin surface). A cross-check test proves a key issued by
`licensing.core` verifies in `app.licensing`. `cryptography` added to the app
image (deferred here from Phase 16).

---
### [NOTE] 2026-08-17 — Group 0: app/licensing.py (verify/status/activate)
Topics: licensing, self-host, ed25519
Affects-phases: phase-17-self-host-licensing
Affects-specs: none
Detail: `app/licensing.py` — own Ed25519 verify + embedded public key
(`PRECEPTA_LICENSE_PUBLIC_KEY`, default the committed dev key), `verify/status/
activate/current`, stable `install_id`, single-row `app_license` store, and
`enforcing()` (default OFF). Cross-check test confirms a `licensing.core`-issued
key verifies here (app pubkey == vendor pubkey). `cryptography` added to the app
requirements. 6 tests.

---
### [NOTE] 2026-08-17 — Group 1: License API + Console screen
Topics: licensing, api, console
Affects-phases: phase-17-self-host-licensing
Affects-specs: none
Detail: `GET /v1/license` (manage-gated — status: plan/state/days_left/install_id/
enforce/can_edit) + `POST /v1/license/activate` (owner-gated — verify+store, 400
on bad key, audited). Console **License** nav item + `licenseView()` (status card +
activate form) + `loadLicense()`/`app.activateLicense`. 8 tests; 3 UI states render.

---
### [DECISION] 2026-08-17 — Heartbeat only when licensed; scheduling is a deploy concern
Topics: licensing, heartbeat, egress, sovereignty
Affects-phases: phase-17-self-host-licensing
Affects-specs: none
Detail: `app.licensing.heartbeat_once` sends a metadata-only body (license_id,
install_id, plan, seats, version) to `{PRECEPTA_LICENSE_URL}/license/heartbeat`,
fail-soft. It is a **no-op when unlicensed** and opens egress to the license host
(`seed_license_egress`, added_by=system:license) ONLY then — so an unlicensed/
local box never phones home and stays sealed. The attestation now discloses the
licensing heartbeat (host + the 5 fields, contains_customer_data=false) separate
from "customer data egress: none". Periodic cadence is a deployment concern (a
systemd timer / cron calls it) — no always-on in-process loop, keeping the app
simple and tests network-free. 4 tests.

---
### [NOTE] 2026-08-17 — Group 3: trial→read-only enforcement (flag-gated)
Topics: licensing, enforcement, pipeline
Affects-phases: phase-17-self-host-licensing
Affects-specs: none
Detail: `_license_gate()` in main.py — when `PRECEPTA_LICENSE_ENFORCE` is ON and
the license state is expired/unlicensed, `/v1/chat/completions` (+`/v1/inference`)
and `/v1/embeddings` return a 403 (`license_expired`/`license_required`) BEFORE
inference. Console + `/v1/license` + `/v1/models` (read paths) stay available =
read-only, not bricked. Default OFF → local/dev unaffected. 3 tests.

---
### [NOTE] 2026-08-17 — Group 4: verification — Phase 17 complete
Topics: verification, licensing, self-host
Affects-phases: phase-17-self-host-licensing
Affects-specs: none
Detail: 21 licensing tests across G0–G3; **425 total green**. App image rebuilt
with `cryptography` (boots clean); SMOKE PASS (sovereignty intact). Live: License
screen served; activate a trial key → active/14-days-left/subject; bad key → 400;
local inference NOT license-blocked (enforce off — local unaffected). Self-host
licensing loop done: activate → verify locally → status → (heartbeat mechanism) →
flag-gated read-only enforcement.

---
