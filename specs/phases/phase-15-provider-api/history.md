---
type: Phase History
phase: 15
name: provider-api
---

# Phase 15 — AI Provider Integration API · History

### [DECISION] 2026-08-11 — Phase scope: AI-provider integration API, not generic CRUD
Topics: api, provider-integration, catalog
Affects-phases: phase-15-provider-api
Affects-specs: specs/phases/phase-15-provider-api/overview.md
Detail: Reframed the "public API" phase around AI-provider integration (à la
LiteLLM's provider/model catalog) rather than generic management CRUD. Novel core
is a provider + model catalog (capabilities/context/pricing) in front of the
existing connect-and-govern flow. Researched LiteLLM's `model_prices_and_context_window.json`
(flat map keyed by model → litellm_provider, mode, max_input/output_tokens,
input/output_cost_per_token, supports_* flags) as the reference shape.

---

### [DECISION] 2026-08-11 — Vocabulary: "backend" → endpoint, "chat" → inference
Topics: naming, api-surface
Affects-phases: phase-15-provider-api
Affects-specs: specs/phases/phase-15-provider-api/overview.md, plan.md
Detail: User directive — drop the words "backend" and "chat". Resource is
**endpoint** (`/v1/endpoints`, each an "inference endpoint"); primary governed
call is **`/v1/inference`**. `/v1/backends*` and `/v1/chat/completions` are kept
as back-compat aliases so the Console and OpenAI SDKs keep working.

---

### [DECISION] 2026-08-11 — Auth: reuse keys + `manage` scope; sovereignty stays owner-only
Topics: auth, keys, sovereignty
Affects-phases: phase-15-provider-api
Affects-specs: specs/phases/phase-15-provider-api/plan.md#group-0
Detail: No new key class — extend per-team keys with a `manage` scope (read-only
vs read-write). A manage key drives the management API but **cannot** change
Sovereign Mode / egress allowlist / router config (those remain
`is_platform_owner`-only) — a management credential must never be able to unseal
the boundary.

---

### [DECISION] 2026-08-11 — Model catalog is curated + in-boundary
Topics: catalog, sovereignty
Affects-phases: phase-15-provider-api
Affects-specs: specs/phases/phase-15-provider-api/plan.md#group-0
Detail: Discovery must not require a runtime external call. Ship a curated,
bundled `app/data/model_catalog.json` (sovereign); a vendored LiteLLM import is
an optional build-time step, off by default. Live-model capabilities come from a
best-effort match to the catalog with an honest `"unknown"` on miss — never a
fabricated capability.

---

### [SCOPE_CHANGE] 2026-08-11 — Deferred: SDKs, webhooks, GraphQL, Terraform, rate-limiting
Topics: scope
Affects-phases: phase-15-provider-api
Affects-specs: specs/phases/phase-15-provider-api/overview.md#scope--out
Detail: Client SDKs, an inbound webhooks/events API, GraphQL, a Terraform
provider, and per-management-key rate limiting are out of scope (rate-limiting →
ENH). No breaking changes — old paths stay as aliases. Workflow builder remains
Phase 13.

---

### [NOTE] 2026-08-11 — Numbered Phase 15
Topics: roadmap
Affects-phases: phase-15-provider-api
Affects-specs: specs/planning/roadmap.md
Detail: Numbered 15 so Phase 13 stays reserved for the Workflow builder and 14
(Deploy: Sovereign Pilot) is untouched. Branch `phase-15-provider-api`, off the
`phase-14-deploy-pilot` code state (Phase 14 not yet merged to `main`).

---
