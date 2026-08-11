"""OpenAI-compatible model backend.

One adapter serves every OpenAI-shaped endpoint — Ollama, vLLM, Neysa, HF
dedicated endpoints — differing only by config (base_url / api_key / prices).
This is the DIP payoff: adding a provider is configuration, not code.

LiteLLM can later replace the raw httpx call behind this same port without the
domain core noticing; kept dependency-free for Phase 1.
"""
from __future__ import annotations

import httpx

from ...ports import Price


class OpenAICompatBackend:
    """Implements ModelBackendPort against any OpenAI-compatible /v1 endpoint."""

    def __init__(
        self,
        name: str,
        base_url: str,
        *,
        in_boundary: bool,
        api_key: str | None = None,
        prices: dict[str, Price] | None = None,
        default_model: str = "",
        tier: int = 1,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.in_boundary = in_boundary
        self.api_key = api_key
        self._prices = prices or {}
        self.default_model = default_model
        self.tier = tier  # capability tier: higher = stronger (used by automatic routing)

    # ── ModelBackendPort ────────────────────────────────────────────────
    def litellm_model(self, model: str) -> str:
        return f"{self.name}/{model}"

    def price(self, model: str) -> Price:
        return self._prices.get(model, Price(0.0, 0.0))

    def health(self, timeout: float = 3.0) -> bool:
        """Reachable AND authorized. 401/403/404/5xx → not healthy (honest status).

        `timeout` is caller-tunable: internal/fast paths keep the short default,
        while UI-facing checks (the status snapshot, the explicit Test button)
        pass a longer one — a cloud endpoint reached over the internet through the
        egress broker answers in ~4-5s, which a 3s probe would wrongly call down."""
        try:
            r = httpx.get(self.base_url + "/models", headers=self._headers(), timeout=timeout)
            return r.status_code < 400
        except httpx.HTTPError:
            return False

    # ── inference ───────────────────────────────────────────────────────
    async def complete(self, messages: list[dict], model: str, **kw) -> dict:
        """Call the backend's /chat/completions and return the OpenAI JSON."""
        payload: dict = {"model": model, "messages": messages, "stream": False}
        for k in ("temperature", "max_tokens", "top_p"):
            if kw.get(k) is not None:
                payload[k] = kw[k]
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(
                self.base_url + "/chat/completions",
                json=payload,
                headers=self._headers(),
            )
            r.raise_for_status()
            return r.json()

    # ── helpers ─────────────────────────────────────────────────────────
    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h
