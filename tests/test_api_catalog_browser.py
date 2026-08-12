"""Phase 15 — LiteLLM-style model catalog: filters, pagination, single lookup,
and the catalog-providers listing (in-boundary, from the vendored snapshot)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app import catalog

client = TestClient(app)
ADMIN = {"Authorization": "Bearer dev-admin"}


def test_catalog_has_broad_coverage():
    assert len(catalog._all()) > 1000          # vendored LiteLLM snapshot merged in
    assert len(catalog.catalog_providers()) > 50


def test_catalog_pagination_shape():
    r = client.get("/v1/catalog/models?page=1&page_size=20", headers=ADMIN)
    assert r.status_code == 200
    b = r.json()
    for k in ("data", "total_count", "has_more", "page", "page_size"):
        assert k in b
    assert len(b["data"]) == 20 and b["page"] == 1 and b["has_more"] is True
    # page 2 differs from page 1
    ids1 = {m["id"] for m in b["data"]}
    b2 = client.get("/v1/catalog/models?page=2&page_size=20", headers=ADMIN).json()
    assert ids1.isdisjoint({m["id"] for m in b2["data"]})


def test_catalog_capability_and_provider_filters():
    fc = client.get("/v1/catalog/models?supports_function_calling=true&page_size=25",
                    headers=ADMIN).json()
    assert fc["total_count"] > 10
    assert all(m["supports_function_calling"] for m in fc["data"])
    op = client.get("/v1/catalog/models?provider=openai&page_size=25", headers=ADMIN).json()
    assert all(m["provider"] == "openai" for m in op["data"])
    srch = client.get("/v1/catalog/models?model=gpt-4o&page_size=50", headers=ADMIN).json()
    assert srch["data"] and all("gpt-4o" in m["id"] for m in srch["data"])


def test_catalog_single_lookup():
    r = client.get("/v1/catalog/models/gpt-4o-mini", headers=ADMIN)
    assert r.status_code == 200 and r.json()["provider"] == "openai"
    assert client.get("/v1/catalog/models/nope-xyz-123", headers=ADMIN).status_code == 404


def test_catalog_providers_listing():
    r = client.get("/v1/catalog/providers", headers=ADMIN)
    assert r.status_code == 200
    data = r.json()["data"]
    assert data and all("provider" in p and "model_count" in p for p in data)
    # sorted by count desc
    assert data[0]["model_count"] >= data[-1]["model_count"]


def test_catalog_requires_auth():
    assert client.get("/v1/catalog/models").status_code == 401
    assert client.get("/v1/catalog/providers").status_code == 401
