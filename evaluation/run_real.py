"""Real-data track: GOV.UK's published architecture decision records (2017–2022).

    python -m scripts.import_govuk                 # once: download + convert
    python -m evaluation.run_real --model openai/gpt-oss-20b

1. Extraction on real prose: recover grounded assumptions from 38 ADRs written by GOV.UK engineers.
2. Retrospective: evaluate decisions "as of" late 2022 using only LATER ADRs as evidence.
   Targets are decisions GOV.UK itself later superseded or reversed; controls are decisions the
   published record never revisits. Ground truth is GOV.UK's own history, not our labels.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import time
from datetime import date, datetime, timezone

from src import baseline, llm, memory
from src.config import DATA, ROOT
from src.ingest import extract_assumptions, load_file, parse_record
from src.reasoning import Pipeline
from src.schema import Status, Verdict
from src.store import Store

BANK = "why-govuk-real"
SRC = DATA / "real" / "govuk-aws"
CACHE = DATA / "extracted_govuk"
TODAY = date(2022, 12, 1)
MISSION = ("Organizational memory for GOV.UK's hosting platform. Remember infrastructure decisions, the conditions they "
           "relied on, and later decisions that changed them, so earlier decisions can be re-evaluated.")

TARGETS = [  # (decision, later record that changed it, how the record says so)
    ("GOVUK-0004", "GOVUK-0015", "explicitly superseded by ADR 15 (DNS infrastructure)"),
    ("GOVUK-0003", "GOVUK-0033", "explicitly, in part, superseded by ADR 33 (IP ranges conflict with the Carrenza VPN)"),
    ("GOVUK-0028", "GOVUK-0038", "implicitly reversed: ADR 38 moves Mongo apps, naming Content Store, to DocumentDB"),
]
CONTROLS = ["GOVUK-0021", "GOVUK-0022", "GOVUK-0024", "GOVUK-0025", "GOVUK-0029"]  # never revisited in the record


def question(rec) -> str:
    return f"Is the decision in {rec.id} ('{rec.title}') still the right approach for GOV.UK today?"


async def build(store: Store) -> dict:
    store.clear()
    await memory.reset_bank(BANK, name="WHY — GOV.UK real ADRs", mission=MISSION)
    stats = {"adrs": 0, "assumptions": 0, "critical": 0, "dropped_ungrounded": 0, "no_assumptions": [], "per_adr": {}}
    records = []
    for path in sorted(SRC.glob("GOVUK-*.md")):
        text, ref = load_file(path)
        rec = parse_record(text, ref)
        rec.assumptions, warnings = await extract_assumptions(rec, text, cache_dir=CACHE)
        dropped = sum("ungrounded" in w for w in warnings)
        stats["adrs"] += 1
        stats["assumptions"] += len(rec.assumptions)
        stats["critical"] += sum(a.critical for a in rec.assumptions)
        stats["dropped_ungrounded"] += dropped
        if not rec.assumptions:
            stats["no_assumptions"].append(rec.id)
        stats["per_adr"][rec.id] = {"title": rec.title, "date": rec.date.isoformat(), "dropped": dropped,
                                    "assumptions": [a.model_dump() for a in rec.assumptions]}
        store.put(rec)
        records.append((rec, text))
        print(f"  {rec.id} {rec.date} {len(rec.assumptions)} assumptions ({dropped} dropped)", flush=True)
    sem = asyncio.Semaphore(4)

    async def one(rec, text):
        async with sem:
            await memory.retain(rec, text, bank_id=BANK)

    await asyncio.gather(*(one(r, t) for r, t in records))
    return stats


async def evaluate(store: Store, with_reflect: bool) -> list[dict]:
    pipe = Pipeline(store, today=TODAY, bank_id=BANK, evidence_kinds=("adr",))
    rows = []
    cases = [(d, later, why, True) for d, later, why in TARGETS] + [(d, None, "not revisited in the record", False) for d in CONTROLS]
    for did, later, why, changed in cases:
        rec = store.get(did)
        q = question(rec)
        t = time.perf_counter()
        r = await pipe.ask(q, "", forced_precedent=did)
        cited = sorted({e for c in r.assumption_checks for e in c.evidence_ids})
        row = {"decision": did, "title": rec.title, "date": rec.date.isoformat(), "changed_later": changed,
               "changed_by": later, "history": why, "verdict": r.verdict.value, "flagged": r.verdict in (Verdict.ADAPT, Verdict.RECONSIDER),
               "cites_changing_record": bool(later and later in cited), "cited": cited, "ms": int((time.perf_counter() - t) * 1000),
               "broken": [{"id": c.assumption_id, "statement": c.statement, "quote": c.quote, "explanation": c.explanation,
                           "evidence": c.evidence_ids} for c in r.assumption_checks if c.status == Status.BROKEN],
               "warnings": r.warnings}
        if with_reflect:
            try:
                b = await baseline.hindsight_reflect(q, bank_id=BANK)
                text = " ".join([b.answer, *b.broken_conditions])
                num = later[-4:].lstrip("0") if later else None
                row["reflect"] = {"verdict": b.verdict.upper(), "flagged": b.verdict.upper() in ("ADAPT", "RECONSIDER"),
                                  "mentions_changing_record": bool(num and re.search(rf"\b(ADR[- ]?|GOVUK-0*){num}\b", text, re.I)),
                                  "answer": b.answer[:400]}
            except Exception as e:
                row["reflect"] = {"error": str(e)[:200]}
        rows.append(row)
        print(f"  {did} changed={changed!s:5} WHY={row['verdict']:11} cites {later}={row['cites_changing_record']} "
              + (f"| reflect={row.get('reflect', {}).get('verdict')}" if with_reflect else ""), flush=True)
    return rows


def render(stats: dict, rows: list[dict], model: str) -> str:
    t = [r for r in rows if r["changed_later"]]
    c = [r for r in rows if not r["changed_later"]]
    L = ["# Real-data track — GOV.UK architecture decisions (2017–2022)", "",
         f"Source: [alphagov/govuk-aws](https://github.com/alphagov/govuk-aws) (MIT). Model `{model}`. Evaluated as of {TODAY}. "
         "Evidence for each decision = only ADRs dated after it. Pilot scale.", "",
         "## 1. Assumption extraction on real prose", "",
         f"- ADRs: {stats['adrs']} · grounded assumptions kept: {stats['assumptions']} ({stats['critical']} marked critical) · "
         f"dropped because the quote was not verbatim in the source: {stats['dropped_ungrounded']}",
         f"- ADRs with no extractable assumption: {len(stats['no_assumptions'])} ({', '.join(stats['no_assumptions']) or 'none'})", "",
         "## 2. Retrospective: does WHY flag the decisions GOV.UK later changed?", "",
         f"- Changed later (targets): flagged **{sum(r['flagged'] for r in t)}/{len(t)}**, citing the record that changed it "
         f"**{sum(r['cites_changing_record'] for r in t)}/{len(t)}**",
         f"- Never revisited (controls): left as REUSE **{sum(not r['flagged'] for r in c)}/{len(c)}**", ""]
    if any("reflect" in r for r in rows):
        rf = [r["reflect"] for r in t if "verdict" in r.get("reflect", {})]
        rc = [r["reflect"] for r in c if "verdict" in r.get("reflect", {})]
        L += [f"- Hindsight `reflect` (baseline): targets flagged {sum(x['flagged'] for x in rf)}/{len(rf)}, "
              f"mentions the changing record {sum(x['mentions_changing_record'] for x in rf)}/{len(rf)}; "
              f"controls left as REUSE {sum(not x['flagged'] for x in rc)}/{len(rc)}", ""]
    L += ["| Decision | Date | What actually happened | WHY | Cited | reflect |", "|---|---|---|---|---|---|"]
    for r in rows:
        L.append(f"| {r['decision']} {r['title']} | {r['date']} | {r['history']} | {r['verdict']} | {', '.join(r['cited']) or '—'} | "
                 f"{r.get('reflect', {}).get('verdict', '—')} |")
    L += ["", "## 3. What WHY said about the changed decisions", ""]
    for r in t:
        L.append(f"**{r['decision']} — {r['title']}** → {r['verdict']}")
        for b in r["broken"]:
            L.append(f"- BROKEN: {b['statement']} — *“{b['quote'][:160]}”* — {b['explanation']} ({', '.join(b['evidence'])})")
        L.append("")
    return "\n".join(L)


async def main(with_reflect: bool) -> None:
    store = Store(DATA / "store_govuk.db")
    print("building GOV.UK memory bank…", flush=True)
    stats = await build(store)
    print("evaluating…", flush=True)
    rows = await evaluate(store, with_reflect)
    out = ROOT / "evaluation" / "results"
    out.mkdir(exist_ok=True)
    report = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "model": llm.current_model(),
              "as_of": TODAY.isoformat(), "extraction": stats, "rows": rows}
    (out / "real_govuk.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    md = render(stats, rows, llm.current_model())
    (out / "real_govuk.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None)
    ap.add_argument("--no-reflect", action="store_true")
    a = ap.parse_args()
    if a.model:
        llm.use_model(a.model)
    asyncio.run(main(not a.no_reflect))
