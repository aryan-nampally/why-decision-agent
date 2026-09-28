"""The WHY pipeline (methodology §6–7, Algorithm 1).

1. Stage-1 recall: find the precedent decision (Hindsight, kind:adr).
2. Stage-2 recall: for each of its assumptions, find what changed since (kind:signal, kind:postmortem).
3. LLM judges each assumption against dated, ID'd evidence.
4. Code grounds the citations and applies the verdict rules.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import date
from typing import Awaitable, Callable, Literal

from pydantic import BaseModel

from . import memory, rules
from .config import AMBIGUITY_MARGIN, K0, K2, ROOT
from .llm import LLMError, complete_json, current_model
from .schema import (AskResponse, Assumption, AssumptionCheck, Candidate, DecisionRecord, EvidenceItem, MemoryHit,
                     Postmortem, Signal, Status, Verdict)
from .store import Store

AssumptionMode = Literal["extracted", "oracle"]
Emit = Callable[[dict], Awaitable[None]]
_GOLD: dict | None = None


def oracle_assumptions(decision_id: str) -> list[Assumption]:
    global _GOLD
    if _GOLD is None:
        _GOLD = json.loads((ROOT / "evaluation" / "gold_assumptions.json").read_text(encoding="utf-8"))
    return [Assumption(id=a["id"], statement=a["statement"], critical=a["critical"], quote=a["quote"], origin="oracle")
            for a in _GOLD.get(decision_id, [])]


# ---------------------------------------------------------------- judge

JUDGE_SYSTEM = """You are WHY, an engineering decision-memory agent. You check whether the assumptions behind a PAST
engineering decision still hold TODAY, using only the evidence provided.

For each assumption return:
- status HOLDS: evidence confirms it still holds (cite it), or no evidence addresses it at all (cite nothing).
- status BROKEN: some evidence item or the USER context shows the condition is no longer true (cite the IDs).
- status UNKNOWN: evidence addresses it but is ambiguous or conflicting.
Evidence is dated; when items conflict, the most recent wins. The question's own wording is NOT evidence:
a question that says "like we did before" does not show the old conditions still hold.
Cite evidence ONLY by the IDs shown in square brackets. Be concrete: quote numbers and dates.

Also decide precedent_relevant: true if the past decision addresses the same kind of choice the question asks about
(same technology decision or same design problem), false if it is only loosely related.

Return JSON:
{"precedent_relevant": true, "assumptions": [{"id": "A1", "status": "HOLDS|BROKEN|UNKNOWN", "explanation": "...", "evidence_ids": ["..."]}],
 "recommendation": "2-3 sentences: what the engineer should do now and why, referencing the decision ID"}"""


class _JudgedAssumption(BaseModel):
    id: str
    status: Status
    explanation: str = ""
    evidence_ids: list[str] = []


class _Judgement(BaseModel):
    precedent_relevant: bool = True
    assumptions: list[_JudgedAssumption]
    recommendation: str = ""


def _evidence_line(e: EvidenceItem) -> str:
    detail = e.detail.replace("\n", " ")
    return f"[{e.id}] {e.date} ({e.kind}) {e.title}: {detail[:450]}"


def _judge_prompt(rec: DecisionRecord, assumptions: list[Assumption], evidence: list[EvidenceItem],
                  question: str, context: str) -> str:
    lines = [f"PAST DECISION [{rec.id}] {rec.date.isoformat()} — {rec.title} (team {rec.team})",
             f"Chosen: {rec.decision}", "", "ASSUMPTIONS IT DEPENDED ON:"]
    for a in assumptions:
        lines.append(f"  {a.id}{' [critical]' if a.critical else ''}: {a.statement}  (source: \"{a.quote}\")")
    lines += ["", "EVIDENCE (recorded after the decision):"]
    lines += [f"  {_evidence_line(e)}" for e in evidence] or ["  (none)"]
    lines += ["", f"[USER] current context from the engineer: {context or '(none given)'}", "", f"QUESTION: {question}"]
    return "\n".join(lines)


# ---------------------------------------------------------------- helpers

def _to_evidence(rec: DecisionRecord | Postmortem | Signal) -> EvidenceItem:
    if isinstance(rec, DecisionRecord):  # a later decision is evidence too (used on real ADR histories)
        return EvidenceItem(id=rec.id, kind="adr", date=rec.date.isoformat(), title=rec.title,
                            detail=f"{rec.context} Decision: {rec.rationale}", source_ref=rec.source_ref)
    if isinstance(rec, Postmortem):
        detail = f"{rec.summary} Root cause: {rec.root_cause}".strip()
        kind = "postmortem"
    else:
        detail, kind = rec.body, "signal"
    return EvidenceItem(id=rec.id, kind=kind, date=rec.date.isoformat(), title=rec.title, detail=detail,
                        source_ref=rec.source_ref)


def _ms(t: float) -> int:
    return int((time.perf_counter() - t) * 1000)


class Pipeline:
    def __init__(self, store: Store | None = None, today: date | None = None, bank_id: str | None = None,
                 evidence_kinds: tuple[str, ...] = ("signal", "postmortem")):
        self.store = store or Store()
        self.today = today
        self.bank = bank_id or memory.BANK_ID
        self.evidence_kinds = evidence_kinds

    # ------------------------------------------------------------ stage 1
    async def find_precedent(self, question: str, context: str) -> tuple[list[Candidate], list[MemoryHit]]:
        hits = await memory.recall(f"{question}\n{context}".strip(), ["adr"], stage="precedent", bank_id=self.bank)
        scores = rules.reciprocal_rank_scores([h.document_id for h in hits], K0)
        cands = []
        for did, s in sorted(scores.items(), key=lambda kv: -kv[1]):
            rec = self.store.get(did)
            if isinstance(rec, DecisionRecord):
                cands.append(Candidate(id=did, title=rec.title, score=round(s, 4)))
        return cands, hits

    # ------------------------------------------------------------ stage 2
    async def gather_evidence(self, rec: DecisionRecord, assumptions: list[Assumption], question: str,
                              context: str, two_stage: bool) -> tuple[list[EvidenceItem], list[MemoryHit], list[str], dict]:
        """Returns (evidence, raw hits, failed-precedent postmortems, trace of what each query found)."""
        if two_stage:
            labels = [a.id for a in assumptions]
            queries = [f"{a.statement}. ({rec.title})" for a in assumptions]
        else:
            labels, queries = ["question"], [f"{question}\n{context}".strip()]
        labels.append("incidents")
        queries.append(f"incident or outage involving {rec.title}: {rec.decision}")  # linked postmortems
        results = await asyncio.gather(*(memory.recall(q, list(self.evidence_kinds), stage=f"change:{i}", bank_id=self.bank)
                                         for i, q in enumerate(queries)))
        evidence: dict[str, EvidenceItem] = {}
        failures: list[str] = []
        all_hits: list[MemoryHit] = []
        trace = {"queries": [], "filtered_before_decision": []}
        for label, q, hits in zip(labels, queries, results):
            all_hits += hits
            taken, found = 0, []
            for h in hits:
                if taken >= K2 or not h.document_id:
                    continue
                if h.document_id in evidence:
                    if h.document_id not in found:
                        found.append(h.document_id)
                    continue
                r = self.store.get(h.document_id)
                if r is None or r.id == rec.id or r.kind not in self.evidence_kinds:
                    continue
                if not rules.admissible(r.date, rec.date):
                    if r.id not in trace["filtered_before_decision"]:
                        trace["filtered_before_decision"].append(r.id)
                    continue
                if self.today and r.date > self.today:
                    continue
                evidence[r.id] = _to_evidence(r)
                found.append(r.id)
                taken += 1
                if isinstance(r, Postmortem) and rec.id in r.contributing_decisions:
                    failures.append(r.id)
            trace["queries"].append({"for": label, "query": q[:160], "facts": len(hits), "found": found})
        ordered = sorted(evidence.values(), key=lambda e: e.date)
        return ordered, all_hits, sorted(set(failures)), trace

    # ------------------------------------------------------------ full evaluation
    async def ask(self, question: str, context: str = "", assumptions_mode: AssumptionMode = "extracted",
                  two_stage: bool = True, forced_precedent: str | None = None, emit: Emit | None = None) -> AskResponse:
        """Algorithm 1. If `emit` is given, a trace event is sent as each stage finishes (orchestration view)."""
        async def ev(stage: str, actor: str, status: str, **data):
            if emit:
                await emit({"stage": stage, "actor": actor, "status": status, **data})

        t_all = time.perf_counter()
        timings: dict[str, int] = {}
        warnings: list[str] = []

        await ev("precedent", "hindsight", "running", detail="recall(question, tags=[kind:adr])")
        t = time.perf_counter()
        cands, hits1 = await self.find_precedent(question, context)
        timings["recall_precedent"] = _ms(t)
        active = [c for c in cands if getattr(self.store.get(c.id), "status", "") != "superseded"]
        pick = forced_precedent or (active[0].id if active else None)
        rec = self.store.get(pick) if pick else None
        await ev("precedent", "hindsight", "done", ms=timings["recall_precedent"], facts=len(hits1),
                 candidates=[c.model_dump() for c in cands[:4]], picked=pick)
        if not isinstance(rec, DecisionRecord):
            await ev("verdict", "code", "done", verdict="INSUFFICIENT_EVIDENCE", rule="no decision in memory matches the question")
            return AskResponse(verdict=Verdict.INSUFFICIENT_EVIDENCE, candidates=cands, memory_hits=hits1,
                               headline="No decision in memory addresses this question.",
                               recommendation="Treat this as a new decision and record it once made.",
                               timings_ms=timings)
        ambiguous = len(active) > 1 and (active[0].score - active[1].score) / active[0].score < AMBIGUITY_MARGIN

        assumptions = oracle_assumptions(rec.id) if assumptions_mode == "oracle" else rec.assumptions
        if not assumptions:
            warnings.append(f"{rec.id} has no grounded assumptions; applicability cannot be checked")

        await ev("assumptions", "store", "done", decision=rec.id, date=rec.date.isoformat(), title=rec.title,
                 assumptions=[{"id": a.id, "statement": a.statement, "critical": a.critical, "quote": a.quote} for a in assumptions])

        n_q = len(assumptions) + 1 if two_stage else 2
        kinds = ", ".join("kind:" + k for k in self.evidence_kinds)
        await ev("changes", "hindsight", "running", detail=f"{n_q} parallel recalls, one per assumption, tags=[{kinds}]")
        t = time.perf_counter()
        evidence, hits2, failures, trace = await self.gather_evidence(rec, assumptions, question, context, two_stage)
        timings["recall_changes"] = _ms(t)
        await ev("changes", "hindsight", "done", ms=timings["recall_changes"], facts=len(hits2), evidence=len(evidence),
                 failures=failures, after=rec.date.isoformat(), **trace)

        await ev("judge", "llm", "running", detail=f"{current_model()} · {len(assumptions)} assumptions × {len(evidence)} evidence items")
        t = time.perf_counter()
        prompt = _judge_prompt(rec, assumptions, evidence, question, context)
        by_id = {a.id: a for a in assumptions}
        try:
            j = await complete_json(JUDGE_SYSTEM, prompt, _Judgement)
            relevant, recommendation = j.precedent_relevant, j.recommendation
            judged = {x.id.split("/")[-1]: x for x in j.assumptions}
            complete = True
        except LLMError as e:  # Property 3: fail safe → everything UNKNOWN, verdict never REUSE
            warnings.append(f"judge failed, defaulting to UNKNOWN: {e}")
            relevant, recommendation, judged, complete = True, "Assumptions could not be evaluated; review manually.", {}, False
        timings["judge"] = _ms(t)

        checks = []
        for a in assumptions:
            x = judged.get(a.id)
            if x is None:
                if judged:
                    warnings.append(f"judge omitted {a.id}; marked UNKNOWN")
                checks.append(AssumptionCheck(assumption_id=a.id, statement=a.statement, critical=a.critical,
                                              quote=a.quote, status=Status.UNKNOWN, basis="ambiguous"))
            else:
                checks.append(AssumptionCheck(assumption_id=a.id, statement=a.statement, critical=a.critical,
                                              quote=a.quote, status=x.status, explanation=x.explanation,
                                              evidence_ids=x.evidence_ids))
        await ev("judge", "llm", "done", ms=timings["judge"], relevant=relevant, ok=complete,
                 statuses=[{"id": c.assumption_id, "status": c.status.value, "evidence": c.evidence_ids} for c in checks])
        provided = {e.id for e in evidence} | {"USER"}
        checks, gw = rules.ground(checks, provided)
        warnings += gw
        await ev("ground", "code", "done", provided=len(provided), changes=gw)

        if not relevant:
            await ev("verdict", "code", "done", verdict="INSUFFICIENT_EVIDENCE",
                     rule=f"judge: {rec.id} does not address this question")
            return AskResponse(verdict=Verdict.INSUFFICIENT_EVIDENCE, candidates=cands, memory_hits=hits1 + hits2,
                               headline=f"Closest memory ({rec.id}: {rec.title}) does not address this question.",
                               recommendation="No trustworthy precedent. Treat this as a new decision.",
                               warnings=warnings, timings_ms=timings)

        v = rules.verdict(checks, precedent_failed=bool(failures), evaluation_complete=complete)
        timings["total"] = _ms(t_all)
        await ev("verdict", "code", "done", verdict=v.value, rule=rules.explain(checks, failures, complete),
                 health=rules.health(checks))
        return AskResponse(
            verdict=v, headline=_headline(v, rec, checks, failures), recommendation=recommendation,
            decision=rec.model_copy(update={"assumptions": assumptions}),
            decision_age=rules.age(rec.date, self.today or date.today()),
            precedent_failed=bool(failures), failure_evidence=failures, health=rules.health(checks),
            assumption_checks=checks, evidence=evidence, candidates=cands, ambiguous=ambiguous,
            memory_hits=hits1 + hits2, warnings=warnings, timings_ms=timings,
        )


def _headline(v: Verdict, rec: DecisionRecord, checks: list[AssumptionCheck], failures: list[str]) -> str:
    broken = [c for c in checks if c.status == Status.BROKEN]
    crit = [c for c in broken if c.critical]
    if v == Verdict.RECONSIDER:
        parts = []
        if crit:
            n = len(crit)
            parts.append(f"{n} critical assumption{'s' if n > 1 else ''} behind {rec.id} no longer hold{'' if n > 1 else 's'}")
        if failures:
            parts.append(f"{', '.join(failures)} records this approach failing")
        return "; ".join(parts) + "."
    if v == Verdict.ADAPT:
        if broken:
            return f"{rec.id} still applies, but {len(broken)} supporting condition{'s' if len(broken) > 1 else ''} changed."
        return f"{rec.id} likely applies, but a critical condition cannot be confirmed."
    return f"{rec.id} still applies: no recorded change contradicts its assumptions."
