# Precepta API

Your **governed, sovereign** AI gateway — as code. It's **OpenAI-compatible**, so
any OpenAI SDK works by changing one line: the base URL. Nothing leaves your
boundary.

- **Base URL:** `http://127.0.0.1:8000` (your deployment's host)
- **Auth:** `Authorization: Bearer <api-key>` on every request
- **Interactive schema:** `GET /docs` · **OpenAPI:** `GET /openapi.json`

---

## Quickstart — one call

Get a key from the Console (**Keys & budgets**), then:

**curl**
```bash
curl -sX POST http://127.0.0.1:8000/v1/inference \
  -H "Authorization: Bearer $KEY" -H "Content-Type: application/json" \
  -d '{"model":"auto","messages":[{"role":"user","content":"hello"}]}'
```

**Python (requests)**
```python
import requests
r = requests.post("http://127.0.0.1:8000/v1/inference",
  headers={"Authorization": "Bearer " + KEY},
  json={"model": "auto", "messages": [{"role": "user", "content": "hello"}]})
print(r.json()["choices"][0]["message"]["content"])
```

**OpenAI SDK** (drop-in — point it at Precepta)
```python
from openai import OpenAI
client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key=KEY)
resp = client.chat.completions.create(
  model="auto", messages=[{"role": "user", "content": "hello"}])
print(resp.choices[0].message.content)
```

`model:"auto"` lets the Smart router pick a healthy in-boundary model; or name one
(`"ollama/llama3.2:3b"`). `/v1/chat/completions` is a drop-in alias of
`/v1/inference`, so existing OpenAI code needs **no change** beyond the base URL.

---

## Keys & scopes
| Key | Scope | Can do |
|---|---|---|
| **Inference** | `inference` | `/v1/inference`, `/v1/embeddings` |
| **Management (read-only)** | `manage:ro` | read providers/catalog/endpoints/usage |
| **Management (read-write)** | `manage:rw` | the above **+** register/edit/remove endpoints |

A management key configures the platform but is **never** a platform owner — it
cannot change Sovereign Mode, the egress allowlist, or the router (owner-only).

---

## Add a provider (management key)
```bash
# 1. what can I connect, and what does it need?
curl -s http://127.0.0.1:8000/v1/providers -H "Authorization: Bearer $KEY"
# 2. register an inference endpoint
curl -sX POST http://127.0.0.1:8000/v1/endpoints -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" \
  -d '{"provider":"hf-llama","base_url":"https://router.huggingface.co/v1",
       "api_key":"hf_...","model":"meta-llama/Llama-3.1-8B-Instruct","in_boundary":false}'
# 3. probe it (cloud host → approve egress in Settings → Egress, owner-only)
curl -sX POST http://127.0.0.1:8000/v1/endpoints/hf-llama/test -H "Authorization: Bearer $KEY"
# 4. confirm it's live + enriched (mode / context / capabilities / health)
curl -s http://127.0.0.1:8000/v1/models -H "Authorization: Bearer $KEY"
```

## Embeddings
```bash
curl -sX POST http://127.0.0.1:8000/v1/embeddings -H "Authorization: Bearer $KEY" \
  -H "Content-Type: application/json" -d '{"model":"auto","input":["embed me"]}'
```

## Model catalog (browse 3000+ models, in-boundary)
```bash
curl -s "http://127.0.0.1:8000/v1/catalog/models?provider=openai&mode=chat&supports_vision=true&page_size=50" -H "Authorization: Bearer $KEY"
curl -s http://127.0.0.1:8000/v1/catalog/providers   -H "Authorization: Bearer $KEY"
curl -s http://127.0.0.1:8000/v1/catalog/models/gpt-4o-mini -H "Authorization: Bearer $KEY"
```
Filters: `provider`, `mode`, `model` (substring), `supports_function_calling`,
`supports_vision`, `supports_reasoning`, `page`, `page_size` (≤500). Response:
`{ data, total_count, has_more, page, page_size }`.

## Observe
```bash
curl -s http://127.0.0.1:8000/v1/usage  -H "Authorization: Bearer $KEY"   # spend by key/team
curl -s http://127.0.0.1:8000/v1/traces -H "Authorization: Bearer $KEY"   # the governed journey
```

---

## Errors
One shape everywhere:
```json
{ "error": { "message": "…", "type": "forbidden|invalid_request_error|not_found|unauthenticated|unavailable", "code": "…" } }
```
`401` no/bad key · `403` wrong scope · `404` unknown resource.

## Explore next
Keys & scopes → **Policies** (governance rules) → **Traces** (per-request journey)
→ **Settings → Egress** (reach approved cloud hosts while everything else stays
sealed). Full reference: **`/docs`**.

## Notes
- The model catalog ships **in-boundary**: a vendored snapshot of BerriAI/litellm's
  `model_prices_and_context_window.json` (MIT reference data) merged with Precepta's
  curated entries — **no external call at runtime**.
- `/v1/backends*` remain back-compat aliases of `/v1/endpoints*`; `/v1/chat/completions`
  of `/v1/inference`.
