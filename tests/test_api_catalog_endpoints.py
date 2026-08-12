"""Phase 15 · Group 1 — providers + model catalog endpoints (in-boundary reads)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
ADMIN = {"Authorization": "Bearer dev-admin"}


def test_providers_list_shape():
    r = client.get("/v1/providers", headers=ADMIN)
    assert r.status_code == 200
    data = r.json()["data"]
    ids = {p["provider"] for p in data}
    assert {"ollama", "hf", "vllm", "neysa", "openai-compatible"} <= ids
    hf = next(p for p in data if p["provider"] == "hf")
    assert hf["requires_egress_approval"] is True
    assert any(f["field"] == "api_key" and f.get("secret") for f in hf["config_schema"])


def test_provider_detail_includes_catalog_models():
    r = client.get("/v1/providers/ollama", headers=ADMIN)
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "ollama"
    assert any(m["id"] == "llama3.2:3b" for m in body["models"])
    assert client.get("/v1/providers/nope", headers=ADMIN).status_code == 404


def test_catalog_models_filters():
    r = client.get("/v1/catalog/models", headers=ADMIN)
    assert r.status_code == 200 and len(r.json()["data"]) >= 5
    chats = client.get("/v1/catalog/models?mode=chat", headers=ADMIN).json()["data"]
    assert chats and all(m["mode"] == "chat" for m in chats)
    hf = client.get("/v1/catalog/models?provider=hf", headers=ADMIN).json()["data"]
    assert hf and all(m["provider"] == "hf" for m in hf)


def test_catalog_requires_auth():
    # PRECEPTA_REQUIRE_AUTH defaults off, but the catalog endpoints enforce it.
    assert client.get("/v1/providers").status_code == 401
    assert client.get("/v1/catalog/models").status_code == 401
