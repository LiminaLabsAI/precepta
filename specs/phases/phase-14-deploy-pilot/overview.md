---
type: Phase Overview
phase: 14
name: deploy-pilot
status: planned
created: 2026-08-10
backlog: FEAT-009, TD-009, TD-007
---

# Phase 14 — Deploy: Sovereign Pilot (self-host)

## Goal
A regulated customer can stand up Precepta **inside their own network with one
command**, with **all helper models running in-boundary**, and the whole stack
**provably zero-egress** (a signed Sovereignty Attestation that includes an
infra-level egress test). This is the smallest complete slice that turns
Precepta from "impressive demo" into "a bank could run this in a pilot."

> The product's whole promise is *"your data never leaves your network — and we
> can prove it."* Today the router's own model calls **public** Hugging Face
> (TD-009), and there is no install package. This phase closes both.

## Problem statement
- **Sovereignty hole (TD-009):** Precepta's router/intent model (`.env` HF,
  `app/router/intent.py`) reads the customer's prompt to classify it and, in
  dev, points at `router.huggingface.co` — so prompts leave the boundary on
  every routed request. This directly contradicts the core promise.
- **No install path (FEAT-009):** there is no package a customer can run inside
  their network. Every feature built on top is unadoptable until this exists.

## Who is suffering · Why now
- **Compliance/security leads** at DPDP-bound regulated firms — can't adopt a
  product whose own router leaks prompts and that can't be installed in-VPC.
- **The founder** — needs a real "run it in your network, here's the proof"
  story for a first pilot (and a stronger fundraising position).
- **Why now:** the governed control plane + smart router are built and live; the
  only thing between Precepta and a real customer is a deployable, in-boundary,
  provably-sovereign package. The code already supports the in-boundary path
  (the router falls back to a local Ollama; embeddings already use local
  Ollama), so closing TD-009 is mostly configuration + bundling.

## Key decisions
| Decision | Choice |
|---|---|
| Form factor | Single-node **docker-compose** all-in-one (defer Helm/K8s) |
| Egress lock | Docker **`internal: true` network** — the app has no internet route; zero-egress by construction, not just by policy |
| Helper models (TD-009) | Bundled **Ollama** service serves the router/intent model + embeddings (`nomic-embed-text`); Precepta configured to use local Ollama; **no public HF** |
| State store | **SQLite** on a persisted volume (defer Postgres) |
| Secrets | `.env` + the existing `SecretStorePort` (defer Vault/KMS) |
| Attestation | Extend the Sovereignty Attestation with a **startup egress probe** → "egress: blocked, verified" |
| Model preload | An **init container** pulls the router + embedding models once into a persistent volume (works offline after the first pull) |
| Structure | Everything additive in a `deploy/` folder + config — **no core change** (DIP, two-way door) |

## Scope
**In:**
- `deploy/Dockerfile` — the app image (pinned Python, deps, app + web console).
- `deploy/docker-compose.yml` — app + ollama + model-init on an **internal
  (no-internet) network**; a persisted data volume; the Console exposed on the host.
- `deploy/.env.example` — in-boundary config (router → local Ollama; no public
  HF), every variable explained in one plain-English line.
- One-command bring-up (`deploy/up.sh` / `make up`) + a `doctor` health check.
- Model preload (router model + embeddings) via the init container.
- Egress lock (internal network) + a **startup egress probe** wired into the
  Sovereignty Attestation; the Console shows the result.
- `deploy/README.md` — the customer runbook.
- An in-product **Deployment** screen (new left-nav item), surfaced in first-run
  Setup: **live sovereignty status** (running in-boundary · egress blocked ·
  helper models in-boundary · attestation ready — all from real endpoints), a
  **setup checklist** (deploy steps shown done; remaining steps are buttons that
  jump to the right screen), and a **"copy the runbook"** action so an operator
  can hand the exact steps to IT / a production environment. Backend-real: every
  status tick comes from a live endpoint, never a fabricated ✓.

**Out (deferred to a later phase):**
- Helm/K8s charts, Postgres adapter, Vault/KMS secret backend.
- Air-gap install media, HA / multi-node.
- Auto-provision users (SCIM, FEAT-018).
- Egress-allowlist for the customer's models running on **other** LAN hosts
  (the single-node all-in-one stack is the pilot posture; a host-allowlist —
  e.g. `aevrin/filter` / `g0efilter` — is a later phase).
- GPU orchestration (the customer provides the GPU; compose passes it through).
- Encryption-at-rest via KMS (TD-007 — the attestation-scope half is done; KMS
  is deferred with Vault).

## Deliverables & verification
Test command: `./run.sh test` (unit) **+ a new deploy smoke test**
(`deploy/smoke.sh`) that brings the stack up and checks the sovereign path.
No build step for the app itself; the deploy artifact is the container image.

| Deliverable | Verification |
|---|---|
| App image + compose stack | `docker compose up` brings the stack up healthy (`/health` 200) |
| In-boundary helper models (TD-009 closed) | a governed `auto` request routes via the **local Ollama** router; **no HF host is contacted** |
| Egress lock | from inside the app container, an outbound probe to a public host **fails/times out** |
| Attestation covers infra | the Sovereignty Attestation reports **"egress: blocked, verified"** |
| One-command UX + runbook | a new operator follows `deploy/README.md` and reaches a working Console |
| Smoke test | `deploy/smoke.sh`: up → governed request → attestation egress=blocked → down, green |

## Acceptance criteria
- **One command** brings up the full stack on a single node.
- A governed request works end-to-end using the **in-boundary Ollama** router —
  **zero prompts leave the boundary** (TD-009 closed).
- The stack is **egress-locked by construction** (internal network) and the
  Sovereignty Attestation **proves it** (egress probe = blocked, verified).
- SQLite state + models **persist** across a restart (volumes).
- A first-time operator can follow the runbook without prior Precepta knowledge.
- **No change to the governed core** — the deploy is an additive `deploy/` layer.

## Pre-mortem (risks the plan must handle)
1. **Internal network also blocks the customer's own model hosts.** → pilot is
   single-node all-in-one (models in the same stack); a host-allowlist is a
   later phase, called out in the runbook.
2. **First model pull needs internet.** → the init container pulls once into a
   volume during setup; document an offline/pre-baked path for air-gapped sites.
3. **Egress "proof" is only as good as the probe.** → the probe attempts a real
   outbound connection and records the failure into the tamper-evident chain;
   the internal network makes success impossible, not just unlikely.
4. **GPU/RAM sizing surprises.** → the `doctor` check + runbook state minimums;
   a CPU-only fallback (small models) keeps the demo path working.
5. **Scope creep into full production.** → HA/Helm/Postgres/Vault/air-gap/SCIM
   are explicitly out; this phase is the single-node provable-sovereign pilot.
