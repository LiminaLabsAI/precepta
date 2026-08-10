---
type: Phase Plan
phase: 14
name: deploy-pilot
---

# Phase 14 — Deploy: Sovereign Pilot · Implementation Plan

Execution order:
`Group 0 → Group 1 → Group 2 → Group 3 → Group 4 → Group 5`

Mostly sequential — each group depends on the previous (image → compose →
in-boundary models → egress lock/attestation → UX → verify). All additive: a
new `deploy/` directory + small config, **no change to the governed core**.

External dependencies: **Docker + docker-compose**, **Ollama** (already used),
and a machine with enough RAM (a small CPU model keeps the demo path working;
GPU is the customer's, passed through).

---

## Group 0 — App container image
**Sequential.** Blocks all. Commit: `infra(deploy): app Dockerfile + image build`

- `deploy/Dockerfile`: pinned Python 3.14 base; install `requirements.txt`; copy
  `app/` + `web/`; non-root user; expose 8000; entrypoint = uvicorn.
- `.dockerignore` (exclude `.venv`, `preceptaai.db*`, `.env`, `.git`).
- Verify: `docker build` succeeds; the image runs `/health` 200 standalone.

## Group 1 — Compose stack + config
**Sequential.** Commit: `infra(deploy): docker-compose stack + .env.example`

- `deploy/docker-compose.yml`:
  - `app` service (built image), Console on the host (`127.0.0.1:8000:8000`),
    data volume for `preceptaai.db` + secrets.
  - `ollama` service (`ollama/ollama`), persistent `ollama_data` volume.
  - `model-init` service: waits for Ollama health, `ollama pull`s the router +
    embedding models, then exits (`restart: "no"`).
  - **`internal: true` network** carrying `app` + `ollama` (no internet route);
    only the Console port is published to the host.
- `deploy/.env.example`: org name, admin email/owner, router→`ollama` config
  (no HF), model names, ports — every line commented in plain English.
- Verify: `docker compose up` → all services healthy; Console reachable on the host.

## Group 2 — In-boundary helper models (TD-009)
**Sequential.** Commit: `infra(deploy): in-boundary router + embedding models`

- Configure the router (`app/router/intent.py` resolution) to use the bundled
  **local Ollama** — the code already supports this; the deploy `.env` simply
  omits the HF vars and points at the `ollama` service.
- `model-init` pulls the router/intent model + `nomic-embed-text` (embeddings)
  into the `ollama_data` volume.
- Verify: a governed `auto` request classifies + routes via local Ollama;
  network capture / logs show **no connection to any HF host**.

## Group 3 — Egress lock + attestation of infra
**Sequential.** Commit: `feat(sovereign): startup egress probe → attestation`

- The `internal: true` network already blocks the app's outbound by construction.
- Add a **startup egress probe** (`app/sovereign/…`): on boot (and on demand),
  attempt an outbound TCP/HTTP connection to a known public host with a short
  timeout; record the result (blocked/allowed) to the tamper-evident chain.
- Extend `build_attestation` to include the egress-probe result
  ("egress: blocked, verified") alongside the existing config + audit proofs.
- Console: surface the egress result in the Policies/Attestation view (the
  existing `egressProbeStatus` hook becomes real).
- Verify: inside the app container the probe fails; the attestation shows blocked.

## Group 4 — One-command UX + runbook
**Sequential.** Commit: `infra(deploy): one-command up + doctor + runbook`

- `deploy/up.sh` (and/or `deploy/Makefile`): build → up → wait for model-init →
  print the Console URL + first-login note. Idempotent.
- `deploy/doctor.sh` (or `precepta doctor`): checks Docker present, ports free,
  models pulled, disk/RAM sane — names the exact fix, not a stack trace.
- `deploy/README.md`: prerequisites → one-command up → first login → add your
  models → generate the attestation → troubleshooting. Plain English.
- **In-product Deployment screen** (`web/console.html`): new left-nav item +
  `deploymentView()` + `/v1/deployment` (or reuse `/health`+`/attestation`+
  `/workflow`). Shows **live sovereignty status** (in-boundary · egress blocked ·
  models loaded · attestation ready), a **setup checklist** (done steps ✓ from
  real state; remaining steps = buttons to Inference/Members/Attestation), and a
  **copy-runbook** action. Surfaced in first-run Setup. Every ✓ is live
  (backend-real). Browser-validate.
- Verify: a clean checkout + `up.sh` yields a working Console following only the
  README; the Deployment screen's status ticks match the real stack state.

## Group 5 — Verification
**Sequential.** Commit: `test(deploy): sovereign smoke test + docs`

- `deploy/smoke.sh`: compose up → `/health` → a governed `auto` request (200,
  routed via local Ollama) → `/attestation` (egress blocked, verified) →
  compose down. Exit non-zero on any failure.
- Confirm SQLite + models persist across a `down`/`up` (volumes).
- Update `HANDOFF.md` + changelog; mark FEAT-009 (pilot slice) + TD-009 resolved;
  note the deferred items (Helm/Postgres/Vault/air-gap/SCIM/host-allowlist).

---

## Deferred out of this phase (tracked, later)
- **Enterprise packaging:** Helm/K8s · Postgres adapter · Vault/KMS (TD-007
  encryption-at-rest) · air-gap install media · HA/multi-node · SCIM (FEAT-018).
- **Multi-host egress-allowlist** for the customer's models on other LAN hosts
  (`aevrin/filter` / `g0efilter` / DockerWall behind the same in-boundary
  allowlist we already enforce at the app layer).
