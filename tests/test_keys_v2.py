"""FEAT-001 v2 — token caps + notifications, key edit, suspend/reactivate."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.adapters.identity import keys
from app import budgets, notifications
from app.db import get_conn

client = TestClient(app)
ADMIN = {"Authorization": "Bearer dev-admin"}


def _cleanup(name: str) -> None:
    budgets.ensure_table(); notifications.ensure_table()
    with get_conn() as conn:
        conn.execute("DELETE FROM api_keys WHERE name=?", (name,))
        conn.execute("DELETE FROM key_usage WHERE key_name=?", (name,))
        conn.execute("DELETE FROM notifications WHERE title LIKE ?", (f"%'{name}'%",))


def test_token_cap_warns_then_blocks_and_notifies():
    try:
        keys.issue_key("tok-key", token_cap_daily=1000)
        assert budgets.check("tok-key")["effect"] == "allow"
        budgets.record_usage("tok-key", "", 900, 0.0)          # 90%
        assert budgets.check("tok-key")["effect"] == "warn"
        budgets.record_usage("tok-key", "", 200, 0.0)          # 1100 > 1000
        assert budgets.check("tok-key")["effect"] == "block"
        assert any("tok-key" in n["title"] for n in notifications.list_recent())
    finally:
        _cleanup("tok-key")


def test_update_key_edits_caps_and_scope():
    try:
        kid, _ = keys.issue_key("edit-key", cost_cap_daily=1.0)
        assert keys.update_key(kid, cost_cap_daily=5.0, token_cap_monthly=50000,
                               allowed_backends=["ollama"])
        m = keys.get_key_meta("edit-key")
        assert m["cost_cap_daily"] == 5.0 and m["token_cap_monthly"] == 50000
        assert m["allowed_backends"] == "ollama"
    finally:
        _cleanup("edit-key")


def test_suspend_blocks_auth_and_reactivate_restores():
    try:
        kid, tok = keys.issue_key("susp-key")
        assert keys.get_api_identity().authenticate(tok) is not None
        keys.set_suspended(kid, True)
        assert keys.get_api_identity().authenticate(tok) is None       # suspended → no auth
        row = next(k for k in keys.list_keys() if k["name"] == "susp-key")
        assert row["suspended"] is True and row["active"] is False
        keys.set_suspended(kid, False)
        assert keys.get_api_identity().authenticate(tok) is not None   # reactivated
    finally:
        _cleanup("susp-key")


def test_edit_and_suspend_endpoints():
    try:
        kid = client.post("/v1/keys", headers=ADMIN,
                          json={"name": "ep-key", "cost_cap_daily": 1}).json()["id"]
        assert client.put(f"/v1/keys/{kid}", headers=ADMIN,
                          json={"cost_cap_daily": 9}).status_code == 200
        assert keys.get_key_meta("ep-key")["cost_cap_daily"] == 9.0
        assert client.post(f"/v1/keys/{kid}/suspend", headers=ADMIN).status_code == 200
        assert next(k for k in keys.list_keys() if k["name"] == "ep-key")["suspended"] is True
        assert client.post(f"/v1/keys/{kid}/reactivate", headers=ADMIN).status_code == 200
    finally:
        _cleanup("ep-key")


def test_notifications_endpoint():
    notifications.notify("test", "warning", "Test alert xyz", "body", dedup=False)
    r = client.get("/notifications", headers=ADMIN)
    assert r.status_code == 200 and r.json()["unread"] >= 1
    assert client.post("/notifications/read", headers=ADMIN).json()["ok"] is True
    with get_conn() as conn:
        conn.execute("DELETE FROM notifications WHERE title='Test alert xyz'")
