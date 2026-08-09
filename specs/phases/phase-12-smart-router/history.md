---
type: Phase History
phase: 12
name: smart-router
---

# Phase 12 — Smart Router · History

### [DECISION] 2026-08-09 — Router brain is a model, not an agent
Topics: router, brain, dip
Affects-phases: phase-12-smart-router
Affects-specs: none
Detail: The routing brain is a single in-boundary **model classify call** (fast, cheap,
auditable), behind a `RouterBrain` port. "Router agent" = the packaged component, not an
agentic loop. An `AgentRouterBrain` adapter stays possible later but is not built.

---

### [DECISION] 2026-08-09 — Two-stage routing (Option B)
Topics: router, resolver, intent
Affects-phases: phase-12-smart-router
Affects-specs: none
Detail: Stage 1 the brain picks **intent**; Stage 2 a config-driven `TargetResolver`
maps intent→target (filter by policy → score `quality − cost − latency + warm` → pick).
Keeps the model's job narrow and makes routing rules **auditable config**, not a prompt.

---

### [DECISION] 2026-08-09 — Unified RouteTarget: models AND agents
Topics: router, targets, agents, dip
Affects-phases: phase-12-smart-router
Affects-specs: none
Detail: One `RouteTarget` socket with `InferenceTarget` and `AgentTarget`. The router
does not care which — both satisfy the port. Agent targets: mandate a trace contract
`{output, status, reason, steps[]}` (D1); their own model calls **re-enter Precepta**
(D2); cache/compression **off by default** for agents (D3).

---

### [ARCH_CHANGE] 2026-08-09 — LiteLLM as an optional InferenceTarget adapter
Topics: litellm, inference, sovereignty, dip
Affects-phases: phase-12-smart-router
Affects-specs: DESIGN.md#ports, specs/architecture (sync at completion)
Detail: Adopt LiteLLM (MIT core only, never `enterprise/`) behind `InferenceTarget` for
many providers + load balancing. Enforce an **in-boundary allowlist** with explicit
`api_base` and no provider fallthrough — LiteLLM proxies to clouds by default and would
break zero-egress otherwise. Use the SDK, not its proxy. Two-way door (behind the port).

---

### [ARCH_CHANGE] 2026-08-09 — Governance-first order preserved for routing
Topics: governance, pipeline, order
Affects-phases: phase-12-smart-router
Affects-specs: DESIGN.md, specs/architecture (sync at completion)
Detail: Router is inserted **after** firewall + policy:
`firewall → policy → ROUTER → cache → compression → dispatch → output-firewall`.
Cache/compression apply to model targets only. Added: enforcement-timing modes
(pre/during/post-call) and a toxicity output filter.

---

### [DECISION] 2026-08-09 — Open-core boundary (Apache-2.0)
Topics: open-source, open-core, licensing
Affects-phases: phase-12-smart-router
Affects-specs: none
Detail: Open-source the **router mechanics + governance hooks** under Apache-2.0; the
governance/audit/attestation implementation stays commercial. **Carve into a package**
Precepta imports first; split to its own repo later. Precepta depends on the OSS router,
never the reverse.

---

### [NOTE] 2026-08-09 — Positioning correction from competitor research
Topics: positioning, competitor, litellm
Affects-phases: phase-12-smart-router
Affects-specs: none
Detail: LiteLLM already does cost-routing, semantic cache, compression, attribution,
guardrails (Presidio/Lakera — some **external**), and mature deploy (Helm/air-gap/Rust).
Cost-routing is **table stakes**. Reframe the headline off "smart router" onto
**sovereignty + in-boundary reasoning-traces + governed agents**. Their guardrails/obs
ship data to third parties; our in-boundary, built-in trace UI is the structural edge.

---

### [DISCOVERY] 2026-08-09 — Competitor "must-add" parity items, split across phases
Topics: competitor, parity, backlog
Affects-phases: phase-12-smart-router, phase-11-traces, deploy
Affects-specs: specs/backlog/backlog.md
Detail: From the LiteLLM neck-to-neck list — **Phase 12:** many providers + load
balancing, usage-by-tool/agent capture, enforcement-timing modes, toxicity filter.
**Traces/phase-11:** live request log, bill-back, render tool/agent usage. **Deploy:**
easy-install packages, auto-provision users. **Backlog:** per-app rate limits (ENH-003),
faster gateway (ENH-008). Added FEAT-013..021, ENH-008 to the backlog.

---

### [NOTE] 2026-08-09 — Router model is oversized and public in dev (TD-009)
Topics: router-model, sovereignty, cost
Affects-phases: phase-12-smart-router, deploy
Affects-specs: none
Detail: Router model today = Gemma-4-31B via **public** `router.huggingface.co` (fallback
Llama-3.2-3B local). Intent classification needs only a small model — right-size it, and
move it **in-boundary** before any customer (resolved at deploy, TD-009).

---

### [FEATURE] 2026-08-09 — Read-only workflow view (show, don't configure)
Topics: workflow, ux, console
Affects-phases: phase-12-smart-router
Affects-specs: none
Detail: Show the governed path + routing rules **auto-generated from live config** (a
projection). Governance rails fixed; routing layer is the composable middle. The
editable **builder** is deferred to Phase 13. Design-time view will pair with run-time
traces (phase-11) into one picture.
