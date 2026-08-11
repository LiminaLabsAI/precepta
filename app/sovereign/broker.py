"""Egress broker — the ONLY path out of the sealed app container.

In a restricted-egress deployment the app has **no direct internet route**; its
outbound HTTPS is sent here via ``HTTPS_PROXY``. This broker opens a CONNECT
tunnel **only** to owner-approved hosts — read live from the allowfile the
control plane writes (`app/sovereign/egress.py`) — and refuses everything else
with 403.

Why this preserves the guarantee: the app still cannot reach the internet
directly (a raw socket to 1.1.1.1 has no route — the attestation's egress probe
keeps proving that), so the *only* way anything leaves is through this filter,
which enforces the same owner-approved allowlist independently of the app. The
posture is honestly "no direct egress; reaches only approved hosts via an
audited broker" — not "wide open."

Host matching mirrors ``egress.is_approved``: exact host or a subdomain of an
approved host, case-insensitive, port ignored. The allowfile is re-read on every
CONNECT, so approving/revoking a host in the Console takes effect immediately —
no reload.
"""
from __future__ import annotations

import os
import select
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_ALLOWFILE = os.environ.get("PRECEPTA_EGRESS_ALLOWFILE", "/data/approved_egress.txt")
_PORT = int(os.environ.get("PRECEPTA_BROKER_PORT", "8080"))


def _approved_hosts() -> list[str]:
    try:
        with open(_ALLOWFILE, encoding="utf-8") as f:
            return [ln.strip().lower() for ln in f
                    if ln.strip() and not ln.startswith("#")]
    except OSError:
        return []


def is_allowed(host: str) -> bool:
    """True if host is exactly an approved host or a subdomain of one."""
    h = (host or "").split(":")[0].strip().lower().strip(".")
    if not h:
        return False
    for a in _approved_hosts():
        if h == a or h.endswith("." + a):
            return True
    return False


class _BrokerHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_CONNECT(self):                       # noqa: N802 (http.server API)
        host = self.path.split(":")[0]
        try:
            port = int(self.path.split(":")[1]) if ":" in self.path else 443
        except ValueError:
            port = 443
        if not is_allowed(host):
            self.send_error(403, "egress host not approved")
            return
        try:
            upstream = socket.create_connection((host, port), timeout=10)
        except OSError:
            self.send_error(502, "upstream connect failed")
            return
        self.send_response(200, "Connection Established")
        self.end_headers()
        self._tunnel(self.connection, upstream)

    @staticmethod
    def _tunnel(client: socket.socket, upstream: socket.socket) -> None:
        conns = [client, upstream]
        try:
            while True:
                readable, _, exceptional = select.select(conns, [], conns, 60)
                if exceptional or not readable:
                    break
                for s in readable:
                    other = upstream if s is client else client
                    data = s.recv(8192)
                    if not data:
                        return
                    other.sendall(data)
        except OSError:
            pass
        finally:
            for s in (client, upstream):
                try:
                    s.close()
                except OSError:
                    pass

    def do_GET(self):                           # noqa: N802
        # Plain-HTTP proxying is intentionally unsupported — cloud inference
        # endpoints are HTTPS (which uses CONNECT). Refuse anything else.
        self.send_error(405, "this broker only tunnels HTTPS (CONNECT)")

    def log_message(self, *args):               # keep stdout quiet
        return


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", _PORT), _BrokerHandler)
    server.daemon_threads = True
    server.serve_forever()


if __name__ == "__main__":
    main()
