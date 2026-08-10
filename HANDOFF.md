# preceptaai — Session Handoff (read this first)

> **Purpose:** everything the next session needs to continue executing the implementation plan
> without re-discovery. **Updated:** 2026-08-10. **Main pushed to GitHub · 314 tests passing.**
>
> **State (2026-08-10):**
> - **Console redesign** landed (Cache & compression two-tab; new **Traces** screen; **Workflow** screen).
> - **Phase 11 — Traces COMPLETE + merged:** per-step trace store (`app/traces.py`), pipeline capture,
>   `/v1/traces*` API, the 3-pane Traces screen (runs · checkpoint waterfall · Summary/Route/Messages/
>   Attributes tabs), **agent sub-trace (L2)**, and **bill-back** (cost by team/app).
> - **Phase 12 — Smart Router COMPLETE + merged + ACTIVATED:** intent catalog + scoring resolver
>   (`app/router/scoring.py`, `intent_catalog.py`), two-stage `smart.decide`, `RouteTarget` +
>   Agent-Trace-Contract (`targets.py`), LiteLLM/Agent adapters (`target_adapters.py`), toxicity filter +
>   enforcement-timing, read-only **Workflow** view, locked router eval (Rule 11) + Apache-2.0 boundary
>   (`app/router/OPEN_CORE.md`). **Live:** auto requests are routed by the two-stage router; the Traces
>   **Route tab shows the real scored candidate set**. +90 tests.
> - **BUG-001** (same-provider backends) fixed + guarded.
> **➡ NEXT: Phase 14 — Deploy: Sovereign Pilot (self-host).** Brainstormed + planned →
> `specs/phases/phase-14-deploy-pilot/`. Single-node **egress-locked docker-compose** + **in-boundary
> helper models** (bundled Ollama serves router + embeddings — closes **TD-009**) + **egress probe in the
> attestation** (provable zero-egress) + an in-product **Deployment** screen (live status + setup checklist
> + copy-runbook). Pilot slice — defers Helm/Postgres/Vault/air-gap/HA/SCIM. Run `/start-phase`.
> *(Verification needs Docker on the host to bring the stack up + smoke-test.)*
>
> **Read order for a fresh session:** this file → `specs/status.md` → `specs/backlog/backlog.md` →
> `specs/phases/phase-14-deploy-pilot/` → `specs/planning/roadmap.md`.

---

## 1. What the product is
**preceptaai** — a self-hosted, governed **control plane** for running open-source AI models on the
customer's own infrastructure. Point any OpenAI-compatible client at it; every request is routed to an
**in-boundary** model, policy-checked, PII/injection-firewalled, and written to a tamper-evident audit
log, with a signed zero-egress **attestation**. The router is a *feature*; the product is the governed
control plane. Buyer = compliance/security leads at regulated firms. **Core promise: data never leaves
the customer's network.**

Stack: **Python 3.14 · FastAPI · SQLite (`preceptaai.db`) · Ollama/vLLM serving · one self-contained
Console (`web/console.html`)**. Architecture: **ports & adapters (DIP)** — the domain core depends only
on Protocols in `app/ports/__init__.py`; everything external is a swappable adapter. New features clip in
behind a port; never rewrite the core.

## 2. How to run / verify (dev)
```bash
./run.sh              # venv + deps + uvicorn on 127.0.0.1:8000  (loads .env: OIDC + backends)
./.venv/bin/python -m pytest -q         # full suite (124 passing)
```
- **Dev auth:** the backend accepts bearer token `dev-admin` → principal `admin@local` (role admin).
  In the browser Console, set it via `localStorage.setItem('precepta_session','dev-admin')` then reload
  (the `#s=` fragment gets stripped by the `/`→`/console` redirect, so localStorage is the reliable way).
- **Backend code changes need a server restart** (`pkill -f "uvicorn app.main"; ./run.sh`) — no autoreload.
  `web/console.html` is served no-store, so UI edits show on refresh without restart.
- **Ollama** runs locally (llama3.2:3b); an **`hf`** backend is configured (Qwen). Both are `in_boundary`.
- **Browser validation:** use the in-app browser MCP (`mcp__Claude_Browser__*`). Every UI change in this
  project is browser-validated against the live backend — **that is the standard.**

## 3. Non-negotiable rules (the user enforces these — do not violate)
1. **Backend-real, NO mock/demo/hardcoded data.** Every number/list from a real endpoint. If a backend
   doesn't exist yet, show an honest empty/pending state — never a fabricated number. (Caught repeatedly.)
2. **Sovereignty:** data never leaves the customer's boundary. Any helper model (router, embeddings,
   compressor) must run **in-boundary**. Never send prompts to an external/Precepta-hosted service.
3. **Safe by default, risk only by explicit opt-in.** (semantic cache off by default, aggressive
   compression opt-in, budget never silently degrades quality, etc.)
4. **Governance blocks are always transparent to the caller** (opposite of cache hits, which are invisible).
5. **Plain English** with the user; avoid jargon; handle technical housekeeping yourself; only ask the
   user genuine product/business decisions, one at a time.
6. **Verify before claiming done** (Rule 12): run real tests + browser-validate each feature before saying
   it's done. Don't claim work you didn't do.
7. **Git:** branch per feature (`feat/…`), Conventional Commits ending with
   `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`, then merge `--ff-only` to `main` and
   `git push origin main`. `.env`, `preceptaai.db*`, `jre/`, `.venv/` are gitignored — never commit secrets.
   Remote: `github.com/LiminaLabsAI/precepta`. (The user has authorized landing each verified feature on
   main + GitHub autonomously.)

## 4. What's BUILT (✅ on main, tested + browser-verified)
| Area | Modules | What works |
|---|---|---|
| **Pricing (TD-001)** | `app/pricing.py`, `PricingPort` | Versioned `model_prices` table; router/stats/infra source price from it; admin `/v1/pricing`; Console shows real prices. Unknown price → "Set price" (never fake $0). |
| **Metering (TD-002)** | `app/metering.py` | One `meter()` def: billable (post-compression, 0 on cache hit) · budget_charge · usage_volume · tokens_saved. |
| **Keys (FEAT-001)** | `app/adapters/identity/keys.py`, `app/budgets.py`, `app/notifications.py` | Expiry (90d/never/401) · per-key **cost + token** caps (daily/monthly, org-tz windows, warn 80% / block 100% → 429) · backend/model **scope** (block) · **edit** (PUT) · **suspend/reactivate** · real **bell notifications** (deduped). `GET /v1/usage`. **Dropped role/team/subject-type** — a key is an app-level credential; admin stays human-only. |
| **Policy scope + edit (FEAT-002)** | `app/governance/policy.py` | `scope_json` + `scope_matches(key/backend/model)` enforced pre-inference (empty=all, AND across dims, unknown value w/ restriction=no match); `update_policy` bumps **version**; `PUT /v1/policies/{id}`. Console: Key/Backend/Model pickers + Edit + scope/version on cards. |
| **Sensitive routing filter (FEAT-007·C)** | `app/governance/sensitive.py` | `sensitive_backends` store (backend + hosting location + approver + ts). Sensitivity auto = firewall PII/PHI OR caller `data_tag`. Sensitive → approved-backend-only, else **block 403 + critical admin notification**. **Off until ≥1 backend approved** (non-breaking; firewall still redacts). `GET/POST/DELETE /v1/routing/approved`. Console "Advanced routing — sensitive data" box real, with location-confirm approval modal. |
| **Router config (Phase 4·1)** | `app/adapters/secret/`, `app/router/config.py`, `app/adapters/authz` | Platform-owner-only surface for where the router's own **in-boundary** model runs. `SecretStorePort` adapter (keys set/checked, **never returned by the API**). `router_config` store (ollama/hf · endpoint · model; HF key → secret store; **fail-closed** — hf needs endpoint+key). `is_platform_owner` (`PRECEPTA_PLATFORM_OWNERS`). `GET/PUT /v1/router/config`; `/auth/me` → `platform_owner`. Console "Router" settings tab. **Consumed by the LLM router (task 3), not yet wired.** |
| **Eval harness (Phase 4·2)** | `tests/benchmarks/` | LOCKED router-quality evaluator (Rule 11) v1: frozen 12-case set + in-boundary Ollama judge (temp=0) + harness driving the REAL router. **Scalar = mean answer-quality**; cost + p50 latency as guardrails. `python -m tests.benchmarks` = the live run; stub-based unit tests keep CI green. Baseline 0.854. Reused later to grade cache/compression. |
| **LLM router (Phase 4·3)** | `app/router/intent.py`, `app/router/brain.py` (`LLMBrain`), `app/gateway/pipeline.py` | `auto` requests optionally routed by an **in-boundary** model (classify goal/difficulty → backend, balanced cost+speed). Cached, **fail-soft → rules**. Governance auto-path filter: sensitive auto request restricted to approved backends (router + failover), fail-closed 403+notify. "Optimize automatically" = real `optimize_auto` org setting (OFF default). |
| **Console/cleanup** | `web/console.html`, `app/main.py` | Rebuilt to the imported design (`design/Precepta Console.dc.html`); logo via `/assets`; top-right "security controls" badge removed; **compliance report + DPDP/GDPR/HIPAA/SOC2 claims removed** (we haven't certified — was a trust risk). Audit log + zero-egress attestation remain (technical facts). |

## 5. What's NEXT — execute in this order (Phase 4 ✅ → 5)
**Phase 4 · Smart routing — ✅ ALL THREE TASKS DONE (committed, UNLANDED — see §10):**
1. ✅ **Router config in Settings** — platform-owner-only (`PRECEPTA_PLATFORM_OWNERS`, default
   `123.sarang@gmail.com` + `admin@local`). `app/adapters/secret/` (SecretStorePort) + `app/router/config.py`
   (ollama|hf, endpoint, model; key in secret store, only `hf_key_set` returned; fail-closed). `GET/PUT
   /v1/router/config`; `/auth/me`→`platform_owner`; Console owner-only "Router" tab.
2. ✅ **Eval harness (FEAT-006)** — LOCKED evaluator `tests/benchmarks/` v1 (eval set + in-boundary Ollama
   judge + harness; **scalar = mean answer-quality**, guardrails cost + p50 latency). `python -m tests.benchmarks`
   runs it live. Baseline (rules): **0.854 / 12**.
3. ✅ **LLM intent-router (FEAT-007·A)** — `app/router/intent.py` (in-boundary classify goal/difficulty,
   cached, fail-soft) + `LLMBrain` (balanced cost+speed mapping) + governance auto-path filter (`allowed` set
   threaded pipeline→brain→engine; fail-closed 403+notify). "Optimize automatically" toggle → real
   `optimize_auto` org setting (OFF by default). Live eval (llm): **0.854** (holds), p50 676ms.
   **Known-honest:** 2 undifferentiated tier-1 local backends = no quality gain yet; 3B classifier emits bad
   JSON ~half the time (fail-soft covers it). Sharpens with a stronger in-boundary backend/judge.

**→ Phase 5 · Cost optimization (NEXT):** Cache (FEAT-003, exact-match default, semantic opt-in, governed loop,
admin-only savings) · Compression (FEAT-005, safe baseline first; LLMLingua later behind the eval). Build
these **with** fail-soft (TD-006) + the streaming decision (TD-003), not after. The eval harness (task 2) is
ready to grade both. **Reminder (HANDOFF §8):** cost features read ~$0 on local Ollama — they only prove out
with a metered backend + real traffic.

Then Phases 6–9 per `IMPLEMENTATION_PLAN.md` §Phase 10.

## 6. Router decisions locked (from this session — for Phase 4)
- Build the **LLM intent-router** (user chose it over rules-based, despite my note it may be over-engineering
  for only 2 backends today — see doubts §8).
- **Balanced** cost+speed optimization.
- Sensitive-data rule = **fail-closed** (block + notify) — done for explicit; extend to auto in the router.
- Backend approval = **show location + confirm** (done).
- Router runs **in-boundary**; **Precepta-owned HF key** (separate from the org's), configurable in
  Settings **only by the platform owner** (`123.sarang@gmail.com`). "Ollama in dev / HF live" = a
  configurable setting, not hardcoded (the user wants to choose where each is used).

## 7. Other product decisions made this session (don't re-litigate)
- Cache: **exact-match default, semantic opt-in** (threshold 1.0 default); per-team scope; in-boundary
  embeddings; **admin-only savings visibility** (invisible to end users); temp=0 + exclude-sensitive defaults.
- Compression: **never surprise the user**; baseline auto (quality-safe), aggressive = opt-in "cost-saving
  mode"; 80% budget = notify only (never auto-downgrade quality); local backend = context-fit only.
- Before/after (compression) + traces training use = **consent-gated, per-customer, in-boundary, never pooled**.
- Metering: cache hit → usage counted, cost budget NOT charged; compression → billed on compressed tokens.

## 8. Open doubts / concerns I raised (worth keeping in mind)
- **LLM router may be over-engineering** for the current 2-backend setup (adds a call per request; marginal
  benefit). User chose to build it anyway — proceed, but keep it fail-soft + eval-gated.
- **Cost features can't be truly exercised** yet: everything runs on **local Ollama ($0)**, so budgets/
  savings honestly read ~$0. They only prove out with a **metered backend + real traffic.** User chose to
  keep building; flag getting a metered workload / a design-partner pilot (the vision's #1 risk).
- **Sensitivity is regex-only** (`app/governance/firewall.py`) — the governance that routing/cache/
  compression lean on is only as strong as that (TD-004). Strengthen when building on it.
- **Fail-soft (TD-006):** cache/compress/router sit in the request path — each must skip-and-proceed on
  failure, never break inference. Bake in as you build.

## 9. Useful state / gotchas
- Dev DB has some demo rows (a `payments-app` key, an approved `ollama` for sensitive, a couple policies).
  `./run.sh reset` clears audit/telemetry; harmless dev data otherwise (gitignored, not on GitHub).
- 2 SSO tests "fail" only when `.env` OIDC vars are loaded (via `run.sh`); running pytest directly (no
  `.env` sourced) → all pass. Not a real failure.
- The backend `/compliance/report` endpoint still exists (unused; UI removed). Remove it + its tests if a
  fully clean cut is wanted.
- The Console (`web/console.html`) is a single ~1300-line vanilla-JS SPA: `state` object → `render()`
  switches on `state.screen`; per-view functions; live handlers appended near the bottom; `loadAll()` fans
  out the initial fetches. `app.*` methods are global (used in `onclick`).

## 10. Landing state — ✅ LANDED (2026-08-03)
All Phase 4–7 work + the Model-Plane and notification fixes are **merged to `main` (`53a160d`) and pushed to
GitHub** (`origin/main` = `53a160d`). The whole session was one linear branch stack; `main` was fast-forwarded
to the tip in a single ff-merge and pushed, then all 12 feature branches were deleted. **Working tree clean;
no unlanded work.** The cross-feature integration test was run green before landing (`scripts/integrated_smoke.py`).

## 11. Phase status (this session, 2026-08-01)
- **Phase 4 (smart routing) — ✅ complete:** router config · eval harness (baseline 0.854) · LLM intent-router.
- **Phase 5 (cost) — ✅ complete:** response cache (live: 287ms→11ms) · prompt compression (14→5 tokens).
- **Phase 6 (learning) — ✅ complete:** traces + thumbs feedback → learned routing (live end-to-end).
- **Phase 7 (hardening) — ✅ complete:** ✅ TD-004 validated PII · ✅ TD-007 attestation data-stores · ✅ TD-006
  fail-soft · ✅ TD-003 streaming (SSE, govern-then-stream) · ✅ TD-005 agent attribution (audit chain) ·
  ✅ TD-008 configurable alerts · ✅ FEAT-004 OpenGuard authZ (configurable RBAC + ABAC + per-agent daily
  request budgets, behind AuthorizationPort). *Note: a full external OpenGuard/OPA engine + real in-boundary
  NER for PII would slot behind the same seams — V1 is the in-boundary implementation.*
- **Phase 8 (deploy) — ⚪ needs a brainstorm.** **Must-address at deploy (TD-009, user-parked 2026-08-01):**
  Precepta's router/helper models (router intent `.env` HF, cache embeddings, eval judge) read customer prompts,
  so the deploy strategy must run them **in-boundary** (dedicated endpoints in the customer's network) — that's
  where data sovereignty is actually enforced. Bring the router-model-public-endpoint concern back here. **Phase 9 (validation) — business, not code:** a metered
  workload + a design-partner pilot. **HF validation finding (updated 2026-08-01):** the current backend is
  `google/gemma-4-31B-it` (via HF/Novita public API — validates quality/routing, NOT sovereign; production
  needs a dedicated in-boundary endpoint). Set to **tier 3**. On the frozen eval it **beats local 3B**: scalar
  **0.854 → 0.888** (rules) / 0.882 (llm); hard-category **0.726 → 0.808** (e.g. reason 0.8→0.96, explain
  0.76→0.95), real cost ~$0.00011/req, p50 latency actually lower. This is the result the eval harness exists
  to catch — a genuinely stronger model raises the number, proving router+eval end-to-end. (The earlier
  `Ternary-Bonsai-27B` did NOT beat 3B — ternary quantization — so it was reverted; Gemma replaces it.)
  **Implication to flag:** with hf at tier 3, hard `auto` queries now route to the paid, non-sovereign Gemma
  by default (both rules and llm brains). Lower its tier if you don't want that as the default.
