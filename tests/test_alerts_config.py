"""TD-008 — alerts config: admin controls which alert categories fire and a
minimum severity; notify() honors it (system alerts stay non-silenceable)."""
from __future__ import annotations

from app import notifications as notif, org
from app.db import get_conn


def _fired(title: str) -> bool:
    notif.ensure_table()
    with get_conn() as conn:
        return conn.execute("SELECT 1 FROM notifications WHERE title=?", (title,)).fetchone() is not None


def _reset():
    org.update({"alerts_enabled": "true", "alert_min_severity": "info",
                "alert_budget": "true", "alert_sensitive": "true", "alert_compression": "true"})
    notif.ensure_table()
    with get_conn() as conn:      # never leak test notifications into the real feed
        conn.execute("DELETE FROM notifications WHERE title LIKE 'alert-%'")


def test_default_fires():
    _reset()
    try:
        notif.notify("budget_warn", "warning", "alert-default-1", "b")
        assert _fired("alert-default-1")
    finally:
        _reset()


def test_master_switch_off():
    _reset()
    org.update({"alerts_enabled": "false"})
    try:
        notif.notify("budget_warn", "warning", "alert-master-off", "b")
        assert not _fired("alert-master-off")
    finally:
        _reset()


def test_category_toggle():
    _reset()
    org.update({"alert_budget": "false"})
    try:
        notif.notify("budget_warn", "warning", "alert-budget-off", "b")
        assert not _fired("alert-budget-off")                 # budget silenced
        notif.notify("sensitive_block", "critical", "alert-sensitive-on", "b")
        assert _fired("alert-sensitive-on")                   # sensitive still fires
    finally:
        _reset()


def test_min_severity_threshold():
    _reset()
    org.update({"alert_min_severity": "critical"})
    try:
        notif.notify("compression_aggressive", "info", "alert-info-below", "b")
        assert not _fired("alert-info-below")                 # info < critical → suppressed
        notif.notify("sensitive_block", "critical", "alert-critical-ok", "b")
        assert _fired("alert-critical-ok")
    finally:
        _reset()


def test_system_alerts_not_silenceable_by_category():
    _reset()
    org.update({"alert_budget": "false", "alert_sensitive": "false", "alert_compression": "false"})
    try:
        notif.notify("system_health", "warning", "alert-system-1", "b")
        assert _fired("alert-system-1")                       # no category toggle → still fires
    finally:
        _reset()
