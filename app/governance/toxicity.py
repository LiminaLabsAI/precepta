"""In-boundary toxicity / abuse detector (Phase 12).

Sovereignty-first: unlike competitors that call an external toxicity API (which
would send the content out of the boundary), this runs a local, deterministic
heuristic — a small starter lexicon of abusive/threatening phrases, extendable
at runtime. It is intentionally conservative (whole-phrase, word-boundary
matches) so ordinary text ("the class started", "kill the process") does not
trip it.

This is a starter guard, not a full classifier: a production deployment plugs a
proper **in-boundary** toxicity model in behind ``scan_toxicity`` — the callers
(output firewall) depend on this function, not its implementation.
"""
from __future__ import annotations

import re

# Starter lexicon — unambiguous abuse/threats, no slurs shipped in source.
_DEFAULT_TERMS: set[str] = {
    "kill yourself",
    "i will kill you",
    "i will hurt you",
    "you are worthless",
    "you should die",
    "shut up idiot",
    "go to hell",
}

_extra: set[str] = set()


def add_terms(terms) -> None:
    """Extend the lexicon at runtime (deployment-specific abuse terms)."""
    _extra.update((t or "").strip().lower() for t in terms if (t or "").strip())


def _all_terms() -> list[str]:
    return list(_DEFAULT_TERMS) + list(_extra)


def scan_toxicity(text: str) -> tuple[bool, str]:
    """Return ``(is_toxic, matched_phrase)``. Case-insensitive, word-boundary."""
    t = (text or "").lower()
    if not t:
        return False, ""
    for phrase in _all_terms():
        if re.search(r"\b" + re.escape(phrase) + r"\b", t):
            return True, phrase
    return False, ""
