"""BUG-001 — multiple backends of the same provider type coexist (identity by id)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.adapters.model.store import load_backends

client = TestClient(app)
ADMIN = {"Authorization": "Bearer dev-admin"}


def _rm(pid):
    client.delete(f"/v1/backends/{pid}", headers=ADMIN)


def test_two_same_type_backends_coexist():
    try:
        r1 = client.post("/v1/backends", headers=ADMIN, json={
            "provider": "hf-model-a", "base_url": "http://a.invalid/v1",
            "model": "org/model-a", "in_boundary": True, "tier": 3})
        r2 = client.post("/v1/backends", headers=ADMIN, json={
            "provider": "hf-model-b", "base_url": "http://b.invalid/v1",
            "model": "org/model-b", "in_boundary": True, "tier": 2})
        assert r1.status_code == 201 and r2.status_code == 201
        assert r1.json()["tier"] == 3                       # strength persisted
        ids = {b["provider"]: b for b in load_backends()}
        # BOTH present — the second did NOT overwrite the first (the BUG-001 fix)
        assert "hf-model-a" in ids and "hf-model-b" in ids
        assert ids["hf-model-a"]["tier"] == 3 and ids["hf-model-b"]["tier"] == 2
        assert ids["hf-model-a"]["model"] == "org/model-a"
    finally:
        _rm("hf-model-a")
        _rm("hf-model-b")


def test_tier_clamped():
    try:
        r = client.post("/v1/backends", headers=ADMIN, json={
            "provider": "hf-clamp", "base_url": "http://c.invalid/v1", "tier": 99})
        assert r.status_code == 201 and r.json()["tier"] == 3    # clamped to [1,3]
    finally:
        _rm("hf-clamp")
