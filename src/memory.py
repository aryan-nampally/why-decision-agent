"""Hindsight memory layer.

Every record is retained with its real historical timestamp, its record ID as
document_id, and a kind tag, so recall can be scoped (decisions vs. changes)
and every recalled fact maps back to a canonical record.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, time
from typing import Iterable

from hindsight_client import Hindsight

from .config import BANK_ID, HINDSIGHT_API_KEY, HINDSIGHT_BASE_URL
from .schema import DecisionRecord, MemoryHit, Postmortem, Signal

BANK_MISSION = (
    "Organizational memory for Keelwright Freight engineering. Remember architecture decisions, "
    "the reasons and conditions they depended on, incidents and their causes, and changes to the "
    "business and technical environment, so past decisions can be re-evaluated when conditions change."
)
RETAIN_MISSION = (
    "Extract: decisions and the options rejected; the concrete conditions each decision relied on "
    "(numbers, volumes, regions, customer locations, contracts, compliance needs, team skills, budgets); "
    "incident causes and which decisions contributed; and any change in those conditions, with dates."
)
CONTEXT = {"adr": "architecture decision record", "postmortem": "incident postmortem", "signal": "engineering change note"}


class MemoryError_(RuntimeError):
    """Hindsight is unreachable or returned an error."""


_client: Hindsight | None = None
CALLS = {"recall": 0, "retain": 0, "reflect": 0}  # process-wide counters (performance evaluation)


def client() -> Hindsight:
    global _client
    if _client is None:
        _client = Hindsight(base_url=HINDSIGHT_BASE_URL, api_key=HINDSIGHT_API_KEY, timeout=120)
    return _client


async def aclose() -> None:
    """Close the Hindsight client's HTTP session (avoids "Unclosed client session" warnings at exit)."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def closing(coro):
    """Run a script's top-level coroutine, then close the Hindsight client."""
    try:
        return await coro
    finally:
        await aclose()


async def reset_bank(bank_id: str = BANK_ID, name: str = "WHY — Keelwright decisions", mission: str = BANK_MISSION) -> None:
    c = client()
    try:
        await c.adelete_bank(bank_id)
    except Exception:
        pass
    await c.acreate_bank(bank_id=bank_id, name=name, mission=mission,
                         retain_mission=RETAIN_MISSION, disposition_skepticism=5, disposition_literalism=4,
                         disposition_empathy=2)


def _content(rec: DecisionRecord | Postmortem | Signal, raw_text: str) -> str:
    header = f"[{rec.id}] {rec.title} ({rec.date.isoformat()})"
    return f"{header}\n\n{raw_text}"


async def retain(rec: DecisionRecord | Postmortem | Signal, raw_text: str, bank_id: str = BANK_ID) -> dict:
    CALLS["retain"] += 1
    tags = [f"kind:{rec.kind}"]
    team = getattr(rec, "team", "")
    if team:
        tags.append(f"team:{team.lower()}")
    try:
        r = await client().aretain(
            bank_id=bank_id, content=_content(rec, raw_text),
            timestamp=datetime.combine(rec.date, time(12, 0)),
            context=CONTEXT[rec.kind], document_id=rec.id, tags=tags,
            metadata={"record_id": rec.id, "kind": rec.kind, "date": rec.date.isoformat()},
        )
    except Exception as e:
        raise MemoryError_(f"retain failed for {rec.id}: {e}") from e
    return {"id": rec.id, "success": getattr(r, "success", None)}


async def recall(query: str, kinds: Iterable[str], stage: str, bank_id: str = BANK_ID,
                 budget: str = "mid", max_tokens: int = 2048) -> list[MemoryHit]:
    CALLS["recall"] += 1
    resp = None
    for attempt in range(3):  # transient network failures should not fail an answer
        try:
            resp = await client().arecall(bank_id=bank_id, query=query[:1800], budget=budget, max_tokens=max_tokens,
                                          tags=[f"kind:{k}" for k in kinds], tags_match="any_strict")
            break
        except Exception as e:
            if attempt == 2:
                raise MemoryError_(f"recall failed: {e}") from e
            await asyncio.sleep(2 * (attempt + 1))
    hits = []
    for r in resp.results or []:
        meta = r.metadata or {}
        score = None
        if r.scores is not None:
            score = r.scores.reranker if r.scores.reranker is not None else r.scores.final
        hits.append(MemoryHit(stage=stage, text=r.text, type=r.type, document_id=r.document_id or meta.get("record_id"),
                              kind=meta.get("kind"), occurred=str(r.occurred_start) if r.occurred_start else None,
                              score=score))
    return hits


async def reflect(query: str, context: str = "", response_schema: dict | None = None, bank_id: str = BANK_ID):
    CALLS["reflect"] += 1
    for attempt in range(3):
        try:
            return await client().areflect(bank_id=bank_id, query=query, context=context or None, budget="mid",
                                           response_schema=response_schema)
        except Exception as e:
            if attempt == 2:
                raise MemoryError_(f"reflect failed: {e}") from e
            await asyncio.sleep(2 * (attempt + 1))


async def ping() -> bool:
    try:
        await client().arecall(bank_id=BANK_ID, query="health check", max_tokens=64, budget="low")
        return True
    except Exception:
        return False
