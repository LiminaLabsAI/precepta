"""In-boundary intent classification for the LLM router (FEAT-007·A).

A small model reads the request and returns {goal, difficulty}. Sovereignty is
non-negotiable: this model runs **inside the boundary** — the local Ollama model
by default, or Precepta's in-boundary HF endpoint if the platform owner
configured one (app/router/config.py). The router never sends the prompt to an
external service.

The call is:
  - **cached** by query hash — identical requests classify once;
  - **fail-soft** — any error returns None and the caller (LLMBrain) falls back
    to the rules router, so inference never breaks on a classifier hiccup.
"""
from __future__ import annotations

import hashlib
import json
import os
import re

import httpx

from .config import get_config, HF_KEY_SECRET
from ..settings import get_settings
from ..adapters.secret import get_secret_store

_GOALS = {"cost", "speed", "quality"}
_DIFF = {"easy", "hard"}
_CACHE: dict[str, dict] = {}         # query-hash → {goal, difficulty}

_SYSTEM = (
    "You route AI requests. Read the user's request and reply with ONLY compact "
    'JSON: {"goal":"cost|speed|quality","difficulty":"easy|hard"}. '
    "goal = what the caller most needs: 'cost' for a cheap simple answer, 'speed' "
    "for a fast reply, 'quality' for the best possible answer. difficulty = 'easy' "
    "for lookups/short tasks, 'hard' for reasoning, analysis, math, or code. "
    "Output the JSON only, no prose."
)


def _target() -> tuple[str, str, str | None]:
    """(base_url, model, api_key) for **Precepta's own router model** — the app's
    IP, NOT a customer backend. Resolution order:

      1. Platform-owner override (Console → Router config), if explicitly set.
      2. Precepta's proprietary model from `.env` (HF_BASE_URL/HF_API_KEY/
         HF_DEFAULT_MODEL) — the standard place it is configured.
      3. Local Ollama — the in-boundary dev fallback.

    SOVEREIGNTY: this model sees the customer's prompt (to classify intent), so
    in production it MUST be an **in-boundary** deployment of Precepta's model
    (a dedicated endpoint inside the customer's network). A public URL here
    (e.g. router.huggingface.co) leaks prompts and is a DEV shortcut only.
    """
    cfg = get_config()
    if cfg["router_backend"] == "hf" and cfg["hf_endpoint"]:            # (1) Console override
        return cfg["hf_endpoint"].rstrip("/"), (cfg["hf_model"] or "default"), \
            get_secret_store().get(HF_KEY_SECRET)
    base, model = os.environ.get("HF_BASE_URL"), os.environ.get("HF_DEFAULT_MODEL")
    if base and model:                                                  # (2) .env — Precepta's model
        return base.rstrip("/"), model, os.environ.get("HF_API_KEY")
    port = get_settings().ollama_port                                  # (3) local Ollama (in-boundary)
    return (f"http://127.0.0.1:{port}/v1",
            os.environ.get("OLLAMA_DEFAULT_MODEL", "llama3.2:3b"), None)


def parse_classification(text: str) -> dict | None:
    """Extract {goal, difficulty} from the model's reply, or None if malformed."""
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        return None
    try:
        obj = json.loads(m.group())
    except (ValueError, TypeError):
        return None
    goal = str(obj.get("goal", "")).lower().strip()
    diff = str(obj.get("difficulty", "")).lower().strip()
    if goal not in _GOALS or diff not in _DIFF:
        return None
    return {"goal": goal, "difficulty": diff}


def clear_cache() -> None:
    _CACHE.clear()


def classify(query: str, *, timeout: float = 8.0) -> dict | None:
    """Return {goal, difficulty} for the request, or None on any failure.

    None is the fail-soft signal — the caller routes by rules instead.
    """
    key = hashlib.sha256((query or "").encode()).hexdigest()
    if key in _CACHE:
        return _CACHE[key]
    base, model, api_key = _target()
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        r = httpx.post(base + "/chat/completions", timeout=timeout, headers=headers, json={
            "model": model, "temperature": 0,
            "messages": [{"role": "system", "content": _SYSTEM},
                         {"role": "user", "content": query or ""}],
        })
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
    except (httpx.HTTPError, KeyError, IndexError, ValueError, TypeError):
        return None
    data = parse_classification(content)
    if data is not None:
        _CACHE[key] = data
    return data
