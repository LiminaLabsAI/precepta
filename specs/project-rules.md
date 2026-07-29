---
type: Project Rules
---

# Project Rules — preceptaai

Project-specific rules, shared by every agent. (CLAUDE.md's `## Project Extensions` points here.)

## Non-negotiables
1. **Sovereign Mode is load-bearing** — never route out-of-boundary when it's on; enforcement lives in `app/sovereign` + the gateway.
2. **DIP** — all external deps behind ports (`app/ports`); adding a provider/store/cloud/technique must not touch the domain core.
3. **Governance in the path** — every request runs authN → authZ → policy → firewall → route → audit. Backend failures are audited too. No unaudited path.
4. **Router-brain / evaluator discipline** — any change to routing intelligence requires a locked evaluator (fixed eval set + scalar) before tuning.
5. **Attributed access** — humans authenticate via SSO session; systems/agents via per-team API keys. The audit actor is always the real principal.

## Console (UI) rules
- **No fake data when served live** — the Console must reflect the real backend (`window.__live`). Mock/seed data is only for the `file://` design preview.
- **Every UI surface is browser-validated** against the live backend before a change is considered done (Rule 12).
- **Settings must be real** — each control is functional+persisted, honestly read-only, or removed. No non-functional toggles.

## Verification
- `./run.sh test` (pytest) must be green. Add a `tests/test_phaseN*.py` (or feature test) for each new capability.
- For UI changes, drive the flow in a browser and confirm real behavior — not just tests.
