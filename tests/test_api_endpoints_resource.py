"""Phase 15 · Group 2 — /v1/endpoints resource (rename + aliases), auth matrix,
and enriched /v1/models."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.adapters.identity.keys import issue_key, revoke_key

client = TestClient(app)
ADMIN = {"Authorization": "Bearer dev-admin"}


def _key(**kw):
    kid, token = issue_key(expires_in_days=None, **kw)
    return kid, {"Authorization": f"Bearer {token}"}


def test_list_endpoints_auth_matrix():
    # manage read-only key can read; inference key cannot; anonymous is 401.
    ro_id, ro = _key(name="ro", scope="manage", manage_write=False)
    inf_id, inf = _key(name="inf")
    try:
        assert client.get("/v1/endpoints", headers=ADMIN).status_code == 200
        assert client.get("/v1/endpoints", headers=ro).status_code == 200
        assert client.get("/v1/endpoints", headers=inf).status_code == 403
        assert client.get("/v1/endpoints").status_code == 401
    finally:
        revoke_key(ro_id); revoke_key(inf_id)


def test_enriched_models_have_catalog_fields():
    data = client.get("/v1/models").json()["data"]   # /v1/models stays open (OpenAI-compat)
    ollama = next((m for m in data if m["id"].startswith("ollama")), None)
    assert ollama is not None
    assert ollama["mode"] == "chat"
    assert ollama["catalog_matched"] is True
    assert "capabilities" in ollama and "pricing" in ollama


def test_endpoints_alias_back_compat():
    # register via the NEW /v1/endpoints path; then it's visible + deletable via either.
    body = {"provider": "g2-test", "base_url": "http://x.invalid/v1",
            "model": "llama3.2:3b", "in_boundary": True}
    try:
        r = client.post("/v1/endpoints", headers=ADMIN, json=body)
        assert r.status_code == 201 and r.json()["provider"] == "g2-test"
        ids = {e["id"] for e in client.get("/v1/endpoints", headers=ADMIN).json()["data"]}
        assert "g2-test" in ids
        # the OLD /v1/backends path still works (alias) for delete
        assert client.delete("/v1/backends/g2-test", headers=ADMIN).status_code == 200
    finally:
        client.delete("/v1/endpoints/g2-test", headers=ADMIN)


def test_manage_write_key_can_register_endpoint():
    kid, rw = _key(name="rw", scope="manage", manage_write=True)
    try:
        r = client.post("/v1/endpoints", headers=rw,
                        json={"provider": "g2-rw", "base_url": "http://x.invalid/v1"})
        assert r.status_code == 201
    finally:
        client.delete("/v1/endpoints/g2-rw", headers=ADMIN)
        revoke_key(kid)


def test_owner_can_issue_management_key_via_api():
    r = client.post("/v1/keys", headers=ADMIN,
                    json={"name": "mgmt-via-api", "scope": "manage", "manage_write": True})
    assert r.status_code in (200, 201)
    token = r.json().get("token") or r.json().get("key")
    assert token
    from app.adapters.identity.keys import get_api_identity, list_keys, revoke_key
    p = get_api_identity().authenticate(token)
    assert p.scope == "manage:rw"
    # cleanup
    for k in list_keys():
        if k["name"] == "mgmt-via-api":
            revoke_key(k["id"])
