"""Reset the Hindsight bank and record store, then load the Keelwright corpus.

Held-out documents (data/holdback/) are NOT loaded; they are ingested live in the demo.

    python -m scripts.seed              # full reset + retain
    python -m scripts.seed --extract    # only (re)run assumption extraction and print it
"""
from __future__ import annotations

import argparse
import asyncio
import time

from src import memory
from src.config import CORPUS, EXTRACTED
from src.ingest import extract_assumptions, load_file, parse_record
from src.store import Store


def corpus_files():
    return sorted(CORPUS.glob("*/*.md"))


async def extract_only(force: bool) -> None:
    for path in sorted((CORPUS / "adrs").glob("*.md")):
        text, ref = load_file(path)
        rec = parse_record(text, ref)
        if force:
            (EXTRACTED / f"{rec.id}.json").unlink(missing_ok=True)
        assumptions, warnings = await extract_assumptions(rec, text)
        print(f"\n{rec.id} — {rec.title}")
        for a in assumptions:
            print(f"  {a.id}{'*' if a.critical else ' '} {a.statement}\n       \"{a.quote}\"")
        for w in warnings:
            print(f"  ! {w}")


async def seed() -> None:
    t0 = time.time()
    store = Store()
    store.clear()
    await memory.reset_bank()
    print("bank reset")
    records = []
    for path in corpus_files():
        text, ref = load_file(path)
        rec = parse_record(text, ref)
        if rec.kind == "adr":
            rec.assumptions, warnings = await extract_assumptions(rec, text)
            for w in warnings:
                print(f"  ! {rec.id}: {w}")
        store.put(rec)
        records.append((rec, text))
    sem = asyncio.Semaphore(4)

    async def one(rec, text):
        async with sem:
            await memory.retain(rec, text)
            print(f"  retained {rec.id} ({rec.date})")

    await asyncio.gather(*(one(r, t) for r, t in records))
    print(f"seeded {len(records)} records in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--extract", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    asyncio.run(memory.closing(extract_only(args.force) if args.extract else seed()))
