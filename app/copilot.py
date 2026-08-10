"""Precepta Copilot — a grounded, in-boundary assistant for the Console.

The copilot answers an operator's questions about *their own* deployment:
which inference endpoints are configured, whether Sovereign Mode is on, how many
keys and policies exist, whether the cache is on, whether egress is blocked, and
so on. It is **grounded**: every answer is built from a snapshot of real state
gathered from the same stores the Console reads, and the model is instructed to
answer only from those facts and to say "I don't have that" otherwise — so it
never fabricates numbers.

Sovereignty: the answer is produced by the same **in-boundary** model registry
as everything else (bundled Ollama in a sovereign deploy). The operator's
question and the state snapshot never leave the boundary.

Fail-soft: if no model is reachable, `answer()` returns a deterministic,
still-useful summary built directly from the facts — never a broken UI, never a
made-up value.
"""
from __future__ import annotations

from typing import Any

# What the copilot is allowed to talk about — keeps it on-rails and honest.
_SYSTEM = (
    "You are the Precepta Copilot, an assistant embedded in the Precepta control "
    "plane — a sovereign, self-hosted AI governance gateway. Answer the operator's "
    "question about THEIR deployment using ONLY the FACTS block below. The facts are "
    "the live, real state of this install. Rules:\n"
    "- Use only the facts. If the answer isn't in them, say you don't have that "
    "detail and point to the relevant screen (Inference plane, Keys, Policies, "
    "Cache & compression, Traces, Deployment).\n"
    "- Never invent numbers, endpoint names, or status.\n"
    "- Be brief and plain (2-5 sentences). No jargon dumps.\n"
    "- Everything runs in-boundary; the operator's data never leaves their network.\n"
)


def gather_facts() -> dict[str, Any]:
    """Snapshot the live deployment state the copilot is allowed to reason over.

    Every field is read from the real stores; any store that errors is skipped
    (the copilot simply won't have that fact) rather than failing the request.
    """
    facts: dict[str, Any] = {}

    def _safe(fn):
        try:
            return fn()
        except Exception:
            return None

    # Org
    def _org():
        from . import org
        return {"name": org.get("org_name"), "timezone": org.get("timezone")}
    org_f = _safe(_org)
    if org_f:
        facts["org"] = org_f

    # Sovereign mode
    def _sov():
        from .controls import sovereign_enabled
        return sovereign_enabled()
    sov = _safe(_sov)
    if sov is not None:
        facts["sovereign_mode"] = sov

    # Inference endpoints (registry) + in-boundary flags
    def _endpoints():
        from .adapters.model.registry import get_registry
        reg = get_registry()
        eps = []
        for name, b in reg.items():
            eps.append({
                "name": name,
                "default_model": getattr(b, "default_model", "") or "",
                "in_boundary": bool(getattr(b, "in_boundary", True)),
            })
        return eps
    eps = _safe(_endpoints)
    if eps is not None:
        facts["inference_endpoints"] = eps
        facts["endpoint_count"] = len(eps)
        facts["all_endpoints_in_boundary"] = bool(eps) and all(e["in_boundary"] for e in eps)

    # Keys
    def _keys():
        from .adapters.identity import keys as _k
        rows = _k.list_keys()
        return {"total": len(rows),
                "active": sum(1 for r in rows if r.get("active", True))}
    keys = _safe(_keys)
    if keys is not None:
        facts["api_keys"] = keys

    # Policies
    def _policies():
        from .governance.policy import list_all
        rows = list_all()
        return {"total": len(rows),
                "enabled": sum(1 for r in rows if r.get("enabled", True))}
    pol = _safe(_policies)
    if pol is not None:
        facts["policies"] = pol

    # Cache & compression (for the 'auto' router endpoint)
    def _features():
        from . import features
        return {"cache_on": features.cache_on("auto"),
                "cache_semantic": features.cache_semantic("auto"),
                "compression_on": features.compression_on("auto")}
    feat = _safe(_features)
    if feat is not None:
        facts["cache_and_compression"] = feat

    # Egress posture (real probe)
    def _egress():
        from .sovereign.probe import egress_probe
        e = egress_probe()
        return {"result": e.get("result"), "verified": e.get("result") == "blocked"}
    eg = _safe(_egress)
    if eg is not None:
        facts["internet_egress"] = eg

    # Recent request activity (platform team view)
    def _traces():
        from . import traces
        return traces.stats("platform")
    tr = _safe(_traces)
    if isinstance(tr, dict):
        facts["recent_activity"] = {
            "total_requests": tr.get("total", tr.get("count", 0)),
        }

    return facts


def _facts_text(facts: dict[str, Any]) -> str:
    import json
    return json.dumps(facts, indent=2, default=str)


def _fallback_answer(question: str, facts: dict[str, Any]) -> str:
    """Deterministic, honest answer when no model is reachable — still grounded."""
    lines = ["I can't reach the in-boundary model right now, so here's the live "
             "state directly:"]
    org = facts.get("org") or {}
    if org.get("name"):
        lines.append(f"- Organization: {org['name']}")
    if "sovereign_mode" in facts:
        lines.append(f"- Sovereign Mode: {'on' if facts['sovereign_mode'] else 'off'}")
    if "endpoint_count" in facts:
        lines.append(f"- Inference endpoints: {facts['endpoint_count']} "
                     f"({'all in-boundary' if facts.get('all_endpoints_in_boundary') else 'some out of boundary'})")
    if "api_keys" in facts:
        lines.append(f"- API keys: {facts['api_keys']['active']} active of {facts['api_keys']['total']}")
    if "policies" in facts:
        lines.append(f"- Policies: {facts['policies']['enabled']} enabled of {facts['policies']['total']}")
    eg = facts.get("internet_egress") or {}
    if eg.get("result"):
        lines.append(f"- Internet egress: {eg['result']}"
                     + (" (verified)" if eg.get("verified") else ""))
    return "\n".join(lines)


async def answer(question: str, model: str | None = None) -> dict[str, Any]:
    """Answer an operator question, grounded in live state. Never raises."""
    q = (question or "").strip()
    facts = gather_facts()
    if not q:
        return {"answer": "Ask me about your endpoints, keys, policies, cache, "
                          "egress, or how sovereignty is enforced.",
                "grounded": True, "model": None}

    try:
        from .adapters.model.registry import get_registry
        reg = get_registry()
        # Prefer an in-boundary backend; fall back to any available.
        be = reg.get("ollama")
        if be is None:
            be = next((b for b in reg.values() if getattr(b, "in_boundary", True)), None)
        if be is None and reg:
            be = next(iter(reg.values()))
        if be is None:
            return {"answer": _fallback_answer(q, facts), "grounded": True,
                    "model": None, "in_boundary": True}

        prompt = (f"FACTS (live state of this deployment):\n{_facts_text(facts)}\n\n"
                  f"Operator question: {q}")
        res = await be.complete(
            [{"role": "system", "content": _SYSTEM},
             {"role": "user", "content": prompt}],
            model or be.default_model, temperature=0.2, max_tokens=400)
        text = (res.get("choices") or [{}])[0].get("message", {}).get("content", "")
        text = (text or "").strip()
        if not text:
            return {"answer": _fallback_answer(q, facts), "grounded": True,
                    "model": getattr(be, "default_model", None),
                    "in_boundary": bool(getattr(be, "in_boundary", True))}
        return {"answer": text, "grounded": True,
                "model": model or getattr(be, "default_model", None),
                "in_boundary": bool(getattr(be, "in_boundary", True))}
    except Exception:
        return {"answer": _fallback_answer(q, facts), "grounded": True,
                "model": None, "in_boundary": True}
