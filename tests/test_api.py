"""API contract tests with memory and LLM mocked out. No network."""
import pytest
from fastapi.testclient import TestClient

from src import app as app_module
from src import memory
from src.schema import AskResponse, Verdict


@pytest.fixture
def client(monkeypatch):
    async def fake_ping():
        return True
    monkeypatch.setattr(memory, "ping", fake_ping)
    return TestClient(app_module.app)


def test_health_and_index(client):
    assert client.get("/health").json()["hindsight"] is True
    assert client.get("/").status_code == 200


def test_ask_returns_contract(client, monkeypatch):
    async def fake_ask(q, c=""):
        return AskResponse(verdict=Verdict.INSUFFICIENT_EVIDENCE, headline="none")
    monkeypatch.setattr(app_module.pipeline, "ask", fake_ask)
    r = client.post("/api/ask", json={"question": "Which payroll vendor?"})
    assert r.status_code == 200 and r.json()["verdict"] == "INSUFFICIENT_EVIDENCE"


def test_ask_validates_input(client):
    assert client.post("/api/ask", json={"question": "x"}).status_code == 422


def test_memory_outage_is_a_clear_503(client, monkeypatch):
    async def down(q, c=""):
        raise memory.MemoryError_("recall failed: connection refused")
    monkeypatch.setattr(app_module.pipeline, "ask", down)
    r = client.post("/api/ask", json={"question": "Should we reuse ADR-007?"})
    assert r.status_code == 503 and "Hindsight" in r.json()["detail"]


def test_malformed_ingest_is_rejected(client):
    r = client.post("/api/ingest", json={"markdown": "just some text without front matter at all"})
    assert r.status_code == 422


def test_unknown_record_404(client):
    assert client.get("/api/records/ADR-999").status_code == 404
