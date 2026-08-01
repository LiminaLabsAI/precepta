"""MCP server (Phase 8) — expose preceptaai to the agentic ecosystem.

A JSON-RPC (MCP) surface at POST /mcp offering governed tools:
  - chat            → governed inference (runs the full pipeline + audit)
  - list_policies   → active governance policies
  - get_attestation → the Sovereignty Attestation
  - verify_audit    → tamper-evident chain status

Every `chat` call re-enters the governed pipeline, so MCP stays inside the
sovereign loop and is fully audited — an MCP client (Cursor, Claude Desktop,
an agent) gets governed, in-boundary inference with attribution.
"""
from __future__ import annotations

import json

import httpx

from . import __version__
from .settings import get_settings
from .adapters.model.registry import get_registry
from .router import is_auto, parse_intent, resolve, RouteError
from .router.brain import get_brain
from .router import engine
from .gateway.pipeline import governed_chat
from .governance import policy as policy_store
from .sovereign.attestation import build_attestation
from .adapters.audit.chain import get_chain

PROTOCOL_VERSION = "2024-11-05"

MCP_TOOLS = [
    {"name": "chat",
     "description": "Run a governed, in-boundary chat completion. Every call is "
                    "policy-checked, PII-firewalled and tamper-evidently audited.",
     "inputSchema": {"type": "object",
                     "properties": {"prompt": {"type": "string"},
                                    "model": {"type": "string",
                                              "description": "e.g. ollama/llama3.2:3b or auto:cheapest"},
                                    "max_tokens": {"type": "integer"}},
                     "required": ["prompt"]}},
    {"name": "list_policies", "description": "List active governance policies.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_attestation", "description": "Get the Sovereignty Attestation (proof of a closed loop).",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "verify_audit", "description": "Verify the tamper-evident audit chain.",
     "inputSchema": {"type": "object", "properties": {}}},
]


def _text(s: str, is_error: bool = False) -> dict:
    out = {"content": [{"type": "text", "text": s}]}
    if is_error:
        out["isError"] = True
    return out


def _make_run_inference(model_str: str, kw: dict, reg: dict, settings):
    async def run_inference(msgs, route_ctx=None):
        allowed = (route_ctx or {}).get("allowed_backends")
        if is_auto(model_str):
            intent = parse_intent(model_str)
            brain = get_brain("rules", get_registry)
            query = next((m.get("content", "") for m in reversed(msgs)
                          if m.get("role") == "user"), "")
            plan = brain.decide(query, intent, allowed=allowed)
            result, meta = await engine.execute(plan, msgs, reg, settings, budget_usd=None,
                                                allowed=allowed, **kw)
            used = reg.get(meta["backend_used"])
            return result, {"backend_used": meta["backend_used"],
                            "in_boundary": bool(used and used.in_boundary),
                            "route_mode": intent, "technique": meta["technique"], "model": model_str}
        backend, model = resolve(model_str, reg)
        result = await backend.complete(msgs, model,
                                        **{k: v for k, v in kw.items() if v is not None})
        return result, {"backend_used": backend.name, "in_boundary": backend.in_boundary,
                        "route_mode": "explicit", "technique": "passthrough", "model": model_str}
    return run_inference


async def _call_tool(name: str, args: dict, principal) -> dict:
    reg = get_registry()
    settings = get_settings()

    if name == "chat":
        prompt = args.get("prompt", "")
        model = args.get("model") or "auto:cheapest"
        kw = {"max_tokens": args.get("max_tokens")}
        messages = [{"role": "user", "content": prompt}]
        run_inf = _make_run_inference(model, kw, reg, settings)
        try:
            status, payload = await governed_chat(messages, kw, principal, False, run_inf)
        except (RouteError, LookupError, httpx.HTTPError) as exc:
            return _text(f"error: {exc}", is_error=True)
        if status != 200:
            msg = payload.get("error", {}).get("message", "blocked")
            return _text(f"blocked by governance: {msg}", is_error=True)
        content = payload["choices"][0]["message"]["content"]
        p = payload.get("precepta", {})
        meta = f"\n\n[via {p.get('backend_used')} · policy: {p.get('policy_decision')} · audit {str(p.get('audit_id') or '')[:8]}]"
        return _text(content + meta)

    if name == "list_policies":
        pols = [{"name": x["name"], "effect": x["effect"], "enabled": bool(x["enabled"])}
                for x in policy_store.list_all()]
        return _text(json.dumps(pols, indent=2))

    if name == "get_attestation":
        return _text(json.dumps(build_attestation(settings, reg), indent=2))

    if name == "verify_audit":
        ch = get_chain()
        return _text(json.dumps({"verified": ch.verify(), "events": ch.count()}))

    return _text(f"unknown tool: {name}", is_error=True)


async def handle(body: dict, principal) -> dict:
    """Dispatch one JSON-RPC / MCP message."""
    method = body.get("method")
    params = body.get("params") or {}
    rid = body.get("id")

    def ok(r):
        return {"jsonrpc": "2.0", "id": rid, "result": r}

    def err(code, msg):
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": msg}}

    if method == "initialize":
        return ok({"protocolVersion": PROTOCOL_VERSION,
                   "capabilities": {"tools": {}},
                   "serverInfo": {"name": "preceptaai", "version": __version__}})
    if method == "tools/list":
        return ok({"tools": MCP_TOOLS})
    if method == "tools/call":
        return ok(await _call_tool(params.get("name"), params.get("arguments") or {}, principal))
    if method in ("notifications/initialized", "ping"):
        return ok({})
    return err(-32601, f"method not found: {method}")
