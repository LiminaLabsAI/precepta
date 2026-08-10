# Precepta — Design Brief & Prompt: Smart Router · Traces · Workflow

*A self-contained brief for a design partner (Claude Design). Goal: produce the best
possible design **before** implementation, so we iterate as little as possible. Written
2026-08-09 from the current vision, roadmap, phase plan, and history.*

---

## 0 · How to use this prompt

You are designing three connected surfaces of an existing product: the **Smart Router**,
the **Traces** experience, and a **Workflow** view. This document is everything you need.
Read it fully, then deliver the design artifacts listed in §9. Where a decision is open,
propose your recommendation with a one-line rationale — don't wait for us.

**Design to the states, not just the happy path.** Most iteration comes from missing
states (empty, loading, blocked, failed, "no data yet"). Cover them up front.

---

## 1 · What Precepta is (context)

A **self-hosted, sovereign control plane for running AI inside a company's own network.**
Every AI request is routed, governed (personal-data/policy/injection checks), cost-optimized,
and tamper-evidently audited — **without the company's data ever leaving their network.**
The buyer is a **compliance / security leader** at a regulated firm; the promise they pay
for is **"data never leaves, and we can prove it."**

The engine already exists and works. This engagement is about making three things
**legible, trustworthy, and beautiful.**

---

## 2 · The one job of this engagement

Design the Smart Router + Traces + Workflow experience so that:
- a **compliance lead trusts it** (sees governance happening, believes the proof),
- a **developer/operator can run it** (configure, debug, understand a decision),
- an **investor gets it in ~30 seconds** (the "aha" that this is real and different).

The through-line: **make an invisible guardrail visible.** A guardrail you can't see is
one you can't trust.

---

## 3 · Who uses these screens

| Audience | Cares about | Design implication |
|---|---|---|
| **Compliance / security lead** (buyer) | proof, sovereignty, "what happened to our data" | plain language, honest reasoning, the zero-egress fact everywhere |
| **Platform / dev / operator** | why a decision was made, debugging, config | a deeper timeline/detail mode |
| **Business staff** | just using it | simple, safe defaults |
| **Investor / design-partner** (demo) | the "wow" in 30s | one screen that tells the whole story |

Design for the **compliance lead first**; give engineers a deeper mode; make the demo view effortless.

---

## 4 · What already exists (build on this — don't reinvent)

- **The Console** — a working operator UI (screens for Setup/Overview, Inference plane,
  Keys & budgets, Policies, Cache & compression, Audit & Attestation, Playground,
  Settings). It is a **single-file vanilla-JS SPA** today (no framework). Design must
  either work within that, or **explicitly flag** if a proposal needs a rebuild.
- **Current design language:** clean, professional SaaS — light theme, blue accent
  (#2563EB), system fonts, card layouts, status pills. Functional but **not yet a
  distinctive, trust-radiating identity** — elevating that is in scope.
- **The engine behind the new surfaces:** a governed request pipeline, a two-stage router
  (a model reads *intent*; config rules pick the *target*), targets that are either
  **inference models or in-premise agents**, and per-step decision data (what/why/timing).

---

## 5 · Non-negotiables (every design must respect these)

1. **Sovereignty first.** Never imply data leaving the network. Reinforce "stays in your
   boundary." The **zero-egress fact** (external calls = 0) and the signed **attestation**
   are hero elements, not footnotes.
2. **Backend-real — no fabricated data, ever.** Every number/row comes from a real
   source. Where data doesn't exist yet, design an **honest empty/pending state**, never a
   fake dashboard. (This is a hard cultural rule; design to it.)
3. **Honest reasoning.** When the router *infers* intent, it must be labeled **"inferred"** —
   never shown as a confident fact. Never invent a "why."
4. **Fixed governance rails.** Governance (personal-data firewall → policy → … → output
   check) is a **fixed spine** the user cannot remove or reorder. Only the *routing layer*
   is composable.
5. **Plain English.** The buyer is a compliance lead, not an ML engineer. Prefer plain
   words over jargon in all copy.
6. **Governance is transparent to the caller.** Blocks and redactions are always shown
   (unlike cache hits, which are silently good).

---

## 6 · What to design (the surfaces, in detail)

### A · Smart Router — "show, don't configure"
The core insight: instead of asking the operator to fill in forms/toggles, **show them how
routing works** and let them understand it at a glance.
- **Must show:** the request's journey (govern → route → target), the **two stages**
  (a model reads *intent* like cheapest/smartest/accuracy → rules pick the *target*), and
  that a target can be a **model or an in-premise agent**.
- **The router's honesty guards** should be visible: the **confidence floor** (a weak
  guess is treated as "hard," not trusted) and the **"no valid target → blocked"** case.
- **States:** no requests yet · routing normally · a request blocked by governance · a
  request where intent was *inferred* · an agent target that failed/timed out.

### B · Read-only Workflow view (auto-generated from config)
A canvas that renders the **actual governed path + routing rules from the live config** —
a *projection*, never a hand-drawn second source of truth.
- Governance shown as **fixed rails**; routing shown as the **composable middle** (read-only
  for now; an editable builder comes later — design so editing can be added).
- This view and the run-time trace (D) should use the **same visual language** so design-time
  and run-time are one picture. *(This symmetry is the hero — see §6G.)*

### C · Traces — the flagship
A **visual, reasoned record of everything that happened to a request**, ingress→egress.
Design **two modes**:
- **Story mode (default — for compliance & demos):** the request as a top-to-bottom
  "receipt." Each step is a card: icon · the decision · the **plain-language why** · a
  status badge (redacted / routed / cached / **blocked**) · small chips for
  cost·tokens·latency. Reads like a story, not a stack trace. **This is the differentiator —
  nobody makes traces readable.**
- **Timeline mode (for engineers):** a waterfall with **duration bars** and nested
  **agent sub-traces**, for debugging. Keep nesting shallow (competitors hit rendering bugs
  when deep).
- **Summary header (both modes):** outcome · total cost · total latency · **external calls = 0**
  · # governance actions — the at-a-glance "aha."
- **Filters:** by who/agent/run/intent — slice traffic.
- **A live request log** — a running list of requests (time, model/agent, cost, speed,
  pass/fail) that drills into a single trace.
- **States:** no traces yet · a clean success · a **blocked** request (governance) · a
  **failed agent** run · a trace where the agent **reported no reasoning** (honest, not blank).

### D · Agent-target visibility
Agents (e.g. CRM/CS/Delivery) are routing destinations *and* they run their own steps.
- Show the **agent's reasoning** as a **sub-trace** nested inside the request's trace.
- Make two invariants visible and reassuring: the agent's own model calls **re-enter
  Precepta** (still governed), and if the agent reports nothing, say so **honestly**.
- **States:** agent succeeded (with steps) · agent failed/timed out (with reason) · agent
  returned no reasoning.

### E · Model / agent onboarding (small but real)
Registering a target: name, endpoint, key, model, **price**, and **boundary** ("intent
within boundary" / "intent crosses boundary"), plus a **unique id** so two targets of the
same provider can coexist. Keep it simple; the current form barely changes.

### F · Bill-back / usage
Show **each team / app / agent exactly what it cost** (internal chargeback), and usage by
**tool and agent**. Trend + a clear "who spent what." Lives in the observability surface.

### G · The design-time ↔ run-time symmetry (the hero move)
The **workflow you see** (B) and the **trace of what happened** (C) should be the **same
picture** — so an operator can watch real requests *light up the path* they designed. If
you nail one thing, nail this: it's the demo that makes an investor lean in and the compliance
lead trust the system.

---

## 7 · Differentiators to make visible (we are NOT a generic gateway)

Our main competitor (LiteLLM) already does cost-routing, caching, budgets, and dashboards —
but it ships observability **to third-party clouds** and shows **metrics, not reasoning**.
So the design should lean hard into what they structurally can't do:
1. **Sovereignty** — everything stays in the network; the proof is a first-class artifact.
2. **Readable reasoning** — the plain-language "why" on every step (with honest "inferred").
3. **Governed agents** — routing to agents *and* keeping them inside governance.
Do **not** out-feature them on plumbing. **Out-trust** them.

---

## 8 · Vocabulary (keep copy consistent)

Inference plane · inference endpoint · **intent within boundary / intent crosses boundary** ·
Smart router · governed · trace · attestation · in-boundary · **external calls = 0**.
Avoid: "model plane," "backend" (user-facing), jargon like "span/telemetry" in Story mode.

---

## 9 · Deliverables

1. **User flows** for: viewing a trace (both modes), the read-only workflow view, agent
   sub-trace drill-in, onboarding a target, bill-back.
2. **High-fidelity screens** for the surfaces in §6, **including every state** in §5/§6
   (empty, loading, populated, blocked, failed, "no reasoning").
3. **A component set** (step card, status badge, duration bar, summary header, filter bar,
   workflow node, boundary pill) — consistent, reusable.
4. **The hero demo screen** (§6G) — the one that tells the whole story in 30 seconds.
5. **Light and dark** treatments; **responsive** (desktop-first, but must not break narrow).
6. **A short rationale doc** — key decisions + any place you propose changing a constraint
   (esp. §4 single-file console).

---

## 10 · What "good" looks like (acceptance — this is how we minimize iteration)

- A **non-technical person** understands a trace's Story mode without help.
- Every screen has its **empty / loading / blocked / failed** state designed.
- Nothing shows **fabricated data**; honest states everywhere.
- **Inferred** reasoning is visibly distinct from **explicit** reasoning.
- Governance reads as a **fixed rail** the user can't remove.
- The **workflow view and the trace look like the same picture** (§6G).
- The **zero-egress fact + attestation** are prominent, not buried.
- Copy uses the §8 vocabulary; no jargon in Story mode.

---

## 11 · Explicit non-goals for this design pass

- The editable **workflow builder** (later phase) — but design the read-only view so
  editing can be added.
- Deploy/install UI, SSO/user-provisioning screens.
- Retraining/ML-ops dashboards (Traces only *captures* the signal for now).
- Re-designing unrelated Console screens beyond a shared visual system.

---

## 12 · Reference material (in the repo, for depth)

- `VISION.md` — the thesis, buyer, moat.
- `specs/planning/roadmap.md` — phase sequence (Smart Router → Traces → Workflow builder).
- `specs/phases/phase-12-smart-router/` — the router phase: `overview.md`, `plan.md`,
  `history.md` (every design decision + why).
- `specs/phases/phase-11-traces/` — the traces phase spec.
- `docs/design-labs-brief.md` — the product-level context brief.
- The live Console — explore it against the running engine to see the current design language.

---

### One-paragraph version (if you paste only one thing)

> Design the Smart Router, Traces, and Workflow surfaces for Precepta — a self-hosted,
> sovereign AI control plane whose whole promise is *"your data never leaves the network,
> and we can prove it."* Make an invisible guardrail **visible and trustworthy**: a
> two-stage router (a model reads intent, rules pick a target — a model **or** an in-premise
> agent), a read-only workflow view auto-generated from config, and a flagship **Traces**
> experience with a plain-language **Story mode** (a readable "receipt" of what happened
> and *why*, with honest "inferred" labels) plus an engineer **Timeline mode** (waterfall +
> nested agent sub-traces). The hero is that the **workflow you design and the trace of what
> happened are the same picture.** Respect the non-negotiables: never imply data leaving
> the network, never show fabricated data (honest empty states only), keep governance a
> fixed rail, and write plain English for a compliance lead. Design every state — empty,
> blocked, failed, "no reasoning" — so we implement once and iterate little.
