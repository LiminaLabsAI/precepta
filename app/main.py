"""FastAPI application — the control-plane entrypoint.

Phase 0: boot, config, DB connectivity, and a real `/health`. Later phases add
`/v1/chat/completions`, `/attestation`, auth, and the governed pipeline.
"""
from __future__ import annotations

import time

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse

import os

from . import __version__
from . import db
from .settings import get_settings, ROOT
from . import org
from .governance import policy as policy_store
from .adapters.model.registry import get_registry
from .adapters.model.openai_compat import OpenAICompatBackend
from .adapters.model import store as backend_store
from .admin_ops import reset_activity
from .router import resolve, RouteError, is_auto, parse_intent
from .router.brain import get_brain
from .router import engine
from .ports import Principal, PolicyCheckContext, Decision
from .adapters.identity import get_identity
from .adapters.identity.keys import (get_api_identity, issue_key, revoke_key,
                                      list_keys, update_key, set_suspended)
from .adapters.identity.session import get_session_identity, create_session, revoke_session
from .adapters.authz import get_authz
from .adapters.audit import get_audit
from .adapters.audit.chain import get_chain
from .gateway.pipeline import governed_chat
from .sovereign import enforce_backend
from .sovereign.attestation import build_attestation
from .adapters.infra import snapshot as infra_snapshot, record_telemetry


def _resolve_principal(request: Request):
    """authN: Bearer token → principal. Returns (principal, error_response|None)."""
    auth = request.headers.get("Authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    require_auth = os.environ.get("PRECEPTA_REQUIRE_AUTH", "0").lower() in ("1", "true", "yes", "on")
    if token:
        # dev tokens → per-team API keys (Phase 7) → login sessions (SSO)
        principal = (get_identity().authenticate(token)
                     or get_api_identity().authenticate(token)
                     or get_session_identity().authenticate(token))
        if principal is None:
            return None, JSONResponse(
                {"error": {"message": "invalid token", "type": "unauthenticated"}},
                status_code=401)
        return principal, None
    if require_auth:
        return None, JSONResponse(
            {"error": {"message": "authentication required", "type": "unauthenticated"}},
            status_code=401)
    return Principal("anonymous", "user", "Anonymous"), None


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="preceptaai control plane",
        version=__version__,
        summary="Self-hosted, governed control plane for open-source AI models.",
    )

    @app.get("/health")
    def health() -> JSONResponse:
        db_health = db.health()
        ok = bool(db_health.get("ok"))
        payload = {
            "status": "ok" if ok else "degraded",
            "version": __version__,
            "sovereign_mode": settings.sovereign_mode,
            "db": db_health,
        }
        return JSONResponse(payload, status_code=200 if ok else 503)

    @app.get("/")
    def root() -> RedirectResponse:
        # The base URL opens the Console UI. API metadata lives at /api.
        return RedirectResponse(url="/console")

    @app.get("/api")
    def api_info() -> dict:
        return {
            "name": "preceptaai",
            "version": __version__,
            "sovereign_mode": settings.sovereign_mode,
            "console": "/console",
            "docs": "/docs",
            "health": "/health",
        }

    # ── Model plane (Phase 1) ───────────────────────────────────────────
    # ── Sovereignty (Phase 4) ───────────────────────────────────────────
    @app.get("/attestation")
    def attestation(request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        if not get_authz().can(principal, "attestation.read"):
            return JSONResponse(
                {"error": {"message": "forbidden", "type": "forbidden"}}, status_code=403)
        return JSONResponse(build_attestation(settings, get_registry()))

    @app.get("/audit/verify")
    def audit_verify(request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        if not get_authz().can(principal, "audit.read"):
            return JSONResponse(
                {"error": {"message": "forbidden", "type": "forbidden"}}, status_code=403)
        chain = get_chain()
        return JSONResponse({"verified": chain.verify(), "events": chain.count()})

    # ── Infra visibility (Phase 5) ──────────────────────────────────────
    @app.get("/infra")
    def infra(request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        if not get_authz().can(principal, "audit.read"):
            return JSONResponse(
                {"error": {"message": "forbidden", "type": "forbidden"}}, status_code=403)
        return JSONResponse({"backends": infra_snapshot(get_registry())})

    @app.get("/audit/log")
    def audit_log(request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        if not get_authz().can(principal, "audit.read"):
            return JSONResponse(
                {"error": {"message": "forbidden", "type": "forbidden"}}, status_code=403)
        import json as _json
        import datetime as _dt
        limit = int(request.query_params.get("limit", 25))
        outcome_label = {"block": "blocked", "warn": "warned", "allow": "allowed"}
        rows = []
        for r in get_chain().recent(limit=limit):
            try:
                meta = _json.loads(r.get("metadata") or "{}")
            except (ValueError, TypeError):
                meta = {}
            try:
                t = _dt.datetime.fromtimestamp(
                    r["timestamp"] / 1e9, _dt.UTC).strftime("%d %b, %H:%M:%S")
            except (ValueError, TypeError, OSError):
                t = str(r["timestamp"])
            rows.append({
                "time": t,
                "actor": r.get("actor") or "—",
                "event": r.get("resource") or "—",
                "backend": meta.get("backend") or "—",
                "outcome": outcome_label.get(r.get("action"), r.get("action") or "allowed"),
                "hash": (r.get("event_hash") or "")[:10] + "…",
            })
        return JSONResponse({"log": rows})

    # ── Policies CRUD (Phase 6 — for the Console) ───────────────────────
    @app.get("/v1/policies")
    def get_policies(request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        pols = [
            {"id": p["id"], "name": p["name"], "description": p.get("description"),
             "enabled": bool(p["enabled"]), "action_type": p["action_type"],
             "effect": p["effect"], "conditions": p.get("conditions", {}),
             "scope": p.get("scope", {}), "version": p.get("version", 1)}
            for p in policy_store.list_all()
        ]
        return JSONResponse({"policies": pols})

    @app.post("/v1/policies")
    async def create_policy(request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        if not get_authz().can(principal, "policy.update"):
            return JSONResponse(
                {"error": {"message": "forbidden", "type": "forbidden"}}, status_code=403)
        b = await request.json()
        pid = policy_store.create_policy(
            b.get("name", ""), b.get("description", ""), b.get("action_type", "*"),
            b.get("effect", "audit"), b.get("conditions", {}) or {},
            scope=b.get("scope", {}) or {})
        return JSONResponse({"id": pid}, status_code=201)

    @app.put("/v1/policies/{pid}")
    async def edit_policy(pid: str, request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        if not get_authz().can(principal, "policy.update"):
            return JSONResponse(
                {"error": {"message": "forbidden", "type": "forbidden"}}, status_code=403)
        b = await request.json()
        fields = {k: b[k] for k in ("name", "description", "action_type", "effect",
                                    "conditions", "scope") if k in b}
        ver = policy_store.update_policy(pid, **fields)
        if ver is None:
            return JSONResponse(
                {"error": {"message": "not found", "type": "not_found"}}, status_code=404)
        return JSONResponse({"id": pid, "version": ver})

    @app.post("/v1/policies/{pid}/toggle")
    def toggle_policy(pid: str, request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        if not get_authz().can(principal, "policy.update"):
            return JSONResponse(
                {"error": {"message": "forbidden", "type": "forbidden"}}, status_code=403)
        new_val = policy_store.toggle_policy(pid)
        if new_val is None:
            return JSONResponse(
                {"error": {"message": "not found", "type": "not_found"}}, status_code=404)
        return JSONResponse({"id": pid, "enabled": bool(new_val)})

    # ── Backends: runtime registration (from onboarding / Add-backend) ──
    @app.get("/stats")
    def stats(request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        if not get_authz().can(principal, "audit.read"):
            return JSONResponse(
                {"error": {"message": "forbidden", "type": "forbidden"}}, status_code=403)
        import datetime as _dt
        now = _dt.datetime.now(_dt.UTC)
        day_ago = (now - _dt.timedelta(hours=24)).isoformat()
        start_today = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        with db.get_conn() as conn:
            req = conn.execute(
                "SELECT COUNT(*) n FROM audit_log WHERE action_type='chat.completion' "
                "AND execution_blocked=0 AND timestamp>=?", (day_ago,)).fetchone()["n"]
            blocks = conn.execute(
                "SELECT COUNT(*) n FROM audit_log WHERE execution_blocked=1 "
                "AND timestamp>=?", (start_today,)).fetchone()["n"]
            # real avg cost/req: telemetry stores the serving backend in agent_id
            tele = conn.execute(
                "SELECT agent_id AS backend, tokens_input, tokens_output FROM telemetry "
                "WHERE captured_at>=?", (day_ago,)).fetchall()
        from . import pricing
        total_cost = sum(
            pricing.cost_of(t["backend"] or "", "", t["tokens_input"] or 0,
                            t["tokens_output"] or 0) for t in tele)
        avg_cost = round(total_cost / len(tele), 6) if tele else 0.0
        return JSONResponse({"requests_24h": req, "external_calls": 0,
                             "blocks_today": blocks, "avg_cost_usd": avg_cost})

    @app.get("/v1/pricing")
    def get_pricing(request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        from . import pricing
        return JSONResponse({"prices": pricing.list_prices()})

    @app.post("/v1/pricing")
    async def set_pricing(request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        if not get_authz().can(principal, "policy.update"):
            return JSONResponse(
                {"error": {"message": "forbidden", "type": "forbidden"}}, status_code=403)
        b = await request.json()
        backend = (b.get("backend") or "").strip()
        if not backend:
            return JSONResponse({"error": {"message": "backend required",
                                 "type": "invalid_request_error"}}, status_code=400)
        try:
            pin = float(b.get("input_per_1m", 0) or 0)
            pout = float(b.get("output_per_1m", 0) or 0)
        except (TypeError, ValueError):
            return JSONResponse({"error": {"message": "prices must be numbers",
                                 "type": "invalid_request_error"}}, status_code=400)
        from . import pricing
        row = pricing.upsert_price(
            backend, (b.get("model") or "").strip(), pin, pout,
            source=(b.get("source") or "").strip(),
            effective_date=(b.get("effective_date") or None),
            created_by=principal.subject)
        return JSONResponse({"ok": True, "price": row}, status_code=201)

    @app.get("/v1/usage")
    def get_usage(request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        from . import budgets as _b
        from .adapters.identity import keys as _k
        rows = []
        for key in _k.list_keys():
            sp = _b.spend(key["name"])
            rows.append({"key": key["name"], "team": key.get("team") or "",
                         "active": key.get("active", True),
                         "spent_day": sp["day"], "spent_month": sp["month"],
                         "cap_day": key.get("cost_cap_daily") or 0,
                         "cap_month": key.get("cost_cap_monthly") or 0})
        return JSONResponse({"usage": rows})

    @app.post("/v1/backends")
    async def register_backend(request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        if not get_authz().can(principal, "policy.update"):
            return JSONResponse(
                {"error": {"message": "forbidden", "type": "forbidden"}}, status_code=403)
        b = await request.json()
        provider = (b.get("provider") or "").strip()
        base_url = (b.get("base_url") or "").strip()
        if not provider or not base_url:
            return JSONResponse(
                {"error": {"message": "provider and base_url required",
                           "type": "invalid_request_error"}}, status_code=400)
        backend = OpenAICompatBackend(
            provider, base_url,
            in_boundary=bool(b.get("in_boundary", True)),
            api_key=(b.get("api_key") or None),
            default_model=(b.get("model") or "").strip(),
        )
        get_registry()[provider] = backend                       # live registry
        backend_store.save_backend(                               # + persist (survives restart)
            provider, base_url, b.get("api_key") or None,
            (b.get("model") or "").strip(), bool(b.get("in_boundary", True)))
        return JSONResponse({"ok": True, "provider": provider,
                             "healthy": backend.health()}, status_code=201)

    @app.delete("/v1/backends/{provider}")
    def remove_backend(provider: str, request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        if not get_authz().can(principal, "policy.update"):
            return JSONResponse(
                {"error": {"message": "forbidden", "type": "forbidden"}}, status_code=403)
        reg = get_registry()
        existed = provider in reg
        reg.pop(provider, None)
        persisted = backend_store.delete_backend(provider)
        if not existed and not persisted:
            return JSONResponse(
                {"error": {"message": "not found", "type": "not_found"}}, status_code=404)
        return JSONResponse({"ok": True, "provider": provider})

    @app.post("/admin/reset")
    def admin_reset(request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        if not get_authz().can(principal, "policy.update"):   # admin-only
            return JSONResponse(
                {"error": {"message": "forbidden", "type": "forbidden"}}, status_code=403)
        return JSONResponse({"ok": True, "cleared": reset_activity()})

    # ── Per-team API keys (Phase 7) ─────────────────────────────────────
    @app.get("/v1/keys")
    def get_keys(request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        if not get_authz().can(principal, "policy.update"):   # admin-only
            return JSONResponse(
                {"error": {"message": "forbidden", "type": "forbidden"}}, status_code=403)
        return JSONResponse({"keys": list_keys()})

    @app.post("/v1/keys")
    async def create_key(request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        if not get_authz().can(principal, "policy.update"):
            return JSONResponse(
                {"error": {"message": "forbidden", "type": "forbidden"}}, status_code=403)
        b = await request.json()
        name = (b.get("name") or "").strip()
        if not name:
            return JSONResponse(
                {"error": {"message": "name required", "type": "invalid_request_error"}},
                status_code=400)
        role = "user"   # keys are app-level credentials — admin is human-only (Console/SSO)
        team = (b.get("team") or "").strip()
        # expiry (FEAT-001): default 90 days; 0/None/"never" = never expires
        exp_raw = b.get("expires_in_days", 90)
        try:
            expires_in_days = None if exp_raw in (None, 0, "never", "0") else int(exp_raw)
        except (TypeError, ValueError):
            expires_in_days = 90
        kid, token = issue_key(
            name, role, team, expires_in_days=expires_in_days,
            allowed_backends=b.get("allowed_backends") or [],
            allowed_models=b.get("allowed_models") or [],
            cost_cap_daily=b.get("cost_cap_daily") or 0,
            cost_cap_monthly=b.get("cost_cap_monthly") or 0,
            token_cap_daily=b.get("token_cap_daily") or 0,
            token_cap_monthly=b.get("token_cap_monthly") or 0)
        # the plaintext key is returned exactly once
        return JSONResponse({"id": kid, "name": name, "role": role, "team": team,
                             "key": token, "expires_in_days": expires_in_days}, status_code=201)

    @app.delete("/v1/keys/{kid}")
    def delete_key(kid: str, request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        if not get_authz().can(principal, "policy.update"):
            return JSONResponse(
                {"error": {"message": "forbidden", "type": "forbidden"}}, status_code=403)
        if not revoke_key(kid):
            return JSONResponse(
                {"error": {"message": "not found", "type": "not_found"}}, status_code=404)
        return JSONResponse({"ok": True, "id": kid, "revoked": True})

    @app.put("/v1/keys/{kid}")
    async def edit_key(kid: str, request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        if not get_authz().can(principal, "policy.update"):
            return JSONResponse(
                {"error": {"message": "forbidden", "type": "forbidden"}}, status_code=403)
        b = await request.json()
        fields = {k: b[k] for k in (
            "allowed_backends", "allowed_models", "cost_cap_daily",
            "cost_cap_monthly", "token_cap_daily", "token_cap_monthly",
            "expires_in_days") if k in b}
        if not update_key(kid, **fields):
            return JSONResponse(
                {"error": {"message": "not found or nothing to update",
                           "type": "not_found"}}, status_code=404)
        return JSONResponse({"ok": True, "id": kid})

    @app.post("/v1/keys/{kid}/suspend")
    def suspend_key_ep(kid: str, request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        if not get_authz().can(principal, "policy.update"):
            return JSONResponse({"error": {"message": "forbidden", "type": "forbidden"}}, status_code=403)
        ok = set_suspended(kid, True)
        return JSONResponse({"ok": ok, "id": kid, "suspended": True},
                            status_code=200 if ok else 404)

    @app.post("/v1/keys/{kid}/reactivate")
    def reactivate_key_ep(kid: str, request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        if not get_authz().can(principal, "policy.update"):
            return JSONResponse({"error": {"message": "forbidden", "type": "forbidden"}}, status_code=403)
        ok = set_suspended(kid, False)
        return JSONResponse({"ok": ok, "id": kid, "suspended": False},
                            status_code=200 if ok else 404)

    # ── Notifications (the bell) ───────────────────────────────────────
    @app.get("/notifications")
    def get_notifications(request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        from . import notifications as _n
        return JSONResponse({"notifications": _n.list_recent(),
                             "unread": _n.unread_count()})

    @app.post("/notifications/read")
    def read_notifications(request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        from . import notifications as _n
        _n.mark_all_read()
        return JSONResponse({"ok": True})

    # ── Organization settings (real, persisted) ────────────────────────
    @app.get("/v1/settings")
    def get_org_settings(request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        return JSONResponse(org.all_settings())

    @app.put("/v1/settings")
    async def put_org_settings(request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        if not get_authz().can(principal, "policy.update"):
            return JSONResponse(
                {"error": {"message": "forbidden", "type": "forbidden"}}, status_code=403)
        b = await request.json()
        return JSONResponse(org.update(b))

    @app.get("/auth/me")
    def whoami(request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        return JSONResponse({"subject": principal.subject, "role": principal.role,
                             "name": principal.display_name or principal.subject,
                             "team": principal.team})

    @app.get("/audit/export.csv")
    def audit_export_csv(request: Request):
        import csv
        import io
        from fastapi.responses import Response
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        if not get_authz().can(principal, "audit.read"):
            return JSONResponse(
                {"error": {"message": "forbidden", "type": "forbidden"}}, status_code=403)
        cols = ["timestamp", "action", "actor", "event", "backend", "outcome", "hash"]
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(cols)
        import datetime as _dt
        for r in get_chain().recent(limit=100000):
            try:
                import json as _json
                meta = _json.loads(r.get("metadata") or "{}")
            except (ValueError, TypeError):
                meta = {}
            try:
                t = _dt.datetime.fromtimestamp(r["timestamp"] / 1e9, _dt.UTC).isoformat()
            except (ValueError, TypeError, OSError):
                t = str(r["timestamp"])
            w.writerow([t, r.get("event_type"), r.get("actor"), r.get("resource"),
                        meta.get("backend") or "", r.get("action"), r.get("event_hash")])
        return Response(content=buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": "attachment; filename=precepta-audit.csv"})

    # ── Compliance evidence + audit export + team scopes (Phase 9) ──────
    @app.get("/compliance/report")
    def compliance_report(request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        if not get_authz().can(principal, "audit.read"):
            return JSONResponse(
                {"error": {"message": "forbidden", "type": "forbidden"}}, status_code=403)
        from .compliance import build_report
        return JSONResponse(build_report())

    @app.get("/audit/export")
    def audit_export(request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        if not get_authz().can(principal, "audit.read"):
            return JSONResponse(
                {"error": {"message": "forbidden", "type": "forbidden"}}, status_code=403)
        return JSONResponse(get_chain().export())

    @app.get("/v1/team-scopes")
    def get_team_scopes(request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        from .adapters.authz.scopes import list_scopes
        return JSONResponse({"scopes": list_scopes()})

    @app.post("/v1/team-scopes")
    async def set_team_scope(request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        if not get_authz().can(principal, "policy.update"):
            return JSONResponse(
                {"error": {"message": "forbidden", "type": "forbidden"}}, status_code=403)
        from .adapters.authz.scopes import set_scope
        b = await request.json()
        team = (b.get("team") or "").strip()
        if not team:
            return JSONResponse(
                {"error": {"message": "team required", "type": "invalid_request_error"}},
                status_code=400)
        set_scope(team, b.get("allowed_backends") or [], int(b.get("max_tokens_per_day", 0) or 0))
        return JSONResponse({"ok": True, "team": team}, status_code=201)

    # ── MCP server (Phase 8) ────────────────────────────────────────────
    @app.post("/mcp")
    async def mcp_endpoint(request: Request) -> JSONResponse:
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        from .mcp import handle
        body = await request.json()
        return JSONResponse(await handle(body, principal))

    # ── Enterprise SSO (Phase 8) — mechanism; needs real IdP config ─────
    @app.get("/auth/sso/status")
    def sso_status() -> JSONResponse:
        from .adapters.identity import sso
        return JSONResponse(sso.status())

    @app.get("/auth/sso/login")
    def sso_login() -> JSONResponse:
        from .adapters.identity import sso
        if not sso.is_configured():
            return JSONResponse(
                {"error": {"message": "SSO not configured — set OIDC_* env vars",
                           "type": "not_configured"}}, status_code=400)
        return JSONResponse({"authorize_url": sso.authorize_url()})

    @app.get("/auth/sso/callback")
    async def sso_callback(request: Request) -> JSONResponse:
        from .adapters.identity import sso
        code = request.query_params.get("code")
        if not sso.is_configured() or not code:
            return JSONResponse(
                {"error": {"message": "SSO not configured or missing code",
                           "type": "not_configured"}}, status_code=400)
        principal = await sso.exchange_code(code)
        if principal is None:
            return JSONResponse(
                {"error": {"message": "SSO login failed", "type": "unauthenticated"}},
                status_code=401)
        # mint a session and hand it to the browser (in the URL fragment, not logged),
        # landing the signed-in Google user straight in the Console.
        session = create_session(principal)
        return RedirectResponse(url=f"/console#s={session}", status_code=302)

    @app.post("/auth/logout")
    def sso_logout(request: Request) -> JSONResponse:
        auth = request.headers.get("Authorization", "")
        token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
        if token:
            revoke_session(token)
        return JSONResponse({"ok": True})

    # ── Console (Phase 6) ───────────────────────────────────────────────
    @app.get("/console", response_class=HTMLResponse)
    def console() -> HTMLResponse:
        path = ROOT / "web" / "console.html"
        if not path.exists():
            return HTMLResponse("<h1>console.html not found</h1>", status_code=404)
        # no-store so the browser never serves a stale Console (which could show mock data)
        return HTMLResponse(path.read_text(encoding="utf-8"),
                            headers={"Cache-Control": "no-store, max-age=0"})

    # Static assets for the Console (logo, etc.) — served from web/assets.
    assets_dir = ROOT / "web" / "assets"
    if assets_dir.is_dir():
        from fastapi.staticfiles import StaticFiles
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/v1/models")
    def list_models() -> dict:
        reg = get_registry()
        data = [
            {"id": f"{name}/*", "object": "model", "owned_by": name,
             "in_boundary": be.in_boundary}
            for name, be in sorted(reg.items())
        ]
        return {"object": "list", "data": data}

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> JSONResponse:
        body = await request.json()
        model_str = body.get("model") or org.get("default_model")
        messages = body.get("messages") or []
        reg = get_registry()
        kw = {"temperature": body.get("temperature"),
              "max_tokens": body.get("max_tokens"), "top_p": body.get("top_p")}

        # ── authN → authZ (gate the whole request) ──
        principal, err = _resolve_principal(request)
        if err is not None:
            return err
        if not get_authz().can(principal, "chat.completion", model_str):
            return JSONResponse(
                {"error": {"message": f"role {principal.role!r} may not run chat.completion",
                           "type": "forbidden"}}, status_code=403)

        # ── per-key cost caps + scope (FEAT-001) — only for key-authenticated callers ──
        from .adapters.identity import keys as _keys
        from . import budgets as _budgets, metering as _metering
        _key_meta = _keys.get_key_meta(principal.subject)
        if _key_meta:
            _bud = _budgets.check(principal.subject)
            if _bud["effect"] == "block":
                ctx = PolicyCheckContext(action_type="chat.completion", principal=principal)
                aid = get_audit().append_check(
                    ctx, Decision("block", _bud["reason"]),
                    tokens=body.get("max_tokens"), pii_count=0, blocked=True)
                return JSONResponse(
                    {"error": {"message": _bud["reason"], "type": "budget_exceeded"},
                     "precepta": {"policy_decision": "block", "policy_reason": _bud["reason"],
                                  "audit_id": aid, "budget": _bud.get("spend")}},
                    status_code=429)

        # explicit model must resolve, and pass Sovereign-Mode enforcement
        req_backend = req_model = None   # policy scope (FEAT-002) — known when explicit
        if not is_auto(model_str):
            try:
                backend, resolved_model = resolve(model_str, reg)
            except RouteError as exc:
                return JSONResponse(
                    {"error": {"message": str(exc), "type": "invalid_request_error"}},
                    status_code=400)
            req_backend, req_model = backend.name, model_str
            from .adapters.authz.scopes import check_backend
            reason = (enforce_backend(backend, settings)
                      or check_backend(principal, backend.name)
                      or _keys.scope_violation(principal.subject, backend.name, resolved_model))
            if reason:
                ctx = PolicyCheckContext(action_type="chat.completion", principal=principal)
                aid = get_audit().append_check(
                    ctx, Decision("block", reason), tokens=body.get("max_tokens"),
                    pii_count=0, blocked=True)
                return JSONResponse(
                    {"error": {"message": reason, "type": "policy_block"},
                     "precepta": {"policy_decision": "block", "policy_reason": reason,
                                  "audit_id": aid, "backend_used": backend.name,
                                  "in_boundary": backend.in_boundary}},
                    status_code=403)

        async def run_inference(msgs: list[dict]):
            if is_auto(model_str):
                intent = parse_intent(model_str)
                brain = get_brain(os.environ.get("PRECEPTA_BRAIN", "rules"), get_registry)
                query = next((m.get("content", "") for m in reversed(msgs)
                              if m.get("role") == "user"), "")
                plan = brain.decide(query, intent)
                result, meta = await engine.execute(
                    plan, msgs, reg, settings, budget_usd=body.get("budget_usd"), **kw)
                used = reg.get(meta["backend_used"])
                return result, {
                    "backend_used": meta["backend_used"],
                    "in_boundary": bool(used and used.in_boundary),
                    "route_mode": intent, "brain": brain.name,
                    "technique": meta["technique"], "reason": meta["reason"],
                    "fell_over": meta["fell_over"], "calls": meta["calls"],
                    "cost_estimate_usd": meta["cost_estimate_usd"], "model": model_str,
                }
            backend, model = resolve(model_str, reg)
            result = await backend.complete(
                msgs, model, temperature=kw["temperature"],
                max_tokens=kw["max_tokens"], top_p=kw["top_p"])
            return result, {
                "backend_used": backend.name, "in_boundary": backend.in_boundary,
                "route_mode": "explicit", "technique": "passthrough", "model": model_str,
            }

        t0 = time.perf_counter()
        try:
            status, payload = await governed_chat(
                messages, kw, principal, bool(body.get("data_tag")), run_inference,
                req_backend=req_backend, req_model=req_model)
        except LookupError as exc:
            return JSONResponse(
                {"error": {"message": str(exc), "type": "no_backend"}}, status_code=503)
        except httpx.HTTPError as exc:
            return JSONResponse(
                {"error": {"message": f"backend failure: {exc}",
                           "type": "backend_unavailable"}}, status_code=502)

        if status == 200:
            latency_ms = int((time.perf_counter() - t0) * 1000)
            payload["precepta"]["latency_ms"] = latency_ms
            usage = payload.get("usage") or {}
            record_telemetry(
                inference_ms=latency_ms,
                tokens_in=usage.get("prompt_tokens"),
                tokens_out=usage.get("completion_tokens"),
                backend=payload["precepta"].get("backend_used"),
            )
            # record real cost against the key's budget (FEAT-001)
            if _key_meta:
                _bk = payload["precepta"].get("backend_used") or ""
                _mm = _metering.meter(_bk, "", usage.get("prompt_tokens") or 0,
                                      usage.get("completion_tokens") or 0)
                _budgets.record_usage(principal.subject, principal.team,
                                      _mm["billable_tokens"], _mm["budget_charge_usd"])
                payload["precepta"]["budget"] = _budgets.spend(principal.subject)
        return JSONResponse(payload, status_code=status)

    # Seed the pricing source-of-truth once (idempotent) so known backends have real prices.
    try:
        from . import pricing
        pricing.seed_defaults()
    except Exception:  # pragma: no cover - never block app boot on seeding
        pass

    return app


app = create_app()
