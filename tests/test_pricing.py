"""TD-001 — pricing source of truth: versioning, fallback, missing flag, cost, endpoints."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app import pricing
from app.ports import Price
from app.db import get_conn

client = TestClient(app)
ADMIN = {"Authorization": "Bearer dev-admin"}


def _cleanup(backend: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM model_prices WHERE backend=?", (backend,))


def test_seed_gives_known_backends_real_prices():
    pricing.seed_defaults()
    assert pricing.price_of("neysa", "") == Price(0.30, 0.30)
    assert pricing.price_of("hf", "") == Price(0.60, 0.60)
    # local backends are known-free ($0), not "unknown"
    p, meta = pricing.price_info("ollama", "")
    assert p == Price(0.0, 0.0) and meta["missing"] is False


def test_unknown_backend_is_flagged_missing_not_silent_zero():
    p, meta = pricing.price_info("no-such-backend-xyz", "")
    assert p == Price(0.0, 0.0)
    assert meta["missing"] is True          # surfaced, never a silent $0


def test_versioning_by_effective_date():
    try:
        pricing.upsert_price("testcloud", "", 1.0, 2.0, effective_date="2026-01-01", source="old")
        pricing.upsert_price("testcloud", "", 3.0, 4.0, effective_date="2026-06-01", source="new")
        # historical report uses the price in effect then
        assert pricing.price_of("testcloud", "", as_of="2026-03-01") == Price(1.0, 2.0)
        # today uses the latest
        assert pricing.price_of("testcloud", "", as_of="2026-12-01") == Price(3.0, 4.0)
    finally:
        _cleanup("testcloud")


def test_exact_model_beats_backend_default():
    try:
        pricing.upsert_price("testcloud", "", 1.0, 1.0, source="default")
        pricing.upsert_price("testcloud", "big-model", 9.0, 9.0, source="specific")
        assert pricing.price_of("testcloud", "big-model") == Price(9.0, 9.0)
        assert pricing.price_of("testcloud", "other") == Price(1.0, 1.0)
    finally:
        _cleanup("testcloud")


def test_cost_of_computes_real_dollars():
    try:
        pricing.upsert_price("testcloud", "", 10.0, 30.0, source="t")   # $/1M tokens
        # 1M in + 1M out = 10 + 30 = 40
        assert pricing.cost_of("testcloud", "", 1_000_000, 1_000_000) == 40.0
        # local/free stays 0
        assert pricing.cost_of("ollama", "", 1_000_000, 1_000_000) == 0.0
    finally:
        _cleanup("testcloud")


def test_pricing_endpoint_lists_rows():
    r = client.get("/v1/pricing", headers=ADMIN)
    assert r.status_code == 200
    backends = {row["backend"] for row in r.json()["prices"]}
    assert "neysa" in backends and "hf" in backends


def test_pricing_post_admin_only_and_persists():
    try:
        # anonymous → user → forbidden
        assert client.post("/v1/pricing", json={"backend": "testcloud",
                           "input_per_1m": 5, "output_per_1m": 5}).status_code == 403
        # admin → created + readable back through the port
        r = client.post("/v1/pricing", headers=ADMIN,
                        json={"backend": "testcloud", "input_per_1m": 5, "output_per_1m": 7,
                              "source": "manual"})
        assert r.status_code == 201
        assert pricing.price_of("testcloud", "") == Price(5.0, 7.0)
    finally:
        _cleanup("testcloud")
