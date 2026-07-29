# preceptaai — Vision & Design

> **A self-hosted control plane for running open-source AI models on your own infrastructure —
> with routing, governance, and tamper-evident audit built in. Total control. Data never leaves.
> Compliance by default.**
>
> **Status:** Draft v2 (pre-founding) · **Owner:** sarang · **Last updated:** 2026-07-20
> **Companion:** `IMPLEMENTATION_PLAN.md` (V1 closed-loop build plan).

This document combines the **Vision** (Part I — why, who pays, wedge, moat) and the **Design**
(Part II — architecture, ports, the closed sovereign loop, contracts).

## Contents
- **Part I — Vision**: problem · vision · product layers · who pays · wedge · moat · architecture · scope · gaps · risks · crux
- **Part II — Design**: the closed sovereign loop · ports & adapters · Sovereign Mode · attestation · gateway & governance contracts · infra visibility · module layout

---
---

# PART I — VISION

## 1. One-line vision

**A self-hosted control plane for running open-source AI models on your own infrastructure —
with routing, governance, and tamper-evident audit built in. Total control. Data never leaves.
Compliance by default.**

The intelligence router is a *feature*. The product is the **control plane** that gives a
regulated enterprise total control over open-source AI running on infrastructure they own.

## 2. Why this exists (the problem)

Regulated and data-sensitive enterprises want AI, but:

1. **They can't send data to third-party clouds.** Compliance (DPDP, HIPAA, GDPR, RBI, SOC2)
   and sovereignty rules forbid it. Cloud AI APIs are off the table for their sensitive workloads.
2. **They want open-source models on their own infra** — for data control, cost, and to avoid
   vendor lock-in — but wiring up serving + routing + governance + audit themselves is a project
   they don't want to own.
3. **Their AI usage is ungoverned.** No enforced policy, no PII controls, no audit trail an
   auditor accepts. Compliance sign-off is a manual scramble.

These are one problem: **enterprises have no easy, self-owned control plane over their AI.**

## 3. The vision (the world it creates)

> preceptaai is the **control plane** an enterprise runs on its own infrastructure so that
> **every AI call — across any open-source model — is routed, policy-enforced, PII-scrubbed,
> and tamper-evidently audited, without data ever leaving their network.**

- **Sovereign** — models and data stay on infra they own (on-prem, VPC, or a sovereign local cloud).
- **Open** — run any open-source model; swap freely; no vendor lock-in.
- **Governed** — policy + audit + compliance evidence on every request, by default.
- **In their control** — one pane of glass: which models, who may use them, what's allowed, full audit.

**Positioning vs the obvious comparisons:**
- **vs Together.ai / hosted providers:** they host models on *their* cloud; we are the control
  plane you run on *your own* infra — data and models stay yours.
- **vs Red Hat AI Factory / NVIDIA NIM:** they own the heavy, expensive, GPU-datacenter,
  large-enterprise/gov end. We are the **lightweight, opinionated, batteries-included** option
  for mid-market regulated firms who can't deploy a Red Hat AI Factory.
- **vs Portkey / TrueFoundry / Kong / Lunar / LiteLLM (AI gateways):** they mostly govern access
  to *hosted* providers; our center of gravity is **self-hosted open-source models + governance
  as one integrated, sovereignty-first control plane** for a specific regulated wedge.

## 4. The product — layered stack

| Layer | What it does | Build vs Integrate |
|---|---|---|
| **1 · Model plane** | Connect & serve open-source models: local (Ollama), self-hosted serving (vLLM / TGI on their GPUs), sovereign local clouds (Neysa / Shakti) | **Integrate** — never rebuild vLLM/serving |
| **2 · Router** | Route across models/backends by cost / latency / intent / policy | **Build** — now a *feature*, not the product |
| **3 · Governance control plane** | Policy enforcement, PII/injection firewall, tamper-evident audit, compliance evidence | **Build — the payable core** |
| **4 · Interfaces** | **API (primary)**, ChatGPT-style chat app, admin console | Build |
| **Cross-cutting** | SSO/RBAC, multi-tenancy, air-gapped/Helm deploy, certifications | Build / earn — enterprise table stakes |

The chat app and the router are *layers*, not the pitch. The **API is the primary surface** —
enterprises govern AI inside their apps and pipelines, not through a chat box.

## 5. Who pays, and the value

**Buyer:** compliance / security leadership (CISO, Head of Compliance) at **regulated,
data-sensitive enterprises** — not developers, not individuals.

**Why they pay:**
1. **Sovereignty** — data + models never leave their network (the #1 driver).
2. **Cost** — own infra + open-source models vs per-token API bills.
3. **No lock-in** — swap open-source models freely.
4. **Governance/audit built-in** — compliance sign-off, not a bolt-on.
5. **Total control, one pane** — models, access, policy, and audit in one place.

## 6. The wedge (beachhead — where the giants aren't)

> **DPDP-bound Indian mid-market regulated firms** (fintech / health / public-sector-adjacent)
> who need sovereignty + governance but can't deploy a Red Hat AI Factory — served by a
> lightweight control plane, bundled with a **sovereign local cloud (Neysa / Shakti)**.

Not "everyone, everywhere." One jurisdiction, one buyer profile, one channel. Expand later.

## 7. The moat — honest

**There is no technical moat** — serving is open (vLLM), governance techniques are known.
Durable moats must be *earned*:

1. **Control-plane lock-in (strongest)** — once every AI call flows through it and years of
   policies + audit history live in it, ripping it out is painful. Become the chokepoint.
2. **Compliance system-of-record** — be the evidence source auditors depend on → renewal is
   non-negotiable.
3. **Jurisdiction / compliance-content moat** — pre-built policy packs mapped to DPDP / HIPAA /
   RBI / sector controls, tedious to replicate (the Vanta/Drata pattern).
4. **Channel moat** — partner with Neysa / Shakti: they have sovereign infra but no governance
   plane; we have the plane but no infra. Bundled = distribution neither has alone.

*Weak / aspirational:* a data flywheel — hard when self-hosted, because the data never returns to us.

## 8. Architecture (summary — see Part II for detail)

- **Stack:** Python + FastAPI + SQLite (existing `preceptaai.db`) — the control plane.
- **Model plane:** integrates Ollama (local), vLLM / TGI (self-hosted serving), and
  Neysa / Shakti (sovereign clouds) via a uniform provider-adapter interface.
- **Governance:** policy engine + firewall + tamper-evident audit (SHA-256 hash chain).
- **Interfaces:** OpenAI-compatible API (primary) + ChatGPT-style UI + admin console.
- **Deployment:** self-hosted — container/Helm, VPC or air-gapped; secrets via the customer's KMS/Vault.
- **Auth:** SSO/SAML + RBAC (admin / user / auditor). (Google login only for the local/solo tier.)

## 9. Scope — MVP vs Later

**MVP / V1 (a demoable, sovereignty-first control plane):**
- **Model plane:** Ollama (local) + one self-hosted serving path (vLLM) + Neysa adapter.
- **Router:** explicit + cheapest + intent, with failover — *as a feature*.
- **Governance:** policy CRUD + evaluate-before-execution, audit log, hash chain, firewall Stage 1 + 3.
- **Sovereign Mode + Sovereignty Attestation:** first-class (see Part II §3–4).
- **Interfaces:** OpenAI-compatible **API** (primary) + ChatGPT-style chat + admin/infra console.
- **Deploy:** documented self-host run story (docker-compose).

**Later (enterprise-hardening — the real "payable" gap, see §10):**
- SSO/SAML + RBAC + multi-tenancy; Helm/air-gapped deploy; KMS integration.
- Auditor-grade evidence (controls mapping: DPDP/HIPAA/SOC2), defensible/anchored (WORM) audit.
- Robust PII/PHI detection (beyond regex); policy lifecycle (versioning/approval).
- Big-provider governance coverage (OpenAI/Anthropic/Azure/Bedrock) for hybrid estates.
- Certifications (SOC2/ISO), compliance policy packs, red-teaming, compliance advisor.
- DSPy behind a `ReasoningPort` ("best-quality"); Shakti / foreign-provider adapters.

## 10. Gaps to "enterprise actually pays" (the trust wall)

Selling a *compliance* product is gated by trust, not features. Load-bearing gaps:

1. **Trust proof** — SOC2/ISO, pen test, DPA, a design partner, references. (None yet.)
2. **A named regulated wedge** — the §6 beachhead, sharpened to a real buyer.
3. **Auditor-grade evidence** — controls mapping + defensible audit an auditor accepts.

Secondary (table stakes to even pilot): enterprise identity (SSO/RBAC), multi-tenancy,
enterprise deploy/ops (Helm/air-gap/HA/backup), SLA on the in-path dependency.

**None of the load-bearing three is code.** They are validated by customers, not built.

## 11. Risks (negation-first)

- **Crowded gateway space + full-stack giants** (Red Hat + NVIDIA, Portkey, TrueFoundry, Lunar).
- **Moat is earned over years, not owned** — lock-in + compliance content + channel.
- **Bigger, harder build** than a router (infra integration, enterprise identity, deploy tooling).
- **Commoditization/absorption** — platform owners keep adding governance; move on the wedge fast.

## 12. The crux & the next move

**Crux (falsifiable):** *"A DPDP-bound Indian mid-market regulated firm will run a paid pilot of
a self-hosted, governed, open-source-model control plane — over rolling their own (vLLM + LiteLLM
+ DIY audit) or buying an incumbent."*

**Next move is NOT building the full stack.** It's the cheapest disconfirming test:
put this vision + the mockup in front of **8–10 compliance/security owners** in the wedge, plus a
**Neysa/Shakti channel conversation**. Pass bar (written up front): *≥3 say "we'd run a paid
pilot" and name a budget line within 7 days.* Fail → Park the commercial version; build as portfolio.

## 13. Success looks like

> A regulated Indian fintech runs preceptaai on their own infra (or on Neysa). Their developers
> hit one governed API; open-source models serve every request; their compliance lead sets the
> policies once and pulls an auditor-ready, tamper-evident report on demand — and no sensitive
> data ever left their network. Switching away would mean unwinding years of policy + audit history.
> That is the moat, and that is the sale.

---
---

# PART II — DESIGN (closed-loop trunk)

> **Serves the crux:** a regulated buyer will pilot a self-hosted governed control plane **only if
> the sovereign loop is enforced and independently verifiable** — not merely present.

## 1. The trunk — the closed sovereign loop

Everything in V1 exists to make this one path complete, enforced, and provable:

```
request (in-boundary)
  → auth + policy check            [local — no external call]
  → route to a model INSIDE the boundary        ← the load-bearing link
       (vLLM on their GPU · Ollama · Neysa in-region)
  → firewall scrub (local)
  → inference (in-boundary)
  → response
  → tamper-evident audit + telemetry (local)
```

**The invariant (what "closed" means):**
> A real AI request is served, governed, and audited **entirely inside the customer's boundary,
> with zero egress**, and their own security team can **independently verify it** and walk away
> with a signed **Sovereignty Attestation**.

If a design decision doesn't serve this invariant, it is not V1.

## 2. Architecture — ports & adapters (hexagonal / DIP)

The **domain core** (router + governance + audit) never imports a concrete provider, store, or
cloud. It depends only on **ports** (interfaces). Everything external is a swappable **adapter**.

```
        ┌──────────────── CONTROL PLANE (domain core) ────────────────┐
  API   │  Router → Governance pipeline → Audit → Telemetry            │
  Chat  │  (policy check → route/failover → firewall → call → audit)   │
  Admin │  + Sovereign Mode enforcement + Attestation                  │
        └─┬──────────┬──────────────┬────────────┬───────────┬────────┘
          │Model      │Policy        │Audit        │Secret      │Infra
          │Backend    │Store         │Sink         │Store       │Visibility
          │Port       │Port          │Port         │Port        │Port      (+ Reasoning, Identity)
   ┌──────┴─────┐ ┌───┴────┐   ┌─────┴─────┐  ┌─────┴───┐  ┌────┴──────────────┐
   │ Ollama     │ │ SQLite │   │ hash-chain│  │ Floci   │  │ vLLM /metrics +   │
   │ vLLM       │ │        │   │ (SQLite;  │  │ vault;  │  │ Ollama + node     │
   │ Neysa      │ │        │   │  WORM     │  │ KMS/    │  │ → telemetry table │
   │ (Shakti,HF,│ │        │   │  later)   │  │ Vault   │  │                   │
   │  foreign = │ └────────┘   └───────────┘  │  later) │  └───────────────────┘
   │  later)    │                             └─────────┘
   └────────────┘
```

### Ports and their V1 adapters

| Port | Contract (essence) | V1 adapters | Deferred adapters |
|---|---|---|---|
| **ModelBackendPort** | `litellm_model()`, `price()`, `health()`, `in_boundary: bool` | Ollama, vLLM, **Neysa** | Shakti, HF, Together/Fireworks/Replicate/SiliconFlow |
| **PolicyStorePort** | CRUD + `enabled_for(action_type)` | SQLite (`governance_policies`) | — |
| **AuditSinkPort** | `append(event)`, `verify_chain()` | SQLite hash-chain (`tamper_evident_audit_log`) | WORM / external anchoring |
| **SecretStorePort** | `get(ref)`, `put(name)` | Floci vault / OS keyring | customer KMS/Vault |
| **InfraVisibilityPort** | `snapshot()` → GPU/VRAM/throughput/latency/cost | vLLM `/metrics` + Ollama + node | full APM |
| **IdentityPort** | `authenticate()`, `role()` | Google (local tier) | SSO/SAML + RBAC + SCIM |
| **ReasoningPort** | `run(program, ctx)` | passthrough (default) | **DSPy** (later "best-quality") |

**DIP payoff:** adding Shakti, swapping the audit store for WORM, or plugging in customer KMS
**never touches the domain core** — you write one adapter.

**Explicitly not a component:** SFD (a dev-time assistant) — dropped from the product.

## 3. Sovereign Mode (the primitive that closes the loop)

A first-class, on-by-default switch for enterprise deployments. When ON it **enforces**, not requests:

1. **In-boundary-only routing** — `ModelBackendPort` yields only adapters with `in_boundary = true`.
   Any route to a non-boundary backend is **blocked by policy** (not by convention).
2. **Egress lock** — deployment runs deny-all egress except allowlisted in-boundary model
   endpoints (enforced at the network/deploy layer; air-gapped is the strongest form).
3. **Audit-on** — auditing cannot be disabled while Sovereign Mode is on.
4. **Residency policy** — a built-in policy asserts data-classification/residency rules for the jurisdiction.

## 4. Sovereignty Attestation (the proof artifact)

A one-page, exportable proof the customer's security team can **independently verify**:
- **Config proof** — the active backend set (all `in_boundary`), Sovereign Mode = ON, egress policy.
- **Audit proof** — over a window: count of requests served, and **zero external calls** in the
  tamper-evident log (chain verified).
- **Egress-test result** — outcome of an egress probe (expected: blocked/none), verifiable with
  the customer's own network monitoring.
- Signed + hash-anchored to the audit chain.

**This artifact is the sale.** Closing the loop = being able to generate it for a real workload.

## 5. Gateway contract (Contract 1 — how clients call)

`POST /v1/chat/completions` — OpenAI-compatible (any OpenAI SDK is a client, incl. a DSPy program).
Routing is expressed via the `model` string:

| `model` value | Meaning |
|---|---|
| `vllm/<model>` `ollama/<model>` `neysa/<model>` | **Explicit** in-boundary backend |
| `auto:cheapest` · `auto:fastest` · `auto:best-quality` | **Intent** routing (in-boundary candidates only under Sovereign Mode) |

Response = OpenAI standard **+ a `precepta` block**: `backend_used`, `in_boundary`, `route_mode`,
`cost_usd`, `latency_ms`, `policy_decision`, `audit_id`. A policy block → HTTP 403 with the same
block, no backend call.

## 6. Governance pipeline (Contract 3 — the one place router meets governance)

```
request
  → build PolicyCheckContext(action_type, url?, tokens, data_tag, backend, in_boundary)
  → [Sovereign Mode] assert backend.in_boundary       # else Block: "out-of-boundary route"
  → [PRE] evaluate_policies()  → most-restrictive wins (block > warn > allow)
        Block → audit row, return 403 (no inference)
  → [PRE] firewall Stage 1     # redact PII in input; detect injection → may block
  → route + failover           # resolve model string → in-boundary backend list → circuit breaker
  → inference (ModelBackendPort)
  → [POST] firewall Stage 3    # scan output for secret/key/db-url leak → may block
  → [POST] audit row + extend SHA-256 hash chain
  → capture cost + latency (InfraVisibilityPort / telemetry)
  → response (+ precepta block)
```

Evaluation and audit-chain math: most-restrictive (block > warn > allow); enabled policies where
`action_type = ctx OR '*'`, ordered `created_at ASC`; audit **every** check; Block breaks the loop;
Warn upgrades Allow but never overrides Block; URL match = plain substring. Audit chain:
`event_hash = SHA256(event_id + timestamp + event_type + actor + resource + action + outcome +
metadata + previous_hash)`, genesis = 64 zeros; verify walks `(timestamp ASC, event_id ASC)`.

## 7. Infra visibility (the "total control, one pane")

Integrate, don't build. `InfraVisibilityPort.snapshot()` pulls **vLLM Prometheus `/metrics`**
(GPU/VRAM, throughput, latency) + Ollama + node metrics into the existing `telemetry` table;
the **admin console** renders: loaded models, hardware, GPU/VRAM %, req/s, p50 latency, $ cost,
health. No Grafana rebuild.

## 8. Module layout (Python / FastAPI)

```
app/
  main.py                 # FastAPI: /v1/chat/completions, /health, /attestation, auth
  gateway/pipeline.py     # Contract-6 middleware + Sovereign Mode enforcement
  router/                 # model-string resolve; cheapest/fastest/intent; failover
  ports/                  # the Protocols (ModelBackend, PolicyStore, AuditSink, Secret, InfraVis, Reasoning, Identity)
  adapters/
    model/                # ollama.py, vllm.py, neysa.py  (shakti/foreign = later)
    audit/ policy/ secret/ infra/ identity/
  governance/             # policy eval; firewall stages; audit + hash chain
  sovereign/              # mode enforcement + attestation builder
  db.py settings.py
web/                      # ChatGPT-style chat + admin console (providers, policies, audit, attestation, infra)
deploy/                   # docker-compose (egress-locked profile); Helm later
```

## 9. What this de-risks + reversibility
- **New backend / store / cloud = one adapter**, never a core change (DIP). Two-way door.
- **Sovereign Mode + attestation** make the pitch *verifiable*, not asserted — the crux.
- **Neysa-vs-Shakti, DSPy-later, WORM-later** are all adapter/config choices = reversible.
- **Integrating vLLM & metrics** (not building them) keeps us out of the giants' lane.
