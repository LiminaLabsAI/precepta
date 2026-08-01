"""Runtime firewall (DESIGN.md §6).

Stage 1 — input scrub: redact PII and detect prompt-injection/jailbreak.
Stage 3 — output leak check: block private keys / secrets / DB URLs.

TD-004 — stronger sensitivity: credit cards are **Luhn-validated** (a random
16-digit number is not mistaken for a card — fewer false positives), and
coverage adds India/DPDP-relevant identifiers (Aadhaar by format, PAN) alongside
SSN / email / phone / card / IP / API keys. For governance we err toward
redaction: Aadhaar is matched by format (12 digits, not starting 0/1) rather
than the Verhoeff checksum, because a wrong checksum would risk a false negative
(leaking a real one) — over-redaction is the safe failure mode.

The honest next step (real "beyond regex") is a self-hosted NER model
(Presidio/spaCy, in-boundary) for names/addresses/context — deferred; this is
the validated-pattern layer it will augment. (Stage 2 — retrieval/PHI scrub —
also deferred.)
"""
from __future__ import annotations

import re

_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE_US = re.compile(r"\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b")
_PHONE_IN = re.compile(r"\b(?:\+91[-\s]?)?[6-9]\d{9}\b")
_APIKEY = re.compile(r"\b(?:sk-[A-Za-z0-9]{6,}|gapi-[A-Za-z0-9]{6,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,})\b")
_PAN = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")                 # Indian PAN
_IPV4 = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
_CARD_CAND = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")        # 13–19 digits, spaces/dashes ok
_AADHAAR_CAND = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")    # 12 digits, optional spacing

_INJECTION = re.compile(
    r"ignore (?:all |your |the )?previous instructions|disregard (?:all |the )?(?:above|previous)|"
    r"system override|jailbreak|you are now .{0,20}mode|do anything now|dan mode|developer mode|"
    r"pretend you are|reveal your (?:system )?prompt",
    re.IGNORECASE,
)
_LEAK = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|client_secret|database_url|"
    r"\b(?:postgres|postgresql|mysql|mongodb)://[^\s]+",
    re.IGNORECASE,
)


def _luhn_ok(digits: str) -> bool:
    if len(digits) < 13:
        return False
    total, alt = 0, False
    for ch in reversed(digits):
        n = int(ch)
        if alt:
            n *= 2
            if n > 9:
                n -= 9
        total += n
        alt = not alt
    return total % 10 == 0


def _aadhaar_format_ok(digits: str) -> bool:
    # Aadhaar is 12 digits and never starts with 0 or 1. Format-only (see module
    # docstring) — err toward redaction; checksum precision is a later refinement.
    return len(digits) == 12 and digits[0] not in "01"


def scrub_input(text: str) -> tuple[str, int, bool]:
    """Return (redacted_text, pii_count, injection_detected)."""
    text = text or ""
    count = 0

    def _sub(pattern: re.Pattern, repl: str, s: str) -> str:
        nonlocal count
        s2, n = pattern.subn(repl, s)
        count += n
        return s2

    def _sub_validated(pattern: re.Pattern, repl: str, s: str, ok) -> str:
        nonlocal count

        def _r(m: re.Match) -> str:
            nonlocal count
            digits = re.sub(r"\D", "", m.group(0))
            if ok(digits):
                count += 1
                return repl
            return m.group(0)
        return pattern.sub(_r, s)

    out = _sub(_SSN, "[SSN_REDACTED]", text)
    out = _sub(_APIKEY, "[API_KEY_REDACTED]", out)
    out = _sub_validated(_CARD_CAND, "[CC_REDACTED]", out, _luhn_ok)
    out = _sub_validated(_AADHAAR_CAND, "[AADHAAR_REDACTED]", out, _aadhaar_format_ok)
    out = _sub(_PAN, "[PAN_REDACTED]", out)
    out = _sub(_EMAIL, "[EMAIL_REDACTED]", out)
    out = _sub(_PHONE_US, "[PHONE_REDACTED]", out)
    out = _sub(_PHONE_IN, "[PHONE_REDACTED]", out)
    out = _sub(_IPV4, "[IP_REDACTED]", out)
    injection = bool(_INJECTION.search(text))
    return out, count, injection


def scan_output(text: str) -> bool:
    """True if the model output appears to leak a secret / key / DB URL."""
    return bool(_LEAK.search(text or ""))
