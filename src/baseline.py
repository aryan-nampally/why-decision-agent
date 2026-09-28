"""Comparison conditions (methodology §10.1). All emit the same fields so scoring is identical.

A  — no memory: the model answers from general knowledge.
B2 — retrieval memory: Hindsight recall over the same bank, top facts pasted into the prompt, no decision structure.
B3 — Hindsight reflect: Hindsight's own reasoning over the bank, with a structured response schema.
"""
from __future__ import annotations

import time

from pydantic import BaseModel

from . import memory
from .llm import complete_json

VERDICTS = "REUSE | ADAPT | RECONSIDER | INSUFFICIENT_EVIDENCE"
_VERDICT_HELP = (f"verdict is one of {VERDICTS}: REUSE if the earlier approach still fits, ADAPT if it fits with changes, "
                 "RECONSIDER if the conditions behind it changed or it failed, INSUFFICIENT_EVIDENCE if you have no "
                 "relevant precedent.")


class BaselineAnswer(BaseModel):
    verdict: str = "INSUFFICIENT_EVIDENCE"
    precedent_id: str | None = None
    broken_conditions: list[str] = []
    answer: str = ""
    timings_ms: dict[str, int] = {}


A_SYSTEM = ("You are a senior engineer advising a colleague at a freight-logistics company. Answer the question. "
            f"Return JSON: {{\"verdict\": \"...\", \"answer\": \"2-3 sentences\"}}. {_VERDICT_HELP}")

B2_SYSTEM = ("You are an engineering assistant with access to your organization's memory. Use the MEMORIES below "
             "(each prefixed with its source record ID) to answer. Return JSON: {\"verdict\": \"...\", "
             "\"precedent_id\": \"ADR-... or null\", \"broken_conditions\": [\"conditions of the earlier decision that "
             f"are no longer true\"], \"answer\": \"2-3 sentences\"}}. {_VERDICT_HELP}")


async def no_memory(question: str, context: str = "") -> BaselineAnswer:
    t = time.perf_counter()
    out = await complete_json(A_SYSTEM, f"Question: {question}\nContext: {context or '(none)'}", BaselineAnswer)
    out.precedent_id, out.broken_conditions = None, []
    out.timings_ms = {"total": int((time.perf_counter() - t) * 1000)}
    return out


async def retrieval_memory(question: str, context: str = "", k: int = 15) -> BaselineAnswer:
    t = time.perf_counter()
    hits = await memory.recall(f"{question}\n{context}".strip(), ["adr", "postmortem", "signal"], stage="b2")
    facts = "\n".join(f"[{h.document_id}] {h.text}" for h in hits[:k])
    out = await complete_json(B2_SYSTEM, f"MEMORIES:\n{facts}\n\nQuestion: {question}\nContext: {context or '(none)'}",
                              BaselineAnswer)
    out.timings_ms = {"total": int((time.perf_counter() - t) * 1000)}
    return out


REFLECT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["REUSE", "ADAPT", "RECONSIDER", "INSUFFICIENT_EVIDENCE"]},
        "precedent_id": {"type": "string"},  # a ["string","null"] union makes the API return 500
        "broken_conditions": {"type": "array", "items": {"type": "string"}},
        "answer": {"type": "string"},
    },
    "required": ["verdict", "answer"],
}


async def hindsight_reflect(question: str, context: str = "", bank_id: str | None = None) -> BaselineAnswer:
    t = time.perf_counter()
    q = (f"{question}\nIs there an earlier decision (give its ADR ID) that applies, and do the conditions it relied on "
         f"still hold? {_VERDICT_HELP}")
    r = await memory.reflect(q, context=context, response_schema=REFLECT_SCHEMA, bank_id=bank_id or memory.BANK_ID)
    data = r.structured_output or {}
    out = BaselineAnswer(verdict=str(data.get("verdict", "INSUFFICIENT_EVIDENCE")),
                         precedent_id=data.get("precedent_id"),
                         broken_conditions=list(data.get("broken_conditions") or []),
                         answer=str(data.get("answer") or r.text or ""))
    out.timings_ms = {"total": int((time.perf_counter() - t) * 1000)}
    return out
