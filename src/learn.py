"""The learning half of the loop: everything that writes new memory.

- ingest:  a new ADR / postmortem / change note → canonical store + Hindsight retain
- signal:  a change typed by an engineer → retain + tripwire scan (Algorithm 2)
- accept:  an accepted recommendation → new decision retained, predecessor superseded
"""
from __future__ import annotations

import asyncio
import re
import time
from datetime import date

from pydantic import BaseModel

from . import memory, rules
from .config import TRIPWIRE_M
from .ingest import extract_assumptions, parse_record
from .llm import LLMError, complete_json
from .schema import (AcceptRequest, Assumption, DecisionRecord, Signal, SignalResponse, TripwireAlert)
from .store import Store


async def ingest_markdown(store: Store, text: str, source_ref: str) -> tuple[object, list[str]]:
    rec = parse_record(text, source_ref)
    warnings: list[str] = []
    if isinstance(rec, DecisionRecord):
        rec.assumptions, warnings = await extract_assumptions(rec, text, use_cache=False)
    store.put(rec)
    await memory.retain(rec, text)
    return rec, warnings


# ---------------------------------------------------------------- tripwire

TRIP_SYSTEM = """A change just happened in an engineering organization. For EACH past decision listed and its assumptions,
decide which assumptions this change directly contradicts. An assumption is broken only if the change makes it
no longer true (not merely related). Judge every decision independently. Return JSON:
{"decisions": [{"id": "ADR-001", "assumptions": [{"id": "A1", "broken": true, "explanation": "one sentence with concrete details"}]}]}"""


class _Trip(BaseModel):
    id: str
    broken: bool
    explanation: str = ""


class _TripDecision(BaseModel):
    id: str
    assumptions: list[_Trip] = []


class _TripOut(BaseModel):
    decisions: list[_TripDecision]


_BACKGROUND: set[asyncio.Task] = set()


def _next_signal_id(store: Store, d: date) -> str:
    prefix = f"SIG-{d.year}-{d.month:02d}"
    n = sum(1 for r in store.all("signal") if r.id.startswith(prefix))
    return prefix if n == 0 else f"{prefix}-{n + 1}"


async def record_signal(store: Store, title: str, detail: str, today: date | None = None) -> SignalResponse:
    t0 = time.perf_counter()
    d = today or date.today()
    sig = Signal(id=_next_signal_id(store, d), title=title, date=d, author="(entered in WHY)",
                 channel="WHY", body=detail or title, source_ref="WHY UI")
    store.put(sig)
    retain_task = asyncio.create_task(memory.retain(sig, f"{title}\n\n{detail}"))
    hits = await memory.recall(f"{title}. {detail}", ["adr"], stage="tripwire")
    scores = rules.reciprocal_rank_scores([h.document_id for h in hits])
    cands = []
    for did, _ in sorted(scores.items(), key=lambda kv: -kv[1]):
        r = store.get(did)
        if isinstance(r, DecisionRecord) and r.status == "accepted" and r.date < d and r.assumptions:
            cands.append(r)
        if len(cands) >= TRIPWIRE_M:
            break

    # one LLM call judges every candidate: a free-tier requests-per-minute limit makes a per-decision fan-out slow
    alerts: list[TripwireAlert] = []
    if cands:
        lines = [f"CHANGE ({d}): {title}. {detail}"]
        for r in cands:
            lines += ["", f"PAST DECISION [{r.id}] {r.date}: {r.title} — {r.decision}"]
            lines += [f"  {a.id}: {a.statement}" for a in r.assumptions]
        try:
            out = await complete_json(TRIP_SYSTEM, "\n".join(lines), _TripOut)
        except LLMError:
            out = _TripOut(decisions=[])
        by_rec = {r.id: r for r in cands}
        for dec in out.decisions:
            r = by_rec.get(dec.id)
            if r is None:
                continue  # the model named a decision it was not given
            by_id = {a.id: a for a in r.assumptions}
            alerts += [TripwireAlert(decision_id=r.id, decision_title=r.title, decision_date=r.date.isoformat(),
                                     assumption_id=x.id, statement=by_id[x.id].statement, critical=by_id[x.id].critical,
                                     explanation=x.explanation)
                       for x in dec.assumptions if x.broken and x.id in by_id]
    alerts.sort(key=lambda a: (not a.critical, a.decision_date))
    _BACKGROUND.add(retain_task)  # Hindsight processes the retain server-side; don't block the response on it
    retain_task.add_done_callback(_BACKGROUND.discard)
    return SignalResponse(signal=sig, alerts=alerts, scanned=[r.id for r in cands],
                          timings_ms={"total": int((time.perf_counter() - t0) * 1000)})


# ---------------------------------------------------------------- accept

ASSUME_SYSTEM = """Given a new engineering decision and its rationale, list 2-3 assumptions about the world it depends on
(volumes, locations, requirements, team skills, external behaviour) that, if they changed, should trigger a review.
Mark at most one as critical. Return JSON: {"assumptions": [{"statement": "...", "critical": true}]}"""


class _A(BaseModel):
    statement: str
    critical: bool = False


class _AOut(BaseModel):
    assumptions: list[_A]


def _next_adr_id(store: Store) -> str:
    nums = [int(m.group(1)) for r in store.all("adr") if (m := re.match(r"ADR-(\d+)", r.id))]
    return f"ADR-{max(nums, default=0) + 1:03d}"


async def accept_decision(store: Store, req: AcceptRequest, today: date | None = None) -> DecisionRecord:
    d = today or date.today()
    if req.assumptions:
        assumptions = [Assumption(id=f"A{i + 1}", statement=s, critical=(i == 0), quote=s, origin="authored")
                       for i, s in enumerate(req.assumptions)]
    else:
        try:
            out = await complete_json(ASSUME_SYSTEM, f"Decision: {req.decision}\nRationale: {req.rationale}", _AOut)
            assumptions = [Assumption(id=f"A{i + 1}", statement=a.statement, critical=a.critical, quote=a.statement,
                                      origin="authored") for i, a in enumerate(out.assumptions[:3])]
        except LLMError:
            assumptions = []
    rec = DecisionRecord(id=_next_adr_id(store), title=req.title, date=d, team=req.team, authors=["(accepted in WHY)"],
                         context=req.question, decision=req.decision, rationale=req.rationale,
                         assumptions=assumptions, supersedes=req.based_on, source_ref="WHY UI")
    if req.based_on:
        old = store.get(req.based_on)
        if isinstance(old, DecisionRecord):
            store.put(old.model_copy(update={"status": "superseded", "superseded_by": rec.id}))
    store.put(rec)
    text = (f"# {rec.id}: {rec.title}\n\n## Context\n{req.question}\n\n## Decision Outcome\n{req.decision}\n\n"
            f"{req.rationale}\n\n## Assumptions\n" + "\n".join(f"- {a.statement}" for a in assumptions)
            + (f"\n\nSupersedes {req.based_on}." if req.based_on else ""))
    await memory.retain(rec, text)
    return rec
