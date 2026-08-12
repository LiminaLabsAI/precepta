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
from ..adapters.audit.chain import get_chain
from .. import cache as _cache
from .. import compression as _compress
from .. import traces as _traces
from .. import features as _features

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
    req_model: str | None = None, model_str: str = "",
    attribution: dict | None = None,
) -> tuple[int, dict]:
    audit = get_audit()
    usage = DbUsage()
    tokens = kw.get("max_tokens")
    attribution = attribution or {}
    # ── trace capture (FEAT-010): fail-soft, in-boundary, team-scoped ──
    tr = _traces.begin(getattr(principal, "team", "") or "",
                       getattr(principal, "subject", ""),
                       getattr(principal, "role", ""), attribution)

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

    if tr is not None:
        for _m in scrubbed:
            if _m.get("role") == "user":
                tr.request_preview = (_m.get("content") or "")[:280]
        tr.step("firewall",
                f"Redacted {pii} item(s)" if pii else "No sensitive data found",
                "Scanned the request for PII and secrets before any model saw it.")

    ctx = PolicyCheckContext(action_type=ACTION, principal=principal,
                             tokens_requested=tokens, has_data_tag=data_tag,
                             workflow_id=attribution.get("workflow_id"),
                             run_id=attribution.get("run_id"),
                             step_name=attribution.get("step_name"),
                             agent_id=attribution.get("agent_id"),
                             end_user=attribution.get("end_user"))

    if injection:
        dec = Decision("block", "prompt-injection/jailbreak detected in input")
        aid = audit.append_check(ctx, dec, tokens=tokens, pii_count=pii, blocked=True)
        if tr is not None:
            tr.step("firewall", "Blocked",
                    "Prompt-injection / jailbreak detected in the input.", status="blocked")
        _traces.save(tr, "blocked", pii=pii)
        return 403, _blocked_payload(dec, aid, pii, injection=True)

    # ── governance routing filter (FEAT-007 / Rule C): sensitive → approved backend only ──
    sensitive = _sensitive.is_sensitive(pii, data_tag)
    reason = _sensitive.block_reason(sensitive, req_backend)   # explicit backend only
    if reason:
        _sensitive.notify_block(getattr(principal, "subject", ""), req_backend)
        dec = Decision("block", reason)
        aid = audit.append_check(ctx, dec, tokens=tokens, pii_count=pii, blocked=True)
        if tr is not None:
            tr.step("sensitivity", "Blocked", reason, status="blocked")
        _traces.save(tr, "blocked", pii=pii)
        return 403, _blocked_payload(dec, aid, pii, injection=False)

    if tr is not None:
        tr.step("sensitivity",
                "Sensitive — fenced to approved endpoints" if sensitive else "Not sensitive",
                "Requests with PII/PHI may only reach endpoints you've approved."
                if sensitive else "No PII/PHI detected; standard routing applies.")

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
        if tr is not None:
            tr.step("policy", "Blocked", decision.reason or "Blocked by policy.",
                    status="blocked")
        _traces.save(tr, "blocked", pii=pii)
        return 403, _blocked_payload(decision, aid, pii, injection=False)
    if tr is not None:
        tr.step("policy", "Warn" if decision.effect == "warn" else "Passed",
                decision.reason or "No policy blocked this request.",
                status="warn" if decision.effect == "warn" else "ok")

    # ── response cache (FEAT-003, per-endpoint FEAT-011): deterministic + non-sensitive ──
    # config key = the endpoint that serves this request: its name for a direct
    # call, or "auto" for a router-decided request.
    team = getattr(principal, "team", "") or ""
    config_key = req_backend or _features.AUTO
    cacheable = _cache.is_cacheable(kw, sensitive, config_key)   # False on temp>0, sensitive, or off
    if cacheable:
        entry = _cache.lookup(model_str, scrubbed, kw, team, config_key)
        if entry is not None:                        # HIT — reuse the prior answer
            saved = _cache.record_hit(entry, team)
            aid = audit.append_check(ctx, decision, tokens=tokens, pii_count=pii, blocked=False)
            # Anchor the cache serve as its own audit event so it's visible under
            # the "Cache & compression" filter — "every cache hit is audited".
            get_chain().append(
                event_type="cache.hit", actor=getattr(principal, "subject", "") or "anonymous",
                resource="cache.hit", action="served", outcome="allowed",
                metadata={"backend": entry.get("backend"), "exact": entry.get("exact"),
                          "tokens_saved": saved["tokens_saved"],
                          "cost_saved_usd": saved["cost_saved_usd"], "audit_id": aid})
            result = dict(entry["response"])
            result["precepta"] = {
                "backend_used": entry.get("backend"), "in_boundary": True,
                "cache": "hit", "cache_exact": entry.get("exact"),
                "cache_similarity": entry.get("similarity"),
                "tokens_saved": saved["tokens_saved"], "cost_saved_usd": saved["cost_saved_usd"],
                "policy_decision": decision.effect, "policy_reason": decision.reason,
                "audit_id": aid, "pii_redacted": pii, "injection_detected": False,
                "principal": principal.subject, "role": principal.role,
            }
            if tr is not None:
                tr.step("cache", "Served from cache",
                        f"Reused a prior answer — saved {saved['tokens_saved']} tokens; "
                        "no model was called.", status="hit")
            _traces.save(tr, "allowed", backend=entry.get("backend"),
                         model=entry.get("model"), pii=pii, cost_usd=0.0,
                         tokens_out=saved.get("tokens_saved", 0))
            return 200, result

    if tr is not None:
        tr.step("cache",
                "Miss — calling the model" if cacheable else "Skipped",
                "No matching prior answer; the request goes to a model."
                if cacheable else
                "Cache doesn't apply here (non-deterministic, sensitive, or off for this endpoint).")

    # ── prompt compression (FEAT-005): shorten before inference; billing follows ──
    infer_msgs = scrubbed
    comp_stats = None
    if _compress.enabled(config_key):
        # 'smart' auto-decides skip/baseline/aggressive per request.
        eff_mode = _compress.effective_mode(config_key, scrubbed)
        if eff_mode != "skip":
            infer_msgs, comp_stats = _compress.compress(
                scrubbed, aggressive=(eff_mode == "aggressive"))
            _compress.record(comp_stats, config_key)
            if comp_stats["saved_tokens"] > 0:
                # Anchor the compression as its own audit event (filterable, tamper-evident).
                get_chain().append(
                    event_type="compression", actor=getattr(principal, "subject", "") or "anonymous",
                    resource="compression", action=comp_stats["mode"], outcome="applied",
                    metadata={"saved_tokens": comp_stats["saved_tokens"],
                              "original_tokens": comp_stats["original_tokens"],
                              "compressed_tokens": comp_stats["compressed_tokens"]})
                if comp_stats["mode"] == "aggressive":
                    _compress.notify_aggressive(comp_stats["saved_tokens"])   # never surprise
    if tr is not None:
        if comp_stats is not None and comp_stats.get("saved_tokens", 0) > 0:
            tr.step("compression", f"{comp_stats['mode'].title()} trim",
                    f"Shortened the prompt by {comp_stats['saved_tokens']} tokens before inference.")
        else:
            tr.step("compression", "None",
                    "Prompt left unchanged (compression off, or nothing to trim).")

    # ── inference (injected router/engine) — failures are audited too ──
    try:
        result, route_meta = await run_inference(
            infer_msgs, {"allowed_backends": allowed_backends})
    except httpx.HTTPError as exc:
        dec = Decision("block", f"backend unavailable / inference failed: {exc}")
        aid = audit.append_check(ctx, dec, tokens=tokens, pii_count=pii, blocked=True)
        payload = _blocked_payload(dec, aid, pii, injection=False)
        payload["error"]["type"] = "backend_unavailable"
        if tr is not None:
            tr.step("inference", "Failed",
                    "The inference endpoint was unavailable or errored.", status="failed")
        _traces.save(tr, "failed", pii=pii)
        return 502, payload
    except LookupError as exc:
        # No eligible backend. For a sensitive auto request under an active filter
        # that means nothing approved is available → fail-closed block + notify.
        if allowed_backends:
            _sensitive.notify_block(getattr(principal, "subject", ""), None)
            dec = Decision("block", "sensitive data (auto route) — no approved-for-"
                           "sensitive backend is available")
            aid = audit.append_check(ctx, dec, tokens=tokens, pii_count=pii, blocked=True)
            if tr is not None:
                tr.step("routing", "Blocked",
                        "No approved-for-sensitive endpoint was available to route to.",
                        status="blocked")
            _traces.save(tr, "blocked", pii=pii)
            return 403, _blocked_payload(dec, aid, pii, injection=False)
        raise

    ctx.backend = route_meta.get("backend_used")   # record backend on the audit row
    if tr is not None:
        _be = route_meta.get("backend_used") or route_meta.get("backend") or "—"
        _cands = route_meta.get("candidates") or []
        tr.step("routing", f"Routed to {_be}",
                route_meta.get("reason") or route_meta.get("plan")
                or "Selected an in-boundary endpoint for this request.",
                inferred=bool(route_meta.get("inferred", req_backend is None)),
                extra=({"candidates": _cands,
                        "intent": route_meta.get("intent")} if _cands else None))
        _u0 = result.get("usage") or {}
        _agent_steps = route_meta.get("agent_steps")   # AgentTarget sub-trace (L2)
        if _agent_steps:
            tr.step("inference", "Agent responded",
                    f"{_be} (agent) handled the request — its own reasoning is nested below.",
                    substeps=_agent_steps)
        elif route_meta.get("agent"):                   # an agent that reported no reasoning
            tr.step("inference", "Agent responded",
                    f"{_be} (agent) handled the request — agent reported no reasoning.")
        else:
            tr.step("inference", "Model responded",
                    f"{_be} generated the answer"
                    + (f" ({_u0.get('completion_tokens')} output tokens)."
                       if _u0.get("completion_tokens") else "."))

    # ── Stage 3: output firewall (leak check) ──
    if scan_output(_content(result)):
        dec = Decision("block", "output leak (secret/private-key/db-url) detected")
        aid = audit.append_check(ctx, dec, tokens=tokens, pii_count=pii, blocked=True)
        if tr is not None:
            tr.step("output", "Blocked",
                    "The response contained a secret/private-key/DB-URL leak.",
                    status="blocked")
        _traces.save(tr, "blocked", backend=route_meta.get("backend_used"), pii=pii)
        return 403, _blocked_payload(dec, aid, pii, injection=False)

    # ── output toxicity filter (opt-in, in-boundary — never surprises) ──
    from .. import org as _org
    if _org.get("toxicity_filter", "false") == "true":
        from ..governance import toxicity as _tox
        toxic, phrase = _tox.scan_toxicity(_content(result))
        if toxic:
            dec = Decision("block", f"toxic/abusive content in output ({phrase})")
            aid = audit.append_check(ctx, dec, tokens=tokens, pii_count=pii, blocked=True)
            if tr is not None:
                tr.step("output", "Blocked",
                        f"Output blocked — abusive/toxic content detected ({phrase}).",
                        status="blocked")
            _traces.save(tr, "blocked", backend=route_meta.get("backend_used"), pii=pii)
            return 403, _blocked_payload(dec, aid, pii, injection=False)

    # ── store the fresh answer for reuse (deterministic + non-sensitive only) ──
    if cacheable:
        u = result.get("usage") or {}
        _cache.store(model_str, scrubbed, kw, team, config_key, result,
                     u.get("prompt_tokens") or 0, u.get("completion_tokens") or 0,
                     route_meta.get("backend_used") or "",
                     route_meta.get("model") or req_model or "")

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
    if comp_stats and comp_stats["saved_tokens"] > 0:      # transparent — never hidden
        result["precepta"]["compression"] = comp_stats
    if attribution:                                        # echo who/what was attributed
        result["precepta"]["attribution"] = attribution
    if tr is not None:
        tr.step("output", "Clean", "Scanned the response for leaks — none found.")
        _u = result.get("usage") or {}
        _cost = 0.0
        try:
            from .. import pricing as _pricing
            _cost = float(_pricing.cost_of(
                route_meta.get("backend_used") or "",
                route_meta.get("model") or req_model or "",
                _u.get("prompt_tokens") or 0, _u.get("completion_tokens") or 0))
        except Exception:
            _cost = 0.0
        _traces.save(tr, "warn" if decision.effect == "warn" else "allowed",
                     backend=route_meta.get("backend_used"),
                     model=route_meta.get("model") or req_model, pii=pii,
                     cost_usd=_cost, tokens_in=_u.get("prompt_tokens") or 0,
                     tokens_out=_u.get("completion_tokens") or 0,
                     response_preview=_content(result))
    return 200, result
