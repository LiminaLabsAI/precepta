"""Enterprise SSO via OIDC (Phase 8) — IdentityPort adapter.

Uses OIDC discovery (`/.well-known/openid-configuration`) so it works with real
providers (Google, Okta, Azure AD) whose endpoints are not the conventional
`/authorize` `/token` `/userinfo`. Config comes from env (OIDC_ISSUER,
OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, OIDC_REDIRECT). Turning it on needs the
customer's IdP credentials (owner action); until configured, `status()` reports
"not configured" and the Console reflects that honestly (no fake login).
"""
from __future__ import annotations

import os
from urllib.parse import urlencode

import httpx

from ...ports import Principal

_discovery: dict[str, dict] = {}


def _cfg() -> dict:
    return {
        "issuer": os.environ.get("OIDC_ISSUER", ""),
        "client_id": os.environ.get("OIDC_CLIENT_ID", ""),
        "client_secret": os.environ.get("OIDC_CLIENT_SECRET", ""),
        "redirect": os.environ.get("OIDC_REDIRECT", "http://127.0.0.1:8000/auth/sso/callback"),
    }


def is_configured() -> bool:
    c = _cfg()
    return bool(c["issuer"] and c["client_id"] and c["client_secret"])


def status() -> dict:
    c = _cfg()
    return {"configured": is_configured(),
            "issuer": c["issuer"] or None,
            "redirect": c["redirect"]}


def discover(issuer: str) -> dict:
    """Resolve the provider's endpoints via OIDC discovery (cached)."""
    issuer = issuer.rstrip("/")
    if issuer in _discovery:
        return _discovery[issuer]
    try:
        r = httpx.get(issuer + "/.well-known/openid-configuration", timeout=5.0)
        d = r.json()
        conf = {"authorization_endpoint": d["authorization_endpoint"],
                "token_endpoint": d["token_endpoint"],
                "userinfo_endpoint": d.get("userinfo_endpoint", issuer + "/userinfo")}
    except (httpx.HTTPError, KeyError, ValueError):
        conf = {"authorization_endpoint": issuer + "/authorize",
                "token_endpoint": issuer + "/token",
                "userinfo_endpoint": issuer + "/userinfo"}
    _discovery[issuer] = conf
    return conf


def authorize_url(state: str = "precepta") -> str:
    c = _cfg()
    ep = discover(c["issuer"])["authorization_endpoint"]
    q = urlencode({"response_type": "code", "client_id": c["client_id"],
                   "redirect_uri": c["redirect"], "scope": "openid email profile",
                   "state": state})
    return f"{ep}?{q}"


async def exchange_code(code: str, *, http_post=None, http_get=None) -> Principal | None:
    """Exchange an auth code for tokens and return a Principal from userinfo.

    `http_post`/`http_get` are injectable for testing without a live IdP.
    """
    c = _cfg()
    if http_post is not None and http_get is not None:      # test path
        tr = await http_post("token", data={"code": code})
        access = tr.json().get("access_token")
        ur = await http_get("userinfo", headers={"Authorization": f"Bearer {access}"})
        return principal_from_userinfo(ur.json())

    conf = discover(c["issuer"])
    async with httpx.AsyncClient(timeout=10.0) as client:
        tr = await client.post(conf["token_endpoint"], data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": c["redirect"], "client_id": c["client_id"],
            "client_secret": c["client_secret"]})
        access = tr.json().get("access_token")
        ur = await client.get(conf["userinfo_endpoint"],
                              headers={"Authorization": f"Bearer {access}"})
        return principal_from_userinfo(ur.json())


def _admin_emails() -> set[str]:
    """Emails granted admin, from PRECEPTA_ADMIN_EMAILS (comma-separated)."""
    return {e.strip().lower()
            for e in os.environ.get("PRECEPTA_ADMIN_EMAILS", "").split(",") if e.strip()}


def principal_from_userinfo(info: dict) -> Principal | None:
    email = info.get("email") or info.get("sub")
    if not email:
        return None
    role = info.get("precepta_role") or "user"          # map an IdP claim → role
    if email.lower() in _admin_emails():                # admin allowlist wins
        role = "admin"
    return Principal(subject=email, role=role,
                     display_name=info.get("name", email),
                     team=info.get("precepta_team", ""))
