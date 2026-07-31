# Phase 10 — Brainstorm (candidate items)

> Accumulating brainstorm of candidate line items for Phase 10, scoped one at a time before
> implementation. Governing rule for **all** items: **backend-real, no virtual/demo values**
> (`specs/project-rules.md` #6). Move into `specs/backlog/` once the brainstorm gate is exited.
> **Last updated:** 2026-07-30
> **Promoted to backlog (2026-07-30):** Item 1→FEAT-001, 2→FEAT-002, 3→FEAT-003, Spike→FEAT-004,
> 4→FEAT-005, eval-harness→FEAT-006, 5→FEAT-007, 7→FEAT-008, 6→FEAT-009; foundations/gaps→TD-001…008
> (`specs/backlog/backlog.md`). Readable summary of everything: `preceptaai-plan.md`.

## Tracker
| # | Item | Status |
|---|---|---|
| 1 | Key expiration + token/cost budgets (+ notifications, timezone, usage view) | 🟢 fully scoped |
| 2 | Policy scope — apply to all vs selected | 🟢 fully scoped |
| 3 | Cache (exact + semantic, per-team, governance-preserving) | 🟢 fully scoped |
| 4 | Compression (history-summarization first; LLMLingua behind an eval) | 🟢 fully scoped |
| 5 | Routing (advanced) — layered: governance-filter → intent-objective → budget-modifier | 🟢 fully scoped |
| 6 | Self-hosting / deploy | ⚪ pending |
| 7 | Traces → learning loop (capture + reward → smarter routing; eval-gated; per-customer) | 🟢 fully scoped |

**Status: 6 of 7 items fully scoped. Only Item 6 (deploy) still to brainstorm. Ready to enter the design phase.**

---

# Build order (what must come before what) — for the design phase

Plain rule: the money/quality features can't be built until the things they *depend on* exist. Build in
this order (backlog IDs in brackets):

**Foundations first (nothing works right without these):**
1. **Pricing** [TD-001] — one trustworthy price list. Every "cost" and "savings" number depends on it.
2. **Counting rules** [TD-002] — one definition of how tokens/cost are counted, so budgets/cache/compression agree.
3. **Quality test** [FEAT-006] — the "taste-test" that proves a change didn't make answers worse. Four features need it.
4. **Sensitivity check quality** [TD-004] — how we know data is sensitive; four governance behaviors rest on it.

**Then the features (each reuses the foundations above):**
5. **Budgets** [FEAT-001] → creates the "near-limit" signal that routing & compression reuse.
6. **Policy scope** [FEAT-002] · **Cache** [FEAT-003] · **Compression** [FEAT-005] · **Routing** [FEAT-007].
7. **Traces → learning** [FEAT-008] — needs traces flowing first, then improves routing.

**Cross-cutting, decide alongside design (don't leave to the end):**
- Streaming vs governance [TD-003] · fail-soft optimizations [TD-006] · secure new data stores + attestation
  [TD-007] · attribution incl. agents [TD-005] · govern-the-control-plane [TD-008].

**Still to brainstorm before it can be built:** Item 6 self-hosting/deploy [FEAT-009].

---

# Item 1 — Key expiration + token/cost budgets

**Goal:** Give every API key a lifetime and real, enforced token + cost budgets — at key *and*
team level — with full usage transparency and in-app notifications. All backend-real.

## 1. Key expiration
- Every API key has an **optional expiry**. Default **90 days**; option to set **"never."**
- Enforcement: an expired key **fails auth (401)**.
- UI: "Expires" choice at issue time; key list shows expiry + an "expired" state.

## 2. Budgets — what & where
- **Two measures, both optional:** **tokens** (capacity) and **cost in USD** (spend — matters for
  metered clouds like Neysa/HF; ≈ $0 for local).
- **Two levels:** **per-key** and **per-team** — independent ceilings.
- **Two windows:** **daily** and **monthly**.

## 3. Reset semantics
- **Calendar-based:** daily resets at **00:00**, monthly on the **1st**.
- Reset boundary honors the **configured timezone** (§7) — IST midnight, not UTC.

## 4. Precedence (key vs team)
- **Most-restrictive wins:** a request proceeds only if within **both** the key's and the team's
  budgets; **either** exceeded → blocked. (Same rule as the policy engine.)

## 5. Grace threshold & enforcement
- **Configurable per budget**; default **warn at 80%, block at 100%.**
- **Warn** = request still succeeds, flagged `warn` in the audit + a notification.
- **Block** = request rejected (**HTTP 429**), audited.
- Conservative: pre-check uses requested `max_tokens` as an upper bound; **actuals recorded post-inference**.

## 6. Default when no budget is set
- **Unset = unlimited**, shown explicitly as **"No limit set"** (never hidden).
- Optional **org-level default budget** that new keys inherit if configured.

## 7. Timezone (cross-cutting — fixes the UTC-everywhere issue)
- Timezone becomes a **real setting** (Settings → General), default **auto-detect from the browser
  at setup** (or ask).
- **Every time display** — audit log, attestation, usage, notifications — renders in it.
- Budget resets honor it.

## 8. Notifications (the bell icon)
- Backed by the **existing `notifications` DB table** (real, not mock).
- **Bell with unread count + dropdown feed** in the Console top bar.
- Fires on budget **warn/block** (extensible to other events later).

## 9. Usage visibility (full transparency)
- A Console **Usage** view + a `GET /v1/usage` endpoint.
- Shows, **per key and per team:** tokens used + cost, **today** and **this month**, vs the limit.
  Visible to all users.

## 10. Hard requirement
- **Everything is backend-real** — usage metered from the actual pipeline, cost from price tables,
  notifications from the DB, timezone converted from real data. **No virtual/demo values.**

## 11. Data-model touchpoints (for implementation)
- `api_keys`: add `expires_at`, token/cost budgets (day + month), `grace_pct`.
- team budgets: extend `team_scopes` similarly.
- a `key_usage` counter (or derive from `telemetry` / `audit_log`).
- `notifications` (exists) · org settings: `timezone`, optional default budget.

## 12. Scope note
- Item 1 alone is **likely a full phase** — size accordingly at implementation.

---

# Item 5 — Routing (advanced)

**Goal:** Make model selection smarter, cheaper, and **governed** — beyond today's keyword heuristic —
by **layering three signals (A classifier, B budget, C trust) that combine according to the caller's
intent**, with governance as a non-negotiable constraint. All backend-real. **Decided 2026-07-30.**

## 1. Current state (grounded)
- `RulesBrain` ([app/router/brain.py](app/router/brain.py)) behind `RouterBrainPort` (DIP). Intents:
  `cheapest` (min price), `fastest` (min latency), `auto/best-quality` (difficulty-aware).
- Difficulty = crude keyword/length heuristic. Real classifier (`optillm-modernbert`) is **stubbed/deferred**
  (falls back to rules). Sovereign mode already filters candidates to in-boundary.

## 2. The layered decision (how A+B+C combine — the core design)
```
1. CANDIDATE SET  all backends
      → filter SOVEREIGN (in-boundary only)
      → filter GOVERNANCE (C): request SENSITIVE (auto: firewall found PII/PHI, or explicit tag)?
           ⇒ keep only APPROVED/CERTIFIED backends (in-boundary + certified); none ⇒ BLOCK + NOTIFY admin (fail-closed)  ← hard, wins over intent
2. OBJECTIVE — LLM INTENT-ROUTER (A): a small in-boundary LLM infers what the caller wants
      (cost / speed / quality) + difficulty ⇒ picks backend. Explicit caller intent OVERRIDES the LLM; admin policy CAPS it.
3. BUDGET MODIFIER (B): team near cost budget ⇒ bias cheaper + may disable best_of_n (same signal that escalates compression)
4. FAILOVER: unhealthy backend (circuit breaker) ⇒ next-best in the SAME governance-filtered set (never escapes C)
5. AUDIT: backend + constraint applied + inferred/explicit intent + budget modifier (the "why")
```
**Ordering is the point:** governance (C) filters FIRST and overrides intent; the LLM (A) picks the
objective/model; budget (B) modulates. Intent drives it; governance is never negotiable.

## 3. The three signals
- **A · LLM intent-router** (in-boundary, replaces the keyword heuristic). A small fast model **infers the
  caller's goal** (cost/speed/quality) + difficulty — so non-expert users needn't declare intent. **Bounded
  by governance** (can't override C) and **budget** (B caps it). **Eval-gated (Rule 11)** with a **safety
  bias: when unsure, route UP (quality), not down**; explicit caller intent overrides; **runs when intent is
  omitted and the decision is cached** (reuse semantic infra) to control latency/cost — *implementation
  detail, sensible default chosen, not a user decision.*
- **B · Budget-aware** (revised 2026-07-30: **budget NEVER auto-downgrades quality**) — at **80%** Precepta
  **notifies only**; normal routing continues (no silent switch to a cheaper model — protects UX). Budget
  *informs* the router but downgrades **only if an admin opts into "cost-saving mode."** When that mode is
  **on** (an admin choice, e.g. prompted by the 80% notice), routing biases cheaper + can disable
  `best_of_n`, and its **on/off transitions fire ONE consolidated notification** (routing + compression
  together), deduped — never per-request. Per-request specifics stay in the audit. At **100%** → hard block (Item 1).
- **C · Governance-aware** (decided: **hard rule, fail-closed + notify**) — the meaningful attributes for a
  **self-hosted** product are **in-boundary + certified** (NOT geography — location is guaranteed by where
  the customer deployed). Sensitivity is **auto-derived from the Stage-1 firewall** (PII/PHI ⇒ sensitive),
  plus explicit caller/admin tags. Sensitive ⇒ approved-only; if none available ⇒ **block, and notify BOTH
  audiences (decided 2026-07-30):**
  - **The caller (immediately, in the response):** a clear, specific reason — *"Blocked: your request contains
    sensitive data (PII/PHI) that policy requires be handled only by an approved model, and none is available.
    Contact your admin."* — inline in the Console chat + in the API error; **not a cryptic 403**. States the
    *category*; never echoes the detected sensitive text back.
  - **The admin (notification):** the existing bell/notification (deduped) to approve a model / add capacity.
  - **General rule established:** *governance blocks are ALWAYS transparent to the caller* (the opposite of
    cache hits, which are invisible) — if Precepta stops a request, the person always learns why.

## 3b. Model approval flow + how residency is handled (decided 2026-07-30)
- **Location is surfaced at APPROVAL time, not per request.** When an admin certifies a model into the trust
  registry, the Console **shows where it's hosted** (host, in-boundary status, region if known) and requires an
  explicit confirmation: *"Sensitive data (PII/PHI) may be routed here — confirm this meets your DPDP/GDPR
  requirements."* The admin approves **consciously, with full knowledge of location.**
- Trust registry stores **hosting location, approved_by, approved_at, and basis** — fully **auditable**.
- **Why this beats per-request location checks:** for a self-hosted product, location is guaranteed by where
  the customer deployed, so per-request geo-checks are redundant; making location a **deliberate human decision
  at approval** is stronger for compliance (conscious + audit trail) than an automated per-request guess.
- **Per-request `region` filtering stays deferred** — Rule C filters on **generic backend attributes**, so if a
  **multi-region** customer ever appears, `region` becomes just one more optional attribute to switch on — no redesign.

## 4. Deferred
- **Per-request region/residency filter** — only a multi-region customer needs it; design C as attribute-generic so it slots in later.
- **D · Model cascade** (cheap-first, escalate-on-low-confidence) — strong saver but double-inference +
  needs a confidence signal → V2.
- **E · RL-learned routing** — route by measured outcomes → **that is Item 7**.

## 5. DIP / auditability / backend-real
- New brain adapter(s) behind `RouterBrainPort` — **zero domain change**; `get_brain()` selects.
- Every decision **auditable** — records backend + which constraint/objective/modifier applied (extends the
  existing `reason`), so an auditor sees e.g. "PHI → certified model only." **No demo values.**

## 6. Cross-item links
- A → shared **eval harness** (Rule 11, TD with cache/compression). B → **FEAT-001** budgets + Item 4 escalation.
  C → `model_trust_registry` + the firewall's `has_data_tag`. E → **Item 7**.

---

# Item 7 — Traces → learning loop

**Goal:** Capture what actually happened at inference **plus a quality/reward signal**, and use it to make
Precepta **smarter over time** — starting with **routing**. Runs **per-customer, in-boundary, consent-gated**;
**eval-gated (Rule 11).** All backend-real. **Decided 2026-07-30.**

## 1. Current state (grounded)
- **Telemetry** (`telemetry` table, written per request) captures resource + tokens + latency; **audit_log**
  captures decision/policy/tokens. vLLM/OpenAI responses carry `usage` (and `logprobs` if requested).
- **The gap:** **no quality/reward signal exists today** — Precepta records *what happened* but not *whether the
  answer was good*. That missing signal is the crux of Item 7.

## 2. The spectrum (how far to go)
| Level | What | Call |
|---|---|---|
| **1 · Traces + reward capture** | record `(prompt, model, answer, cost, latency, confidence)` **+ quality signal** | ✅ **v1 foundation** — nothing else works without it |
| **2 · Learned routing** | reward → learn best quality-for-cost model per query type → route accordingly | ✅ **v1 first use** = the deferred **Item 5·E**; cheap, no GPU |
| **3 · Model fine-tuning (RLHF/DPO)** | retrain the open models on collected preferences | ⛔ **defer** — GPU-heavy, per-customer, full training infra |

## 3. Reward signal (decided: **explicit + implicit**)
- **Explicit:** thumbs up/down (Console + an API feedback endpoint).
- **Implicit:** **regenerate = negative**, **edit = correction**, **agent task success = positive**. Implicit
  gives dense data (users rarely click thumbs); explicit gives clean anchors. Combined = signal that's both dense and calibrated.

## 4. Two non-negotiable guardrails
- **Rule 11 — locked evaluator FIRST.** This item *is* an optimization loop. No learning switches on until a
  fixed eval set + single scalar are committed to `tests/benchmarks/` (shared harness with cache/compression/routing).
- **Sovereignty.** Traces = prompts + answers (sensitive) ⇒ the **whole loop is per-customer, in-boundary,
  consent-gated, NEVER pooled across customers** (same rule as the compression corpus, X5). Data never leaves.

## 5. The closed loop (v1)
`route (Item 5) → serve → capture trace + reward → (offline, eval-gated) update routing policy → better route next time`
- v1 optimizer = a lightweight **contextual bandit** over `(query features → model)` maximizing a
  quality-per-cost reward; **no GPU**. Upgrades to heavier methods later behind the same port.

## 6. DIP / data model / backend-real
- New ports: **`TraceSinkPort`** (capture), **`FeedbackPort`** (reward in), **`LearningPort`** (the optimizer) — swappable.
- Data: a `traces` record (prompt hash, model, response ref, cost, latency, confidence/logprob, reward) +
  a `feedback` signal (thumbs / regenerate / edit / task-outcome). Extend telemetry/audit or a dedicated table.
- **Backend-real:** real traces, real reward, routing improvement **measured against the locked eval** — no demo numbers.

## 7. Cross-item links
- **Item 5·E** (this delivers it) · **Item 4 corpus** → Level-3 compressor/model training later ·
  shared **eval harness** (Rule 11) · **X5** sovereignty-of-training.

---

# Cross-cutting — must define BEFORE building Items 1/3/4 (raised 2026-07-30)

> These are "define once, up front" decisions, not big builds. Cheap now, expensive if discovered
> mid-implementation. Captured as risks so the brainstorm→design handoff doesn't lose them.

**X1 · Pricing source-of-truth (#4) — DESIGN AGREED 2026-07-30 (record as TD-001 design spec; build in design phase).**
All dollar figures = `tokens × price_per_token` from ONE source feeding Items 1/3/4.

*Current state (grounded):* `Price(input_per_1m, output_per_1m)` exists; router uses `backend.price(model)`.
BUT prices are **hardcoded in `app/adapters/model/registry.py`** (Neysa 0.30, HF 0.60), and — **live bug** —
backends added via the **Console/onboarding** (`load_backends()`) get **no prices ⇒ `Price(0.0,0.0)`**, so a
customer's own metered endpoint shows **$0 cost/budget/savings** today. (Discovery under TD-001.)

*Design — the owned artifact:*
1. **`model_prices` table:** `backend, model('' = default), input_per_1m, output_per_1m, currency(USD canonical),
   effective_date, source, created_at, created_by`.
2. **`PricingPort` (DIP) — single source of truth:** `price(backend, model, as_of=None) -> Price`.
   `DbPricing` adapter picks the row with the **latest `effective_date ≤ as_of`**. Fallback: DB → registry
   default → **`$0` WITH a "price missing" flag** (unknown-$0 is visible, never silently wrong).
   Backends/router/budgets/cache/compression **all call this one port** — also fixes the Console-backend $0 bug.
3. **Versioning = audit integrity:** historical reports pass the request timestamp as `as_of` ⇒ use the price
   in effect *then*; every stored dollar figure **stamped with the `effective_date` used** (reproducible).
4. **Admin-maintained:** Console → Settings → **Pricing** CRUD (source + effective date + "last updated");
   local = explicit $0; **warning banner when a live backend has no price row.**
→ backlog **TD-001** (design captured here).

**X2 · Canonical metering / accounting (#5).** Budgets (1), cache (3), compression (4) all touch the same
token/cost counters; combined behavior is undefined. **Define once, all three obey:**
`billable_tokens` = tokens actually sent+returned post-compression, **0 on a cache hit**; `budget_charge`
= billable_tokens × price (the one money number); `usage_volume` counts every request incl. cache hits;
`tokens_saved` = compression + cache-avoided. Canonical order:
`firewall → policy → budget pre-check → cache → compress → inference → measure actuals → budget commit → audit`.
Cache hit → usage-volume yes, cost-budget no. Compression → budget billed on **compressed** tokens.
→ backlog **TD-002**.

**X3 · Streaming vs governance.** Output firewall, cache, and compression all assume the FULL response is
available before sending. Streaming (which enterprises expect) breaks that. Needs an explicit design:
buffered-then-scan, chunk-scan, or streaming disabled where policy requires. → backlog **TD-003**.

**X4 · Semantic-cache go/no-go instrumentation.** Keeping semantic cache for now (user decision), but it
must be **evaluable**: kill-switch + metrics (semantic-hit rate, flagged-wrong rate, similarity
distribution) so "right trick or not?" is answered with data later. → folded into FEAT-003.

**X5 · Sovereignty of any training use.** Compression corpus / traces used for training must be
**per-customer, in-boundary, consent-gated** — never pooled across customers, or "data never leaves"
breaks. → folded into FEAT-003/FEAT-005 and Item 7.

---

# Item 4 — Compression (prompt / context)

**Goal:** Reduce **tokens sent to the model** to cut latency, fit long contexts, and cut cost on
metered backends — **without silently or unsafely altering prompts** in a governed system.
All backend-real. **Decided 2026-07-30.**

## 1. Value — core for the target user (revised 2026-07-30)
> **Guiding principle (confirmed 2026-07-30): compression must NEVER surprise the user.** No silent change to
> answer quality or experience. Baseline compression is allowed *only because* it's quality-safe (never worsens
> the answer); anything that could affect the experience is **opt-in + notified** (cost-saving mode).
- **Kept in (not deferred).** The buyer's users are **non-expert** enterprise staff who write **bloated,
  long prompts** and paste **long documents**, and who lean on **metered** backends — precisely where
  token savings become real dollars. Compression quietly cleans up rambly prompts so the model (and the
  bill) only sees what matters; the user never has to learn "prompt hygiene."
- It is a **direct cost lever** for a user base that would otherwise overspend by accident — not a
  marginal latency tweak.

## 1b. When compression applies — per-request gates (decided 2026-07-30)
Decision point: **after cache-miss, just before inference.** Fires only when it genuinely saves without
hurting the answer:
1. **Enabled** for the team/policy (admin, likely org-wide for this buyer).
2. **Size gate** — only prompts above a threshold (~800 tokens); short prompts skipped.
3. **Worth-it gate** — biggest win on **metered** backends (tokens saved × price = $ saved).
4. **No-regret gate** — use the compressed version only if it's **≥20% smaller AND safe**; else send the
   original. **Compression can never make a request worse.**

## 1c. Triggers (decided: **both**)
- **Always-on** for long prompts on **metered** backends — the baseline cost saver.
- **Baseline compression stays automatic** (quality-safe: only used if ≥20% smaller AND passes the safety
  check; eval-gated; "never makes a request worse") — helps overspending non-expert users **without** degrading UX.
- **Aggressive / budget-triggered compression is OPT-IN, not automatic** (revised 2026-07-30). At **80%**
  budget Precepta **notifies only** — it does NOT silently compress harder. Heavier compression happens **only
  when an admin turns on "cost-saving mode."** That mode is the **same shared lever as routing (Item 5 §3·B)**;
  its on/off transitions fire **one consolidated notification** (routing + compression together), not a per-item alert.
- **Local (~$0) backends:** compress **only for context-fit** (when a prompt would overflow the context
  window — a correctness need), **not for cost** — avoids quality risk where there is no dollar saving.

## 2. Types & disposition
| Type | Helps with | v1? |
|---|---|---|
| **History summarization** — summarize older chat turns | long **multi-turn** chats | ✅ **v1** — safe, low risk; ship first |
| **Prompt-token compression** (LLMLingua-style small-LM token dropping) | long **documents / single prompts** — **the buyer's primary case** | ✅ **v1 (eval-gated)** — the real cost win here, so **prioritize locking the eval early**, not "far future" |
| **RAG chunk compression** | retrieved context | ⛔ defer — only once RAG exists |
| **KV-cache / serving compression** | serving memory | ⛔ out of scope — that's the model plane (vLLM), not the control plane |

> **Sequencing note (revised):** because the target user's pain is **long docs/prompts**, prompt-token
> compression is the main event — not a deferred nice-to-have. History summarization ships first (safe,
> fast), but the compression **eval (`tests/benchmarks/`) must be locked early** so LLMLingua-style
> compression follows quickly and safely (Rule 11).

## 2b. Observability & evaluation — "how will I know?" (decided 2026-07-30)
**All numbers measured, never estimated. Admin/auditor-only (end users see nothing).**

**Per request (audit detail):** `compressed` (yes/no) · `skip_reason` (too_short/disabled/no_gain) ·
`technique` · `original_tokens → compressed_tokens` · `ratio` · `tokens_saved` · **`cost_saved_usd` (net)** ·
`compression_ms` · `net_latency_ms` · `original_hash / compressed_hash`.

**Aggregate (Compression Savings dashboard, Console → Usage):** % compressed · avg ratio · total tokens
saved · **total $ saved (net)** · avg latency saved · trend line · per-team leaderboard. Filter by
team/backend/model/period.

**Formulas (real counts × price tables):**
```
tokens_saved      = original_tokens − compressed_tokens
gross_cost_saved  = tokens_saved × backend_price_per_token
compression_cost  = compressor_tokens × compressor_price
NET cost_saved    = gross_cost_saved − compression_cost      ← always show NET
latency_saved     = tokens_saved × per_token_gen_time − compression_ms
```

**Quality evaluation (the other half):** the locked eval (`tests/benchmarks/`, Rule 11) scores answers
**with vs without** compression → a **quality-retention scalar** ("at 60% compression, 98% retained"), so
aggressiveness is set where quality stays safe. Cost saved is never reported without this quality number.

## 2c. Before/after capture → governed compression corpus (decided 2026-07-30)
- **Full before/after prompt text captured** for compressed requests (metrics + hashes remain for integrity).
- Stored as a **dedicated, access-controlled "compression corpus"** (not buried in the audit) — because it
  has a **downstream training use**: distill a cheaper in-house compressor, or feed the **Item 7 traces→RL
  loop** (explicit Item 4 → Item 7 link).
- **It is the PII-scrubbed text** (compression runs after Stage-1 firewall) ⇒ not a raw-PII corpus, by construction.
- **Governance caveat (load-bearing, confirmed by user 2026-07-30):** retaining/using prompt content for
  training happens **only with explicit enterprise consent** — no approval ⇒ the data **stays entirely with
  them**, never captured. When approved, any training is **per-customer and in-boundary, never pooled across
  customers** (else "data never leaves" breaks — see X5). Per-org toggle + configurable retention + admin-only access.

## 3. Governance / sovereignty constraints
- **Integrity in audit:** ratio + **hash of original + compressed** always recorded (proves the transform).
  Full before/after text lives in the governed corpus above (§2c), gated by the per-org toggle.
- **In-boundary only** — the compressor/summarizer model runs **locally** (Ollama), never an external
  API. Same load-bearing sovereignty rule as the semantic-cache embeddings.
- **Opt-in, OFF by default** — per policy/team; never rewrite prompts unless the org enabled it.
- **Order in the pipeline:** after PII scrub (Stage 1) **and after the cache lookup** (cache keys stay
  on the original scrubbed prompt); compression runs **only on a cache miss, just before inference**.
- **Rule 11 (locked evaluator first)** — compression trades tokens for quality, so before any tuning
  loop we lock an eval set + a single quality scalar in `tests/benchmarks/`. LLMLingua stays gated
  until that eval exists.

## 4. DIP
- New **`CompressionPort`**: `compress(messages, budget) -> (messages, meta)`.
- Adapters: **`NoopCompression`** (default) → **`HistorySummarizer`** (v1) → **`LLMLinguaCompression`**
  (later, behind the eval). Pipeline calls it optionally; zero change to swap adapters.

## 5. Console / metrics (admin-only, like the cache)
- Per-policy/team **toggle**; a real **"tokens saved by compression"** tile. End users see nothing.
- Backend-real: ratio + tokens from the actual transform; **no demo numbers.**

## 6. Build order
1. `CompressionPort` + `NoopCompression` (wired, no-op) + audit fields (ratio, hashes).
2. `HistorySummarizer` adapter (in-boundary) + Console toggle + savings tile.
3. **Lock the compression eval** (`tests/benchmarks/`) — set + quality scalar.
4. `LLMLinguaCompression` adapter, optimized **only against the locked eval**.

## 7. Deferred
- LLMLingua/token compression until the eval is locked · RAG chunk compression · any serving-level compression.

---

# Item 3 — Cache (exact + semantic response cache)

**Goal:** Skip the expensive inference call when we've already answered the same (or semantically
equivalent) request — cutting cost + latency — **as an optimization inside the governed loop, never a
bypass of it.** All backend-real. **Decided 2026-07-30.**

## 1. Where it sits (governance-preserving)
```
input firewall → policy evaluate → [CACHE HIT? serve + audit(cache_hit)] → inference → output firewall → [STORE] → audit
```
- Firewall + policy run on **every** request; only **inference** is skipped on a hit.
- **Every hit is still audited** (outcome `cache_hit`, with tokens/cost saved) ⇒ sovereignty invariant intact.
- Cache key is computed over the **already-PII-scrubbed** content (Stage 1 runs first) ⇒ no raw PII in keys.

## 2. Match type (decided 2026-07-30: **exact by default; semantic is an explicit opt-in**)
1. **Exact-match — the DEFAULT.** Hash of `(scope, model, normalized messages, gen params)`. Fast, zero-risk.
   **Similarity threshold defaults to 1.0** ⇒ only identical requests hit ⇒ **semantic matching is OFF by default.**
   The fuzzy-answer liability never occurs unless someone deliberately turns it on.
2. **Semantic — OFF unless opted in.** Enabling it means lowering the threshold below 1.0; then, on exact-miss,
   embed the scrubbed prompt and cosine-match within the **same team+model**, serving only above the chosen threshold.
   - **Embeddings MUST be in-boundary** (e.g. Ollama `nomic-embed-text`) — never an external embedding
     API, else prompts leak out of the boundary. **Load-bearing sovereignty constraint.**
   - Semantic hits are **marked distinctly in the audit** (traceable); toggling semantic off returns to pure exact.
   - **Go/no-go instrumentation:** when opted in, ship with a **kill-switch + metrics** (semantic-hit rate,
     flagged-wrong rate, similarity distribution) so its value is judged on **data, not a guess** (see X4).
   - v1 storage: embedding vector as a blob + brute-force cosine over `(team, model)` candidates (SQLite).
     A real vector index is a later swap.

## 3. Scope (decided: **per-team**)
- A cached answer is reused **only within the same team** (keyed by team). No cross-tenant sharing by default.
- Opt-in **global** or stricter **per-key** are configurable.

## 4. What's cacheable by default (decided: **both guardrails ON**, configurable)
- **Deterministic only (`temperature = 0`)** — temp>0 means the caller wants variety; don't freeze it.
  The cache-worthy workloads (classification/extraction/RAG/structured) are temp=0 anyway. Higher-temp = explicit opt-in.
- **Exclude data-tagged / sensitive (`has_data_tag`)** — a cached response is another copy of data at rest;
  default-exclude keeps the sensitive footprint minimal. Opt-in per policy.
- **Never cache:** blocks/warns, streaming responses (v1), output-firewall failures.
- On serve, **re-scan the cached response through the output firewall** (cheap) in case policies tightened.

## 5. Invalidation / freshness
- Per-entry **TTL** (configurable) · **keyed by model** (a model swap misses automatically) · admin **purge** ·
  **LRU / size cap** eviction.

## 6. DIP
- New **`ResponseCachePort`** (`get / put / invalidate / stats`) in `app/ports`; **`SqliteCache`** adapter (v1).
- Pipeline only calls `cache.get(...)` / `cache.put(...)`. Later **`RedisCache`** (distributed) or a real
  **`SemanticCache`** vector-index adapter swaps in with **zero pipeline change**.

## 7. Visibility — admin-only (decided 2026-07-30)
- **End user / caller sees NOTHING** — the API response and Console chat are **identical** whether served
  from cache or the model. **No user-facing badge; `precepta.cache*` fields omitted** for non-privileged
  principals. The cache is seamless to the consumer.
- **Admin / auditor sees everything** — a **Cache Savings dashboard** (tokens / $ / latency-ms saved,
  hit-rate %, aggregate **and per-team**, with trend) + `cache_hit` rows in the audit log (exact vs semantic
  marked). Numbers from price/telemetry × cached token counts. **No demo values.**
- Optional **admin-only debug toggle** (off by default) to expose the cache field in responses for troubleshooting.

## 7b. Temperature — who sets it (clarified 2026-07-30)
- **Value** = set by the **caller per request** (OpenAI-compatible `temperature` param); Console chat sends a
  **system default**; the business end user does not set it.
- **Rules** = set by the **admin**: the caching threshold (default *cache only when `temperature ≤ 0`*) and an
  optional **governance-policy clamp/default** (e.g. cap or default temperature per team — the policy engine
  already inspects request params).
- **Omitted `temperature` → treated as non-deterministic → not cached** (conservative, OpenAI-compatible);
  admin may set an org default.

## 8b. Backend-real metrics
- Real `response_cache` table; real hit/miss counts; **tokens, $ and latency saved** computed from the existing
  price/telemetry data. **No demo numbers.**

## 8. Data-model touchpoints
- `response_cache`: `id, scope, model, cache_key, embedding(blob), response_json, prompt_tokens,
  completion_tokens, created_at, expires_at, hit_count, last_hit_at`; index `(scope, model, cache_key)`.
- Config (org/team): `cache_enabled, scope, ttl, semantic_enabled (default OFF), semantic_threshold (default 1.0 = exact), cache_temp0_only,
  exclude_sensitive`.

## 9. Build order
1. `ResponseCachePort` + `SqliteCache` + `response_cache` table.
2. Exact-match get/put wired into `governed_chat` (after policy-allow / after output firewall).
3. `cache_hit` audit outcome + real saved tokens/cost.
4. Semantic tier (in-boundary embeddings + cosine + threshold, audit-marked).
5. Console: toggle + scope/TTL/threshold settings + hit-rate/savings tile.

## 10. Deferred (V2)
- Redis / distributed cache · real vector index · streaming-response caching.

---

# Item 2 — Policy scope (apply to all vs selected)

**Goal:** Let a governance policy optionally target **selected** teams / roles / subject-types /
backends / models instead of always applying globally — with **agents governed the same as humans**.
All backend-real. **Decided 2026-07-30.**

## 1. Problem (today's reality)
- In [app/governance/policy.py](app/governance/policy.py), a policy is matched by **one dimension
  only**: `WHERE enabled=1 AND (action_type=? OR action_type='*')`. Every enabled policy therefore
  applies to **every** request of that action type — no way to target a team, a backend, agents-only, etc.
- Item 2 closes that gap: **all (default) vs selected**.

## 2. Mechanism — an optional `scope` selector
- Each policy gets an optional **`scope`** (new `scope_json` column, default `{}`).
- **Empty `{}` = applies to all** → identical to today ⇒ **zero migration**, existing policies unaffected.
- **Non-empty = applies only where the request matches** — **AND across** dimensions, **OR within**
  a dimension's list. **Include-only** (no exclusions in v1 — decided).
- Insertion point: `load_enabled(action_type)` returns candidates → **add one scope-filter step**
  (keep policies whose `scope` matches the live `PolicyCheckContext`) → `evaluate()` unchanged.
  Most-restrictive-wins precedence untouched; scope only decides candidacy.

## 3. Scope dimensions (v1 — **all**, decided) — every input already real
| Dimension | Real source | Example |
|---|---|---|
| **Team** | `Principal.team` / `api_keys.team` | "PII-redact for the support team only" |
| **Role** | `Principal.role` (admin/user/auditor) | "auditors read-only" |
| **Subject type** | human vs **agent/service** (API-key principals) | "block PII egress for agent calls" |
| **Backend** | `PolicyCheckContext.backend` | "stricter on metered Neysa than local Ollama" |
| **Model** | model id from the request | "no PHI to model X" |

## 4. Agent parity (explicit ask)
- Because **Subject type** is a scope dimension, one policy can target **agents-only**, **humans-only**,
  or **both**. Same block/warn/audit engine, same precedence — agents are governed like humans.

## 5. Engine boundary (decided: **keep separate**)
- This governance-policy scope stays a **lightweight, self-contained** mechanism for the firewall
  policies (*is this request allowed under org rules?*). The [OpenGuard spike](#spike--open-guard-python-behind-authorizationport-dip)
  engine governs authZ/**delegation** (*can this principal act at all?*). Same dimensions, **no merge in v1** —
  revisit only if/when OpenGuard is adopted.

## 6. Console UX
- Policy editor gains an **"Applies to"** section: default **"All requests"**; switch to **"Selected"**
  reveals multi-selects for Team / Role / Subject type / Backend / Model — **populated from real data**
  (teams from `api_keys`/`team_scopes`, backends from `registered_backends`, models from `/v1/models`).
- Policy list shows a scope badge ("All" vs "Scoped: 2 teams, agents").

## 7. Data-model touchpoints
- `governance_policies`: add `scope_json TEXT NOT NULL DEFAULT '{}'`.
- No other schema change; scope inputs derive from the existing `PolicyCheckContext` + `Principal`.
- May extend `PolicyCheckContext` with `model` + `actor_type` (currently has `backend`, `principal`).

## 8. Hard requirement
- **Backend-real** — scope matched against the actual request/principal; empty scope explicitly shown
  as **"All requests"** (never hidden). No demo targeting.

---

# Spike — `open-guard-python` behind `AuthorizationPort` (DIP)

> **Date:** 2026-07-30 · **Status:** ✅ de-risked, recommend adopt · **Type:** throwaway spike
> (Rule 14 spike; gate-exempt). Bears on Item 1 (budgets), Item 2 (policy scope), and the
> user's ask to govern **agent / user / delegation**.

**Question:** Can [`open-guard-python`](https://pypi.org/project/open-guard-python/) (`open_guard`
0.12.5, MIT, in-process) sit behind our `AuthorizationPort` (`app/ports`) without touching the
domain core, and does it actually deliver agent + user + bounded-delegation authZ?

**Proven against the real port + our stack (Python 3.14):**

| Claim | Result |
|---|---|
| Installs & imports on Py 3.14, in-process, SQLite/Postgres via `build_guard(dsn)` | ✅ |
| **Fail-closed by default** — no matching policy → `DENIED` (critical for a governance product) | ✅ |
| Per-subject grant + **deny-by-default**: user allowed, ungranted agent denied | ✅ |
| Agents/users/services first-class (`ActorType.USER/AGENT/SERVICE/ROBOT/DEVICE`) | ✅ |
| **Identity chains** — `Subject.on_behalf_of` + rich policy namespace `chain.depth / chain.root_actor / chain.ancestors`, `max_chain_depth=5` | ✅ |
| **Bounded delegation** — `budget`(Decimal) + `max_uses` + `expires_at`; consume to exhaustion → `UsageExhaustedError` | ✅ |
| **Revocation** kills further use | ✅ |
| **Tri-state** decisions (`allowed / denied / pending_approval`) + `requires_approval`, `non_delegable`, `max_delegation_depth=10`, `default_delegate_policy='self_only'` | ✅ |
| POC `OpenGuardAuthz` **satisfies our `AuthorizationPort` Protocol**; domain core untouched | ✅ |

**API shape learned (for the adapter):**
- `g = og.build_guard(dsn)` → `g.policy_store` (property: `add/get_by_tenant/get_by_tenant_and_type/remove`).
- `g.authorize(subject, action, resource, tenant_id, context=None) → Decision(.allowed, .status)`.
- `g.delegate(**kw)` · `g.consume_delegation(id, tenant, amount, cost)` · `g.revoke_delegation(id, caller, tenant)`.
- Policy matching: **ABAC** = action + resource + **`conditions`** dict (`{"subject.id": {"op":"eq","value":…}}`);
  subject scoping goes through `conditions`, **not** `subject_match`. RBAC = roles/relations; ReBAC = relationship tuples.

**DIP mapping (adapter sketch — `app/adapters/authz/openguard.py`, not yet built):**
`Principal.subject → Subject.id` · `role in {agent,service} → ActorType.AGENT` else `USER` ·
`action → Action(name)` · `resource → Resource(id, resource_type="model")` · `can() → decision.allowed`.
Delegation/budget/PENDING_APPROVAL exceed today's boolean `can()`; capturing them = a small **additive**
port extension later (`authorize()` tri-state + `delegate/consume` surface), not a domain change.

**Verdict:** Strong fit for the "govern agent / user / delegation" goal and folds Item 1 budgets +
Item 2 scoping + delegation into one fail-closed engine. **Recommend:** adopt as the `AuthorizationPort`
adapter in a dedicated phase; keep `RoleCheck`/`scopes` as the default adapter until parity is proven
(swap via DIP, never a rewrite).

---

# Status of all items (updated 2026-07-30)

All sections are above. Items **1, 2, 3, 4, 5, 7** are 🟢 fully scoped (each has its own detailed
section). The cross-cutting foundations (X1–X5) and the OpenGuard spike are captured too. **Only Item 6
(self-hosting / deploy) is still to brainstorm.** See the Tracker + Build-order at the top.
