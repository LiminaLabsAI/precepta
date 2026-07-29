"""Configuration loader.

Reads `config.toml` (the project's existing config) with environment-variable
overrides. Kept deliberately small — the control plane reads these at startup.
"""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

# Project root = the directory that holds config.toml / preceptaai.db.
ROOT = Path(__file__).resolve().parent.parent


def _as_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    db_path: Path
    host: str
    port: int
    sovereign_mode: bool          # in-boundary-only routing + egress lock + audit-on
    default_model: str            # e.g. "vllm/mistral-large-2411"
    ollama_port: int

    @property
    def db_uri(self) -> str:
        return str(self.db_path)


@lru_cache
def get_settings() -> Settings:
    cfg: dict = {}
    cfg_file = ROOT / "config.toml"
    if cfg_file.exists():
        with cfg_file.open("rb") as fh:
            cfg = tomllib.load(fh)

    inference = cfg.get("inference", {})

    db_path = Path(os.environ.get("PRECEPTA_DB", ROOT / "preceptaai.db"))
    host = os.environ.get("PRECEPTA_HOST", "127.0.0.1")
    port = int(os.environ.get("PRECEPTA_PORT", "8000"))
    sovereign = (
        _as_bool(os.environ["PRECEPTA_SOVEREIGN"])
        if "PRECEPTA_SOVEREIGN" in os.environ
        else True  # sovereign by default — the whole point of the product
    )
    default_model = os.environ.get("PRECEPTA_DEFAULT_MODEL", "ollama/llama3.2:3b")
    ollama_port = int(inference.get("ollama_port", 11434))

    return Settings(
        db_path=db_path,
        host=host,
        port=port,
        sovereign_mode=sovereign,
        default_model=default_model,
        ollama_port=ollama_port,
    )
