"""Parsing and quote-grounding tests. No network."""
import pytest

from src.config import CORPUS
from src.ingest import IngestError, load_file, parse_record, quote_in_source
from src.schema import DecisionRecord, Postmortem, Signal


def test_parse_every_corpus_file():
    for path in CORPUS.glob("*/*.md"):
        text, ref = load_file(path)
        rec = parse_record(text, ref)
        assert rec.id in path.name and ref.startswith("data/corpus/")


def test_adr_fields():
    text, ref = load_file(CORPUS / "adrs" / "ADR-007.md")
    rec = parse_record(text, ref)
    assert isinstance(rec, DecisionRecord)
    assert rec.decision.startswith("PostgreSQL 14 on RDS")
    assert len(rec.options) == 3 and rec.team == "Payments"


def test_postmortem_links_and_signal():
    pm = parse_record(*load_file(CORPUS / "postmortems" / "PM-2025-02.md"))
    assert isinstance(pm, Postmortem) and pm.contributing_decisions == ["ADR-012"]
    sig = parse_record(*load_file(CORPUS / "signals" / "SIG-2025-08.md"))
    assert isinstance(sig, Signal) and sig.date.isoformat() == "2025-08-14"


def test_malformed_documents_rejected():
    with pytest.raises(IngestError):
        parse_record("no front matter here", "x")
    with pytest.raises(IngestError):
        parse_record("---\nid: ADR-099\ntitle: t\ndate: 2025-01-01\n---\n\nno sections", "x")
    with pytest.raises(IngestError):
        parse_record("---\nid: XYZ-1\ntitle: t\ndate: 2025-01-01\n---\n\nbody", "x")


SRC = "Finance's month-end close runs a set of about 40 SQL reports. Current peak load is roughly 600 writes per second."


def test_quote_grounding():
    assert quote_in_source("Finance’s month‑end close runs a set of about 40 SQL reports", SRC)  # typography
    assert quote_in_source("Finance's month-end close runs ... roughly 600 writes per second", SRC)  # elision
    assert not quote_in_source("Finance runs 400 SQL reports every night", SRC)  # fabricated
    assert not quote_in_source("Finance's month-end close ... peak load is roughly 900 writes", SRC)  # one bad fragment
    assert not quote_in_source("reports", SRC)  # too short to count as evidence
