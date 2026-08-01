---
type: Backlog
---

# Backlog

> **Last Updated**: 2026-07-30

---

## Priority Levels

| Level | Meaning |
|-------|---------|
| **P0** | Critical — blocks current phase |
| **P1** | High — address in current/next phase |
| **P2** | Medium — within 2 phases |
| **P3** | Low — nice to have |

**Status**: `open` | `in-progress` | `resolved` | `deferred` | `deprecated`

---

## Bugs

| ID | Title | Priority | Status | Phase | Detail |
|----|-------|----------|--------|-------|--------|
| BUG-001 | Model Plane: adding a 2nd backend of the same provider **type** overwrites the first | P2 | open | 10 | Backends are keyed by provider *type*, not per-model. Console sends `provider=PROVIDER_OF[type]` (e.g. every HF backend → `"hf"`); `registered_backends.provider` is PK with `ON CONFLICT DO UPDATE`, and `registry[provider]=backend`, so a 2nd HF (or vLLM/Ollama) model **replaces** the first. The typed **Name** is sent but ignored. Fix: give each backend a unique id (slug of Name, or provider+name) and key the registry/store/pricing/routing/sensitive-approved/key-scopes by that id. Ripples through anything that references a backend by name — do as a small scoped change. Reported by user 2026-08-01. |

## Features

| ID | Title | Priority | Status | Phase | Detail |
|----|-------|----------|--------|-------|--------|
| FEAT-001 | Key expiration + cost/token budgets + per-key scope (backend/model) | P1 | resolved | 10 | **DONE + verified 2026-08-01.** Expiry (90d/never/401), per-key **cost + token** caps (daily/monthly, timezone, warn-80/block-100 → 429 + **bell notification**), backend/model scope (block), **edit**, **suspend/reactivate**, `GET /v1/usage`. Dropped subject-type + team (user decision). 14 tests; browser-validated. |
| FEAT-002 | Policy scope (Key / Backend / Model) + editable policies (version bump) | P1 | resolved | 10 | **DONE + verified 2026-08-01.** `scope_json` + `scope_matches` (empty=all, AND across dims, unknown=no-match); enforced in gateway pre-inference; PUT /v1/policies/{id} edit with version bump. Console: Key/Backend/Model scope pickers + Edit modal + scope/version on cards. Dropped team/role/subject (user decision). 6 tests; 119/119; browser-validated. |
| FEAT-003 | Response cache — exact + semantic, per-team, governance-preserving, admin-only visibility | P2 | open | 10 (cand) | Fully scoped — `BRAINSTORM.md` §Item 3. Behind a `ResponseCachePort` (DIP); in-boundary embeddings; invisible to end user. |
| FEAT-004 | OpenGuard authZ/delegation adapter behind `AuthorizationPort` (agent/user/bounded delegation) | P2 | open | 10 (cand) | De-risked spike ✅ — `BRAINSTORM.md` §Spike. Adopt in a dedicated phase; keep `RoleCheck`/`scopes` as default until parity. |
| FEAT-005 | Compression — history-summarization + prompt-token (LLMLingua), budget-aware (opt-in), consent-gated corpus | P2 | open | 10 (cand) | Fully scoped — `BRAINSTORM.md` §Item 4. Never surprises the user; in-boundary; admin-only savings view. Eval-gated (needs FEAT-006). |
| FEAT-006 | **Eval harness (foundation)** — fixed test set + per-use scorers (routing/compression/cache/learning), versioned (Rule 11) | P1 | open | pre-10 | **Gates FEAT-003(semantic)/005/007/008 — build FIRST.** `BRAINSTORM.md` gap #1. Currently assumed by 4 items, owned by none. |
| FEAT-007 | Advanced routing — governance filter → LLM intent-router → budget modifier; failover; auditable | P2 | open | 10 (cand) | Fully scoped — `BRAINSTORM.md` §Item 5. Sensitivity auto-detected; sensitive→approved-only (block+notify caller+admin). Classifier eval-gated (FEAT-006). |
| FEAT-008 | Traces → learning loop — capture traces + reward (explicit+implicit) → learned routing | P3 | open | 10 (cand) | Fully scoped — `BRAINSTORM.md` §Item 7. Per-customer/in-boundary/consent; delivers Item 5·E. Model fine-tuning deferred. Eval-gated (FEAT-006). |
| FEAT-009 | Self-hosting / deploy — container + compose bundle, then Helm/Postgres/Vault/air-gap | P1 | open | 10 (cand) | **Not yet brainstormed** — `BRAINSTORM.md` Item 6 paused. Blocks actual customer self-hosting. |

## Tech Debt

| ID | Title | Priority | Status | Phase | Detail |
|----|-------|----------|--------|-------|--------|
| TD-001 | Pricing source-of-truth — versioned `model_prices` table + `PricingPort` feeding all $ figures (budgets/cache/compression) | P1 | resolved | 10 | **Built + verified 2026-07-31** (`app/pricing.py`, `PricingPort`, wired router/stats/infra, admin `/v1/pricing`, Console price column + avg-cost tile). 7 new tests, 95 total pass; browser-validated. Silent-$0 bug fixed (unknown price → "Set price"). |
| TD-002 | Canonical metering/accounting — one definition of billable vs saved vs usage tokens across budgets/cache/compression | P1 | resolved | 10 | **Built + unit-tested 2026-07-31** (`app/metering.py` `meter()`): billable (post-compression, 0 on cache hit) · budget_charge · usage_volume · tokens_saved; canonical pipeline order documented. Budgets/cache/compression integrate it. |
| TD-003 | Streaming vs governance — output-firewall/cache/compression assume full response before send | P1 | open | pre-10 | `BRAINSTORM.md` §X3. Enterprises expect streaming; needs buffered-scan / chunk-scan / policy-gated-disable design. |
| TD-004 | Sensitivity detection quality — regex firewall is load-bearing for 4 features (routing/cache/compression/traces) | P1 | open | pre-10 | Gap #3. If "sensitive" is wrong, governance is silently weak everywhere. VISION flags "PII beyond regex" as open. |
| TD-005 | Attribution model — key/team/user/**agent + delegation chain** across budgets/traces/audit | P1 | open | pre-10 | Gap #4. When an agent acts for a user (FEAT-004), whose budget/trace/audit is it? Define once. |
| TD-006 | Fail-soft for in-path optimizations — cache/compress/classify/embed must skip-and-proceed, never break inference | P1 | open | pre-10 | Gap #5. Each optimization adds a failure mode in the request path; define soft-fail behavior for each. |
| TD-007 | New data stores at rest + attestation scope — cache/corpus/traces hold sensitive content | P1 | open | pre-10 | Gap #6. Encrypt + access-control; expand the Sovereignty Attestation (proves egress today) to cover these stores. |
| TD-008 | Govern the control plane itself — config precedence + role granularity (separation of duties) + notification delivery (email/Slack/SIEM) | P2 | open | pre-10 | Gap #7. Growing toggles/roles/notification sources need one coherent model. |

## Enhancements

| ID | Title | Priority | Status | Phase | Detail |
|----|-------|----------|--------|-------|--------|
| ENH-001 | Key rotation — regenerate a key's secret without losing its config | P2 | open | — | Security hygiene when a key leaks (rotate, not rebuild). |
| ENH-002 | Key last-used + request count — spot dormant/misused keys | P2 | open | — | Show last-used timestamp + volume per key. |
| ENH-003 | Per-key rate limiting (requests/min) | P2 | open | — | Stop a runaway loop burning budget in seconds. |
| ENH-004 | Dedicated Usage page — per-key/per-team spend + tokens over time | P2 | open | — | Beyond the per-card badge; trends + export. |
| ENH-005 | Per-key IP allowlist; admin-configurable alert thresholds | P3 | open | — | Enterprise hardening. |
