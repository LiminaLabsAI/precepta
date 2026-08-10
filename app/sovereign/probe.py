"""Egress probe — actually attempt outbound connections to prove the boundary.

The Sovereignty Attestation should not merely *assert* zero-egress from a config
flag; it should *test* it. This probe tries to open a TCP connection to a couple
of public hosts with a short timeout. In the egress-locked deploy (the app on a
Docker ``internal`` network) these fail — there is no route and DNS does not
resolve — so ``result`` is ``"blocked"``. If any succeed, egress is ``"open"``
(a real leak the operator must see), independent of the Sovereign-Mode toggle.

Fail-soft: a probe that itself errors reports ``result: "unknown"`` rather than
claiming a guarantee it could not verify.
"""
from __future__ import annotations

import socket

# One IP (fast fail on no-route) + one hostname (also tests DNS egress).
_PROBE_TARGETS = (("1.1.1.1", 443), ("huggingface.co", 443))


def egress_probe(timeout: float = 2.0) -> dict:
    targets = []
    reachable = False
    errored = 0
    for host, port in _PROBE_TARGETS:
        ok, err = False, None
        try:
            s = socket.create_connection((host, port), timeout)
            s.close()
            ok = True
        except (OSError, socket.gaierror, socket.timeout) as exc:
            err = type(exc).__name__
        except Exception as exc:                 # pragma: no cover
            err = type(exc).__name__
            errored += 1
        targets.append({"target": f"{host}:{port}", "reachable": ok, "error": err})
        reachable = reachable or ok

    if reachable:
        result = "open"
    elif errored == len(_PROBE_TARGETS):
        result = "unknown"
    else:
        result = "blocked"
    return {"result": result, "reachable": reachable, "targets": targets}
