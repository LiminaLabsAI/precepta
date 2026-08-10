"""Fresh-database schema bootstrap.

Most modules create their own table lazily on first use. On a brand-new
database (a fresh self-host deploy), a *read-before-write* path can hit a table
that no request has created yet — which is exactly what surfaced during Phase 14
(governance_policies / audit_log / telemetry 500'd on the first request).

``ensure_all()`` runs every module's ``ensure_table()`` once at startup, so a
fresh DB is fully initialised before serving. It is **fail-soft per module** (a
single module's problem never blocks the rest) and idempotent (all DDLs are
``CREATE TABLE IF NOT EXISTS``), so it is safe to call on every boot.
"""
from __future__ import annotations

import importlib

# Every module that owns a table (exposes ``ensure_table()``).
_MODULES = (
    "app.budgets", "app.cache", "app.compression", "app.controls",
    "app.features", "app.learning", "app.notifications", "app.org",
    "app.pricing", "app.traces",
    "app.governance.sensitive",
    "app.router.config",
    "app.adapters.audit", "app.adapters.audit.chain",
    "app.adapters.authz.openguard", "app.adapters.authz.scopes",
    "app.adapters.identity.keys", "app.adapters.identity.session",
    "app.adapters.model.store", "app.adapters.secret", "app.adapters.infra",
)


def ensure_all() -> None:
    """Create every known table if missing. Fail-soft per module."""
    for name in _MODULES:
        try:
            mod = importlib.import_module(name)
            fn = getattr(mod, "ensure_table", None)
            if callable(fn):
                fn()
        except Exception:
            pass
    # policy uses a differently-named ensurer (creates the table + migrates scope).
    try:
        from app.governance.policy import _ensure_scope_column
        _ensure_scope_column()
    except Exception:
        pass
