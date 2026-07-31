"""TD-002 — canonical metering: billable vs saved vs usage, cache-hit = free."""
from __future__ import annotations

from app import metering, pricing


def setup_module(_):
    pricing.upsert_price("testmeter", "", 10.0, 30.0, source="test")   # $/1M in / out


def teardown_module(_):
    from app.db import get_conn
    with get_conn() as conn:
        conn.execute("DELETE FROM model_prices WHERE backend='testmeter'")


def test_normal_request_charges_real_cost():
    m = metering.meter("testmeter", "", 1_000_000, 1_000_000)
    assert m["billable_tokens"] == 2_000_000
    assert m["budget_charge_usd"] == 40.0        # 10 + 30
    assert m["usage_volume"] == 1
    assert m["tokens_saved"] == 0


def test_cache_hit_is_free_but_still_counts_usage():
    m = metering.meter("testmeter", "", 500, 500, cache_hit=True, original_tokens=1000)
    assert m["billable_tokens"] == 0             # no inference ran
    assert m["budget_charge_usd"] == 0.0         # spends no budget
    assert m["usage_volume"] == 1                # ...but is still counted
    assert m["tokens_saved"] == 1000             # avoided the model entirely


def test_compression_savings_counted():
    m = metering.meter("testmeter", "", 400, 100, original_tokens=1000, compressed_tokens=400)
    # billable is the compressed (actual) tokens; saved = original - compressed
    assert m["billable_tokens"] == 500
    assert m["tokens_saved"] == 600


def test_local_backend_is_free():
    m = metering.meter("ollama", "", 1_000_000, 1_000_000)
    assert m["budget_charge_usd"] == 0.0
