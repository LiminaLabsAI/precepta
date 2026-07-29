"""Runtime firewall (DESIGN.md §6).

Stage 1 — input scrub: redact PII (SSN / email / phone / card / API key) and
detect prompt-injection/jailbreak.
Stage 3 — output leak check: block private keys / secrets / DB URLs.

(Stage 2 — retrieval/PHI scrub — is deferred to a later phase.)
"""
from __future__ import annotations

import re

_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_CARD = re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b")
_PHONE = re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b")
_APIKEY = re.compile(r"\b(?:sk-[A-Za-z0-9]{6,}|gapi-[A-Za-z0-9]{6,})\b")
_INJECTION = re.compile(
    r"ignore previous instructions|system override|jailbreak|you are now .{0,20}mode|"
    r"do anything now|dan mode|developer mode",
    re.IGNORECASE,
)
_LEAK = re.compile(
    r"-----BEGIN PRIVATE KEY-----|client_secret|client_id|database_url",
    re.IGNORECASE,
)


def scrub_input(text: str) -> tuple[str, int, bool]:
    """Return (redacted_text, pii_count, injection_detected)."""
    text = text or ""
    count = 0

    def _sub(pattern: re.Pattern, repl: str, s: str) -> str:
        nonlocal count
        s2, n = pattern.subn(repl, s)
        count += n
        return s2

    out = _sub(_SSN, "[SSN_REDACTED]", text)
    out = _sub(_APIKEY, "[API_KEY_REDACTED]", out)
    out = _sub(_CARD, "[CC_REDACTED]", out)
    out = _sub(_EMAIL, "[EMAIL_REDACTED]", out)
    out = _sub(_PHONE, "[PHONE_REDACTED]", out)
    injection = bool(_INJECTION.search(text))
    return out, count, injection


def scan_output(text: str) -> bool:
    """True if the model output appears to leak a secret / key / DB URL."""
    return bool(_LEAK.search(text or ""))
