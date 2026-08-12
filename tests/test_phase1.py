"""Phase 1 validation — model plane + OpenAI-compatible gateway."""
from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.adapters.model.registry import get_registry
from app.router import resolve, RouteError
from app.settings import get_settings

client = TestClient(app)


def _ollama_up() -> bool:
    s = get_settings()
    try:
        r = httpx.get(f"http://127.0.0.1:{s.ollama_port}/v1/models", timeout=2.0)
        return r.status_code < 500
    except httpx.HTTPError:
        return False


def test_registry_has_ollama():
    reg = get_registry()
    assert "ollama" in reg
    assert reg["ollama"].in_boundary is True


def test_resolve_explicit():
    reg = get_registry()
    backend, model = resolve("ollama/llama3.2:3b", reg)
    assert backend.name == "ollama"
    assert model == "llama3.2:3b"


def test_resolve_rejects_auto_and_bad():
    reg = get_registry()
    with pytest.raises(RouteError):
        resolve("auto:cheapest", reg)
    with pytest.raises(RouteError):
        resolve("bareword", reg)
    with pytest.raises(RouteError):
        resolve("nosuch/model", reg)


def test_list_models_endpoint():
    r = client.get("/v1/models")
    assert r.status_code == 200
    # Phase 15: /v1/models is enriched (id is "<endpoint>/<model>", + owned_by).
    data = r.json()["data"]
    assert any(m["owned_by"] == "ollama" for m in data)
    assert any(m["id"].startswith("ollama") for m in data)


def test_bad_model_returns_400():
    r = client.post("/v1/chat/completions", json={"model": "nope/x", "messages": []})
    assert r.status_code == 400
    assert r.json()["error"]["type"] == "invalid_request_error"


@pytest.mark.skipif(not _ollama_up(), reason="Ollama not running on localhost")
def test_real_inference_through_gateway():
    r = client.post("/v1/chat/completions", json={
        "model": "ollama/llama3.2:3b",
        "messages": [{"role": "user", "content": "Reply with exactly the word: pong"}],
        "max_tokens": 10,
    })
    assert r.status_code == 200, r.text
    body = r.json()
    content = body["choices"][0]["message"]["content"]
    assert isinstance(content, str) and content.strip()
    assert body["precepta"]["backend_used"] == "ollama"
    assert body["precepta"]["in_boundary"] is True
    assert body["precepta"]["route_mode"] == "explicit"
