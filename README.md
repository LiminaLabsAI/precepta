# preceptaai

> A **self-hosted, governed control plane** for running open-source AI models on your own
> infrastructure — with routing, governance, and tamper-evident audit built in.
> **Total control. Data never leaves. Compliance by default.**

Point any OpenAI-compatible client at preceptaai instead of a cloud API, and every request is
**routed** to an in-boundary model, **policy-checked**, **PII/injection-firewalled**, and written to a
**tamper-evident audit log** — with a **Sovereignty Attestation** your security team can independently
verify. The intelligence router is a feature; the product is the governed control plane.

---

## Why

Regulated and data-sensitive enterprises want AI, but they can't send data to third-party clouds
(DPDP / HIPAA / GDPR / SOC2 + sovereignty), have no easy way to run the cheapest capable open-source
model on their own infra, and have no enforced governance or audit an auditor accepts. preceptaai is
the control plane that gives them that — self-hosted, so **models and data stay on infrastructure they own**.

## What it does

- **OpenAI-compatible API** — one endpoint (`/v1/chat/completions`); adopt it with a one-line `base_url` change.
- **Model plane** — Ollama (local), vLLM (your GPUs), Neysa (sovereign cloud), HF dedicated endpoints — all in-boundary; pluggable via one adapter (DIP).
- **Intelligent router** — explicit, or intent (`auto:cheapest` / `auto:fastest` / `auto:best-quality`); failover + circuit breaker; reasoning techniques (best-of-N, self-consistency) with cost-gating.
- **Governance** — authN → authZ (roles + team scopes), a policy engine (block > warn > allow, most-restrictive wins), and a runtime firewall (PII redaction + injection/leak detection).
- **Sovereign Mode + Attestation** — in-boundary-only routing enforced; a **SHA-256 hash-chained, tamper-evident audit**; a signed, hash-anchored **attestation** proving zero egress.
- **The Console** — a ChatGPT-style web UI: Playground, Model plane, Policies, Audit & Attestation, Compliance report.
- **Enterprise access** — per-team **API keys** (every call attributed in the audit), an **MCP server** for agentic tools, **Google/OIDC SSO**, and a **compliance evidence report** (DPDP/SOC2/HIPAA/GDPR/ISO → controls).

## Architecture

Ports & adapters (hexagonal) — the domain core never imports a provider, store, or cloud. Everything
external is a swappable adapter. The **closed sovereign loop**:

```
request
  → authN (who)  →  authZ (what)  →  policy check  →  route in-boundary (cost/intent)
  → firewall (PII/injection)  →  inference  →  tamper-evident audit  →  response (+ metadata)
```

`app/` — control plane · `web/console.html` — the Console · `specs/` — vision, roadmap, decisions.

## Quickstart

**Prerequisites:** Python 3.14, and [Ollama](https://ollama.com) running with a model
(`ollama pull llama3.2:3b`).

```bash
git clone https://github.com/LiminaLabsAI/precepta.git
cd precepta
cp .env.example .env      # optional: for SSO / extra backends
./run.sh                  # auto-creates the venv, installs deps, serves on :8000
```

Then open **http://127.0.0.1:8000** — sign in, and use the Playground.

```bash
./run.sh test             # run the test suite (88 tests)
./run.sh reset            # clear audit / telemetry back to a clean slate
```

## Use it as an API (the other door)

Any OpenAI SDK works — change one line:

```python
from openai import OpenAI

client = OpenAI(base_url="http://127.0.0.1:8000/v1", api_key="<your-key>")
resp = client.chat.completions.create(
    model="auto:cheapest",                 # or "ollama/llama3.2:3b"
    messages=[{"role": "user", "content": "Summarize this claim..."}],
)
print(resp.choices[0].message.content)
```

Issue per-team keys in the Console (**Settings → API keys**); every call is attributed to the key in
the audit log.

## Configuration (`.env`)

`run.sh` loads `.env` if present. See `.env.example` for the full list. Highlights:

```bash
# Google / OIDC SSO (see the Console → Settings → Security for status)
OIDC_ISSUER=https://accounts.google.com
OIDC_CLIENT_ID=<your-client-id>.apps.googleusercontent.com
OIDC_CLIENT_SECRET=<your-secret>
OIDC_REDIRECT=http://127.0.0.1:8000/auth/sso/callback

# Grant admin to specific emails (everyone else defaults to 'user')
PRECEPTA_ADMIN_EMAILS=you@yourco.com

# Extra in-boundary backends
VLLM_BASE_URL=http://10.0.4.12:8000/v1
NEYSA_BASE_URL=https://your-org.neysa.ai
NEYSA_API_KEY=neysa_live_...
```

## Key endpoints

| Endpoint | Purpose |
|---|---|
| `POST /v1/chat/completions` | OpenAI-compatible governed inference |
| `GET /v1/models` · `POST /v1/backends` | List / register model backends |
| `GET /attestation` · `GET /audit/verify` | Sovereignty attestation · chain verification |
| `GET /audit/log` · `GET /audit/export.csv` | Tamper-evident audit log · CSV export |
| `GET /compliance/report` | Controls-mapped compliance evidence |
| `POST /v1/keys` | Issue per-team API keys |
| `POST /mcp` | MCP server (JSON-RPC) for agentic tools |
| `/auth/sso/*` | OIDC / Google login |
| `/console` (or `/`) | The web Console |

## Status

Phases 0–9 complete (**88 tests**; every UI surface validated against the live backend). See
`specs/status.md` and `specs/planning/roadmap.md`. Deferred: SOC2/ISO *certification* (an audit
process, not code), retention pruning (archive-and-anchor), and a hosted SaaS (self-hosted first).

## Tech

Python 3.14 · FastAPI · SQLite · Ollama/vLLM (serving) · a single self-contained Console (HTML/JS).
No cloud dependency to run.
