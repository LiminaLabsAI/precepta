"""Governed chat pipeline — the one place router meets governance.

    input firewall (Stage 1) → policy evaluate (most-restrictive)
      → [block? stop + audit] → inference (injected) → output firewall (Stage 3)
      → [leak? stop + audit] → audit allow/warn → response(+precepta)

authN/authZ happen in the endpoint (they gate the whole request); this function
owns everything from the firewall inward. `run_inference` is injected so the
router/engine stays decoupled from governance.
"""
from __future__ import annotations

from typing import Awaitable, Callable

import httpx

from ..ports import Decision, PolicyCheckContext, Principal
from ..governance.firewall import scrub_input, scan_output
from ..governance.policy import load_enabled, evaluate, scope_matches, DbUsage
from ..governance import sensitive as _sensitive
from ..adapters.audit import get_audit

RunInference = Callable[..., Awaitable[tuple[dict, dict]]]

ACTION = "chat.completion"


def _content(result: dict) -> str:
    try:
        return result["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError):
        return ""


def _blocked_payload(decision: Decision, audit_id: str, pii: int, injection: bool) -> dict:
    return {
        "error": {"message": decision.reason, "type": "policy_block"},
        "precepta": {
            "policy_decision": "block",
            "policy_reason": decision.reason,
            "audit_id": audit_id,
            "pii_redacted": pii,
            "injection_detected": injection,
            "backend_used": None,
            "in_boundary": None,
        },
    }


async def governed_chat(
    messages: list[dict], kw: dict, principal: Principal, data_tag: bool,
    run_inference: RunInference, req_backend: str | None = None,
    req_model: str | None = None,
) -> tuple[int, dict]:
    audit = get_audit()
    usage = DbUsage()
    tokens = kw.get("max_tokens")

    # ── Stage 1: input firewall (redact PII, detect injection) ──
    pii = 0
    injection = False
    scrubbed: list[dict] = []
    for m in messages:
        if m.get("role") == "user":
            text, n, inj = scrub_input(m.get("content") or "")
            pii += n
            injection = injection or inj
            scrubbed.append({**m, "content": text})
        else:
            scrubbed.append(m)

    ctx = PolicyCheckContext(action_type=ACTION, principal=principal,
                             tokens_requested=tokens, has_data_tag=data_tag)

    if injection:
        dec = Decision("block", "prompt-injection/jailbreak detected in input")
        aid = audit.append_check(ctx, dec, tokens=tokens, pii_count=pii, blocked=True)
        return 403, _blocked_payload(dec, aid, pii, injection=True)

    # ── governance routing filter (FEAT-007 / Rule C): sensitive → approved backend only ──
    sensitive = _sensitive.is_sensitive(pii, data_tag)
    reason = _sensitive.block_reason(sensitive, req_backend)   # explicit backend only
    if reason:
        _sensitive.notify_block(getattr(principal, "subject", ""), req_backend)
        dec = Decision("block", reason)
        aid = audit.append_check(ctx, dec, tokens=tokens, pii_count=pii, blocked=True)
        return 403, _blocked_payload(dec, aid, pii, injection=False)

    # Auto path (no explicit backend): restrict the router to the approved set for
    # a sensitive request, so the LLM router + failover can only pick an approved
    # backend. If none is approved the router raises → fail-closed block below.
    allowed_backends: set[str] | None = None
    if sensitive and req_backend is None:
        approved = _sensitive.approved_set()
        if approved:                          # empty = filter off (firewall still redacts)
            allowed_backends = approved

    # ── policy evaluation (most-restrictive), scoped to this request (FEAT-002) ──
    policies = [p for p in load_enabled(ACTION)
                if scope_matches(p.get("scope", {}), principal.subject, req_backend, req_model)]
    decision = evaluate(ctx, policies, usage)
    if decision.effect == "block":
        aid = audit.append_check(ctx, decision, tokens=tokens, pii_count=pii, blocked=True)
        return 403, _blocked_payload(decision, aid, pii, injection=False)

    # ── inference (injected router/engine) — failures are audited too ──
    try:
        result, route_meta = await run_inference(
            scrubbed, {"allowed_backends": allowed_backends})
    except httpx.HTTPError as exc:
        dec = Decision("block", f"backend unavailable / inference failed: {exc}")
        aid = audit.append_check(ctx, dec, tokens=tokens, pii_count=pii, blocked=True)
        payload = _blocked_payload(dec, aid, pii, injection=False)
        payload["error"]["type"] = "backend_unavailable"
        return 502, payload
    except LookupError as exc:
        # No eligible backend. For a sensitive auto request under an active filter
        # that means nothing approved is available → fail-closed block + notify.
        if allowed_backends:
            _sensitive.notify_block(getattr(principal, "subject", ""), None)
            dec = Decision("block", "sensitive data (auto route) — no approved-for-"
                           "sensitive backend is available")
            aid = audit.append_check(ctx, dec, tokens=tokens, pii_count=pii, blocked=True)
            return 403, _blocked_payload(dec, aid, pii, injection=False)
        raise

    ctx.backend = route_meta.get("backend_used")   # record backend on the audit row

    # ── Stage 3: output firewall (leak check) ──
    if scan_output(_content(result)):
        dec = Decision("block", "output leak (secret/private-key/db-url) detected")
        aid = audit.append_check(ctx, dec, tokens=tokens, pii_count=pii, blocked=True)
        return 403, _blocked_payload(dec, aid, pii, injection=False)

    # ── allow / warn → audit + response ──
    aid = audit.append_check(ctx, decision, tokens=tokens, pii_count=pii, blocked=False)
    result["precepta"] = {
        **route_meta,
        "policy_decision": decision.effect,
        "policy_reason": decision.reason,
        "audit_id": aid,
        "pii_redacted": pii,
        "injection_detected": False,
        "principal": principal.subject,
        "role": principal.role,
    }
    return 200, result
