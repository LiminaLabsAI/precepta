"""Verify a Google Sign-In (GIS) ID token server-side, so a recorded login is
real. Pluggable: tests inject `verifier`; production verifies via Google.

No extra dependency — the default verifier calls Google's tokeninfo endpoint with
httpx (already a dep). It checks the audience matches our OAuth client id and the
email is verified, then returns {sub, email, name}.
"""
from __future__ import annotations

import os

import httpx

_TOKENINFO = "https://oauth2.googleapis.com/tokeninfo"


class GoogleAuthError(Exception):
    """The Google credential could not be verified."""


def _default_verifier(credential: str) -> dict:
    try:
        r = httpx.get(_TOKENINFO, params={"id_token": credential}, timeout=10.0)
    except httpx.HTTPError as exc:
        raise GoogleAuthError(f"could not reach Google to verify sign-in ({type(exc).__name__})") from exc
    if r.status_code != 200:
        raise GoogleAuthError("Google rejected the sign-in token")
    return r.json()


def verify_id_token(credential: str, *, client_id: str | None = None,
                    verifier=None) -> dict:
    """Return {sub, email, name} for a valid Google ID token, else raise."""
    if not credential:
        raise GoogleAuthError("missing Google credential")
    client_id = client_id if client_id is not None else os.environ.get("GOOGLE_CLIENT_ID", "")
    claims = (verifier or _default_verifier)(credential)
    aud = claims.get("aud")
    if client_id and aud and aud != client_id:
        raise GoogleAuthError("Google token audience does not match this app")
    if str(claims.get("email_verified", "true")).lower() not in ("true", "1", "yes"):
        raise GoogleAuthError("Google email is not verified")
    email = claims.get("email")
    sub = claims.get("sub")
    if not (email or sub):
        raise GoogleAuthError("Google token has no email/subject")
    return {"sub": sub or email, "email": email or sub, "name": claims.get("name", email or sub)}
