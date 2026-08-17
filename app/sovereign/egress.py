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
import os
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


def is_internal_host(host: str) -> bool:
    """Heuristic: does this host name refer to something *inside* the network,
    so approving it for internet egress would make no sense?

    Internal: bare names with no dot (``ollama``, ``vllm``), ``localhost``,
    ``*.internal`` / ``*.local``, and private/loopback IP literals. Everything
    else (a public FQDN like ``router.huggingface.co``) is treated as external
    and therefore approvable.
    """
    h = host_of(host)
    if not h or h in ("localhost",):
        return True
    if "." not in h:                       # bare service name (docker/k8s)
        return True
    if h.endswith(".internal") or h.endswith(".local") or h.endswith(".svc"):
        return True
    # private / loopback IPv4 literals
    if all(p.isdigit() for p in h.split(".")) and h.count(".") == 3:
        a, b, *_ = (int(x) for x in h.split("."))
        if a == 10 or a == 127 or (a == 192 and b == 168) or (a == 172 and 16 <= b <= 31):
            return True
    return False


def is_approvable(url_or_host: str) -> bool:
    """A host worth offering an 'approve egress' action for: external and not
    already approved."""
    host = host_of(url_or_host)
    return bool(host) and not is_internal_host(host) and not is_approved(url_or_host)


def list_hosts() -> list[dict]:
    ensure_table()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT host, added_by, added_at, note FROM approved_egress "
            "ORDER BY host").fetchall()
    return [{"host": r[0], "added_by": r[1], "added_at": r[2], "note": r[3] or ""}
            for r in rows]


def _allowfile_path() -> str | None:
    """The file the egress broker reads. Set PRECEPTA_EGRESS_ALLOWFILE in a
    restricted-egress deployment; unset in the sealed default (no broker)."""
    return os.environ.get("PRECEPTA_EGRESS_ALLOWFILE")


def sync_allowfile() -> None:
    """Write the current approved hosts to the broker's allowfile (fail-soft).

    Called on every change and at startup, so the broker always reflects the
    live allowlist. A no-op when no allowfile path is configured (sealed mode).
    """
    path = _allowfile_path()
    if not path:
        return
    try:
        hosts = [h["host"] for h in list_hosts()]
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("# approved egress hosts — written by Precepta, read by the broker\n")
            for h in hosts:
                f.write(h + "\n")
        os.replace(tmp, path)      # atomic swap so the broker never reads a partial file
    except OSError:
        pass


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
    sync_allowfile()
    return {"host": h, "added_by": added_by or "", "added_at": now, "note": note or ""}


def remove_host(host: str) -> bool:
    h = host_of(host)
    ensure_table()
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM approved_egress WHERE host=?", (h,))
    sync_allowfile()
    return cur.rowcount > 0


# ── OIDC sign-in egress (Google) ───────────────────────────────────────────
# The sealed app has no direct internet route, so "Sign in with Google" can't
# reach Google's discovery/token/userinfo endpoints unless those hosts are on
# the approved-egress allowlist. When Google OIDC is configured we seed them
# into the SAME owner-approved list (added_by='system:oidc') — so they show up
# in Console → Egress and the attestation, and the restricted-egress broker
# forwards the login flow. Never a hidden backdoor: it's visible and revocable.
_GOOGLE_OIDC_HOSTS = (
    "accounts.google.com",          # discovery + authorize
    "oauth2.googleapis.com",        # token exchange
    "openidconnect.googleapis.com",  # userinfo (current)
    "www.googleapis.com",           # userinfo (legacy) / certs
)


def seed_oidc_egress() -> None:
    """Auto-approve Google's OIDC hosts when Google sign-in is configured.

    Idempotent and fail-soft. No-op unless OIDC is configured against Google
    (issuer contains ``accounts.google.com`` and a client id+secret are set) —
    so deployments that don't use Google SSO get no extra egress.
    """
    issuer = os.environ.get("OIDC_ISSUER", "").strip().lower()
    if "accounts.google.com" not in issuer:
        return
    if not (os.environ.get("OIDC_CLIENT_ID") and os.environ.get("OIDC_CLIENT_SECRET")):
        return
    for h in _GOOGLE_OIDC_HOSTS:
        try:
            add_host(h, added_by="system:oidc",
                     note="Google sign-in (OIDC) — auto-approved so the login flow can reach Google")
        except ValueError:
            pass   # add_host syncs the allowfile on each insert
