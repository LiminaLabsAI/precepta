"""Demo seed creates real, governed sample policies + keys, and is idempotent."""
from __future__ import annotations

import pytest

from app import demo_seed
from app.db import get_conn
from app.governance import policy as P
from app.adapters.identity.keys import list_keys


@pytest.fixture(autouse=True)
def _cleanup_seeded_rows():
    """Seed writes to the shared dev DB; remove the sample rows afterwards so a
    (deliberately blocking) demo policy can't leak into other tests."""
    yield
    pol_names = [p[0] for p in demo_seed._POLICIES]
    key_names = [k[0] for k in demo_seed._KEYS]
    with get_conn() as conn:
        conn.executemany("DELETE FROM governance_policies WHERE name=?",
                         [(n,) for n in pol_names])
        conn.executemany("DELETE FROM api_keys WHERE name=?",
                         [(n,) for n in key_names])


def test_seed_creates_all_samples_and_is_idempotent():
    demo_seed.seed()                                   # ensure present (may be a no-op)
    pol_names = {p["name"] for p in P.list_all()}
    key_names = {k["name"] for k in list_keys()}
    for name, *_ in demo_seed._POLICIES:
        assert name in pol_names
    for name, *_ in demo_seed._KEYS:
        assert name in key_names
    # a second run must create nothing (idempotent by name)
    again = demo_seed.seed()
    assert again["policies_created"] == []
    assert again["keys_created"] == []


def test_seeded_key_has_real_budget_caps():
    demo_seed.seed()
    mobile = next(k for k in list_keys() if k["name"] == "mobile-app")
    assert mobile["cost_cap_daily"] == 5.0
    assert mobile["cost_cap_monthly"] == 100.0
