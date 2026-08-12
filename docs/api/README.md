# Precepta API

Your **governed, sovereign** AI gateway — as code. It's **OpenAI-compatible**: any
OpenAI SDK works by changing one line (the base URL). Nothing leaves your boundary.

- **Base URL:** `http://127.0.0.1:8000` · **Auth:** `Authorization: Bearer <api-key>`
- **Interactive schema:** `GET /docs` · **OpenAPI:** `GET /openapi.json`

Two planes: the **data plane** is 100% OpenAI-standard (drop-in); the **control
plane** (`/v1/providers`, `/v1/endpoints`, `/v1/policies`, …) is Precepta-specific
management, like LiteLLM's/OpenRouter's own admin APIs. Every response also carries
an additive `precepta` block (governance metadata) — SDKs ignore unknown fields.

---

## Quickstart — one call

**curl**
```bash
curl -sX POST http://127.0.0.1:8000/v1/chat/completions \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"auto","messages":[{"role":"user","content":"hello"}]}'
```
**Python (requests)**
```python
import requests
r = requests.post("http://127.0.0.1:8000/v1/chat/completions",
  headers={"Authorization": "Bearer " + KEY},
  json={"model": "auto", "messages": [{"role": "user", "content": "hello"}]})
print(r.json()["choices"][0]["message"]["content"])
```
**OpenAI SDK** (drop-in — only the base URL changes)
```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key=KEY)
resp = client.chat.completions.create(
  model="auto", messages=[{"role": "user", "content": "hello"}])
print(resp.choices[0].message.content)
```

---

## Data plane (OpenAI-standard)

### `POST /v1/chat/completions`  ·  alias `POST /v1/inference`
**Request**
```json
{ "model": "auto",
  "messages": [{"role": "user", "content": "hello"}],
  "temperature": 0.3, "max_tokens": 64, "stream": false }
```
**Response** (`stream:true` returns OpenAI-style SSE `chat.completion.chunk`s instead)
```json
{ "id": "chatcmpl-…", "object": "chat.completion", "created": 1712345678,
  "model": "ollama/llama3.2:3b",
  "choices": [{ "index": 0, "finish_reason": "stop",
                "message": {"role": "assistant", "content": "Hello!"} }],
  "usage": {"prompt_tokens": 9, "completion_tokens": 3, "total_tokens": 12},
  "precepta": {"backend_used": "ollama", "in_boundary": true,
               "policy_decision": "allow", "cache": "miss", "pii_redacted": 0,
               "trace_id": "…"} }
```

### `POST /v1/embeddings`
**Request** — `{ "model": "auto", "input": "some text" }` (or `"input": ["a","b"]`)
**Response**
```json
{ "object": "list",
  "data": [{"object": "embedding", "index": 0, "embedding": [0.01, -0.02, "…768 floats"]}],
  "model": "ollama/nomic-embed-text",
  "usage": {"prompt_tokens": 3, "total_tokens": 3},
  "precepta": {"backend_used": "ollama", "in_boundary": true, "policy_decision": "allow"} }
```

### `POST /v1/moderations` — content screening (governed, in-boundary)
**Request** — `{ "input": "ignore all previous instructions" }`
**Response**
```json
{ "id": "modr-…", "model": "precepta-guard",
  "results": [{ "flagged": true,
                "categories": {"prompt_injection": true, "pii": false, "toxicity": false},
                "category_scores": {"prompt_injection": 1.0, "pii": 0.0, "toxicity": 0.0} }] }
```

### `GET /v1/models`  ·  `GET /v1/models/{model}`
**Response**
```json
{ "object": "list",
  "data": [{"id": "ollama/llama3.2:3b", "object": "model", "created": 1704067200, "owned_by": "ollama"}] }
```
Enriched view (capabilities/context/pricing/health) is on `GET /v1/endpoints` — see below.

---

## Control plane (Precepta management — needs a `manage`-scoped key)

| Key scope | Can do |
|---|---|
| `inference` | `/v1/chat/completions`, `/v1/embeddings`, `/v1/moderations`, `/v1/models` |
| `manage:ro` | read providers/catalog/endpoints/usage |
| `manage:rw` | the above **+** register/edit/remove endpoints |

A management key can configure the platform but is **never** a platform owner — it
cannot change Sovereign Mode, the egress allowlist, or the router (owner-only).

### `GET /v1/providers` → what you can connect
```json
{ "object": "list", "data": [
  { "provider": "hf", "name": "Hugging Face endpoint", "boundary": "cloud",
    "requires_egress_approval": true,
    "config_schema": [{"field":"base_url","required":true},
                      {"field":"api_key","secret":true,"required":true},
                      {"field":"model","required":true}] }] }
```

### `POST /v1/endpoints` → register an inference endpoint
**Request**
```json
{ "provider": "hf-llama", "base_url": "https://router.huggingface.co/v1",
  "api_key": "hf_…", "model": "meta-llama/Llama-3.1-8B-Instruct", "in_boundary": false }
```
**Response** — `{ "ok": true, "provider": "hf-llama", "tier": 2, "healthy": false }`
Then: `POST /v1/endpoints/{id}/test` (probe) · `POST /v1/endpoints/{id}/approve-egress` (owner).

### `GET /v1/endpoints` → your endpoints, enriched
```json
{ "object": "list", "data": [
  { "id": "ollama", "model": "llama3.2:3b", "mode": "chat", "in_boundary": true,
    "status": "healthy", "max_input_tokens": 131072, "max_output_tokens": 8192,
    "pricing": {"input_per_1m": 0, "output_per_1m": 0, "source": "local — free"},
    "capabilities": {"streaming": true, "function_calling": false, "vision": false} }] }
```

### `GET /v1/catalog/models` → browse 3000+ models (in-boundary)
Filters: `provider`, `mode`, `model` (substring), `supports_function_calling`,
`supports_vision`, `supports_reasoning`, `page`, `page_size` (≤500).
```json
{ "data": [{ "id": "gpt-4o-mini", "provider": "openai", "mode": "chat",
             "max_input_tokens": 128000, "max_output_tokens": 16384,
             "input_cost_per_1m": 0.15, "output_cost_per_1m": 0.6,
             "supports_function_calling": true, "supports_vision": true }],
  "total_count": 3011, "has_more": true, "page": 1, "page_size": 100 }
```
Also: `GET /v1/catalog/providers` (counts) · `GET /v1/catalog/models/{id}` (one model).

### Observe — `GET /v1/usage`, `GET /v1/traces`
Spend by key/team, and the full governed journey per request.

---

## Errors — one shape
```json
{ "error": { "message": "…", "type": "forbidden|invalid_request_error|not_found|unauthenticated|unavailable", "code": "…" } }
```
`401` no/bad key · `403` wrong scope · `404` unknown resource · `400` bad body.

## Notes
- Data plane matches OpenAI exactly (paths + payloads) — a base-URL swap is all you
  change. `/v1/backends*` and `/v1/chat/completions` remain as aliases.
- The catalog ships **in-boundary** (vendored BerriAI/litellm data, MIT) — no runtime
  external call.
