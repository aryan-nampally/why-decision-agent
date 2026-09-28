"""Decision health board for the case study: WHY evaluates every active Keelwright decision as of today.

    python -m scripts.casestudy_health --model qwen/qwen3.8-27b

Writes data/casestudy/health.json (read by the Case study page). Read-only against the demo memory.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date, datetime, timezone

from src import llm
from src.config import DATA
from src.reasoning import Pipeline
from src.schema import DecisionRecord, Status

OUT = DATA / "casestudy" / "health.json"
TODAY = date(2026, 9, 28)


async def main(model: str | None) -> None:
    if model:
        llm.use_model(model)
    pipe = Pipeline(today=TODAY)
    board = []
    for rec in pipe.store.all("adr"):
        if not isinstance(rec, DecisionRecord) or rec.status != "accepted":
            continue
        r = await pipe.ask(f"Is the decision in {rec.id} ('{rec.title}') still the right approach today?", "",
                           forced_precedent=rec.id)
        broken = [c for c in r.assumption_checks if c.status == Status.BROKEN]
        board.append({
            "id": rec.id, "title": rec.title, "date": rec.date.isoformat(), "team": rec.team, "verdict": r.verdict.value,
            "health": r.health, "age": r.decision_age, "headline": r.headline,
            "broken": [{"id": c.assumption_id, "statement": c.statement, "critical": c.critical,
                        "evidence": c.evidence_ids, "explanation": c.explanation} for c in broken],
            "failures": r.failure_evidence, "assumptions": len(r.assumption_checks),
        })
        print(f"  {rec.id} {r.verdict.value:22} health {r.health}", flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                               "as_of": TODAY.isoformat(), "model": llm.current_model(), "decisions": board}, indent=2),
                   encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None)
    asyncio.run(main(ap.parse_args().model))
