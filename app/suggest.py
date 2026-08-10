"""Dynamic follow-up suggestions for the Playground.

Given the last exchange, ask an **in-boundary** model for a few short, relevant
follow-up questions the user might ask next. Fail-soft: any error (no backend,
bad JSON, model down) returns an empty list, and the Console falls back to its
static prompts — never a broken UI.

Sovereignty: this uses the same in-boundary model registry as everything else;
the content never leaves the boundary.
"""
from __future__ import annotations

import json
import re

_PROMPT = (
    "Based on the assistant's answer below, suggest exactly 3 short, natural "
    "follow-up questions the user might ask next. Each under 8 words. Return "
    "ONLY a JSON array of 3 strings, nothing else.\n\nAnswer:\n{answer}"
)


async def suggest_followups(last_response: str, model: str | None = None) -> list[str]:
    """Return up to 3 follow-up questions, or [] on any failure."""
    if not (last_response or "").strip():
        return []
    try:
        from .adapters.model.registry import get_registry
        reg = get_registry()
        be = reg.get("ollama") or (next(iter(reg.values())) if reg else None)
        if be is None:
            return []
        prompt = _PROMPT.format(answer=str(last_response)[:1500])
        res = await be.complete(
            [{"role": "user", "content": prompt}],
            model or be.default_model, temperature=0.4, max_tokens=200)
        text = (res.get("choices") or [{}])[0].get("message", {}).get("content", "")
        m = re.search(r"\[.*\]", text, re.S)
        arr = json.loads(m.group(0)) if m else []
        out = [str(x).strip() for x in arr if str(x).strip()]
        return out[:3]
    except Exception:
        return []
