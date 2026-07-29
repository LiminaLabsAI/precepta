"""Infra visibility (InfraVisibilityPort) — integrate, don't build (DESIGN.md §7).

Composes a per-backend snapshot from: health checks, last observed latency
(router state), Ollama `/api/ps` (loaded model + VRAM), and — when a backend
exposes it — a vLLM Prometheus `/metrics` scrape. Also records a `telemetry`
row per request so the console has real history.
"""
from __future__ import annotations

import datetime as _dt
import uuid

import httpx

from ...db import get_conn
from ..model.registry import get_registry  # noqa: F401  (re-exported convenience)
from ...router.state import latency as _latency


# ── Prometheus text parser (pure, testable) ─────────────────────────────
def parse_prometheus(text: str) -> dict[str, float]:
    """Parse Prometheus exposition text → {metric_name: last_value}.

    Labels are ignored (last sample per bare metric name wins). Good enough for
    the handful of gauges the console shows.
    """
    out: dict[str, float] = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        name = parts[0].split("{", 1)[0]
        try:
            out[name] = float(parts[-1])
        except ValueError:
            continue
    return out


def _ollama_vram(base_url: str) -> tuple[str, str]:
    """(loaded_model, vram_str) from Ollama /api/ps, or ('—','—')."""
    root = base_url.replace("/v1", "").rstrip("/")
    try:
        r = httpx.get(root + "/api/ps", timeout=2.0)
        models = r.json().get("models", [])
        if models:
            m = models[0]
            vram = m.get("size_vram", 0)
            gb = f"{vram / 1e9:.1f}GB" if vram else "—"
            return m.get("name", "—"), gb
    except (httpx.HTTPError, ValueError, KeyError):
        pass
    return "—", "—"


def snapshot(registry: dict | None = None) -> list[dict]:
    reg = registry if registry is not None else get_registry()
    out = []
    for name, be in sorted(reg.items()):
        lat = _latency(name)
        entry = {
            "backend": name,
            "in_boundary": bool(be.in_boundary),
            "model": getattr(be, "default_model", ""),
            "latency_ms": None if lat == float("inf") else round(lat),
            "status": "healthy" if be.health() else "down",
            "gpu": "—",
            "vram": "—",
        }
        if name == "ollama":
            model, vram = _ollama_vram(be.base_url)
            if model != "—":
                entry["model"] = model
            entry["vram"] = vram
        out.append(entry)
    return out


# ── telemetry recording ─────────────────────────────────────────────────
def record_telemetry(*, inference_ms: int | None, tokens_in: int | None,
                     tokens_out: int | None, backend: str | None = None) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO telemetry (id,captured_at,workflow_id,agent_id,cpu_pct,"
            "memory_gb,gpu_pct,vram_gb,tokens_input,tokens_output,inference_ms) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (uuid.uuid4().hex, _dt.datetime.now(_dt.UTC).isoformat(), None, backend,
             None, None, None, None, tokens_in, tokens_out, inference_ms),
        )
