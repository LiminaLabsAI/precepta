"""Phase 5 validation — infra visibility: metrics parse, snapshot, telemetry."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.adapters.infra import parse_prometheus, snapshot, record_telemetry
from app.db import get_conn

client = TestClient(app)


class FakeBE:
    def __init__(self, name, in_boundary=True, model="m", healthy=True):
        self.name = name
        self.in_boundary = in_boundary
        self.default_model = model
        self.base_url = "http://x/v1"
        self._h = healthy
    def health(self): return self._h


def test_parse_prometheus():
    text = (
        "# HELP vllm:gpu_cache_usage_perc GPU KV-cache usage\n"
        "# TYPE vllm:gpu_cache_usage_perc gauge\n"
        "vllm:gpu_cache_usage_perc 0.62\n"
        'vllm:num_requests_running{model="mistral"} 4\n'
        "garbage line\n"
    )
    m = parse_prometheus(text)
    assert m["vllm:gpu_cache_usage_perc"] == 0.62
    assert m["vllm:num_requests_running"] == 4.0


def test_snapshot_structure():
    reg = {"a": FakeBE("a", healthy=True), "b": FakeBE("b", in_boundary=False, healthy=False)}
    snap = {e["backend"]: e for e in snapshot(reg)}
    assert snap["a"]["status"] == "healthy"
    assert snap["a"]["in_boundary"] is True
    assert snap["b"]["status"] == "down"
    assert snap["b"]["in_boundary"] is False
    for e in snap.values():
        assert set(e) >= {"backend", "in_boundary", "model", "latency_ms", "status", "gpu", "vram"}


def test_record_telemetry_writes_row():
    with get_conn() as conn:
        before = conn.execute("SELECT COUNT(*) c FROM telemetry").fetchone()["c"]
    record_telemetry(inference_ms=123, tokens_in=5, tokens_out=7, backend="ollama")
    with get_conn() as conn:
        after = conn.execute("SELECT COUNT(*) c FROM telemetry").fetchone()["c"]
        row = conn.execute("SELECT * FROM telemetry ORDER BY captured_at DESC LIMIT 1").fetchone()
    assert after == before + 1
    assert row["inference_ms"] == 123
    assert row["agent_id"] == "ollama"


def test_infra_endpoint():
    r = client.get("/infra")
    assert r.status_code == 200
    backends = {b["backend"]: b for b in r.json()["backends"]}
    assert "ollama" in backends
    assert "status" in backends["ollama"]
