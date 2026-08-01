"""Test isolation helpers.

Several features fire real bell notifications (budget caps, sensitive blocks,
aggressive compression). Because the suite runs against the same SQLite DB as
dev, those test-created notifications used to leak into the real feed. This
autouse fixture removes any notification a test creates, while preserving any
that already existed — so tests never pollute the operator's notification feed.
"""
from __future__ import annotations

import pytest

from app.db import get_conn
from app import notifications


@pytest.fixture(autouse=True)
def _no_notification_leak():
    notifications.ensure_table()
    with get_conn() as conn:
        before = [r["id"] for r in conn.execute("SELECT id FROM notifications").fetchall()]
    yield
    with get_conn() as conn:
        if before:
            placeholders = ",".join("?" * len(before))
            conn.execute(f"DELETE FROM notifications WHERE id NOT IN ({placeholders})", before)
        else:
            conn.execute("DELETE FROM notifications")   # nothing pre-existed → all are test-created
