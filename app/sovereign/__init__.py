"""Sovereign Mode — the primitive that closes the loop (DESIGN.md §3).

When on, it *enforces* (not requests): in-boundary-only routing, audit-on, and
a residency posture. Egress-lock is a deployment concern (deny-all egress) that
the attestation reports on; this module enforces the routing half in code.
"""
from __future__ import annotations


def enforce_backend(backend, settings=None) -> str | None:
    """Return a block reason if routing to `backend` violates Sovereign Mode.
    Uses the EFFECTIVE (runtime-overridable) Sovereign Mode, not the deploy
    default, so the Console's owner-gated toggle actually takes effect.

    An out-of-boundary backend is permitted only if its host is on the
    owner-approved egress allowlist (`app/sovereign/egress.py`) — that is the
    sanctioned way to reach a specific cloud endpoint while everything else
    stays sealed."""
    from ..controls import sovereign_enabled
    if sovereign_enabled() and not getattr(backend, "in_boundary", True):
        base_url = getattr(backend, "base_url", "") or ""
        try:
            from .egress import is_approved
            if base_url and is_approved(base_url):
                return None                        # explicitly approved by an owner
        except Exception:
            pass
        name = getattr(backend, "name", "?")
        from .egress import host_of
        host = host_of(base_url) or "its host"
        return (f"'{name}' is outside your network boundary, so Sovereign Mode "
                f"blocked it. To use it, an owner can approve its host "
                f"('{host}') under Settings → Egress — Precepta will then reach "
                f"only that host and nothing else. (Alternatively, mark '{name}' "
                f"as in-boundary if it truly runs inside your network, or turn "
                f"off Sovereign Mode in Policies.)")
    return None
