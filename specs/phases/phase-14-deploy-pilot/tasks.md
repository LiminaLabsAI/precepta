---
type: Phase Tasks
phase: 14
name: deploy-pilot
---

# Phase 14 — Deploy: Sovereign Pilot · Tasks

Legend: `[ ]` todo · `[/]` in progress · `[x]` done

## Group 0 — App container image
- [ ] `deploy/Dockerfile` (pinned Python, deps, app + web, non-root, uvicorn entrypoint)
- [ ] `.dockerignore` (.venv, preceptaai.db*, .env, .git)
- [ ] `docker build` succeeds; image runs `/health` 200 standalone

## Group 1 — Compose stack + config
- [ ] `deploy/docker-compose.yml`: app + ollama + model-init services
- [ ] `internal: true` network (app + ollama, no internet); only Console port published
- [ ] data volume (SQLite + secrets) + `ollama_data` volume
- [ ] `deploy/.env.example` — commented, in-boundary defaults, no HF
- [ ] `docker compose up` → all healthy; Console reachable on host

## Group 2 — In-boundary helper models (TD-009)
- [ ] Router configured to use bundled local Ollama (omit HF vars)
- [ ] `model-init` pulls router/intent model + `nomic-embed-text`
- [ ] Governed `auto` request routes via local Ollama; **no HF contacted**

## Group 3 — Egress lock + attestation
- [ ] Startup egress probe (outbound attempt, short timeout, recorded to chain)
- [ ] Extend `build_attestation` with the egress result ("blocked, verified")
- [ ] Console surfaces the real egress-probe result
- [ ] Inside the container the probe fails; attestation shows blocked

## Group 4 — One-command UX + runbook
- [ ] `deploy/up.sh` (build → up → wait → print Console URL) idempotent
- [ ] `deploy/doctor.sh` (Docker? ports? models? disk/RAM?) with plain fixes
- [ ] `deploy/README.md` runbook (prereqs → up → login → add models → attestation → troubleshoot)
- [ ] In-product **Deployment** screen: new nav item + `deploymentView()` — live sovereignty status, setup checklist (done ✓ from real state; remaining = buttons), copy-runbook; surfaced in first-run Setup; browser-validated
- [ ] A clean checkout + `up.sh` yields a working Console via the README only

## Group 5 — Verification
- [ ] `deploy/smoke.sh`: up → health → governed request → attestation egress=blocked → down
- [ ] SQLite + models persist across down/up (volumes)
- [ ] Update HANDOFF + changelog; mark FEAT-009 (pilot) + TD-009 resolved; note deferred items
