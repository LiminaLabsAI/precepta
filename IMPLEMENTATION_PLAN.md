# preceptaai — Implementation Plan & Roadmap (V1: closed sovereign loop)

> **Status:** Draft v4 — V1 (Phases 0–9) shipped; **Phase 10** added below (cost / quality / governance
> controls), scoped in `BRAINSTORM.md` and aligned to the refreshed **Precepta Console** design
> (re-imported from Claude Design 2026-07-30 → `design/Precepta Console.dc.html`).
> **Companions:** `VISION.md` (why/wedge/moat), `DESIGN.md` (architecture/ports/contracts),
> `BRAINSTORM.md` (Phase 10 scoping), `preceptaai-plan.md` (combined plain-English overview).
> **Last updated:** 2026-08-01 — Phase 10 rewritten as a status-tracked, phase-wise development plan.

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

## Phase 10 — Cost / quality / governance controls (phase-wise plan)

> Phase 10 turns the control plane from "governs correctly" into "governs, saves cost, and gets
> smarter." **Governing stance:** safe by default, extra risk only by explicit opt-in, nothing hidden
> from the person using it. Every item lands behind an existing port (no core rewrite) and is
> **backend-real** (no demo values), UI wired surface-by-surface as each backend lands.
> **Status legend:** ✅ done (on `main`, tested + browser-verified) · 🔵 in progress · ⚪ pending.
> **Reflects live state as of 2026-08-01.**

| Phase | Focus | Contents | Status | Needs first |
|---|---|---|---|---|
| **1 · Money foundations** | Make every $ real | Pricing source-of-truth (TD-001) · one counting definition (TD-002) | ✅ Done | — |
| **2 · Access & keys** | Governed app credentials | Key expiry · cost + token caps · backend/model scope · edit · suspend · bell alerts (FEAT-001). *Dropped role/team/subject-type from keys — a key is an app-level credential; admin stays human-only.* | ✅ Done | Phase 1 |
| **3 · Policy governance** | Targeted rules + sensitive routing | Policy scope (Key/Backend/Model) + editing with version bump (FEAT-002) · sensitive-data → approved-backend filter, fail-closed + notify, approval-with-location (FEAT-007·C) | ✅ Done | Phase 2 |
| **4 · Smart routing** | Make "Optimize automatically" real | Router config in Settings (platform-owner-only, Ollama/HF, Precepta in-boundary key) · **eval harness (FEAT-006)** · LLM intent-router · budget-aware modifier (FEAT-007·A/B) | 🔵 In progress | eval harness gates the router |
| **5 · Cost optimization** | Cut cost & latency | Response cache — exact default, semantic opt-in (FEAT-003) · prompt/history compression (FEAT-005) | ⚪ Pending | eval harness · fail-soft · streaming decision |
| **6 · Learning loop** | Router gets smarter | Traces + reward (explicit + implicit) → learned routing (FEAT-008) | ⚪ Pending | eval harness · traces |
| **7 · Enterprise hardening** | Robust & secure | OpenGuard authZ (FEAT-004) · sensitivity beyond regex (TD-004) · fail-soft (TD-006) · streaming vs governance (TD-003) · secure new data stores + attestation scope (TD-007) · attribution incl. agents (TD-005) · control-plane roles/config/alerts (TD-008) | ⚪ Pending | interleave with Phase 5 |
| **8 · Deploy** | Customer can actually run it | Container + one-command bundle → Helm / Postgres / Vault / air-gap (FEAT-009) | ⚪ Pending | **needs its own brainstorm** |
| **9 · Validation** *(business, parallel)* | Prove someone pays | A metered workload + a design-partner pilot | ⚪ Not started | — |

**Sequencing notes:**
- Phases 1–3 complete; Phase 4 is current. Inside Phase 4 the one hard dependency is *eval harness before the LLM router*.
- Phases 5–7 **interleave**: build cache/compression (5) *with* fail-soft + the streaming decision (7 items), not after, to avoid rework.
- Phase 8 (deploy) is **unscoped** — needs a brainstorm pass before build.
- Phase 9 is the vision's real risk (will a regulated customer pilot this) — run in parallel with the build.

**Removed from the plan (deliberately, 2026-08-01):** the compliance-evidence report + named-regulation
claims (DPDP/GDPR/HIPAA/SOC2) — we haven't certified against them, so implying compliance was a trust risk.
Audit log + zero-egress attestation remain (technical facts, not compliance claims).

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
