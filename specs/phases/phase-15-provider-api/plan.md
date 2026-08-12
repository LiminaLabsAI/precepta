---
type: Phase Plan
phase: 15
name: provider-api
---

# Phase 15 — AI Provider Integration API · Implementation Plan

Execution order:
```
Group 0 → (Group 1 + Group 2 + Group 3 in parallel) → Group 4 → Group 5
```
Verification command (from `specs/config.md`): `./run.sh test` · no build step.
Branch: `phase-15-provider-api`.

---

## Group 0 — Contract foundations
**Sequential. Blocks everything.**
External deps: none (all in-boundary).

- `app/api/schemas.py` — Pydantic request/response models for the resources
  (Provider, ProviderConfigField, CatalogModel, Endpoint, ModelInfo,
  InferenceRequest/Response, EmbeddingsRequest/Response). Used so `/openapi.json`
  is accurate and inputs are validated.
- `app/api/errors.py` — one standard envelope `{"error":{"message,type,code}}` +
  a helper `error(status, type, message, code=None)` reused everywhere.
- **`manage` scope on keys** — extend `app/adapters/identity/keys.py` so a key
  carries a `scope` (`inference` | `manage`) and a `manage_write` flag
  (read-only vs read-write management). `_resolve_principal` maps a `manage`
  key to a principal that `can()` admin-tier actions. A `require_manage(write=…)`
  FastAPI dependency (in `app/api/deps.py`) enforces it. **Sovereignty ops
  (sovereign mode, egress approve, router config) remain `is_platform_owner`-only**
  — a manage key cannot unseal the boundary.
- `app/catalog.py` — the **curated, in-boundary model catalog** (a bundled
  `app/data/model_catalog.json`: id, provider, mode, max_input/output_tokens,
  input/output_cost_per_1m, capabilities{streaming,function_calling,vision,…}),
  plus `catalog_lookup(provider, model)` (best-effort match, honest miss) and a
  build-time importer stub for the vendored LiteLLM dataset (optional, off by default).

*Commit:* `feat(api): manage-scope keys + typed contract + in-boundary model catalog`

---

## Group 1 — Providers + catalog endpoints
**Parallel with Groups 2 and 3.**

- `GET /v1/providers` — list provider *types* (ollama, vllm, neysa, hf,
  openai-compatible) with `{provider,name,boundary,requires_egress_approval,
  config_schema[]}` (the connect-config fields). Source: a small provider-type
  registry (derive from the existing `backendTypeMeta`/registry knowledge).
- `GET /v1/providers/{type}` — one provider type + its catalog models.
- `GET /v1/catalog/models?provider=&mode=` — filtered catalog listing (typed).
- Contract tests for each (shape, filters, in-boundary — no network).

*Commit:* `feat(api): provider + model catalog endpoints`

---

## Group 2 — Endpoints resource + enriched models
**Parallel with Groups 1 and 3.**

- Rename the backends surface to **endpoints**:
  `GET/POST /v1/endpoints`, `GET/PUT/DELETE /v1/endpoints/{id}`,
  `POST /v1/endpoints/{id}/test`, `POST /v1/endpoints/{id}/approve-egress`.
  Keep `/v1/backends*` as thin **aliases** (delegate to the same handlers) so the
  running Console and early callers don't break.
- Add pagination (`limit`/`offset`) + consistent status codes (201 create,
  200 update, 204 delete) via the Group-0 schemas/errors.
- Enrich `GET /v1/models` — for each live endpoint: `{id,provider,mode,
  in_boundary,status,max_input_tokens,max_output_tokens,pricing{…},
  capabilities{…}}`, filled from `catalog_lookup` (honest `"unknown"` on miss)
  + real pricing (TD-001) + real health.
- Tests: endpoints CRUD via typed contract, alias back-compat, models enrichment.

*Commit:* `feat(api): endpoints resource (rename+alias) + enriched /v1/models`

---

## Group 3 — Governed inference/embeddings + OpenAPI/docs
**Parallel with Groups 1 and 2.**

- `POST /v1/inference` — governed inference; **shares the exact governed pipeline**
  as today's `/v1/chat/completions`, which becomes an alias (both call one handler).
  OpenAI-shaped request/response + the `precepta{…}` envelope.
- `POST /v1/embeddings` — governed embeddings for embedding-mode endpoints
  (routes to an in-boundary embedding model; policy → trace → audit like inference).
- OpenAPI curation: tags, summaries, a Bearer **security scheme**, enable `/docs`
  + `/openapi.json`; standardise error responses in the schema.
- `docs/api/README.md` — the API guide: auth (manage vs inference keys), the
  utilization flow, and runnable `curl` examples for every endpoint.

*Commit:* `feat(api): governed /v1/inference + /v1/embeddings + curated OpenAPI + docs`

---

## Group 4 — Console surface
**Sequential (wiring). Depends on Groups 1–3.**

- Migrate the Console's remaining `/v1/backends*` calls to `/v1/endpoints*`
  (aliases keep it working during the change); scrub the word "backend" from any
  remaining user-facing copy → "endpoint".
- Key issuance: a **"Management key"** option (scope=manage) with read-only vs
  read-write, alongside the existing inference keys.
- A new **API** page (nav item or Settings tab): base URL, how to authenticate,
  copyable `curl` examples, and a link to `/docs`.

*Commit:* `feat(console): endpoints rename + management-key issuance + API page`

---

## Group 5 — Verification
**Sequential. Last.**

- Tests: auth matrix (manage-read / manage-write / inference-only / anonymous /
  owner-only sovereignty), provider+catalog shapes, endpoints CRUD + alias
  back-compat, enriched models, governed `/v1/inference` + `/v1/embeddings`
  (policy/trace/audit), OpenAPI presence + security scheme.
- Live smoke: register an endpoint via the API → governed `/v1/inference` returns
  in-boundary → `/v1/usage` reflects it.
- Browser-validate the API page + management-key issuance.
- Update `HANDOFF.md` + `specs/changelog/`; mark the roadmap/status/backlog.

*Commit:* `test(api): auth matrix + contract + governed-inference + docs verification`
