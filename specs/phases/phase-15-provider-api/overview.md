---
type: Phase Overview
phase: 15
name: provider-api
title: AI Provider Integration API
status: planned
---

# Phase 15 — AI Provider Integration API

## Goal
A documented, **governed AI-provider integration API**: discover supported
providers and their model catalog (capabilities, context window, pricing —
LiteLLM-style but fully in-boundary), register an **inference endpoint**, and
drive **governed inference / embeddings** — all as code, with the same
sovereignty guarantees as the Console.

This is not generic CRUD: it is the "integrate an AI provider, governed and
sovereign" loop expressed as a stable, typed API.

## Key decisions
| Decision | Choice | Why |
|---|---|---|
| "backend" → **endpoint** | resource is `/v1/endpoints`; each item is an *inference endpoint* with a provider *type* | Matches the Console's existing "Inference plane / inference endpoint" vocabulary; drops the word "backend". |
| "chat" → **`/v1/inference`** | primary governed call; `/v1/chat/completions` kept as an OpenAI-compat alias | Brand around "inference"; keep drop-in OpenAI-SDK compatibility. |
| Auth | reuse per-team keys + a **`manage` scope**; sovereignty ops stay **owner-only** | No new key system; a management key must never be able to unseal the boundary. |
| Model catalog | **curated, in-boundary JSON** (sovereign); optional vendored LiteLLM import at build time | Discovery must not require an external call at runtime. |
| Live capabilities | best-effort **match to the catalog**; honest `"unknown"` when unmatched | Never fabricate a capability/context we don't actually know. |
| Compatibility | old paths (`/v1/backends`, `/v1/chat/completions`) stay as **aliases** | Nothing the Console or early integrators use breaks. |
| Contract | Pydantic schemas → accurate **OpenAPI** at `/docs`; one error envelope; require-auth on management | Turns Console-era endpoints into a real product API. |

## Endpoint surface (final names)
| Method · Path | Purpose | Status |
|---|---|---|
| `GET /v1/providers` · `GET /v1/providers/{type}` | supported provider types + connect-config schema | NEW |
| `GET /v1/catalog/models` | curated model catalog (mode/context/pricing/capabilities) | NEW |
| `GET /v1/models` | your live endpoints, enriched (mode/context/pricing/capabilities/health) | enrich |
| `GET/POST /v1/endpoints` · `GET/PUT/DELETE /v1/endpoints/{id}` | list/register/edit/remove an inference endpoint | rename of `/v1/backends` (+alias) |
| `POST /v1/endpoints/{id}/test` · `/approve-egress` | probe · approve host (owner) | rename (+alias) |
| `POST /v1/inference` | governed inference (OpenAI-shaped) | NEW path (+`/v1/chat/completions` alias) |
| `POST /v1/embeddings` | governed embeddings | NEW |
| `GET /v1/usage` · `GET /v1/traces` | integrator observability | exists |

## Utilization flow
```
GET  /v1/providers            → supported providers + what each needs to connect
GET  /v1/catalog/models       → pick a model; read context/cost/capabilities
POST /v1/endpoints            → register the inference endpoint (host + key + model)
POST /v1/endpoints/{id}/test  → probe; if cloud → POST …/approve-egress (owner)
GET  /v1/models               → confirm it's live + healthy, with real capabilities
POST /v1/inference            → governed inference   (model:"auto" or "<id>/<model>")
POST /v1/embeddings           → governed embeddings
GET  /v1/usage , /v1/traces   → spend + the governed journey
```

## Scope — in
- `GET /v1/providers`, `/v1/providers/{type}`, `/v1/catalog/models` (typed, in-boundary).
- `manage` scope on API keys (read-only vs read-write); auth required on all
  management routes; inference keys cannot manage; sovereignty ops owner-only.
- Rename `/v1/backends` → `/v1/endpoints` (keep aliases); enrich `GET /v1/models`.
- `POST /v1/inference` (+ `/v1/chat/completions` alias) and `POST /v1/embeddings`,
  both governed (policy → trace → audit) and OpenAI-shaped.
- Pydantic schemas + one error envelope; curated OpenAPI at `/docs` + `/openapi.json`.
- In-product **API** page (base URL, auth, examples, link to `/docs`) + `docs/api/` guide.

## Scope — out (non-goals)
Client SDKs · webhooks/events API · GraphQL · Terraform provider · per-management-key
rate limiting (→ ENH) · breaking changes to existing paths (aliases kept) ·
the Workflow builder (Phase 13).

## Deliverables & verification
| Deliverable | Verify with |
|---|---|
| Providers + catalog endpoints | `./run.sh test` (contract tests) + curl in `docs/api/` |
| `manage` scope + auth matrix | `./run.sh test` (auth-matrix test) |
| `/v1/inference` + `/v1/embeddings` governed | `./run.sh test` + live smoke (governed, in-boundary) |
| Enriched `/v1/models` | `./run.sh test` (capability-match test) |
| OpenAPI + docs + aliases | `./run.sh test` (openapi presence + alias back-compat) |

## Acceptance criteria
1. `GET /v1/providers` + `/v1/catalog/models` return the documented shapes
   (capabilities/context/pricing), fully in-boundary (no external call).
2. A `manage`-scoped key can list/register/edit/remove **endpoints**; an
   inference-only key gets 403; anonymous gets 401; sovereignty ops stay owner-only.
3. `POST /v1/inference` and `POST /v1/embeddings` are governed and OpenAI-shaped;
   `/v1/chat/completions` alias still works.
4. `GET /v1/models` shows real capabilities/context/pricing (honest "unknown"
   when unmatched).
5. `/openapi.json` + `/docs` render with the Bearer security scheme; `docs/api/`
   curl examples run green; old paths still work; full suite green via `./run.sh test`.
