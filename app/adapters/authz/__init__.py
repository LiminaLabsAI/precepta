"""Authorization adapters (AuthorizationPort) — authZ, decides *what*.

V1 = a simple role check (admin / user / auditor). `open-guard` (RBAC/ABAC +
agent budgets) is the deferred adapter behind the same port.
"""
from __future__ import annotations

import os

from ...ports import Principal

# read-only surfaces an auditor may reach
_READ_ONLY = {"audit.read", "attestation.read"}

# Platform owner(s) — a tier above org admin. Only they may configure the
# router's own model backend + Precepta's in-boundary key (a
# Precepta-operator concern, not a customer-admin one). `admin@local` is the
# dev-admin principal, kept here so local/browser validation works out of the box.
_OWNER_DEFAULT = "123.sarang@gmail.com,admin@local"


def platform_owners() -> set[str]:
    raw = os.environ.get("PRECEPTA_PLATFORM_OWNERS", _OWNER_DEFAULT)
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def is_platform_owner(principal: Principal | None) -> bool:
    subject = getattr(principal, "subject", "") or ""
    return subject.lower() in platform_owners()


class RoleCheck:
    name = "role_check"

    def can(self, principal: Principal, action: str, resource: str = "") -> bool:
        role = getattr(principal, "role", "")
        if role == "admin":
            return True
        if role == "auditor":
            return action in _READ_ONLY
        if role == "user":
            return action == "chat.completion" or action in _READ_ONLY
        return False

    def budget(self, principal: Principal) -> dict:
        return {}


# FEAT-004: OpenGuard (configurable RBAC/ABAC) is the active adapter; RoleCheck
# stays as the reference/fallback implementation of the same port.
from .openguard import get_openguard


def get_authz():
    return get_openguard()
