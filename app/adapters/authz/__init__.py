"""Authorization adapters (AuthorizationPort) — authZ, decides *what*.

V1 = a simple role check (admin / user / auditor). `open-guard` (RBAC/ABAC +
agent budgets) is the deferred adapter behind the same port.
"""
from __future__ import annotations

from ...ports import Principal

# read-only surfaces an auditor may reach
_READ_ONLY = {"audit.read", "attestation.read"}


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


_authz = RoleCheck()


def get_authz() -> RoleCheck:
    return _authz
