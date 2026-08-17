"""Key material for the licensing service.

Production: set `LICENSE_SIGNING_KEY` (base64url raw Ed25519 private key) as a
secret on the vendor service, and embed the matching public key in the self-host
app (Phase 17) via `LICENSE_PUBLIC_KEY` / a committed constant.

Dev/tests: a fixed, clearly-labelled **dev-only** keypair is committed so tests
and local runs work out of the box. It is NOT the production signing key — never
trust a key signed by the dev key in a real deployment.
"""
from __future__ import annotations

import os

# ⚠️ DEV-ONLY keypair — safe to commit; production overrides via env.
DEV_PRIVATE_KEY = "IeguCmLA_034gfZ8dXHxD1QW9qMGqrqbRhtre3l7WVU"
DEV_PUBLIC_KEY = "2-mX2RFERjZzJdsvPyN_Ju0fU--pnXJhOpVqsG_i5L4"


def signing_key() -> str:
    """The private key used to SIGN licenses (vendor side)."""
    return os.environ.get("LICENSE_SIGNING_KEY", "").strip() or DEV_PRIVATE_KEY


def public_key() -> str:
    """The public key used to VERIFY licenses. In Phase 17 the self-host app
    embeds this same value (production key via env / a committed constant)."""
    return os.environ.get("LICENSE_PUBLIC_KEY", "").strip() or DEV_PUBLIC_KEY


def using_dev_key() -> bool:
    return signing_key() == DEV_PRIVATE_KEY
