# preceptaai — Decision & Discussion Log

> **Purpose:** a durable record of *how we got here* — the journey, the rationale,
> and the roads not taken — so it never depends on chat memory. The other docs
> capture the end-state (`VISION.md`, `DESIGN.md`, `IMPLEMENTATION_PLAN.md`); this
> one captures the *why* and the *why-not*.
> **Last updated:** 2026-07-20

---

## 1. Journey (how the idea evolved)

| Stage | What we thought it was | What moved it |
|---|---|---|
| Start | Get **Floci** (local AWS emulator) running locally | Done via OrbStack; realized Floci is infra, not the product |
| Idea 1 | A **model router** to reduce Hugging-Face dependency + control cost | Routing alone is a free commodity (LiteLLM/OpenRouter) |
| Idea 2 | Router **+ governance/compliance** (policy, PII, audit) | Governance is the only payable half — but still not enough |
| SIEVE gate | "Will an enterprise pay?" | **No** for a generic governed router; **maybe** for provable sovereignty |
| Reframe | **Self-hosted control plane** for open-source models on the customer's own infra | Sovereignty is the real enterprise money; router becomes a *feature* |
| FORGE | Map components → ports (DIP); decide V1 | optillm/DSPy deferred, SFD dropped, foreign providers out of the sovereign core |
| Close-loop | Make sovereignty **enforced + provable**, not asserted | Added **Sovereign Mode** + **Sovereignty Attestation** as the trunk |
| Build | Phase 0–1 implemented and validated | Real inference through the gateway on local Ollama |

## 2. Key decisions (decision → why → rejected)

- **Product = control plane, not a router.** The router is a feature. *Rejected:* selling
  "a governed OpenRouter" — free commodity, no willingness-to-pay, weekend-clonable.
- **Self-hosted first (not SaaS).** Data + models stay on the customer's infra — the #1
  enterprise driver. *Rejected:* hosted SaaS for V1 (contradicts the sovereignty pitch;
  deferred as a later option).
- **Sovereignty must be provable.** Ship **Sovereign Mode** (enforced in-boundary routing +
  egress lock + audit-on) and a **Sovereignty Attestation** an auditor can independently verify.
  *Rejected:* treating "data never leaves" as a marketing claim — a CISO won't take our word.
- **Ports & adapters (hexagonal / DIP).** Core depends on ports; providers/stores/clouds are
  swappable adapters. *Why:* adding Shakti/WORM/KMS is one adapter, never a core change.
- **Stack = Python + FastAPI + SQLite.** LiteLLM-native path; fastest to a working demo.
  *Note:* Phase 1 uses a raw httpx OpenAI-compatible adapter (LiteLLM swappable later behind the port).
- **Model plane V1 = Ollama + vLLM + Neysa + HF-endpoint.** *Rejected for V1:* Together /
  Fireworks / Replicate / **SiliconFlow (China)** — hosted foreign clouds contradict sovereignty;
  the port supports them, but they're out of the sovereign core.
- **Router brain behind `RouterBrainPort`.** Classifier is the intended default; **rules brain is
  the working V1 default** because the classifier needs a ~400 MB model download.
- **Reasoning techniques are library adapters** behind `ReasoningPort` with an injected governed
  `call_model` — so multi-call techniques (best-of-N, MoA) stay inside the sovereign loop and fully
  audited. *Rejected:* running optillm as an opaque upstream proxy (would break the loop/audit).
- **authN and authZ are separate ports.** `IdentityPort` (login = who) vs `AuthorizationPort`
  (roles/budgets = what). *Rejected:* conflating login with permissions, or treating open-guard as
  the login.
- **DSPy = a client of our API, not a component.** Deferred behind an optional `ReasoningPort`.
- **SFD = dropped.** A dev-time assistant (3★, immature), not a product component.

## 3. SIEVE conclusions — whether / what / pays

- **Crux (falsifiable):** *a DPDP-bound Indian mid-market regulated firm will run a paid pilot of a
  self-hosted, governed, open-source-model control plane — over DIY (vLLM+LiteLLM+own logging) or an
  incumbent.*
- **Will enterprises pay?** Not for the generic router (free commodity). **Maybe** for provable
  sovereignty + governance — gated by **trust** (SOC2/ISO, pen test, DPA, a design partner), not features.
- **Money model:** enterprise annual license per self-hosted deployment. **Good margin** — the
  customer pays their own inference/GPU (their keys), so we sell software, not tokens.
- **Moat (earned, not owned):** control-plane lock-in · compliance system-of-record · jurisdiction /
  compliance-content packs (DPDP/HIPAA) · Neysa/Shakti channel bundle. *No technical moat* — serving
  (vLLM) is open, governance techniques are known.
- **Next real move:** a demand test — put the vision + Console in front of 8–10 compliance owners;
  pass bar = ≥3 say "we'd run a paid pilot" with a budget line in 7 days. **Building all phases before
  a design partner is the main risk.**

## 4. FORGE conclusions — architecture

- The **closed sovereign loop** is the trunk: `authN → authZ → policy check → in-boundary route →
  firewall → inference → audit`, with **zero egress**, independently verifiable.
- Serving is **integrated, never built** (vLLM/Ollama) — stays out of Red Hat/NVIDIA's lane.
- Infra visibility is **integrated metrics** (vLLM `/metrics` + Ollama + node), not a rebuilt Grafana.
- V1 job = **one credible, provable loop a design partner can pilot** — not breadth.

## 5. Competitive landscape (research, 2026)

- **Category is real + hot:** self-hosted / sovereign AI is a growing enterprise budget.
- **Serving is commodity/owned:** vLLM/SGLang/TGI open; **Red Hat AI Factory + NVIDIA NIM** own the
  heavy full-stack (FedRAMP-High). Can't out-serve or out-certify them.
- **Gateways are crowded:** Portkey, TrueFoundry, Kong, Lunar.dev, LiteLLM — some already do
  self-hosted VPC + air-gap + SOC2 + audit.
- **The gap we target:** mid-market regulated firms in a specific jurisdiction (India/DPDP) who can't
  deploy a Red Hat AI Factory — lightweight, opinionated, bundled with Neysa/Shakti.

## 6. Locked decisions (current)

Stack Python/FastAPI/SQLite · ports & adapters · control-plane product · self-hosted first · both
doors (API + Console) · model plane Ollama/vLLM/Neysa/HF · router brain (rules V1, classifier later) ·
reasoning passthrough/self-consistency/best-of-N (optillm/DSPy later) · authN Google + authZ roles ·
Sovereign Mode + Attestation first-class · Neysa as V1 sovereign cloud (Shakti swap) · SFD dropped.

## 7. Open questions / risks

- **No design partner yet** — the demand crux is untested (SIEVE's main warning).
- **Trust wall** — no certs; a self-hosted security tool a CISO must audit.
- **Console is CDN-fonts/icons** — self-host before any real deployment (ironic for sovereignty).
- **Classifier brain** not running (needs model download) — rules brain is the V1 default.
- **Incumbent absorption** — platform owners keep adding governance; move on the wedge fast.

## 8. Build status (as of this log)

**All six V1 phases complete and validated — 53/53 unit tests, 14/14 live-smoke checks.**

- **Phase 0 ✅** scaffold + ports + DB layer + `/health`.
- **Phase 1 ✅** model plane + OpenAI-compatible gateway — real inference via local Ollama.
- **Phase 2 ✅** intelligent router — RouterBrain (rules), route modes, ReasoningPort
  (passthrough/self-consistency/best-of-N), failover + circuit breaker, cost-gating.
- **Phase 3 ✅** governance — authN (dev tokens) → authZ (roles), policy engine (most-restrictive),
  input/output firewall, wired into the pipeline, audit per check.
- **Phase 4 ✅** Sovereign Mode + tamper-evident SHA-256 chain + Sovereignty Attestation
  (`/attestation`, `/audit/verify`) — **the closed, provable loop**.
- **Phase 5 ✅** infra visibility — vLLM Prometheus parser + Ollama `/api/ps` + telemetry → `/infra`.
- **Phase 6 ✅** Precepta Console wired to the live backend — Playground does real governed
  inference; policies CRUD; live attestation. Verified in-browser.

**Enterprise access — Phases 7–9 (post-V1) ✅ complete, browser-validated — 78/78 tests:**
- **Phase 7 ✅** Per-team API keys (issue/revoke, scoped, hashed, **attributed in audit**),
  Console "API keys" tab with a drop-in "connect your app" snippet, zero-code adoption via
  `OPENAI_BASE_URL`. Verified: issued key → API call → audit actor = key name.
- **Phase 8 ✅** MCP server (`/mcp`, JSON-RPC) exposing governed `chat` + policy/audit/attestation
  tools (every MCP call re-enters the governed pipeline); SSO/OIDC mechanism (`OidcIdentity` +
  `/auth/sso/*`) — honest "not configured" status until real IdP creds. Console Security shows both.
- **Phase 9 ✅** Team-scoped authZ + budgets (open-guard-style), **compliance-evidence report**
  (DPDP/SOC2/HIPAA/GDPR/ISO → control IDs, live, in a Console modal), tamper-evident **audit
  export** (WORM-ready). Verified in browser: compliance report 6/6 controls met, signed + anchored.

**Still needing an external piece (mechanism built, flagged):** real SSO IdP credentials
(Okta/Google/Azure-AD), actual SOC2/ISO certification (an audit process, not code). Console fonts/
icons still CDN — self-host before real deployment.

**Deferred behind ports (not yet built):** real Google OAuth (dev-token stub now), classifier router brain
(rules default; needs model download), optillm/DSPy reasoning, open-guard authZ, SSO/multi-tenant,
customer KMS, WORM anchoring, Shakti/foreign adapters, certs. Console still uses CDN fonts/icons
(self-host before real deployment).
