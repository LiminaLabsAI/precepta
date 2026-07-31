# preceptaai — Implementation Plan & Roadmap (V1: closed sovereign loop)

> **Status:** Draft v4 — V1 (Phases 0–9) shipped; **Phase 10** added below (cost / quality / governance
> controls), scoped in `BRAINSTORM.md` and aligned to the refreshed **Precepta Console** design
> (re-imported from Claude Design 2026-07-30 → `design/Precepta Console.dc.html`).
> **Companions:** `VISION.md` (why/wedge/moat), `DESIGN.md` (architecture/ports/contracts),
> `BRAINSTORM.md` (Phase 10 scoping), `preceptaai-plan.md` (combined plain-English overview).
> **Last updated:** 2026-07-30

---

## North star (the V1 success threshold)

> **V1 succeeds when a real regulated workload runs end-to-end on the customer's own infra —
> routed, governed, audited, zero egress — and produces a Sovereignty Attestation their security
> team can independently verify. Plus one design partner willing to pilot it.**

The **Precepta Console** is the operator surface for exactly this loop: onboard infra → set
in-boundary backends → policies/security controls → run a request (Playground) → prove it (Audit &
Attestation).

## Locked decisions

- **Stack:** Python + FastAPI + SQLite (existing `preceptaai.db`); Console = web frontend.
- **Architecture:** ports & adapters (hexagonal / DIP) — core depends on ports, never on providers.
- **The product:** a self-hosted **control plane**; the router is a *feature*, not the product.
- **Model plane (V1 in-boundary):** Ollama, vLLM, **Neysa**, HF dedicated endpoint. (Shakti/foreign = later.)
- **Intelligent router:** `RouterBrainPort` (classifier default) + route modes (manual/cheapest/automatic) + failover.
- **ReasoningPort:** passthrough + self-consistency + best-of-N, each inner call re-enters the governed pipeline (injected `call_model`). optillm adapter = fast-follow; DSPy = later.
- **Identity & access:** authN (`IdentityPort` = Google, V1) **→** authZ (`AuthorizationPort` = role check admin/user/auditor, V1; open-guard later).
- **Sovereign Mode + Attestation:** first-class V1 deliverables (the 4 security controls + the proof artifact).
- **Interfaces:** OpenAI-compatible **API (primary)** + **Precepta Console** (chat Playground + admin).
- **Distribution:** self-hosted (docker-compose V1; Helm later); keys/audit stay in-boundary.
- **Deferred behind ports:** optillm/DSPy reasoning, open-guard authZ, SSO/SAML + multi-tenancy, customer KMS, WORM audit, Shakti/foreign adapters, certs.
- **Dropped:** SFD (a dev-time tool, not a product component).

## Phase-wise build (V1 trunk)

| Phase | What we do | What you get (visible outcome) | Effort |
|---|---|---|---|
| **0 · Scaffold + ports** | FastAPI, DB over `preceptaai.db`, define the **ports** (Protocols), docker-compose run story | App boots one-command; `/health` OK; ports defined | S |
| **1 · Model plane + gateway** | `ModelBackendPort` + **Ollama · vLLM · Neysa · HF-endpoint** adapters, key vault, `/v1/chat/completions`, explicit routing | POST a prompt → completion from a model **on your own infra** | M |
| **2 · Intelligent router** | `RouterBrainPort` (classifier) + route modes (cheapest/automatic) + failover; **`ReasoningPort`** (passthrough, self-consistency, best-of-N) with injected governed `call_model`; **cost-gating** | "automatic" picks tier×technique **within budget**; fails over | M |
| **3 · Governance + identity/access** | authN (Google) → authZ (roles admin/user/auditor); policy CRUD + evaluate (most-restrictive); firewall S1 + S3; **wire into gateway**; audit row per check | Login proves *who*; role gates *what*; a block-policy stops a request + logs why | M |
| **4 · Close the loop: Sovereign Mode + Attestation** | SHA-256 audit chain + verify; **Sovereign Mode** = 4 controls (in-boundary routing · egress lock · audit-on · residency); **Sovereignty Attestation** + egress probe | **The attestation**: a real request served in-boundary, zero egress, verifiable | M |
| **5 · Infra visibility** | Integrate vLLM `/metrics` + Ollama + node → `telemetry` → Console | One pane: backends, GPU/VRAM, req/s, p50, cost, health | M |
| **6 · Precepta Console (UI)** | Implement the imported design: login · onboarding · Overview · Model plane · Policies · Audit & Attestation · Playground · Settings (members & roles) | The full operator product, end to end | M–L |
| **L · Later** | optillm/DSPy reasoning, open-guard authZ, SSO/SAML + multi-tenant, KMS, WORM, Shakti/foreign, red-teaming, compliance-advisor, certs | Additive — behind existing ports, no rearchitecting | — |

**The loop closes at Phase 4** (built on 1–3). That's the milestone that turns the pitch from claim to proof.

## Enterprise access — Phases 7–9 (post-V1)

Enterprises consume through **layers** (govern/build/run/use); the API is the backbone and
other doors sit on top, unified by per-team identity + governance (see VISION §7b).

| Phase | Name | What ships | Browser-validated surface |
|---|---|---|---|
| **7** | **Enterprise access** | Per-team/per-system **API keys** (issue/revoke, scoped, hashed, **attributed in audit**); **Console key management**; **zero-code adoption** (`OPENAI_BASE_URL` override + "connect your app" snippet) | Settings → Keys: issue → use → see actor in Audit |
| **8** | **Reach & identity** | **MCP server** (governed inference + policy/audit/attestation as MCP tools); **SSO/OIDC** mechanism for the Console (works with real IdP config; dev-testable path) | Console SSO toggle; MCP validated via test client |
| **9** | **Hardening & tenancy** | Richer **RBAC/ABAC authZ** (open-guard-style, per-team scopes/budgets); **compliance-evidence export** (audit/attestation mapped to DPDP/HIPAA/SOC2 controls); **audit export + external anchor**; **org/team multi-tenancy** | Compliance export button; org/team in Settings; per-team key scoping |

**Sequencing rationale:** keys/attribution/zero-code (7) unblock every other door; MCP+SSO (8)
extend reach; hardening (9) makes it enterprise-grade. Real SSO needs the customer's IdP creds
and real certs are an audit process — both are built as working mechanisms with the external
piece flagged.

## Phase 10 — Cost / quality / governance controls (next; scoped in `BRAINSTORM.md`)

> Phase 10 turns the control plane from "governs correctly" into "governs, saves cost, and gets
> smarter" — driven by the target buyer's non-expert users on metered backends. **Governing stance
> (from the brainstorm): safe by default, extra risk only by explicit opt-in, and nothing hidden
> from the person using it.** Every item lands behind an existing port (no core rewrite) and is
> **backend-real** (no demo values). The refreshed **Precepta Console** is the UI surface for all of it,
> implemented **surface-by-surface as each backing feature lands** (browser-validated, no mock data).

### 10a · Foundations first (the features lean on these — build before them)
| Step | Backlog | What / why |
|---|---|---|
| **Pricing artifact** | TD-001 | One versioned, admin-maintained price list (`model_prices` + `PricingPort`). Every $ figure depends on it; also fixes the live Console-backend `$0` bug. |
| **Counting rules** | TD-002 | One metering definition (billable vs saved vs usage tokens) so budgets/cache/compression agree. |
| **Quality test / eval harness** | FEAT-006 | Fixed set + per-use scorers (routing/compression/cache/learning), versioned (Rule 11). Gates the risky features. |
| **Sensitivity quality** | TD-004 | Reliable "is this sensitive?" (beyond regex) — four governance behaviours rest on it. |

### 10b · The features (each behind its port; UI wired as it lands)
| Step | Backlog | What ships | Console surface |
|---|---|---|---|
| **Budgets + key expiry** | FEAT-001 | Key lifetimes; token+cost budgets per key & team, daily+monthly, timezone; 80% notify / 100% block; usage view; notifications | Keys (expiry/suspend/extend) · **Usage** · bell feed |
| **Policy scope** | FEAT-002 | Optional "applies to" — team/role/subject-type/backend/model; agents like humans | Policies → "Applies to" (all vs selected) |
| **Cache** | FEAT-003 | Exact-match by default; semantic opt-in; governed-loop; admin-only savings | **Savings** (cache) · policy toggles |
| **Compression** | FEAT-005 | Long-prompt/doc compression; never surprises the user; opt-in "cost-saving mode"; consent-gated corpus | **Savings** (compression) · settings |
| **Advanced routing** | FEAT-007 | Governance filter → LLM intent-router → budget modifier; sensitive→approved-only (block + notify caller & admin); model-approval shows hosting location | Model plane · approval flow · audit "why" |
| **Traces → learning** | FEAT-008 | Capture traces + reward (explicit + implicit) → smarter routing; per-customer, in-boundary, consent | Playground thumbs/feedback · (learning offline) |
| **Console refresh** | (design) | Implement the re-imported `Precepta Console.dc.html` — refresh existing surfaces + add the new ones above | The whole operator UI, updated |
| **OpenGuard authZ** | FEAT-004 | Adopt as `AuthorizationPort` adapter — agents + bounded delegation; keep role-check default until parity | Settings → Members / access |

### 10c · Cross-cutting (decide alongside design, don't defer to the end)
Streaming vs governance (TD-003) · fail-soft for in-path helpers (TD-006) · secure the new data stores +
expand the attestation (TD-007) · attribution incl. agents (TD-005) · govern-the-control-plane —
config precedence, finer roles, alert delivery (TD-008).

### 10d · Still to brainstorm before building
**Self-hosting / deploy** (FEAT-009) — container + one-command bundle, then Helm / Postgres / Vault /
air-gapped. Paused in the brainstorm; needs its own scoping pass.

**Build order:** 10a foundations → FEAT-001 (creates the budget-pressure signal) → FEAT-002/003/005/007
→ FEAT-008 → Console refresh wired surface-by-surface throughout. See `BRAINSTORM.md` "Build order".

## Roadmap — horizons

| Horizon | Theme | Contents | Exit criteria |
|---|---|---|---|
| **H0 · V1 — "Prove the loop"** | Phases 0–6 | Governed sovereign control plane + Console + attestation | Attestation generated for **one design partner's** real workload |
| **H1 · V1.1 — "Harden for pilot"** | pilot-readiness | **Phase 10** (cost/quality/governance controls: budgets, cache, compression, advanced routing, traces→learning, refreshed Console) · **open-guard** authZ · robust PII/PHI detection · optillm reasoning · controls-mapped evidence (DPDP/HIPAA) · Helm / air-gapped deploy | A regulated pilot runs in the customer's environment |
| **H2 · V2 — "Enterprise-grade / sell"** | trust + scale | Certifications (SOC2/ISO), WORM / externally-anchored audit, multi-tenancy, customer KMS, DSPy reasoning, big-provider hybrid governance, compliance policy packs, **Neysa/Shakti channel bundle** | First paid contract; repeatable sales motion |

## Owner actions (some gate later phases, none block the start)

1. **Design partner** — one regulated (DPDP) firm to pilot; their real workload is the V1 spec. *(Highest leverage — pursue in parallel with the build.)*
2. **Neysa API access** (+ optionally HF endpoint) — keys + endpoint shape, to confirm adapters at Phase 1–2.
3. **An egress-lockable environment** — a VPC/host (or air-gapped box) to demonstrate zero-egress at Phase 4.
4. **Google OAuth credential** — for authN login at Phase 3/6.

## Timeline dial

- **V1 = Phases 0–6.** Load-bearing spine: **0 → 1 → 3 → 4** (a governed, provable in-boundary call).
- **Safe cut order (if squeezed):** Playground polish → reasoning techniques (keep passthrough) → infra-console depth → automatic routing (keep cheapest) → HF/Neysa adapter (demo on vLLM+Ollama).
- **Never cut:** in-boundary routing, authN+authZ, policy evaluate, audit + hash chain, **Sovereign Mode + attestation**, the Console. Cutting those removes the reason to exist.

## Reality check (from SIEVE)
This is a **commercial bet with an untested demand crux**. Building all six phases before landing a
design partner is the main risk. Recommended sequencing: **pursue the design partner + a
Neysa/Shakti channel conversation in parallel with Phase 0–1**, so the build and the proof of demand
advance together. The Console (already designed) is your best asset for those conversations *now*.
