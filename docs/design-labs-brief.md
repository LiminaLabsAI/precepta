# Precepta — Product & Design Context Brief

*Prepared for a design partner (Claude Design Labs). Grounded in the product vision,
the current build, and the roadmap. Last updated: 2026-08-06.*

---

## 0 · TL;DR (read this first)

**Precepta is a self-hosted, sovereign control plane for running open-source AI inside a
company's own network.** Every AI request that passes through it is routed, governed
(PII/policy/injection), cost-optimized, and tamper-evidently audited — **without the
company's data ever leaving their boundary.**

The **governed engine is built and working** (211 automated tests, a live operator
Console). What we want from design partnership is to make the product's value **legible
and beautiful** — starting with **Traces**: a visual, reasoned timeline of exactly what
the guardrail did to every request, and *why*. Traces is the investor-facing "aha" and
the highest-priority design work.

---

## 1 · What Precepta is

> A self-hosted control plane for running open-source AI models on your own
> infrastructure — with routing, governance, and tamper-evident audit built in.
> **Total control. Data never leaves. Compliance by default.**

Point any OpenAI-compatible app at it; every request is routed to an **in-boundary**
model, policy-checked, PII/injection-firewalled, cost-optimized, and written to a
tamper-evident audit log — then a **signed zero-egress attestation** proves it.

The "AI router" people expect is just *a feature*. **The product is the governed control
plane** — the single chokepoint an enterprise runs so its AI usage is controlled and
provable.

**Positioning line we're moving toward:** *a runtime guardrail platform for AI companies.*

---

## 2 · Why it exists · who suffers

Regulated, data-sensitive enterprises want AI but **can't send their data to third-party
clouds** (DPDP / HIPAA / GDPR / RBI / SOC2 forbid it). They want open-source models on
their own infra, but wiring up serving + routing + governance + audit is a project they
don't want to own — and their AI usage today is ungoverned (no enforced policy, no PII
controls, no audit an auditor accepts).

- **Buyer:** compliance / security leadership (CISO, Head of Compliance) at regulated
  firms — **not developers, not individuals.**
- **Beachhead wedge:** DPDP-bound Indian mid-market regulated firms (fintech / health /
  public-sector-adjacent), often bundled with a sovereign local cloud (Neysa / Shakti).

**The buyer pays for one thing above all: sovereignty — data + models never leave their
network.** Cost savings, no-lock-in, and built-in governance are the supporting reasons.

---

## 3 · The core promise — the constraint every design must respect

> **Data never leaves the customer's boundary. Zero egress. Independently verifiable.**

This is the whole product. It means, for design:
- **Never imply data going to a cloud/third party.** Reinforce "stays in your network."
- The **Sovereignty Attestation** (a signed, exportable proof of zero-egress) is *the
  sale* — treat it as a hero artifact, not a footnote.
- **Trust is the currency.** The design's job is to make governance *visible and
  believable*, because an invisible guardrail is indistinguishable from none.

---

## 4 · Who uses it (the "doors")

An enterprise isn't one user — it's layers, each reaching Precepta a different way:

| Layer | Who | How they touch it | Design surface |
|---|---|---|---|
| **Govern** | Security / compliance admin (the buyer) | The **Console** (with SSO) | primary UI |
| **Build** | Developers | OpenAI-compatible **API** + their own key | snippets / docs |
| **Run** | Apps / services / agents | Per-app API keys (attributed in audit) | — |
| **Use** | Business staff | Console **chat** (Playground) | secondary UI |

The **API is the backbone**; the Console is the operator's pane of glass and the demo
surface. Most design leverage is in the **Console**.

---

## 5 · What's already built (the current product)

The governed engine is complete, and a working **Console** sits on top of it. Every screen
shows **real data from real endpoints** (see the Backend-Real principle in §7).

**Console screens today:**
- **Setup / Overview** — onboarding + a live dashboard (requests in 24h, **external calls = 0**, cost/req, endpoint health).
- **Inference plane** — register & manage the endpoints where inference runs; each row shows its **boundary** ("Intent within boundary" / "Intent crosses boundary"), price, live health.
- **Keys & budgets** — per-app keys with daily/monthly cost + token caps, backend/model scope, expiry, suspend/revoke, live spend.
- **Policies** — the four **sovereignty controls** (in-boundary routing, egress lock, audit, residency), custom policies (block/warn/audit, scoped), **sensitive-data routing** (fence PII to approved endpoints), and the **Smart router** toggle ("optimize automatically").
- **Cache & compression** — two tabs, configured **per endpoint** (+ a "Smart router" row), with strategy dropdowns (exact/semantic cache; baseline/aggressive compression) and a "bring-your-own — coming" placeholder.
- **Audit & Attestation** — the **tamper-evident audit log** + the **zero-egress attestation** (verify chain, generate/export the signed proof).
- **Playground** — send a governed request the way an app would; see the routing + governance metadata back; 👍/👎 to teach the router.
- **Settings** — Router config (platform-owner), Alerts, Members & roles (RBAC + per-agent budgets), Data controls.

**The engine behind them:** smart routing (an in-boundary model reads each request's goal),
PII/injection firewall, a policy engine, sensitive-data fencing, per-endpoint cache &
compression, a learning loop (thumbs → smarter routing), SSE streaming, a SHA-256
tamper-evident audit chain, a signed attestation, agent attribution, and a
runtime-toggleable Sovereign Mode.

**Current design language:** a clean, professional SaaS console — light theme, a blue
accent (#2563EB), system typography, card layouts, status pills, generative-AI vocabulary
("Inference plane," "inference endpoint," "intent within/crosses boundary"). It's
functional and honest; it is **not yet a distinctive, trust-radiating visual identity** —
that's part of the opportunity.

---

## 6 · The architecture (enough to design within it)

- **Ports & adapters (hexagonal).** A domain core (routing + governance + audit) that never
  imports a specific provider, store, or cloud; everything external is a swappable adapter.
  *(Why designers care: the product is deployment-flexible by design — on-prem, VPC, or
  sovereign cloud — all "the customer's boundary.")*
- **The governed request loop** — this is the story **Traces** will visualize:
  `request → firewall (PII/injection) → policy → sensitivity & routing (which model, why) → cache/compression → inference → output scan → audit → response`.
- **Stack:** Python + FastAPI + SQLite. The Console is a **single-file vanilla-JS SPA**
  (`web/console.html`) — **no framework.** New UI must work in that today (or the brief can
  include a recommendation to migrate — flag it explicitly if so).

---

## 7 · Design principles / non-negotiables

1. **Sovereignty first** — reinforce "data stays in your network"; never imply egress.
2. **Backend-real** — **every number and list comes from a real endpoint.** No fabricated
   dashboards, no demo values, no lorem metrics. Where a backend doesn't exist yet, show an
   **honest empty/pending state.** *(This is enforced culturally and repeatedly — please
   design to it.)*
3. **Safe by default** — risky behavior is opt-in and never hidden from the person using it.
4. **Governance is transparent** — blocks and redactions are always shown to the caller
   (the opposite of cache hits, which are invisibly beneficial).
5. **Plain English** — the buyer is a compliance lead, not an ML engineer. Prefer plain
   words over jargon.

---

## 8 · The roadmap — where design help is needed

**① Traces — the hero (highest priority).**
A **visual, reasoned workflow** of everything Precepta does to a request, ingress→egress.
Two levels:
- **L1 — a single request's journey:** each governed step (firewall → policy → routing →
  cache/compress → inference → output scan) shown as a flow, each step annotated with the
  **decision AND the "why" in plain language** (e.g. "Redacted 1 email before the model saw
  it," "Sent to gemma-31b — *inferred* goal: quality → strongest endpoint," "Served from
  cache — saved 35 tokens"). Router inferences are labeled **"inferred"** — never a fake
  confident reason.
- **L2 — an agent-run timeline:** many requests from one agent run, stitched into one
  step-by-step timeline.

It must be **simple enough that a non-technical investor gets it in ~30 seconds**, and
**honest enough that a compliance lead trusts it.** This is where great information design
matters most. *(Full spec lives in the repo at `specs/phases/phase-11-traces/`.)*

**② Cloud / sovereign deployment** — packaging Precepta to run inside a customer's boundary
(VPC / sovereign cloud / air-gapped). Mostly infra; light design (deploy/onboarding UX).

**③ Positioning & messaging** — carry the "runtime guardrail platform" voice across the
product (taglines, screen intros, empty states).

**④ First-run setup copilot** — an onboarding moment: *"Want an agent to set this up for
you, or do it yourself?"*

---

## 9 · The immediate design ask

1. **Design the Traces experience** (priority) — the L1 request-lifecycle workflow + the L2
   agent-run timeline. Make the guardrail's actions and reasoning *legible and trustworthy*.
2. **Elevate the Console into a distinctive, trust-radiating visual system** — one that
   reads "serious, sovereign, provable governance," not generic SaaS.

Both build on the live Console and the real governed engine — this is elevation and new
surface design, **not** a rebuild of the product.

---

## 10 · How to build on what exists

- The **Console is live and explorable** against the running engine (real data).
- This brief is self-contained; for full depth the repo carries `VISION.md`, `DESIGN.md`
  (architecture), and `specs/phases/phase-11-traces/` (the Traces spec).
- **Constraints to honor:** the sovereignty promise (§3), the backend-real principle (§7.2),
  and the single-file vanilla-JS Console reality (§6) — flag explicitly if a proposal needs
  to change any of these.
