# preceptaai — Design Spec (closed-loop trunk, v2)

> **Status:** Draft v2 — ports & adapters around a *provable* sovereign loop (pre-implementation).
> **Serves the crux:** a regulated buyer will pilot a self-hosted governed control plane **only if
> the sovereign loop is enforced and independently verifiable** — not merely present.
> **Companion:** `VISION.md`, `IMPLEMENTATION_PLAN.md`. **Last updated:** 2026-07-20

---

## 1. The trunk — the closed sovereign loop

Everything in V1 exists to make this one path complete, enforced, and provable:

```
request (in-boundary)
  → auth + policy check            [local — no external call]
  → route to a model INSIDE the boundary        ← the load-bearing link
       (vLLM on their GPU · Ollama · Neysa in-region)
  → firewall scrub (local)
  → inference (in-boundary)
  → response
  → tamper-evident audit + telemetry (local)
```

**The invariant (what "closed" means):**
> A real AI request is served, governed, and audited **entirely inside the customer's boundary,
> with zero egress**, and their own security team can **independently verify it** and walk away
> with a signed **Sovereignty Attestation**.

If a design decision doesn't serve this invariant, it is not V1.

## 2. Architecture — ports & adapters (hexagonal / DIP)

The **domain core** (router + governance + audit) never imports a concrete provider, store, or
cloud. It depends only on **ports** (interfaces). Everything external is a swappable **adapter**.

```
        ┌──────────────── CONTROL PLANE (domain core) ────────────────┐
  API   │  Router → Governance pipeline → Audit → Telemetry            │
  Chat  │  (policy check → route/failover → firewall → call → audit)   │
  Admin │  + Sovereign Mode enforcement + Attestation                  │
        └─┬──────────┬──────────────┬────────────┬───────────┬────────┘
          │Model      │Policy        │Audit        │Secret      │Infra
          │Backend    │Store         │Sink         │Store       │Visibility
          │Port       │Port          │Port         │Port        │Port      (+ Reasoning, Identity)
   ┌──────┴─────┐ ┌───┴────┐   ┌─────┴─────┐  ┌─────┴───┐  ┌────┴──────────────┐
   │ Ollama     │ │ SQLite │   │ hash-chain│  │ Floci   │  │ vLLM /metrics +   │
   │ vLLM       │ │        │   │ (SQLite;  │  │ vault;  │  │ Ollama + node     │
   │ Neysa      │ │        │   │  WORM     │  │ KMS/    │  │ → telemetry table │
   │ (Shakti,HF,│ │        │   │  later)   │  │ Vault   │  │                   │
   │  foreign = │ └────────┘   └───────────┘  │  later) │  └───────────────────┘
   │  later)    │                             └─────────┘
   └────────────┘
```

### Ports and their V1 adapters

| Port | Contract (essence) | V1 adapters | Deferred adapters |
|---|---|---|---|
| **ModelBackendPort** | `litellm_model()`, `price()`, `health()`, `in_boundary: bool` | Ollama, vLLM, **Neysa**, **HF dedicated endpoint** | Shakti, Together/Fireworks/Replicate/SiliconFlow |
| **PolicyStorePort** | CRUD + `enabled_for(action_type)` | SQLite (`governance_policies`) | — |
| **AuditSinkPort** | `append(event)`, `verify_chain()` | SQLite hash-chain (`tamper_evident_audit_log`) | WORM / external anchoring |
| **SecretStorePort** | `get(ref)`, `put(name)` | Floci vault / OS keyring | customer KMS/Vault |
| **InfraVisibilityPort** | `snapshot()` → GPU/VRAM/throughput/latency/cost | vLLM `/metrics` + Ollama + node | full APM |
| **IdentityPort** *(authN — who)* | `authenticate()` → verified principal | Google (local tier) | SSO / SAML / OIDC + SCIM |
| **AuthorizationPort** *(authZ — what)* | `can(principal, action, resource)`, `budget(principal)` | simple role check (admin/user/auditor) | **open-guard** (RBAC/ABAC/ReBAC + agent budgets & identity chains) |
| **ReasoningPort** | `run(messages, ctx, call_model)` — technique gets an **injected governed model call** | passthrough (default), self-consistency, best-of-N | **optillm** techniques (MoA/CoT/…), DSPy |
| **RouterBrainPort** | `decide(query, intent, ctx, budget)` → `RoutePlan` | **classifier** (pre-trained optillm-modernbert, self-hosted) | `rules`, `llm` (Qwen2.5-local), fine-tuned classifier |

**DIP payoff:** adding Shakti, swapping the audit store for WORM, or plugging in customer KMS
**never touches the domain core** — you write one adapter.

### Identity & access — two distinct steps (authN → authZ)
- **Authentication (`IdentityPort`)** — *proves who* the caller is. **This is the login.**
  V1: Google (local tier); later SSO / SAML / OIDC.
- **Authorization (`AuthorizationPort`)** — *decides what* that principal may do: roles
  (admin / user / auditor), per-agent budgets, delegation. V1: a simple role check; later
  **open-guard** as the adapter.

```
login (Google/SSO) → principal (who)  →  authZ can(principal, action, resource)?  →  pipeline
```

authZ is **not** governance: it gates *actors → actions* (may this user/agent do this?);
governance (§6) gates *actions → PII / limits / audit* (is this action itself allowed?). Both run,
different axes. `open-guard` is an **adapter behind `AuthorizationPort`**, never the login and never
a replacement for governance.

**Explicitly not a component:** SFD (a dev-time assistant) — dropped from the product.

## 3. Sovereign Mode (the primitive that closes the loop)

A first-class, on-by-default switch for enterprise deployments. When ON it **enforces**, not requests:

1. **In-boundary-only routing** — `ModelBackendPort` yields only adapters with `in_boundary = true`.
   Any route to a non-boundary backend is **blocked by policy** (not by convention).
2. **Egress lock** — deployment runs deny-all egress except allowlisted in-boundary model
   endpoints (enforced at the network/deploy layer; air-gapped is the strongest form).
3. **Audit-on** — auditing cannot be disabled while Sovereign Mode is on.
4. **Residency policy** — a built-in policy asserts data-classification/residency rules for the jurisdiction.

## 4. Sovereignty Attestation (the proof artifact)

A one-page, exportable proof the customer's security team can **independently verify**:
- **Config proof** — the active backend set (all `in_boundary`), Sovereign Mode = ON, egress policy.
- **Audit proof** — over a window: count of requests served, and **zero external calls** in the
  tamper-evident log (chain verified).
- **Egress-test result** — outcome of an egress probe (expected: blocked/none), verifiable with
  the customer's own network monitoring.
- Signed + hash-anchored to the audit chain.

**This artifact is the sale.** Closing the loop = being able to generate it for a real workload.

## 5. Gateway contract (Contract 1 — how clients call)

`POST /v1/chat/completions` — OpenAI-compatible (any OpenAI SDK is a client, incl. a DSPy program).
Routing is expressed via the `model` string:

| `model` value | Meaning |
|---|---|
| `vllm/<model>` `ollama/<model>` `neysa/<model>` `hf/<model>` | **Explicit** in-boundary backend |
| `auto:cheapest` · `auto:fastest` · `auto:best-quality` | **Intent** routing (in-boundary candidates only under Sovereign Mode) |

Response = OpenAI standard **+ a `precepta` block**: `backend_used`, `in_boundary`, `route_mode`,
`cost_usd`, `latency_ms`, `policy_decision`, `audit_id`. A policy block → HTTP 403 with the same
block, no backend call.

## 6. Governance pipeline (Contract 3 — the one place router meets governance)

```
request
  → authN (IdentityPort): resolve principal (who)          # reject 401 if unauthenticated
  → authZ (AuthorizationPort): can(principal, action, resource)?   # reject 403 if not permitted
  → build PolicyCheckContext(principal, action_type, url?, tokens, data_tag, backend, in_boundary)
  → [Sovereign Mode] assert backend.in_boundary       # else Block: "out-of-boundary route"
  → [PRE] evaluate_policies()  → most-restrictive wins (block > warn > allow)
        Block → audit row, return 403 (no inference)
  → [PRE] firewall Stage 1     # redact PII in input; detect injection → may block
  → route + failover           # resolve model string → in-boundary backend list → circuit breaker
  → inference (ModelBackendPort)
  → [POST] firewall Stage 3    # scan output for secret/key/db-url leak → may block
  → [POST] audit row + extend SHA-256 hash chain
  → capture cost + latency (InfraVisibilityPort / telemetry)
  → response (+ precepta block)
```

Evaluation and audit-chain math unchanged from the governance spec (most-restrictive; enabled
policies where `action_type = ctx OR '*'`, `created_at ASC`; `event_hash = SHA256(fields +
previous_hash)`, genesis = 64 zeros).

## 7. The intelligent router & ReasoningPort (two-axis, governed)

The router (Layer 2) is "intelligent" because it decides on **two axes at once**:
- **Backend** (`ModelBackendPort`) — *where* to run → cost / latency.
- **Technique** (`ReasoningPort`) — *how* to reason → quality.

An intent (`auto:cheapest | fastest | best-quality | auto`) is satisfied by choosing the right
**(model tier × technique)** pair — within the caller's cost/token budget and policy.

### Decision flow
```
query + intent + policy budget
  → Classifier (in-boundary) → difficulty / type
  → Decide  (model tier via ModelBackendPort)  ×  (technique via ReasoningPort)
  → Cost-gate: estimated calls × price  vs  governance token/cost caps   ← the differentiator
        over budget → downgrade to a cheaper technique, or Block
  → Execute through the governance pipeline (§6); each inner call re-enters the pipeline
```

### ReasoningPort contract — the injected `call_model` (the load-bearing detail)
```python
class ReasoningPort(Protocol):
    name: str
    def estimate_calls(self, ctx) -> int          # Best-of-N=3, MoA=k … → used for cost-gating
    def run(self, messages, ctx, call_model) -> Response: ...
    #                              └── injected callback that routes EACH inner model call
    #                                  back through governance + ModelBackendPort
    #                                  → in-boundary, policy-checked, audited.
```
Because every inner call re-enters the governed pipeline, **the sovereign loop stays closed and
the audit stays complete** even for multi-call techniques. This is why techniques are a *library*
behind our port, never an opaque upstream proxy.

### Adapters (behind ReasoningPort)
- **passthrough** (default) — one governed call.
- **self-consistency, best-of-N** — in-boundary, cheap, high-ROI → the **V1-lite** intelligent router.
- **OptillmAdapter** (library mode) — wraps optillm's Apache-2.0 algorithms (MoA, CoT-reflection,
  AutoThink…), patched to use the injected `call_model`. Fast-follow.
- **DSPy** — later.

### The router brain — a swappable adapter (`RouterBrainPort`)
The decision-maker is **itself behind a port**, so it evolves without rework (same DIP as backends):

| Adapter | What it is | Cost / behaviour | Use |
|---|---|---|---|
| **classifier** (default) | pre-trained `optillm-modernbert-large`, **self-hosted** | one forward pass, ~ms, deterministic, in-boundary, **no training data needed** | **V1 default** |
| **rules** | deterministic `decide()` over cheap signals (tokens, task type, difficulty) | free, fully **explainable** | fallback / overrides |
| **llm** | Qwen2.5 on local Ollama (or other) | free & in-boundary, but **generates** → slower, non-deterministic | hard / novel escalation |

`RouterBrainPort.decide(query, intent, ctx, budget) -> RoutePlan`. Runs only under `auto`/intent;
an explicit `model` string or `extra_body` technique **overrides** the brain entirely. All adapters
run **in-boundary** — the brain never calls out.

**Backend tier is config, not intelligence:** dev → Ollama/Qwen2.5 (free), prod → HF/Neysa — a
setting, not a model decision.

**Evaluator-first:** the pre-trained classifier gets you *started*; **lock an evaluator** (fixed
eval set + a scalar like quality-per-cost) before trusting or tuning it on real workloads.

### optillm usage rules (DIP)
- optillm is an **adapter behind `ReasoningPort`**, never a port and never the owner of routing.
- **Sovereign core:** library mode only (injected `call_model`); classifier self-hosted; external
  plugins (`web_search`, `readurls`, `executecode`, `mcp`) **disabled** (egress).
- **Dev / non-sovereign tier:** may run optillm as a sidecar OpenAI-compatible proxy adapter.
- We own Layer-2 routing; optillm's own `proxy`/`router` plugins are not adopted as the owner.

### Cost-gating (why ours beats a raw optimizer)
Techniques multiply calls 3–5×. optillm applies them blind to cost. Ours **gates technique choice
on governance token/cost caps** → better answers *within* budget, not an unbounded token blowup.
This fusion — intelligent routing + governance + cost control — is the on-thesis differentiator.

## 7c. Enterprise access (Phases 7–9) — identity, keys, MCP, tenancy

All new mechanisms live behind existing ports (DIP) — the domain core is unchanged.

**Phase 7 — per-team API keys (IdentityPort adapter).**
- `api_keys` table: `id, key_hash (sha256), name, role, team, created_at, revoked_at`.
- `ApiKeyIdentity` implements `IdentityPort.authenticate(token)` → hash lookup → `Principal(subject=name, role)`; `_resolve_principal` tries dev tokens → API key → anonymous.
- `Principal` gains `team` for attribution/scoping; the audit actor becomes the key's name (e.g. `svc-underwriting`).
- Endpoints: `POST/GET/DELETE /v1/keys` (admin). Console "Keys" settings tab + "connect your app" snippet (base_url + key).
- **Zero-code adoption:** the OpenAI-compatible endpoint already honours `OPENAI_BASE_URL`; documented + snippet-generated.

**Phase 8 — MCP server + SSO.**
- **MCP:** a JSON-RPC MCP surface (`/mcp`) exposing tools — `chat` (governed inference), `list_policies`, `get_attestation`, `verify_audit`. Each tool call runs the same governed pipeline + audit, so MCP stays inside the sovereign loop. Auth via the same bearer/API key.
- **SSO:** `OidcIdentity` behind `IdentityPort` — an OIDC login flow for the Console; provider config (`issuer`, `client_id/secret`, `redirect`) is env-driven. Real IdP creds are an owner action; a dev/test path exercises the flow.

**Phase 9 — hardening & tenancy.**
- `AuthorizationPort` upgraded to a scope/budget model (open-guard-style): `can(principal, action, resource)` consults role **and** team scope; per-team token/cost budgets.
- **Compliance evidence:** attestation/audit export mapped to control IDs (DPDP/HIPAA/SOC2) — a `ComplianceReport` builder + endpoint + Console export.
- **Audit export + anchor:** signed JSON export of the chain + an external-anchor hook (WORM-ready).
- **Multi-tenancy:** an `org/team` dimension on keys, policies, and audit; the Console shows the active org/team.

## 8. Infra visibility (the "total control, one pane")

Integrate, don't build. `InfraVisibilityPort.snapshot()` pulls **vLLM Prometheus `/metrics`**
(GPU/VRAM, throughput, latency) + Ollama + node metrics into the existing `telemetry` table;
the **admin console** renders: loaded models, hardware, GPU/VRAM %, req/s, p50 latency, $ cost,
health. No Grafana rebuild.

## 9. Module layout (Python / FastAPI)

```
app/
  main.py                 # FastAPI: /v1/chat/completions, /health, /attestation, auth
  gateway/pipeline.py     # Contract-6 middleware + Sovereign Mode enforcement
  router/                 # model-string resolve; cheapest/fastest/intent; failover; RoutePlan
  ports/                  # Protocols: ModelBackend, RouterBrain, Reasoning, PolicyStore, AuditSink, Secret, InfraVis, Identity, Authorization
  adapters/
    model/                # ollama.py, vllm.py, neysa.py, hf_endpoint.py  (shakti/foreign = later)
    brain/                # classifier.py (optillm-modernbert, self-hosted), rules.py, llm.py (qwen2.5-local)
    reasoning/            # passthrough.py, self_consistency.py, best_of_n.py, optillm_adapter.py (dspy = later)
    identity/             # authN — google.py (v1); sso/oidc = later
    authz/                # authZ — role_check.py (v1); open_guard.py = later
    audit/ policy/ secret/ infra/
  governance/             # policy eval; firewall stages; audit + hash chain; technique cost-gating
  sovereign/              # mode enforcement + attestation builder
  db.py settings.py
web/                      # Precepta Console — login · onboarding · Overview · Model plane · Policies · Audit & Attestation · Playground · Settings (members & roles)
deploy/                   # docker-compose (egress-locked profile); Helm later
```

## 10. What this de-risks + reversibility
- **New backend / store / cloud / technique = one adapter**, never a core change (DIP). Two-way door.
- **Sovereign Mode + attestation** make the pitch *verifiable*, not asserted — the crux.
- **Reasoning techniques are library adapters** behind `ReasoningPort` with an injected governed
  `call_model` → adding optillm/DSPy never breaks the sovereign loop or the audit.
- **Neysa-vs-Shakti, optillm-vs-DIY-techniques, DSPy-later, WORM-later** are adapter/config choices = reversible.
- **Integrating vLLM, metrics & optillm algorithms** (not building them) keeps us out of the giants' lane.
