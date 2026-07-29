"""Validation — SSO login sessions (the Google-login last mile)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.adapters.identity.session import create_session, SessionIdentity, revoke_session
from app.ports import Principal

client = TestClient(app)


def test_session_roundtrip():
    tok = create_session(Principal("g@gmail.com", "user", "G User", "sales"))
    try:
        p = SessionIdentity().authenticate(tok)
        assert p is not None
        assert p.subject == "g@gmail.com" and p.team == "sales" and p.display_name == "G User"
        assert tok.startswith("ps-")
    finally:
        revoke_session(tok)
    assert SessionIdentity().authenticate(tok) is None    # revoked


def test_session_token_authenticates_and_logout():
    tok = create_session(Principal("123.sarang@gmail.com", "admin", "Sarang", ""))
    # a session token authenticates API calls as the Google user
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    assert r.json()["subject"] == "123.sarang@gmail.com" and r.json()["role"] == "admin"
    # logout revokes it
    assert client.post("/auth/logout", headers={"Authorization": f"Bearer {tok}"}).status_code == 200
    r2 = client.get("/auth/me", headers={"Authorization": f"Bearer {tok}"})
    assert r2.status_code == 401


def test_bad_session_token_401():
    r = client.get("/auth/me", headers={"Authorization": "Bearer ps-not-a-real-session"})
    assert r.status_code == 401
