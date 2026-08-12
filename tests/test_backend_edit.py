"""Editing a registered endpoint in place: PUT updates URL/model/tier/boundary,
a blank key keeps the stored one, and it's admin-only."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.adapters.model.registry import get_registry
from app.adapters.model.store import load_backends

client = TestClient(app)
ADMIN = {"Authorization": "Bearer dev-admin"}
USER = {"Authorization": "Bearer dev-user"}


def test_edit_updates_fields_and_keeps_key():
    try:
        client.post("/v1/backends", headers=ADMIN, json={
            "provider": "edit-test", "base_url": "http://old.invalid/v1",
            "api_key": "secret-key", "model": "old-model", "in_boundary": True, "tier": 1})
        # edit URL/model/tier/boundary, leave key blank → keep stored key
        r = client.put("/v1/backends/edit-test", headers=ADMIN, json={
            "base_url": "http://new.invalid/v1", "model": "new-model",
            "in_boundary": False, "tier": 3})
        assert r.status_code == 200
        be = get_registry()["edit-test"]
        assert be.base_url == "http://new.invalid/v1"
        assert be.default_model == "new-model"
        assert be.in_boundary is False
        assert be.tier == 3
        assert be.api_key == "secret-key"                    # blank key kept the old one
        row = next(b for b in load_backends() if b["provider"] == "edit-test")
        assert row["base_url"] == "http://new.invalid/v1"    # persisted
        assert row["model"] == "new-model"
    finally:
        client.delete("/v1/backends/edit-test", headers=ADMIN)


def test_edit_can_replace_key():
    try:
        client.post("/v1/backends", headers=ADMIN, json={
            "provider": "edit-key", "base_url": "http://x.invalid/v1", "api_key": "old"})
        client.put("/v1/backends/edit-key", headers=ADMIN, json={"api_key": "brand-new"})
        assert get_registry()["edit-key"].api_key == "brand-new"
    finally:
        client.delete("/v1/backends/edit-key", headers=ADMIN)


def test_edit_unknown_is_404_and_user_forbidden():
    assert client.put("/v1/backends/nope-xyz", headers=ADMIN, json={}).status_code == 404
    try:
        client.post("/v1/backends", headers=ADMIN, json={
            "provider": "edit-authz", "base_url": "http://x.invalid/v1"})
        assert client.put("/v1/backends/edit-authz", headers=USER,
                          json={"model": "m"}).status_code == 403   # admin-only
    finally:
        client.delete("/v1/backends/edit-authz", headers=ADMIN)
