"""Typed request/response contracts for the AI Provider Integration API (Phase 15).

These feed FastAPI's OpenAPI so `/docs` and `/openapi.json` describe the real
shapes, and validate inbound bodies. Response bodies stay dict-based in the
handlers (governance envelope, etc.), with these models documenting them.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── providers + catalog ────────────────────────────────────────────────────
class ProviderConfigField(BaseModel):
    field: str
    label: str = ""
    required: bool = True
    secret: bool = False
    example: str = ""


class ProviderInfo(BaseModel):
    provider: str                          # type id: ollama | vllm | neysa | hf | openai-compatible
    name: str
    boundary: str                          # "in-boundary" | "cloud" | ...
    requires_egress_approval: bool = False
    config_schema: list[ProviderConfigField] = Field(default_factory=list)


class Capabilities(BaseModel):
    streaming: bool = False
    function_calling: bool = False
    vision: bool = False


class CatalogModel(BaseModel):
    id: str
    provider: str
    mode: str = "chat"                     # chat | embedding | ...
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    input_cost_per_1m: float | None = None
    output_cost_per_1m: float | None = None
    capabilities: Capabilities = Field(default_factory=Capabilities)


# ── endpoints (renamed from "backends") ─────────────────────────────────────
class EndpointCreate(BaseModel):
    provider: str = Field(..., description="type id or a unique name-slug for this endpoint")
    base_url: str
    api_key: str | None = None
    model: str = ""
    in_boundary: bool = True
    tier: int = 1


class EndpointUpdate(BaseModel):
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    in_boundary: bool | None = None
    tier: int | None = None


# ── inference + embeddings (OpenAI-shaped) ──────────────────────────────────
class ChatMessage(BaseModel):
    role: str
    content: str


class InferenceRequest(BaseModel):
    model: str = "auto"
    messages: list[ChatMessage]
    temperature: float | None = None
    max_tokens: int | None = None
    stream: bool = False


class EmbeddingsRequest(BaseModel):
    model: str = "auto"
    input: str | list[str]


# ── management keys ─────────────────────────────────────────────────────────
class ManageKeyCreate(BaseModel):
    name: str
    scope: str = "manage"                  # 'manage' | 'inference'
    manage_write: bool = False             # read-only vs read-write (management keys)
    team: str = ""
    expires_in_days: int | None = 90


class ErrorBody(BaseModel):
    error: dict[str, Any]
