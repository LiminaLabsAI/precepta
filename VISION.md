# preceptaai — Vision Document

> **Status:** Draft v2 — re-imagined around the enterprise-payable thesis (pre-founding).
> **Last updated:** 2026-07-20
> **Owner:** sarang
> **Companion docs:** `IMPLEMENTATION_PLAN.md` (V1 closed-loop trunk) and `DESIGN.md`
> (ports & adapters around the provable sovereign loop) — both aligned to this v2.

---

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

## 7b. How enterprises consume it (the doors)

An enterprise isn't one user — it's **layers**, each reaching preceptaai a different
way, all governed and attributed:

| Layer | Who | Mechanism |
|---|---|---|
| **Govern** | Security/compliance admin (buyer) | Console (with SSO) |
| **Build** | Developers | OpenAI-compatible API + their own key + drop-in |
| **Run** | Apps / services / agents | Per-system API keys (attributed in audit) |
| **Use** | Business staff | Console chat |

**The API is the backbone; SDK / drop-in proxy / MCP / Console are ergonomic front doors
on top of it, unified by per-team identity + governance.**

What makes it *enterprise-easy* (≠ solo-dev easy): **zero-code adoption** (`OPENAI_BASE_URL`
override, no rewrite) · **self-service scoped keys** (per team/app, role-bound) ·
**attribution** (every call traceable in the tamper-evident audit) · **SSO** (corporate
identity for Console) · **MCP** (agentic tools reach governed inference as a tool).

**Sequencing principle:** identity + attribution + zero-code adoption come *before* a new
protocol — MCP without per-team identity would recreate the dev-token problem. So **keys
first (Phase 7), then MCP + SSO (Phase 8), then hardening (Phase 9)**.

## 8. Architecture

- **Stack:** Python + FastAPI + SQLite (existing `preceptaai.db`) — the control plane.
- **Model plane:** integrates Ollama (local), vLLM / TGI (self-hosted serving), and
  Neysa / Shakti (sovereign clouds) via a uniform provider-adapter interface.
- **Governance:** policy engine + firewall + tamper-evident audit (SHA-256 hash chain).
- **Interfaces:** OpenAI-compatible API (primary) + ChatGPT-style UI + admin console.
- **Deployment:** self-hosted — container/Helm, VPC or air-gapped; secrets via the customer's KMS/Vault.
- **Auth:** SSO/SAML + RBAC (admin / user / auditor). (Google login only for the local/solo tier.)

## 9. Foundations already in place

- ✅ Database schema (router + governance tables designed).
- ✅ Floci running locally (local AWS emulation — vault/S3/secrets).
- ✅ Ollama running locally (open-source models).
- ✅ Design contracts (`DESIGN.md`) + ChatGPT-style UI mockup (published artifact).
- ❌ No application code yet — greenfield.

## 10. Scope — MVP vs Later

> **Phase 10 — cost / quality / governance controls (scoped; design next).** Turns the control plane
> from "governs correctly" into "governs, saves cost, and gets smarter" — for the target buyer's
> non-expert users on metered backends. Items: key expiry + token/cost budgets · policy scoping
> (all vs selected) · response cache · prompt compression · advanced (LLM-driven, governed) routing ·
> traces → learning loop · self-hosting/deploy. Full scoping in [`BRAINSTORM.md`](BRAINSTORM.md);
> architecture in [`DESIGN.md`](DESIGN.md) §11; sequence in [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) §Phase 10;
> plain-English overview in [`preceptaai-plan.md`](preceptaai-plan.md). **Governing stance: safe by
> default, extra risk only by explicit opt-in, and nothing hidden from the person using it.**


**MVP (a demoable, sovereignty-first control plane):**
- **Model plane:** Ollama (local) + one self-hosted serving path (vLLM) + Neysa/Shakti adapter.
- **Router:** explicit + cheapest + intent, with failover — *as a feature*.
- **Governance:** policy CRUD + evaluate-before-execution, audit log, hash chain, firewall Stage 1 + 3.
- **Interfaces:** OpenAI-compatible **API** (primary) + ChatGPT-style chat + basic admin.
- **Deploy:** documented self-host run story.

**Later (enterprise-hardening — the real "payable" gap, see §11):**
- SSO/SAML + RBAC + multi-tenancy; Helm/air-gapped deploy; KMS integration.
- Auditor-grade evidence (controls mapping: DPDP/HIPAA/SOC2), defensible/anchored audit.
- Robust PII/PHI detection (beyond regex); policy lifecycle (versioning/approval).
- Big-provider governance coverage (OpenAI/Anthropic/Azure/Bedrock) for hybrid estates.
- Certifications (SOC2/ISO), compliance policy packs, red-teaming, compliance advisor.

## 11. Gaps to "enterprise actually pays" (the trust wall)

Selling a *compliance* product is gated by trust, not features. Load-bearing gaps:

1. **Trust proof** — SOC2/ISO, pen test, DPA, a design partner, references. (None yet.)
2. **A named regulated wedge** — the §6 beachhead, sharpened to a real buyer.
3. **Auditor-grade evidence** — controls mapping + defensible audit an auditor accepts.

Secondary (table stakes to even pilot): enterprise identity (SSO/RBAC), multi-tenancy,
enterprise deploy/ops (Helm/air-gap/HA/backup), SLA on the in-path dependency.

**None of the load-bearing three is code.** They are validated by customers, not built.

## 12. Risks (negation-first)

- **Crowded gateway space + full-stack giants** (Red Hat + NVIDIA, Portkey, TrueFoundry, Lunar).
- **Moat is earned over years, not owned** — lock-in + compliance content + channel.
- **Bigger, harder build** than a router (infra integration, enterprise identity, deploy tooling).
- **Commoditization/absorption** — platform owners keep adding governance; move on the wedge fast.

## 13. The crux & the next move

**Crux (falsifiable):** *"A DPDP-bound Indian mid-market regulated firm will run a paid pilot of
a self-hosted, governed, open-source-model control plane — over rolling their own (vLLM + LiteLLM
+ DIY audit) or buying an incumbent."*

**Next move is NOT building the full stack.** It's the cheapest disconfirming test:
put this vision + the mockup in front of **8–10 compliance/security owners** in the wedge, plus a
**Neysa/Shakti channel conversation**. Pass bar (written up front): *≥3 say "we'd run a paid
pilot" and name a budget line within 7 days.* Fail → Park the commercial version; build as portfolio.

## 14. Success looks like

> A regulated Indian fintech runs preceptaai on their own infra (or on Neysa). Their developers
> hit one governed API; open-source models serve every request; their compliance lead sets the
> policies once and pulls an auditor-ready, tamper-evident report on demand — and no sensitive
> data ever left their network. Switching away would mean unwinding years of policy + audit history.
> That is the moat, and that is the sale.
