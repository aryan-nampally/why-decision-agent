"""End-to-end pipeline test with Hindsight and the LLM mocked. No network.

Uses the real Keelwright records in the store fixture, so it exercises precedent scoring,
the date filter, grounding, the verdict rule and the orchestration event stream.
"""
import asyncio
import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from src import app as app_module
from src import memory, reasoning
from src.config import CORPUS
from src.ingest import load_file, parse_record
from src.schema import Assumption, MemoryHit
from src.store import Store


@pytest.fixture
def store(tmp_path):
    s = Store(tmp_path / "t.db")
    for path in CORPUS.glob("*/*.md"):
        rec = parse_record(*load_file(path))
        if rec.id == "ADR-007":
            rec.assumptions = [
                Assumption(id="A1", statement="Peak writes stay under ~1,800/s", critical=True, quote="q1"),
                Assumption(id="A2", statement="Payments run only in us-east-1", critical=True, quote="q2"),
            ]
        s.put(rec)
    return s


def fake_recall(query, kinds, stage, bank_id=None, **_):
    """ADR-007 dominates precedent recall; change recall returns the 3.1k TPS note plus a pre-2023 note."""
    async def go():
        if kinds == ["adr"]:
            ids = ["ADR-007", "ADR-007", "ADR-031", "ADR-007"]
        else:
            ids = ["SIG-2025-12", "SIG-2022-11", "SIG-2025-01"]
        return [MemoryHit(stage=stage, text=f"fact from {i}", document_id=i, kind="x") for i in ids]
    return go()


class Judged:
    precedent_relevant = True
    recommendation = "Evaluate a write-scalable store."

    class A:
        def __init__(self, i, status, ev):
            self.id, self.status, self.explanation, self.evidence_ids = i, status, "x", ev

    assumptions = [A("A1", "BROKEN", ["SIG-2025-12", "SIG-FAKE"]), A("A2", "HOLDS", ["SIG-2025-01"])]


async def fake_judge(system, prompt, model, retries=1):
    assert "SIG-2022-11" not in prompt  # predates the decision: must never reach the judge
    from src.schema import Status
    return model.model_validate({"precedent_relevant": True, "recommendation": Judged.recommendation,
                                 "assumptions": [{"id": a.id, "status": Status(a.status), "explanation": "x",
                                                  "evidence_ids": a.evidence_ids} for a in Judged.assumptions]})


def test_pipeline_events_and_verdict(store, monkeypatch):
    monkeypatch.setattr(memory, "recall", fake_recall)
    monkeypatch.setattr(reasoning, "complete_json", fake_judge)
    events = []

    async def emit(e):
        events.append(e)

    r = asyncio.run(reasoning.Pipeline(store, today=date(2026, 9, 28)).ask("Postgres for the new ledger?", "", emit=emit))

    assert r.verdict.value == "RECONSIDER" and r.decision.id == "ADR-007"
    assert r.assumption_checks[0].evidence_ids == ["SIG-2025-12"]  # hallucinated SIG-FAKE removed
    done = [e["stage"] for e in events if e["status"] == "done"]
    assert done == ["precedent", "assumptions", "changes", "judge", "ground", "verdict"]
    changes = next(e for e in events if e["stage"] == "changes" and e["status"] == "done")
    assert "SIG-2022-11" in changes["filtered_before_decision"]
    ground = next(e for e in events if e["stage"] == "ground")
    assert any("SIG-FAKE" in c for c in ground["changes"])
    verdict = next(e for e in events if e["stage"] == "verdict")
    assert verdict["rule"] == "critical A1 BROKEN → RECONSIDER"


def test_stream_endpoint(store, monkeypatch):
    monkeypatch.setattr(memory, "recall", fake_recall)
    monkeypatch.setattr(reasoning, "complete_json", fake_judge)
    monkeypatch.setattr(app_module, "pipeline", reasoning.Pipeline(store, today=date(2026, 9, 28)))
    with TestClient(app_module.app) as c:
        body = c.post("/api/ask/stream", json={"question": "Postgres for the new ledger?"}).text
    items = [json.loads(line[6:]) for line in body.splitlines() if line.startswith("data: ")]
    assert items[0]["stage"] == "precedent" and items[-1]["stage"] == "result"
    assert items[-1]["data"]["verdict"] == "RECONSIDER"
