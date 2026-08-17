"""Phase 16 · Group 2 — the onboarding site (served by the vendor backend)."""
from __future__ import annotations

import importlib

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("LICENSE_DB", str(tmp_path / "lic.db"))
    import licensing.service as svc
    importlib.reload(svc)
    return TestClient(svc.app)


def test_root_serves_onboarding_page(client):
    html = client.get("/").text
    assert "Get Precepta" in html
    assert "accounts.google.com/gsi/client" in html          # Google Sign-In library
    assert '/onboard/config' in html and '"/onboard"' in html or "/onboard" in html
    assert "steps" in html and "Copy" in html                # install steps + copy buttons
    assert "notconfigured" in html                           # honest not-configured state


def test_onboard_config_exposes_public_client_id(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid.apps.googleusercontent.com")
    import licensing.service as svc
    importlib.reload(svc)
    c = TestClient(svc.app)
    assert c.get("/onboard/config").json()["google_client_id"] == "cid.apps.googleusercontent.com"
