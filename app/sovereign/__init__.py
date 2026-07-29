"""Sovereign Mode — the primitive that closes the loop (DESIGN.md §3).

When on, it *enforces* (not requests): in-boundary-only routing, audit-on, and
a residency posture. Egress-lock is a deployment concern (deny-all egress) that
the attestation reports on; this module enforces the routing half in code.
"""
from __future__ import annotations


def enforce_backend(backend, settings) -> str | None:
    """Return a block reason if routing to `backend` violates Sovereign Mode."""
    if settings.sovereign_mode and not getattr(backend, "in_boundary", True):
        return (f"out-of-boundary route to {getattr(backend, 'name', '?')!r} "
                "blocked by Sovereign Mode (in-boundary-only routing)")
    return None
