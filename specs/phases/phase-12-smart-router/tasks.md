---
type: Phase Tasks
phase: 12
name: smart-router
---

# Phase 12 — Smart Router · Tasks

Legend: `[ ]` todo · `[/]` in progress · `[x]` done

## Group 0 — Contracts + migrations
- [ ] `RouterBrain`, `TargetResolver`, `RouteTarget` (`InferenceTarget` | `AgentTarget`) ports
- [ ] `RouteDecision {target, intent, reason, confidence, inferred}`
- [ ] Intent registry (open list; new intent = one row)
- [ ] `AgentTraceContract` → `TargetResult {output, status, reason, steps[]}`
- [ ] BUG-001: backend **unique id** across registry/store/pricing/routing/scopes

## Group 1 — Brain + resolver
- [ ] `ModelRouterBrain` (single classify call, in-boundary target, fail-soft)
- [ ] Confidence floor (weak match → treat as hard; print reason; `inferred` flag)
- [ ] `TargetResolver`: filter by policy → score `quality − cost − latency + warm` → pick
- [ ] Warm-prefix bonus as a scoring input
- [ ] "No target" → blocked + traced

## Group 2 — Targets
- [ ] `InferenceTarget` via LiteLLM (MIT-only, explicit `api_base`, in-boundary allowlist)
- [ ] Many-providers + load balancing across model copies
- [ ] Existing thin adapters still work behind the port
- [ ] `AgentTarget`: dispatch + timeout + fail-soft
- [ ] Agent egress re-enters Precepta (governed)
- [ ] Agent sub-trace capture per contract (honest "no reasoning" fallback)
- [ ] Usage-by-tool/agent captured on dispatch

## Group 3 — Governance-first wiring
- [ ] Router inserted after firewall + policy in `governed_chat`
- [ ] Cache/compression = model targets only; off by default for agents
- [ ] Enforcement-timing modes (pre / during / post-call)
- [ ] Toxicity output filter
- [ ] `RouteDecision` audited (intent · target · why · inferred · rule)

## Group 4 — Read-only workflow view
- [ ] Console **Workflow** screen auto-generated from live config (projection)
- [ ] Governance rails fixed; routing layer shown (read-only)
- [ ] Browser-validate (no JS errors); matches live config

## Group 5 — Verification
- [ ] Unit: brain + floor, resolver, targets (model/agent/timeout), BUG-001, enforcement, toxicity, fail-soft
- [ ] Lock router eval set — 7 scenarios in `tests/benchmarks` (Rule 11)
- [ ] Live: tagged request → model **and** agent, governed first, plain reason
- [ ] OSS: router package builds standalone under Apache-2.0 (no commercial imports)
- [ ] Update HANDOFF + changelog; mark FEAT-013/014/015/020 + BUG-001 resolved
