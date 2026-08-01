"""Router configuration (platform-owner-only) — where the router's own model runs.

The intent-router (FEAT-007·A) uses a small model to read a request's goal
(cost / speed / quality). That model runs **in-boundary** — inside the
customer's network — so the router never sends prompts to Precepta's servers.
This module holds *which* backend that model uses:

- ``ollama``  — the local model (default; free; good for dev and small installs)
- ``hf``      — Precepta's own dedicated HF endpoint, deployed **inside the
  customer's boundary**, with a Precepta-owned key (separate from the org's own
  backend keys). Endpoint URL is stored here; the key lives in the secret store
  and is never returned over the API.

Config is persisted (survives restart) and editable only by the platform owner.
The intent-router (a later slice) reads this to pick where it runs; until then
the surface exists so the owner can configure it ahead of the router landing.
"""
from __future__ import annotations

from ..db import get_conn
from ..adapters.secret import get_secret_store

_DDL = "CREATE TABLE IF NOT EXISTS router_config (key TEXT PRIMARY KEY, value TEXT)"

# The router key lives under this name in the secret store — never in this table.
HF_KEY_SECRET = "router.hf_key"

_DEFAULTS = {
    "router_backend": "ollama",     # "ollama" | "hf"
    "hf_endpoint": "",              # Precepta's in-boundary HF endpoint URL
    "hf_model": "",                # model id served at that endpoint (optional)
}
_ALLOWED = set(_DEFAULTS)
_BACKENDS = {"ollama", "hf"}


def ensure_table() -> None:
    with get_conn() as conn:
        conn.execute(_DDL)


def _get(key: str) -> str:
    ensure_table()
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM router_config WHERE key=?", (key,)).fetchone()
    return row["value"] if row is not None else _DEFAULTS.get(key, "")


def get_config() -> dict:
    """Safe-to-return config: the HF key is reported as a boolean, never its value."""
    return {
        "router_backend": _get("router_backend"),
        "hf_endpoint": _get("hf_endpoint"),
        "hf_model": _get("hf_model"),
        "hf_key_set": get_secret_store().is_set(HF_KEY_SECRET),
    }


class RouterConfigError(ValueError):
    """A router-config update was rejected (bad backend, or HF chosen but unconfigured)."""


def update_config(values: dict) -> dict:
    """Apply an owner edit. ``hf_key`` (if a non-empty string) is written to the
    secret store and dropped from the stored config; "" leaves the key unchanged.

    Rejects an unknown ``router_backend`` and rejects selecting ``hf`` unless an
    endpoint and a key are present (so the router never points at a dead config).
    """
    backend = values.get("router_backend")
    if backend is not None and backend not in _BACKENDS:
        raise RouterConfigError(f"router_backend must be one of {sorted(_BACKENDS)}")

    # Validate the *resulting* state before writing anything (all-or-nothing).
    current = get_config()
    key = values.get("hf_key")
    key_provided = isinstance(key, str) and bool(key.strip())
    resulting = {
        "router_backend": (backend if backend is not None else current["router_backend"]),
        "hf_endpoint": (values.get("hf_endpoint") if values.get("hf_endpoint") is not None
                        else current["hf_endpoint"]),
        "hf_key_set": key_provided or current["hf_key_set"],
    }
    if resulting["router_backend"] == "hf" and not (
            str(resulting["hf_endpoint"]).strip() and resulting["hf_key_set"]):
        raise RouterConfigError(
            "HF router backend needs both an in-boundary endpoint and a key")

    # Validated → persist. Key goes to the secret store, never into router_config.
    if key_provided:
        get_secret_store().put(HF_KEY_SECRET, key.strip())
    ensure_table()
    with get_conn() as conn:
        for k, v in values.items():
            if k in _ALLOWED and v is not None:
                conn.execute(
                    "INSERT INTO router_config (key,value) VALUES (?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (k, str(v).strip()))
    return get_config()
