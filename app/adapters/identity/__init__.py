"""Identity adapters (IdentityPort) — authN, proves *who*."""
from __future__ import annotations

from ...ports import Principal


class DevIdentity:
    """Bearer-token → principal, for local/dev and tests.

    Real Google OAuth (verifying a Google ID token) is deferred to Phase 6 /
    an owner action (needs a Google OAuth client). Until then, dev tokens map
    to the three roles so authZ can be exercised end-to-end.
    """

    _DEFAULT = {
        "dev-admin": Principal("admin@local", "admin", "Dev Admin"),
        "dev-user": Principal("user@local", "user", "Dev User"),
        "dev-auditor": Principal("auditor@local", "auditor", "Dev Auditor"),
    }

    def __init__(self, tokens: dict[str, Principal] | None = None) -> None:
        self._tokens = tokens or dict(self._DEFAULT)

    def authenticate(self, token: str) -> Principal | None:
        return self._tokens.get(token)


_identity = DevIdentity()


def get_identity() -> DevIdentity:
    return _identity
