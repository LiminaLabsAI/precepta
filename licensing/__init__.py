"""Precepta licensing — the VENDOR side.

This package is Precepta's own control server, NOT part of the sovereign
self-host image customers run. It issues Ed25519-**signed** license keys, records
onboarding logins, and receives install heartbeats. The private signing key lives
only here (env `LICENSE_SIGNING_KEY`); the self-hosted app embeds only the public
verify key (Phase 17).

Keep this cleanly separate from `app/` — the self-host image must never contain
the private key or the admin surface.
"""
