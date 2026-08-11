"""Approved-egress allowlist — the owner-gated set of hosts Precepta may reach.

Default posture is **fully sealed**: an empty allowlist means zero egress, and
an out-of-boundary inference endpoint stays blocked. An owner can *approve a
specific host* (e.g. ``huggingface.co``) so that endpoints on that host are
permitted to be reached, while everything else stays blocked. The attestation
records exactly which hosts are approved, so the guarantee shifts honestly from
"nothing leaves" to "only these named hosts can be reached, nothing else."

Matching is host-based and subdomain-friendly: approving ``huggingface.co`` also
covers ``api.huggingface.co``. Port and scheme are ignored.

This module owns the *policy* (which hosts are allowed). The network posture
(whether the app container even has a path to those hosts) is a deployment
choice documented in ``deploy/README.md`` — sealed by default, restricted-egress
as an explicit opt-in. Keeping the two separate is deliberate: the allowlist is
meaningless as a guarantee unless the operator can also see it in the
attestation, which is why it is surfaced there.
"""
from __future__ import annotations

import datetime as _dt
from urllib.parse import urlparse

from ..db import get_conn

_DDL = """
CREATE TABLE IF NOT EXISTS approved_egress (
    host      TEXT PRIMARY KEY,
    added_by  TEXT,
    added_at  TEXT,
    note      TEXT
)
"""


def ensure_table() -> None:
    with get_conn() as conn:
        conn.execute(_DDL)


def host_of(url_or_host: str) -> str:
    """Extract a bare, lowercased hostname from a URL or host string.

    ``https://api.huggingface.co/v1`` → ``api.huggingface.co``;
    ``huggingface.co:443`` → ``huggingface.co``; ``huggingface.co`` → itself.
    """
    s = (url_or_host or "").strip().lower()
    if not s:
        return ""
    if "://" not in s:
        # bare host (maybe with port/path) — give urlparse a scheme to chew on
        s = "http://" + s
    net = urlparse(s).netloc or ""
    host = net.split("@")[-1]        # drop any user:pass@
    host = host.split(":")[0]        # drop :port
    return host.strip(".")


def list_hosts() -> list[dict]:
    ensure_table()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT host, added_by, added_at, note FROM approved_egress "
            "ORDER BY host").fetchall()
    return [{"host": r[0], "added_by": r[1], "added_at": r[2], "note": r[3] or ""}
            for r in rows]


def _approved_set() -> list[str]:
    return [h["host"] for h in list_hosts()]


def is_approved(url_or_host: str) -> bool:
    """True if the host is exactly an approved host or a subdomain of one."""
    host = host_of(url_or_host)
    if not host:
        return False
    for approved in _approved_set():
        if host == approved or host.endswith("." + approved):
            return True
    return False


def add_host(host: str, added_by: str | None = None, note: str | None = None) -> dict:
    """Approve a host (normalised). Idempotent — re-adding updates the note."""
    h = host_of(host)
    if not h:
        raise ValueError("empty host")
    ensure_table()
    now = _dt.datetime.now(_dt.UTC).isoformat()
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO approved_egress (host, added_by, added_at, note) "
            "VALUES (?,?,?,?) ON CONFLICT(host) DO UPDATE SET note=excluded.note",
            (h, added_by or "", now, note or ""))
    return {"host": h, "added_by": added_by or "", "added_at": now, "note": note or ""}


def remove_host(host: str) -> bool:
    h = host_of(host)
    ensure_table()
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM approved_egress WHERE host=?", (h,))
    return cur.rowcount > 0
