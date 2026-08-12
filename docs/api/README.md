# Precepta API — AI Provider Integration

Integrate any AI provider, **governed and sovereign**, over one API. Everything
you can do in the Console you can do as code: discover providers, register an
inference endpoint, and run governed inference/embeddings.

- **Base URL:** `http://127.0.0.1:8000` (your deployment's host)
- **Interactive docs:** `GET /docs` · **schema:** `GET /openapi.json`
- **Auth:** `Authorization: Bearer <api-key>` on every request.

## Two kinds of key
| Key | Scope | Can do |
|---|---|---|
| **Inference key** | `inference` | call `/v1/inference`, `/v1/embeddings` |
| **Management key (read-only)** | `manage:ro` | read providers/catalog/endpoints/usage |
| **Management key (read-write)** | `manage:rw` | the above **+** register/edit/remove endpoints |

Issue keys from the Console (**Keys & budgets** → *Management key*). A management
key can configure the platform but is **never** a platform owner — it cannot
change Sovereign Mode, the egress allowlist, or the router (those stay owner-only).

## The integration flow
```bash
BASE=http://127.0.0.1:8000
KEY=pk-...    # a management (read-write) key

# 1. Discover providers + what each needs to connect
curl -s $BASE/v1/providers -H "Authorization: Bearer $KEY"

# 2. Browse the in-boundary model catalog (capabilities / context / pricing)
curl -s "$BASE/v1/catalog/models?provider=hf&mode=chat" -H "Authorization: Bearer $KEY"

# 3. Register an inference endpoint
curl -s -X POST $BASE/v1/endpoints -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"provider":"hf-llama","base_url":"https://router.huggingface.co/v1",
       "api_key":"hf_...","model":"meta-llama/Llama-3.1-8B-Instruct","in_boundary":false}'

# 4. Probe it (and, for a cloud host, approve egress — owner only)
curl -s -X POST $BASE/v1/endpoints/hf-llama/test -H "Authorization: Bearer $KEY"

# 5. Confirm it's live + enriched (mode / context / capabilities / health)
curl -s $BASE/v1/models -H "Authorization: Bearer $KEY"

# 6. Governed inference (OpenAI-shaped). /v1/chat/completions is a compat alias.
curl -s -X POST $BASE/v1/inference -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"auto","messages":[{"role":"user","content":"hello"}]}'

# 7. Governed embeddings (in-boundary; PII-redacted, audited)
curl -s -X POST $BASE/v1/embeddings -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"model":"auto","input":["some text to embed"]}'

# 8. Observe spend + the governed journey
curl -s $BASE/v1/usage  -H "Authorization: Bearer $KEY"
curl -s $BASE/v1/traces -H "Authorization: Bearer $KEY"
```

## Errors
Every error is one shape:
```json
{ "error": { "message": "…", "type": "forbidden|invalid_request_error|not_found|unauthenticated|unavailable", "code": "…" } }
```
`401` = no/'invalid key · `403` = wrong scope (e.g. an inference key hitting a
management route, or a read-only key writing) · `404` = unknown resource.

## OpenAI compatibility
Point any OpenAI SDK at `<base>/v1` with a Precepta key. `/v1/chat/completions`
and `/v1/models` keep working unchanged; `/v1/inference` is the branded alias.

## Notes
- The model catalog is **curated and in-boundary** — no external call at runtime.
  Live-endpoint capabilities are matched to it best-effort (honest `unknown` when
  a model isn't in the catalog).
- `/v1/backends*` remain as back-compat aliases of `/v1/endpoints*`.
