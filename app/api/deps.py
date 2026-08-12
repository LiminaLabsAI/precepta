"""Auth guards for the management API (Phase 15).

Called at the top of a handler after the principal is resolved, matching the
existing `principal, err = _resolve_principal(request)` style (returns a
JSONResponse on failure, else None) — no FastAPI Depends machinery, no circular
imports.

Management access = an admin-role principal (owner login / dev-admin / a
read-write management key), OR a management-scoped key. Read-only management keys
may read but not write. **Sovereignty stays owner-only elsewhere** — a management
key is never a platform owner, so it can't change Sovereign Mode / egress / router
(those keep their own `is_platform_owner` checks).
"""
from __future__ import annotations

from ..ports import Principal
from .errors import forbidden, unauthorized


def require_auth(principal: Principal | None) -> "None | object":
    """Any authenticated (non-anonymous) caller. 401 otherwise."""
    if principal is None or getattr(principal, "subject", "") in ("", "anonymous"):
        return unauthorized()
    return None


def require_manage(principal: Principal | None, *, write: bool):
    """Gate a management operation. Returns a JSONResponse to short-circuit, or None."""
    if principal is None or getattr(principal, "subject", "") in ("", "anonymous"):
        return unauthorized()
    role = getattr(principal, "role", "") or ""
    scope = getattr(principal, "scope", "inference") or "inference"
    # admin role = owner login, dev-admin, or a read-write management key.
    if role == "admin":
        return None
    if scope.startswith("manage"):        # a management-scoped key
        if write and not scope.endswith(":rw"):
            return forbidden("this management key is read-only", code="read_only_key")
        return None
    return forbidden("a management-scoped key (or owner) is required",
                     code="management_scope_required")
