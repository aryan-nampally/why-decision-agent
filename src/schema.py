"""Data contracts for WHY.

Every historical claim the system makes must resolve to a record ID and a
source path, so provenance lives in the schema rather than in the prompt.
"""
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Verdict(str, Enum):
    REUSE = "REUSE"
    ADAPT = "ADAPT"
    RECONSIDER = "RECONSIDER"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class Status(str, Enum):
    HOLDS = "HOLDS"
    BROKEN = "BROKEN"
    UNKNOWN = "UNKNOWN"


class Alternative(BaseModel):
    name: str
    rejected_because: str = ""


class Assumption(BaseModel):
    """A premise the decision depends on, grounded in an exact quote from the source."""

    id: str  # "A1", "A2", ... (qualified as "ADR-007/A1" in output)
    statement: str
    critical: bool = True
    quote: str = ""
    origin: Literal["extracted", "oracle", "authored"] = "extracted"


class DecisionRecord(BaseModel):
    kind: Literal["adr"] = "adr"
    id: str
    title: str
    date: date
    team: str = ""
    authors: list[str] = []
    status: Literal["accepted", "superseded", "deprecated"] = "accepted"
    context: str = ""
    options: list[str] = []
    decision: str = ""
    rationale: str = ""
    consequences: str = ""
    assumptions: list[Assumption] = []
    supersedes: str | None = None
    superseded_by: str | None = None
    source_ref: str


class Postmortem(BaseModel):
    kind: Literal["postmortem"] = "postmortem"
    id: str
    title: str
    date: date
    severity: str = ""
    authors: list[str] = []
    contributing_decisions: list[str] = []
    summary: str = ""
    root_cause: str = ""
    body: str = ""
    source_ref: str


class Signal(BaseModel):
    kind: Literal["signal"] = "signal"
    id: str
    title: str
    date: date
    author: str = ""
    channel: str = ""
    body: str = ""
    source_ref: str


# ---------------------------------------------------------------- API contracts


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    current_context: str = Field(default="", max_length=4000)


class AssumptionCheck(BaseModel):
    assumption_id: str
    statement: str
    critical: bool
    quote: str = ""
    status: Status
    basis: Literal["confirmed", "no_change_recorded", "contradicted", "ambiguous"] = "no_change_recorded"
    explanation: str = ""
    evidence_ids: list[str] = []


class MemoryHit(BaseModel):
    """A raw Hindsight recall result, surfaced so the memory is inspectable."""

    stage: str
    text: str
    type: str | None = None
    document_id: str | None = None
    kind: str | None = None
    occurred: str | None = None
    score: float | None = None


class EvidenceItem(BaseModel):
    id: str
    kind: str
    date: str
    title: str
    detail: str
    source_ref: str


class Candidate(BaseModel):
    id: str
    title: str
    score: float


class AskResponse(BaseModel):
    verdict: Verdict
    headline: str
    recommendation: str = ""
    decision: DecisionRecord | None = None
    decision_age: str | None = None
    precedent_failed: bool = False
    failure_evidence: list[str] = []
    health: float | None = None
    assumption_checks: list[AssumptionCheck] = []
    evidence: list[EvidenceItem] = []
    candidates: list[Candidate] = []
    ambiguous: bool = False
    memory_hits: list[MemoryHit] = []
    warnings: list[str] = []
    timings_ms: dict[str, int] = {}


class StatelessResponse(BaseModel):
    answer: str
    verdict: str
    timings_ms: dict[str, int] = {}


class AcceptRequest(BaseModel):
    question: str
    title: str
    decision: str
    rationale: str
    based_on: str | None = None
    assumptions: list[str] = []
    team: str = "Platform"


class SignalRequest(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    detail: str = Field(default="", max_length=4000)


class TripwireAlert(BaseModel):
    decision_id: str
    decision_title: str
    decision_date: str
    assumption_id: str
    statement: str
    critical: bool
    explanation: str


class SignalResponse(BaseModel):
    signal: Signal
    alerts: list[TripwireAlert]
    scanned: list[str] = []
    timings_ms: dict[str, int] = {}


class IngestRequest(BaseModel):
    markdown: str = Field(min_length=20)
