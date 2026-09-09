---
type: Phase
phase: 20
name: AI Inventory, Registry & Risk
status: planned
tags: [inventory, registry, risk-scoring, evaluation, red-team, governance, know, decide]
---

# Phase 20 — AI Inventory, Registry & Risk

> **Verification:** `./run.sh test` · **Build:** none
> **Backlog:** FEAT-027, FEAT-028, FEAT-029 · **Roadmap:** P1 · **Target:** Q1 – Q2 2027

## Goal
Add the "Know" and "Decide" jobs Precepta is missing: an **AI registry**
auto-built from the traffic that routes through it, **per-system risk
classification & dynamic scoring**, and a **pre-deployment evaluation +
red-team gate** before anything goes live.

## Why (plain English)
"What AI are we actually running?" is the first question in every buyer demo,
and most companies can't answer it. Regulators and boards then want that AI
**sorted by risk**, and want proof each system was **tested before go-live**.
Today Precepta answers neither — this phase closes both.

## Key decisions
| Decision | Choice |
|---|---|
| Registry source | **Auto-built** from routed traffic (first-seen model/agent → entry) + manual entries for AI that doesn't route through us |
| Risk scoring | Rules-based (data sensitivity + use-case + autonomy) with **reasons**, updated from live traces (dynamic) |
| Go-live gate | Fixed **eval test-set** with pass thresholds + a **red-team** prompt library; block enable until pass |
| Ties | Risk score + eval results attach to the registry entry |

## Scope — in
- Registry data model + auto-capture from traffic + owner/first-seen. (FEAT-027)
- Registry UI (list, owner, risk) + manual entries. (FEAT-027)
- Risk classification & dynamic scoring engine (score + reasons). (FEAT-028)
- Pre-deployment eval + red-team gate; results on the registry entry. (FEAT-029)
- Tests + a live E2E (route → auto-registered → scored → gated).

## Scope — out
- Full framework/compliance mapping (Phase 19); bias/drift/quality monitoring (later);
  third-party model-scanning integrations.

## Deliverables & verification
| Deliverable | Verify |
|---|---|
| Auto-built registry | `./run.sh test`: first use of a model/agent creates an entry (owner, first-seen) |
| Risk scoring | test: score + reasons; a behaviour change moves the score |
| Eval + red-team gate | test: fails threshold → go-live blocked; passes → allowed; results attached |
| Registry UI | headless render: list + risk + manual add |
| Full suite | `./run.sh test` green; SMOKE PASS |

## Acceptance criteria
- Using a model/agent auto-creates a registry entry with an owner and a risk level.
- Each system carries a risk score with reasons that updates as behaviour changes.
- A system cannot go live until it passes the eval + red-team gate, and the results
  are visible on its registry entry. Full suite green; sovereignty unaffected.
