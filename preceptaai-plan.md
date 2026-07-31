# preceptaai — Master Plan (Vision · Design · Phase 10 · Backlog)

> **One place to see why we're building this, how it's built, and exactly what we need to do next.**
> Combines `VISION.md`, `DESIGN.md`, `BRAINSTORM.md`, and `specs/backlog/backlog.md`.
> **Last updated:** 2026-07-30 · **Owner:** sarang · **Status:** Phases 0–9 shipped; Phase 10 scoped, entering design.

---

## Part 1 — The Vision (why & what)

**In one line:** a self-hosted control plane for running open-source AI on your own infrastructure —
with routing, governance, and tamper-evident audit built in. **Total control. Data never leaves. Compliance by default.**

**The problem.** Regulated, data-sensitive enterprises want AI but (1) can't send data to outside clouds
(DPDP / HIPAA / GDPR / SOC2), (2) want open-source models on their own infra but don't want to wire up
serving + routing + governance + audit themselves, and (3) have no enforced policy or audit an auditor accepts.

**The product.** Point any OpenAI-compatible app at preceptaai, and every request is routed to an
in-boundary model, policy-checked, PII-scrubbed, and written to a tamper-proof audit log — with a signed
proof (a "Sovereignty Attestation") the customer's security team can verify. **The smart router is a
feature; the product is the governed control plane.**

**Who pays & why.** Compliance/security leaders (CISO, Head of Compliance) at regulated firms, because:
sovereignty (data never leaves), lower cost (own infra + open models vs per-token bills), no lock-in,
governance/audit built-in, and one pane of glass.

**The beachhead.** DPDP-bound Indian mid-market regulated firms (fintech / health) who need sovereignty +
governance but can't deploy a heavy stack like Red Hat AI Factory — served by a **lightweight,
batteries-included** control plane, ideally bundled with a sovereign local cloud (Neysa / Shakti).

**Honest truth about the moat.** No technical moat — it's earned over time: control-plane lock-in, being the
compliance system-of-record, pre-built policy packs per regulation, and channel partnerships.

---

## Part 2 — The Design (how it's built)

### The closed sovereign loop (the heart of the product)

Everything exists to make this one path complete, enforced, and provable:

```
request  → who are you? (login)  → what may you do? (authZ)  → is this request allowed? (policy)
         → route to a model INSIDE the boundary  → scrub PII / injection  → run the model (in-boundary)
         → answer  → write a tamper-evident audit record
```

**The invariant:** a real AI request is served, governed, and audited **entirely inside the customer's
boundary, with zero data leaving** — and their security team can independently verify it. If a design
decision doesn't serve this, it isn't in the product.

### Ports & adapters (why we can add things without breaking the core)

The core (router + governance + audit) never talks to a specific vendor or database directly. It only talks
to **"ports"** (fixed interfaces). Everything external — a model provider, the database, the secret store —
is a **swappable "adapter"** behind a port. **This is the rule every new feature follows:** it goes in as a
new adapter, never by touching the core.

| Port | What it decides | Today | Later |
|---|---|---|---|
| **ModelBackendPort** | where a model runs | Ollama, vLLM, Neysa, HF endpoint | Shakti, others |
| **PolicyStorePort** | the governance rules | SQLite | — |
| **AuditSinkPort** | the tamper-proof log | SQLite hash-chain | WORM / external anchoring |
| **SecretStorePort** | where secrets live | Floci vault / OS keyring | customer KMS / Vault |
| **IdentityPort** (login) | *who* the caller is | Google login | full SSO / SAML |
| **AuthorizationPort** | *what* they may do | simple role check | **OpenGuard** (agents + delegation) |
| **RouterBrainPort** | which model to pick | rules | LLM intent-router (Phase 10) |
| **ReasoningPort** | answer-quality technique | passthrough, best-of-N | optillm / DSPy |

### What already exists (Phases 0–9, shipped, 88 tests)

Model plane + gateway · smart router (cheapest/fastest/quality) · governance (policy engine + PII/injection
firewall + hash-chained audit) · Sovereign Mode + Attestation · the Console (chat + admin) · per-team API
keys · MCP server · Google/OIDC SSO · compliance report.

---

## Part 3 — Phase 10 plan (what we need to do next)

Seven ideas were brainstormed one at a time. **Six are fully thought through; one (deployment) is still
open.** The consistent stance across every decision: **safe by default, extra risk only if someone
deliberately turns it on, and never hide things from the person using it.**

### Foundations — build these FIRST (everything else leans on them)

- **Pricing list (TD-001).** One trustworthy, admin-maintained price list (per model, dated). Every "cost"
  and "money saved" number depends on it. *(Fixes a live bug: models added through the Console currently
  show $0 cost.)*
- **Counting rules (TD-002).** One definition of how tokens and cost are counted, so budgets, cache, and
  compression all agree instead of showing different numbers.
- **Quality test / eval harness (FEAT-006).** A fixed "taste-test" that proves a change didn't make answers
  worse. **Four features below depend on it — build it before them.**
- **Sensitivity check quality (TD-004).** How we reliably know a request contains sensitive data. Four
  governance behaviours rest on this one signal.

### The six scoped features

**1 · Key expiry + budgets (FEAT-001).** Every API key gets a lifetime (default 90 days, or "never") and
real, enforced **token + cost budgets** — per key *and* per team, daily *and* monthly, in the customer's
timezone. At **80% → notify only** (never silently degrade). At **100% → block.** A live usage view and
bell-icon notifications, all from real data.

**2 · Policy scope (FEAT-002).** Today a rule applies to everyone. Add an optional **"applies to"** so a
policy can target selected **teams / roles / people / agents / backends / models** — default is still
"everyone." Agents are governed exactly like people.

**3 · Cache (FEAT-003).** Reuse a previous answer instead of paying to run the model again — inside the
governed loop (still checked and audited; every reuse is logged). **Exact-match only by default;** the
fuzzy "semantic" match is **off unless deliberately turned on** (it can otherwise serve a confidently-wrong
answer). **Invisible to the user; savings visible only to the admin.**

**4 · Compression (FEAT-005).** Shrink long, rambly prompts and big documents before the model sees them —
cutting cost and latency for non-expert users who over-write. **Never surprises the user:** safe baseline
compression is automatic (it can't worsen an answer); anything more aggressive is **opt-in ("cost-saving
mode") and notified.** The admin sees real tokens/$/latency saved. Before/after text is kept only with the
customer's consent, for their own future training.

**5 · Advanced routing (FEAT-007).** Pick the right model per request in three layers:
(a) **safety first** — sensitive data (auto-detected) can only go to an **approved** model; if none is
available, **block and tell both the user and the admin why**;
(b) a **smart model reads the request and figures out** whether the user wants cheapest / fastest / best;
(c) **budget keeps it honest** (only degrades if the admin opts in). Where a model is *hosted* is confirmed
once, at approval time, not re-checked per request.

**7 · Traces → learning loop (FEAT-008).** Record what happened *and* whether the answer was good (thumbs
up/down + signals like regenerates/edits), then use it to **route smarter over time.** Runs
**per-customer, inside their boundary, with consent — never pooled across customers.** Re-training the
models themselves is deferred. Gated by the quality test (FEAT-006).

### The one still to brainstorm

**6 · Self-hosting / deploy (FEAT-009).** Today it runs on a laptop; a customer can't yet install it in
their own datacenter. Needs: a container, a one-command bundle, then the enterprise pack (Kubernetes/Helm,
a real database for scale, secrets via their vault, offline install). **Not yet brainstormed.**

### Cross-cutting gaps to decide *alongside* design (don't leave to the end)

- **Streaming vs governance (TD-003).** The firewall/cache/compression assume the full answer is ready
  before sending; live "typing" answers need a plan.
- **Fail-soft (TD-006).** If a helper (cache/compressor/classifier) breaks, the request must still go
  through — these must never take down the core.
- **Secure the new data + attestation (TD-007).** Cache/traces/corpus hold sensitive content; encrypt them
  and expand the "proof" to cover them.
- **Attribution (TD-005).** When an agent acts for a person, whose budget/trace/audit is it?
- **Govern the control plane itself (TD-008).** Who can change which setting; finer admin roles (the person
  who sets budgets ≠ the person who approves a model for medical data); send alerts to email/Slack too.

---

## Part 4 — Build order (plain)

**Foundations first:** Pricing (TD-001) → Counting rules (TD-002) → Quality test (FEAT-006) →
Sensitivity quality (TD-004).
**Then features:** Budgets (FEAT-001, creates the "near-limit" signal) → Policy scope (FEAT-002) ·
Cache (FEAT-003) · Compression (FEAT-005) · Routing (FEAT-007) → Traces→learning (FEAT-008).
**Alongside:** the cross-cutting gaps (TD-003/005/006/007/008).
**Still to brainstorm before building:** Deploy (FEAT-009).

---

## Part 5 — The full to-do list (backlog)

### Features
| ID | Title | Priority | Notes |
|----|-------|----------|-------|
| FEAT-006 | **Quality test / eval harness (foundation)** | P1 | Build FIRST — gates cache(semantic)/compression/routing/learning |
| FEAT-001 | Key expiry + token/cost budgets | P1 | Per key & team; 80% notify, 100% block |
| FEAT-002 | Policy scope (all vs selected) | P1 | Team/role/agent/backend/model; agents like humans |
| FEAT-003 | Response cache (exact default; semantic opt-in) | P2 | Governed loop; admin-only visibility |
| FEAT-005 | Compression (long prompts/docs) | P2 | Never surprises the user; consent-gated corpus |
| FEAT-007 | Advanced routing (safety → smart intent → budget) | P2 | Sensitive→approved-only, block+notify |
| FEAT-008 | Traces → learning loop | P3 | Per-customer, in-boundary; smarter routing |
| FEAT-009 | Self-hosting / deploy | P1 | **Not yet brainstormed** — blocks real self-hosting |
| FEAT-004 | OpenGuard authZ/delegation adapter | P2 | Agents + bounded delegation; de-risked ✅ |

### Foundations & cross-cutting (technical must-dos)
| ID | Title | Priority | Notes |
|----|-------|----------|-------|
| TD-001 | Pricing source-of-truth (versioned price list) | P1 | All $ figures depend on it; fixes live $0 bug |
| TD-002 | Counting rules (one metering definition) | P1 | Budgets/cache/compression must agree |
| TD-003 | Streaming vs governance | P1 | Live-typing answers need a plan |
| TD-004 | Sensitivity detection quality (beyond regex) | P1 | Load-bearing for 4 governance behaviours |
| TD-005 | Attribution incl. agents/delegation | P1 | Whose budget/trace when an agent acts for a user |
| TD-006 | Fail-soft for in-path helpers | P1 | Optimizations must never break inference |
| TD-007 | Secure new data stores + expand attestation | P1 | Cache/traces/corpus at rest |
| TD-008 | Govern the control plane (config/roles/alerts) | P2 | Config precedence, finer roles, alert delivery |

---

## Part 6 — Guiding principles (the product's spine)

1. **Sovereignty is non-negotiable** — data and models never leave the customer's boundary; any helper model
   (embeddings, compressor, router) runs in-boundary too.
2. **Safe by default** — the risky option (fuzzy cache, aggressive compression, cheaper routing) is always
   opt-in, never automatic.
3. **Never surprise the user** — no silent quality change; when the system blocks something, the person is
   always told why.
4. **Everything backend-real** — every number (cost, savings, usage, audit) comes from real data, never demo values.
5. **New features go in as adapters** — behind a port, never by touching the core.
6. **Measure before trusting** — quality-affecting features are gated by a locked quality test.
