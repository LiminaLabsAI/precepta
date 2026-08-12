---
type: Phase Tasks
phase: 15
name: provider-api
---

# Phase 15 — AI Provider Integration API · Tasks

Legend: `[ ]` todo · `[/]` in progress · `[x]` done

## Group 0 — Contract foundations
- [x] `app/api/schemas.py` — Pydantic models (Provider, ProviderConfigField, CatalogModel, Endpoint, ModelInfo, Inference req/resp, Embeddings req/resp)
- [x] `app/api/errors.py` — standard error envelope + helper
- [x] `manage` scope on keys — store column(s), `issue_key` param, authenticate → principal
- [x] `app/api/deps.py` — `require_manage(write=…)` dependency; sovereignty stays owner-only
- [x] `app/data/model_catalog.json` + `app/catalog.py` — curated in-boundary catalog + `catalog_lookup` + optional LiteLLM import stub
- [x] tests: manage-scope authenticate + require_manage matrix; catalog_lookup hit/miss

## Group 1 — Providers + catalog endpoints
- [x] `GET /v1/providers` (types + config_schema)
- [x] `GET /v1/providers/{type}` (type + its catalog models)
- [x] `GET /v1/catalog/models?provider=&mode=` (typed, filtered)
- [x] tests: shapes, filters, no-network/in-boundary

## Group 2 — Endpoints resource + enriched models
- [ ] `GET/POST /v1/endpoints`, `GET/PUT/DELETE /v1/endpoints/{id}`, `/test`, `/approve-egress`
- [ ] `/v1/backends*` aliases → same handlers (back-compat)
- [ ] pagination + consistent status codes
- [ ] enrich `GET /v1/models` (mode/context/pricing/capabilities/health via catalog_lookup)
- [ ] tests: CRUD via contract, alias back-compat, models enrichment (honest unknown)

## Group 3 — Governed inference/embeddings + OpenAPI/docs
- [ ] `POST /v1/inference` (governed) + `/v1/chat/completions` alias → one handler
- [ ] `POST /v1/embeddings` (governed; in-boundary embedding model)
- [ ] OpenAPI: tags, summaries, Bearer security scheme; enable `/docs` + `/openapi.json`
- [ ] `docs/api/README.md` — auth + flow + runnable curl examples
- [ ] tests: governed inference/embeddings (policy/trace/audit), openapi presence

## Group 4 — Console surface
- [ ] migrate Console `/v1/backends*` → `/v1/endpoints*`; scrub "backend" copy → "endpoint"
- [ ] key issuance: "Management key" (scope=manage, read-only/read-write)
- [ ] API page (base URL, auth, curl examples, link to `/docs`)
- [ ] browser-verify

## Group 5 — Verification
- [ ] auth-matrix test (manage-read/write · inference-only · anonymous · owner-only sovereignty)
- [ ] contract + alias + catalog + enriched-models tests
- [ ] live smoke: register endpoint via API → governed `/v1/inference` in-boundary → `/v1/usage`
- [ ] browser-validate API page + management-key issuance
- [ ] update HANDOFF + changelog; mark roadmap/status/backlog
