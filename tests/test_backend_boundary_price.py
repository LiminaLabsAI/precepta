"""Model Plane UX: correct a backend's boundary flag, and set a price from the app."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.adapters.model.store import load_backends
from app import pricing

client = TestClient(app)
ADMIN = {"Authorization": "Bearer dev-admin"}
USER = {"Authorization": "Bearer dev-user"}


def test_boundary_can_be_corrected():
    try:
        client.post("/v1/backends", headers=ADMIN, json={
            "provider": "bt-test", "base_url": "http://x.invalid/v1", "in_boundary": True})
        r = client.post("/v1/backends/bt-test/boundary", headers=ADMIN, json={"in_boundary": False})
        assert r.status_code == 200 and r.json()["in_boundary"] is False
        row = next(b for b in load_backends() if b["provider"] == "bt-test")
        assert row["in_boundary"] == 0                       # persisted
        assert client.post("/v1/backends/bt-test/boundary", headers=USER,
                           json={"in_boundary": True}).status_code == 403   # admin-only
    finally:
        client.delete("/v1/backends/bt-test", headers=ADMIN)


def test_set_price_from_app():
    r = client.post("/v1/pricing", headers=ADMIN, json={
        "backend": "bt-priced", "model": "m", "input_per_1m": 0.8,
        "output_per_1m": 1.2, "source": "console"})
    assert r.status_code == 201
    p = pricing.price_of("bt-priced", "m")
    assert p.input_per_1m == 0.8 and p.output_per_1m == 1.2   # feeds the $ source of truth
