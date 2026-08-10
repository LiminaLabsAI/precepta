---
type: Phase History
phase: 14
name: deploy-pilot
---

# Phase 14 — Deploy: Sovereign Pilot · History

### [DECISION] 2026-08-10 — Scope: the "pilot slice" (not full production)
Topics: deploy, scope, sovereignty
Affects-phases: phase-14-deploy-pilot
Affects-specs: none
Detail: Chose the smallest complete slice — one customer can self-host via an
egress-locked docker-compose bundle with all helper models in-boundary, provably
zero-egress — over "just close TD-009" (still un-installable) and "full
production" (Helm/Postgres/Vault/air-gap/HA/SCIM — weeks of speculative infra).
Rationale: this is the minimum that makes the sovereignty promise both *true*
and *installable*, which is what unblocks a first pilot; enterprise hardening
waits until a real customer's environment says which parts matter.

---

### [DECISION] 2026-08-10 — Egress lock by construction (internal network)
Topics: egress, sovereignty, docker
Affects-phases: phase-14-deploy-pilot
Affects-specs: none
Detail: Use a Docker `internal: true` network so the app container has **no
route to the internet at all** — zero-egress is guaranteed by construction, not
merely by policy. A startup egress probe records the (failed) outbound attempt
into the tamper-evident chain and the Sovereignty Attestation, so the claim is
provable. Multi-host egress-allowlists (aevrin/filter, g0efilter, DockerWall)
behind the app-layer in-boundary allowlist are deferred to a later phase.

---

### [DECISION] 2026-08-10 — TD-009 closed by config + bundling, not new code
Topics: td-009, helper-models, ollama
Affects-phases: phase-14-deploy-pilot
Affects-specs: none
Detail: The router/intent model resolution already supports a local Ollama
fallback, and embeddings already use local Ollama. So the deploy closes TD-009
by bundling an **Ollama** service (with a model-init that pre-pulls the router +
`nomic-embed-text` models into a volume) and pointing the router at it — the
deploy `.env` simply omits the public HF vars. No governed-core change.

---

### [ARCH_CHANGE] 2026-08-10 — Additive deploy layer (DIP, no core change)
Topics: deploy, dip, architecture
Affects-phases: phase-14-deploy-pilot
Affects-specs: DESIGN.md#deploy, specs/architecture (sync at completion)
Detail: The entire phase is a new `deploy/` directory (Dockerfile, compose,
.env.example, up/doctor scripts, README, smoke test) plus a startup egress probe
and an attestation extension. State stays SQLite (volume); secrets stay `.env` +
`SecretStorePort`; Postgres/KMS remain behind their ports for a later phase.
"New cloud/store/deploy = one adapter/layer, never a core change" (two-way door).

---

### [DISCOVERY] 2026-08-10 — Research: egress lock + Ollama bundling patterns
Topics: research, docker, ollama
Affects-phases: phase-14-deploy-pilot
Affects-specs: none
Detail: Web research confirmed the approach. Egress control: Docker
`internal: true` networks (all-or-nothing, ideal for the single-node pilot) +
mature egress-filter containers for a future host-allowlist. Ollama in compose:
persistent `/root/.ollama` volume + an init container that pre-pulls models once
(offline after the first pull) is the standard, well-trodden pattern.

---

### [NOTE] 2026-08-10 — Why now / strategic framing
Topics: strategy, pilot
Affects-phases: phase-14-deploy-pilot
Affects-specs: none
Detail: The governed control plane + smart router are built and live; the only
thing between Precepta and a real customer is a deployable, in-boundary,
provably-sovereign package. TD-009 (router model on public HF) is a direct
contradiction of the core promise — closing it + shipping an installable bundle
turns "impressive demo" into "a bank could run this in a pilot," and strengthens
the fundraising story ("and it runs, provably, inside the customer's network").
