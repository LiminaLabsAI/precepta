---
type: Phase Tasks
phase: 14
name: deploy-pilot
---

# Phase 14 — Deploy: Sovereign Pilot · Tasks

Legend: `[ ]` todo · `[/]` in progress · `[x]` done

## Group 0 — App container image
- [x] `deploy/Dockerfile` (pinned Python, deps, app + web, non-root, uvicorn entrypoint)
- [x] `.dockerignore` (.venv, preceptaai.db*, .env, .git)
- [x] `docker build` succeeds; image runs `/health` 200 standalone

## Group 1 — Compose stack + config
- [x] `deploy/docker-compose.yml`: app + ollama + model-init services
- [x] `internal: true` network (app + ollama, no internet); only Console port published
- [x] data volume (SQLite + secrets) + `ollama_data` volume
- [x] `deploy/.env.example` — commented, in-boundary defaults, no HF
- [x] `docker compose up` → all healthy; Console reachable on host

## Group 2 — In-boundary helper models (TD-009)
- [x] Router configured to use bundled local Ollama (omit HF vars)
- [x] `model-init` pulls router/intent model + `nomic-embed-text`
- [x] Governed `auto` request routes via local Ollama; **no HF contacted**

## Group 3 — Egress lock + attestation
- [x] Startup egress probe (outbound attempt, short timeout, recorded to chain)
- [x] Extend `build_attestation` with the egress result ("blocked, verified")
- [x] Console surfaces the real egress-probe result
- [x] Inside the container the probe fails; attestation shows blocked

## Group 4 — One-command UX + runbook
- [x] `deploy/up.sh` (build → up → wait → print Console URL) idempotent
- [x] `deploy/doctor.sh` (Docker? ports? models? disk/RAM?) with plain fixes
- [x] `deploy/README.md` runbook (prereqs → up → login → add models → attestation → troubleshoot)
- [x] In-product **Deployment** screen: new nav item + `deploymentView()` — live sovereignty status, setup checklist (done ✓ from real state; remaining = buttons), copy-runbook; surfaced in first-run Setup; browser-validated
- [x] A clean checkout + `up.sh` yields a working Console via the README only

## Group 5 — Verification
- [x] `deploy/smoke.sh`: up → health → governed request → attestation egress=blocked → down
- [x] SQLite + models persist across down/up (volumes)
- [x] Update HANDOFF + changelog; mark FEAT-009 (pilot) + TD-009 resolved; note deferred items
