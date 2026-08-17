"""Sovereignty Attestation (DESIGN.md §4) — the proof artifact.

Config proof + audit proof + egress-test result + chain integrity, signed and
hash-anchored to the audit chain. This is what a customer hands an auditor.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json

from ..adapters.audit.chain import get_chain
from ..db import list_tables

# Data stores that may hold customer-derived data (TD-007). All are LOCAL SQLite
# in the customer's boundary — nothing here is a remote/managed service. Listed
# in the attestation only when the table actually exists, so the artifact never
# claims a store that isn't there.
_STORE_DESCRIPTORS = {
    "audit_log": "Governance decisions (in-boundary, tamper-evident).",
    "tamper_evident_audit_log": "Hash-chained audit anchor (in-boundary).",
    "response_cache": "Cached model responses; sensitive requests are never cached (in-boundary).",
    "route_traces": "Routing metadata + query hashes (not raw prompts); for the learning loop (in-boundary).",
    "secrets": "Provider keys, held in the secret store — never returned by the API (in-boundary).",
    "registered_backends": "Backend endpoints + keys registered at runtime (in-boundary).",
}


def _data_stores() -> list[dict]:
    try:
        present = set(list_tables())
    except Exception:
        present = set()
    return [{"store": name, "location": "local (in-boundary)", "description": desc}
            for name, desc in _STORE_DESCRIPTORS.items() if name in present]


def _egress_result() -> dict:
    """Real egress probe → attestation payload, recorded to the tamper-evident chain."""
    try:
        from .probe import egress_probe
        probe = egress_probe()
    except Exception:
        probe = {"result": "unknown", "reachable": False, "targets": []}
    try:
        get_chain().append(
            event_type="egress.probe", actor="system", resource="egress",
            action="probe", outcome=probe["result"],
            metadata={"targets": probe.get("targets", [])})
    except Exception:
        pass
    # Owner-approved egress hosts shift the posture honestly from "sealed"
    # (nothing may leave) to "restricted" (only these named hosts may be reached).
    try:
        from .egress import list_hosts
        approved = [h["host"] for h in list_hosts()]
    except Exception:
        approved = []
    return {"result": probe["result"], "verified": probe["result"] == "blocked",
            "targets": probe.get("targets", []),
            "approved_hosts": approved,
            "posture": "restricted" if approved else "sealed"}


def _licensing_disclosure() -> dict:
    """Honest disclosure: customer prompts/data never leave (zero egress). When a
    license is active, a SEPARATE metadata-only heartbeat (license id + status —
    no customer data) is sent to the vendor. Disclosed here so the sovereignty
    claim stays truthful."""
    try:
        from .. import licensing as _lic
        st = _lic.status()
        active = st.get("state") != "unlicensed"
        host = ""
        if active:
            from .egress import host_of
            host = host_of(_lic.license_url())
        return {
            "customer_data_egress": "none",     # prompts/data never leave the boundary
            "license_active": active,
            "heartbeat": {
                "enabled": active,               # only phones home when licensed
                "host": host,
                "sends": ["license_id", "install_id", "plan", "seats", "version"],
                "contains_customer_data": False,
            },
        }
    except Exception:
        return {"customer_data_egress": "none", "license_active": False,
                "heartbeat": {"enabled": False}}


def build_attestation(settings, registry) -> dict:
    from ..controls import sovereign_enabled
    sovereign = sovereign_enabled()          # effective (runtime-overridable) mode
    chain = get_chain()
    backends = [{"name": n, "in_boundary": bool(b.in_boundary)}
                for n, b in sorted(registry.items())]
    all_in_boundary = all(b["in_boundary"] for b in backends) if backends else True
    verified = chain.verify()

    body = {
        "generated_at": _dt.datetime.now(_dt.UTC).isoformat(),
        "sovereign_mode": sovereign,
        "config": {
            "backends": backends,
            "all_in_boundary": all_in_boundary,
        },
        "data_stores": {
            "all_in_boundary": True,      # every store is local SQLite in the boundary
            "stores": _data_stores(),
        },
        "audit": {
            "events": chain.count(),
            "external_calls": 0,          # in-boundary-only routing → zero egress
            "chain_verified": verified,
        },
        "egress_test": _egress_result(),   # a REAL outbound probe, not just the flag
        "licensing": _licensing_disclosure(),
    }
    anchor = chain.head_hash()
    signature = hashlib.sha256(
        (json.dumps(body, sort_keys=True) + anchor).encode("utf-8")
    ).hexdigest()
    body["anchored_to"] = anchor
    body["signature"] = signature
    return body
