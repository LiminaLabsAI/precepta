"""Vendor licensing service — onboarding, key issuance, heartbeat receiver, admin.

Run: `uvicorn licensing.service:app`. This is the VENDOR control server (its own
DB + the private signing key); it is NOT the sovereign self-host image.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from . import google, keys, store

ROOT = Path(__file__).parent
REPO_URL = os.environ.get("PRECEPTA_REPO_URL", "https://github.com/LiminaLabsAI/precepta.git")


def install_steps() -> list[dict]:
    """The copy-paste self-host runbook shown after sign-in (mirrors deploy/)."""
    return [
        {"n": 1, "title": "Get Precepta", "cmd": f"git clone {REPO_URL} && cd precepta"},
        {"n": 2, "title": "Set your details", "cmd": "cp deploy/.env.example deploy/.env"},
        {"n": 3, "title": "Start it (sealed, in-boundary)", "cmd": "./deploy/up.sh"},
        {"n": 4, "title": "Open the Console", "cmd": "open http://127.0.0.1:8000"},
    ]


def _require_admin(request: Request):
    want = os.environ.get("LICENSE_ADMIN_TOKEN", "dev-admin")
    auth = request.headers.get("Authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    if token != want:
        return JSONResponse({"error": {"message": "admin token required",
                             "type": "unauthenticated"}}, status_code=401)
    return None


def create_app() -> FastAPI:
    app = FastAPI(title="precepta licensing", summary="Onboarding + license issuance (vendor).")

    @app.get("/health")
    def health():
        return {"status": "ok", "dev_signing_key": keys.using_dev_key()}

    # ── onboarding ──────────────────────────────────────────────────────────
    @app.get("/onboard/config")
    def onboard_config():
        # the onboarding page needs the (public) Google client id for GIS
        return {"google_client_id": os.environ.get("GOOGLE_CLIENT_ID", "")}

    @app.post("/onboard")
    async def onboard(request: Request):
        body = await request.json()
        credential = body.get("credential") or body.get("id_token") or ""
        try:
            who = google.verify_id_token(credential)
        except google.GoogleAuthError as exc:
            return JSONResponse({"error": {"message": str(exc), "type": "unauthenticated"}},
                                status_code=401)
        store.record_login(who["sub"], who["email"], who["name"])
        lic = store.create_or_get_trial(who["email"])
        return JSONResponse({
            "subject": lic["subject"], "license_id": lic["license_id"],
            "plan": lic["plan"], "expires_at": lic["expires_at"],
            "key": lic["token"], "name": who["name"], "steps": install_steps(),
        })

    # ── heartbeat receiver (metadata only) ───────────────────────────────────
    @app.post("/license/heartbeat")
    async def heartbeat(request: Request):
        body = await request.json()
        try:
            return JSONResponse(store.record_heartbeat(body))
        except ValueError as exc:
            return JSONResponse({"error": {"message": str(exc), "type": "invalid_request"}},
                                status_code=400)

    # ── admin (owner-gated) ──────────────────────────────────────────────────
    @app.get("/admin/logins")
    def admin_logins(request: Request):
        return _require_admin(request) or JSONResponse({"data": store.list_logins()})

    @app.get("/admin/licenses")
    def admin_licenses(request: Request):
        return _require_admin(request) or JSONResponse({"data": store.list_licenses()})

    @app.get("/admin/installs")
    def admin_installs(request: Request):
        return _require_admin(request) or JSONResponse({"data": store.list_installs()})

    @app.post("/admin/licenses/{license_id}/plan")
    async def admin_set_plan(license_id: str, request: Request):
        err = _require_admin(request)
        if err:
            return err
        body = await request.json()
        plan = "subscription" if str(body.get("plan", "")).lower() == "subscription" else "trial"
        days = body.get("days")
        row = store.set_plan(license_id, plan, int(days) if days else None)
        if row is None:
            return JSONResponse({"error": {"message": "not found", "type": "not_found"}},
                                status_code=404)
        return JSONResponse({"ok": True, "license": row})

    @app.post("/admin/licenses/{license_id}/revoke")
    def admin_revoke(license_id: str, request: Request):
        err = _require_admin(request)
        if err:
            return err
        if not store.revoke(license_id):
            return JSONResponse({"error": {"message": "not found", "type": "not_found"}},
                                status_code=404)
        return JSONResponse({"ok": True, "license_id": license_id, "revoked": True})

    @app.get("/admin", response_class=HTMLResponse)
    def admin_dashboard(request: Request):
        err = _require_admin(request)
        if err:
            return HTMLResponse("<h1>401 — admin token required</h1>", status_code=401)
        return HTMLResponse(_admin_html())

    # ── onboarding site (Group 2 fills in site/index.html) ───────────────────
    @app.get("/", response_class=HTMLResponse)
    def site_root():
        f = ROOT / "site" / "index.html"
        if f.exists():
            return HTMLResponse(f.read_text(encoding="utf-8"),
                                headers={"Cache-Control": "no-store"})
        return HTMLResponse("<h1>Precepta — onboarding site (coming in Group 2)</h1>")

    return app


def _admin_html() -> str:
    # Minimal owner dashboard; fetches JSON with the admin token entered in the box.
    return """<!doctype html><meta charset=utf-8><title>Precepta licensing — admin</title>
<style>body{font:14px system-ui;margin:24px;color:#111}h1{font-size:20px}
input{padding:6px 10px;border:1px solid #ccc;border-radius:6px;width:280px}
button{padding:6px 12px;border:1px solid #ccc;border-radius:6px;background:#fff;cursor:pointer}
table{border-collapse:collapse;margin:10px 0;width:100%}td,th{border:1px solid #eee;padding:6px 8px;text-align:left;font-size:12.5px}
h2{font-size:15px;margin-top:22px}.muted{color:#888}</style>
<h1>Precepta licensing — admin</h1>
<p>Admin token: <input id=tok placeholder="Bearer token"> <button onclick=load()>Load</button></p>
<div id=out class=muted>Enter the admin token and press Load.</div>
<script>
async function j(p){const r=await fetch(p,{headers:{Authorization:'Bearer '+document.getElementById('tok').value}});return r.ok?r.json():{data:[]}}
function tbl(rows,cols){if(!rows.length)return '<p class=muted>none</p>';return '<table><tr>'+cols.map(c=>'<th>'+c).join('')+'</tr>'+rows.map(r=>'<tr>'+cols.map(c=>'<td>'+(r[c]==null?'':String(r[c]))).join('')+'</tr>').join('')+'</table>'}
async function load(){
 const [lg,lc,ins]=await Promise.all([j('/admin/logins'),j('/admin/licenses'),j('/admin/installs')]);
 document.getElementById('out').innerHTML =
  '<h2>Logins ('+lg.data.length+')</h2>'+tbl(lg.data,['email','name','login_count','last_seen'])+
  '<h2>Licenses ('+lc.data.length+')</h2>'+tbl(lc.data,['subject','plan','status','expires_at','revoked','license_id'])+
  '<h2>Installs ('+ins.data.length+')</h2>'+tbl(ins.data,['install_id','license_id','plan','version','heartbeat_count','last_seen']);
}
</script>"""


app = create_app()
