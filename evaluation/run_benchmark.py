"""Benchmark: does structured, assumption-aware memory change decisions correctly?

    python -m evaluation.run_benchmark            # full run (reseeds the bank before and after)
    python -m evaluation.run_benchmark --only C   # a subset of conditions

Conditions (methodology §10.1):
  A          no memory
  B2         Hindsight recall top facts → LLM (same bank, no decision structure)
  B3         Hindsight reflect with a structured response schema
  C          WHY, assumptions extracted from ADR prose (production path)
  C-oracle   WHY with hand-labelled gold assumptions
  C-1stage   WHY with a single question-keyed recall instead of assumption-keyed recall
  ALWAYS-R   trivial: always RECONSIDER (shows FRR alone can be gamed)

Scoring is exact-match against evaluation/cases.json. No LLM grades anything.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import time
from datetime import date, datetime, timezone
from math import comb, sqrt
from pathlib import Path

from scripts.seed import seed
from src import baseline, learn, llm
from src.config import HOLDBACK, ROOT
from src.ingest import load_file
from src.reasoning import Pipeline, oracle_assumptions
from src.schema import Status

EVAL = ROOT / "evaluation"
CASES = json.loads((EVAL / "cases.json").read_text(encoding="utf-8"))
GOLD = json.loads((EVAL / "gold_assumptions.json").read_text(encoding="utf-8"))
CONDITIONS = ["C", "C-oracle", "B3", "B2", "A", "ALWAYS-R", "C-1stage"]  # ablation last: quota may run out
TODAY = date(2026, 9, 28)  # frozen clock for reproducible decision ages


# ---------------------------------------------------------------- alignment of extracted → gold assumptions

def _words(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", s.lower().replace("‑", "-"))) - {"the", "a", "of", "and", "to", "in", "is", "our", "we", "on"}


def align(decision_id: str, quote: str) -> str | None:
    """Map an extracted assumption to the gold assumption whose quote it overlaps most (>= 60% of the shorter)."""
    best, best_ov = None, 0.0
    q = _words(quote)
    for g in GOLD.get(decision_id, []):
        gw = _words(g["quote"])
        if not q or not gw:
            continue
        ov = len(q & gw) / min(len(q), len(gw))
        if ov > best_ov:
            best, best_ov = g["id"], ov
    return best if best_ov >= 0.6 else None


# ---------------------------------------------------------------- running one condition on one case

class QuotaExhausted(RuntimeError):
    pass


async def run_case(cond: str, case: dict, pipe: Pipeline) -> dict:
    q, c = case["question"], case["context"]
    t = time.perf_counter()
    out = {"case": case["id"], "condition": cond,
           "model": "hindsight-reflect" if cond == "B3" else None if cond == "ALWAYS-R" else llm.current_model()}
    try:
        if cond == "ALWAYS-R":
            out.update(verdict="RECONSIDER", precedent=None, broken=[])
        elif cond == "A":
            r = await baseline.no_memory(q, c)
            out.update(verdict=r.verdict, precedent=None, broken=None, answer=r.answer)
        elif cond == "B2":
            r = await baseline.retrieval_memory(q, c)
            out.update(verdict=r.verdict, precedent=r.precedent_id, broken=None, conditions=r.broken_conditions,
                       answer=r.answer)
        elif cond == "B3":
            r = await baseline.hindsight_reflect(q, c)
            out.update(verdict=r.verdict, precedent=r.precedent_id, broken=None, conditions=r.broken_conditions,
                       answer=r.answer)
        else:
            mode = "oracle" if cond == "C-oracle" else "extracted"
            r = await pipe.ask(q, c, assumptions_mode=mode, two_stage=(cond != "C-1stage"))
            did = r.decision.id if r.decision else None
            broken = []
            for chk in r.assumption_checks:
                if chk.status == Status.BROKEN:
                    gid = chk.assumption_id if mode == "oracle" else align(did, chk.quote)
                    broken.append(gid or f"?{chk.assumption_id}")
            if any(w.startswith("judge failed") for w in r.warnings):
                raise RuntimeError(next(w for w in r.warnings if w.startswith("judge failed"))[:200])
            out.update(verdict=r.verdict.value, precedent=did, broken=sorted(set(broken)),
                       grounding_removals=sum("removed citation" in w or "downgraded" in w for w in r.warnings),
                       n_evidence=len(r.evidence), headline=r.headline)
    except Exception as e:  # a failed call is scored as a wrong answer, and recorded
        out.update(verdict="ERROR", precedent=None, broken=None, error=f"{type(e).__name__}: {str(e)[:200]}")
    out["ms"] = int((time.perf_counter() - t) * 1000)
    if "per day" in str(out.get("error", "")) or "RateLimitError" in str(out.get("error", "")):
        raise QuotaExhausted(out["error"])
    v = str(out["verdict"]).upper().strip()
    out["verdict"] = next((x for x in ("INSUFFICIENT_EVIDENCE", "RECONSIDER", "ADAPT", "REUSE") if x in v), v)
    return out


# ---------------------------------------------------------------- statistics

def wilson(x: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = x / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (round((c - h) / d, 3), round((c + h) / d, 3))


def mcnemar(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    return round(min(1.0, 2 * sum(comb(n, k) for k in range(min(b, c) + 1)) * 0.5 ** n), 4)


def frac(x: int, n: int) -> dict:
    return {"x": x, "n": n, "rate": round(x / n, 3) if n else None, "ci95": wilson(x, n)}


def metrics(rows: list[dict], cases: dict[str, dict]) -> dict:
    ok = lambda r: r["verdict"] == cases[r["case"]]["verdict"]
    with_prec = [r for r in rows if cases[r["case"]]["precedent"]]
    stale = [r for r in rows if cases[r["case"]]["verdict"] in ("ADAPT", "RECONSIDER")]
    valid = [r for r in rows if cases[r["case"]]["verdict"] == "REUSE"]
    failed = [r for r in rows if cases[r["case"]].get("failed")]
    premise = [r for r in rows if cases[r["case"]].get("premise")]
    m = {
        "verdict_accuracy": frac(sum(ok(r) for r in rows), len(rows)),
        "precedent_hit@1": frac(sum((r.get("precedent") or "").upper() == cases[r["case"]]["precedent"] for r in with_prec), len(with_prec)),
        "false_reuse_rate": frac(sum(r["verdict"] == "REUSE" for r in stale), len(stale)),
        "false_reconsider_rate": frac(sum(r["verdict"] == "RECONSIDER" for r in valid), len(valid)),
        "repeat_error_rate": frac(sum(r["verdict"] == "REUSE" for r in failed), len(failed)),
        "premise_accuracy": frac(sum(ok(r) for r in premise), len(premise)),
        "median_ms": sorted(r["ms"] for r in rows)[len(rows) // 2] if rows else None,
        "errors": sum(r["verdict"] == "ERROR" for r in rows),
    }
    pairs: dict[str, dict] = {}
    for r in rows:
        cs = cases[r["case"]]
        if cs.get("pair"):
            pairs.setdefault(cs["pair"], {})[cs["pair_side"]] = ok(r)
    full = [p for p in pairs.values() if len(p) == 2]
    m["flip_accuracy"] = frac(sum(p["before"] and p["after"] for p in full), len(full))
    if all(r.get("broken") is not None for r in rows):
        tp = sum(len(set(r["broken"]) & set(cases[r["case"]]["broken"])) for r in rows)
        pred = sum(len(r["broken"]) for r in rows)
        gold = sum(len(cases[r["case"]]["broken"]) for r in rows)
        p = tp / pred if pred else 0.0
        rc = tp / gold if gold else 0.0
        m["assumption_detection"] = {"tp": tp, "predicted": pred, "gold": gold, "precision": round(p, 3),
                                     "recall": round(rc, 3), "f1": round(2 * p * rc / (p + rc), 3) if p + rc else 0.0}
    return m


# ---------------------------------------------------------------- tripwire

async def run_tripwire(store) -> dict:
    tp = pred = gold = 0
    rows = []
    for t in CASES["tripwire"]:
        r = await learn.record_signal(store, t["title"], t["detail"], today=TODAY)
        got = {(a.decision_id, align(a.decision_id, next((x.quote for x in store.get(a.decision_id).assumptions
                                                         if x.id == a.assumption_id), "")) or f"?{a.assumption_id}")
               for a in r.alerts}
        want = {tuple(x) for x in t["alerts"]}
        tp += len(got & want); pred += len(got); gold += len(want)
        rows.append({"id": t["id"], "predicted": sorted(got), "gold": sorted(want), "ms": r.timings_ms["total"]})
    p, rc = (tp / pred if pred else 0.0), (tp / gold if gold else 0.0)
    return {"rows": rows, "precision": round(p, 3), "recall": round(rc, 3), "tp": tp, "predicted": pred, "gold": gold}


# ---------------------------------------------------------------- main (resumable)

CKPT = EVAL / "results" / "rows.jsonl"
TRIP = EVAL / "results" / "tripwire.json"
INFRA = ("Cannot connect", "getaddrinfo", "(402)", "Insufficient credits", "tokens per day", "Connection",
         "RateLimit", "Rate limit", "429")


def is_infra_error(r: dict) -> bool:
    """Network / credit / quota failures say nothing about the system: re-run them instead of scoring them."""
    return r.get("verdict") == "ERROR" and any(m in str(r.get("error", "")) for m in INFRA)


def load_checkpoint() -> dict[tuple[str, str], dict]:
    done: dict[tuple[str, str], dict] = {}
    if CKPT.exists():
        for line in CKPT.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                if not is_infra_error(r):
                    done[(r["condition"], r["case"])] = r
    return done


def save_row(r: dict) -> None:
    CKPT.parent.mkdir(exist_ok=True)
    with CKPT.open("a", encoding="utf-8") as f:
        f.write(json.dumps(r) + "\n")


async def main(only: list[str], reseed: bool = False, report_only: bool = False) -> None:
    unknown = [c for c in only if c not in CONDITIONS]
    if unknown:
        raise SystemExit(f"unknown condition(s) {unknown}; choose from {CONDITIONS}")
    conds = [] if report_only else (only or CONDITIONS)
    cases = {c["id"]: c for c in CASES["ask"]}
    done = load_checkpoint()
    todo = {ph: [(cond, c) for c in CASES["ask"] if c["phase"] == ph for cond in conds if (cond, c["id"]) not in done]
            for ph in ("before", "after")}
    print(f"checkpoint has {len(done)} rows; to run: {len(todo['before'])} before + {len(todo['after'])} after", flush=True)
    if reseed:
        await seed()
    pipe = Pipeline(today=TODAY)
    stopped, dirty = None, False

    async def run(pairs):
        for cond, cs in pairs:
            r = await run_case(cond, cs, pipe)
            save_row(r)
            if not is_infra_error(r):
                done[(cond, cs["id"])] = r
            mark = "ok " if r["verdict"] == cs["verdict"] else "XX "
            print(f"  {mark}{cs['id']} {cond:9} {r['verdict']:22} gold={cs['verdict']:22} {r['ms']:>6} ms"
                  + (f"  broken={r.get('broken')}" if r.get("broken") else "") + (f"  {r.get('error')}" if r.get("error") else ""),
                  flush=True)

    trip = json.loads(TRIP.read_text(encoding="utf-8")) if TRIP.exists() else None
    try:
        await run(todo["before"])
        if todo["after"]:
            text, ref = load_file(HOLDBACK / "PM-2024-11.md")
            await learn.ingest_markdown(pipe.store, text, ref)
            dirty = True
            print("ingested PM-2024-11; waiting 20 s for Hindsight to index it", flush=True)
            await asyncio.sleep(20)
            await run(todo["after"])
        if trip is None and "C" in conds and not report_only:
            trip = await run_tripwire(pipe.store)
            dirty = True
            TRIP.write_text(json.dumps(trip, indent=2), encoding="utf-8")
    except QuotaExhausted as e:
        stopped = f"stopped early: LLM daily quota exhausted ({str(e)[:100]}); re-run later to resume"
        print(stopped, flush=True)
    finally:
        if dirty:
            print("restoring clean demo memory…", flush=True)
            await seed()

    rows = list(done.values())
    report = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "model": llm.current_model(),
              "extraction_model": "openai/gpt-oss-120b (cached in data/extracted/)", "note": stopped,
              "git_commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                                           cwd=ROOT).stdout.strip() or None,
              "n_cases": len(cases), "conditions": {}, "incomplete": {}, "tripwire": trip, "rows": rows,
              "models": {c: sorted({r.get("model") or "—" for r in rows if r["condition"] == c}) for c in CONDITIONS}}
    for cond in CONDITIONS:
        cr = [r for r in rows if r["condition"] == cond]
        if len(cr) == len(cases):
            report["conditions"][cond] = {"all": metrics(cr, cases),
                                          "test_split": metrics([r for r in cr if cases[r["case"]]["split"] == "test"], cases)}
        else:
            report["incomplete"][cond] = f"{len(cr)}/{len(cases)} cases" if cr else "not run yet"
    report["mcnemar_vs_C"] = {}
    if "C" in report["conditions"]:
        c_ok = {r["case"]: r["verdict"] == cases[r["case"]]["verdict"] for r in rows if r["condition"] == "C"}
        for cond in report["conditions"]:
            if cond == "C":
                continue
            o_ok = {r["case"]: r["verdict"] == cases[r["case"]]["verdict"] for r in rows if r["condition"] == cond}
            b = sum(o_ok[k] and not c_ok[k] for k in c_ok)
            c = sum(c_ok[k] and not o_ok[k] for k in c_ok)
            report["mcnemar_vs_C"][cond] = {"other_right_C_wrong": b, "C_right_other_wrong": c, "p": mcnemar(b, c)}
    out_dir = EVAL / "results"
    (out_dir / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (out_dir / "results.md").write_text(render(report), encoding="utf-8")
    print(render(report))


def _f(m: dict) -> str:
    return "—" if not m or m.get("n") == 0 else f"{m['x']}/{m['n']} ({m['rate']:.2f})"


def render(rep: dict) -> str:
    lines = [f"# WHY benchmark results — {rep['run_at']}", "",
             f"Judge/baseline model `{rep['model']}` · assumption extraction `{rep['extraction_model']}` · B3 uses Hindsight's own reflect model · "
             f"commit `{rep['git_commit']}` · {rep['n_cases']} cases · one run per condition · pilot scale; intervals are Wilson 95%.", ""]
    if rep.get("note"):
        lines += [f"> {rep['note']}", ""]
    if rep.get("incomplete"):
        lines += ["> Not yet complete (excluded from tables): " + ", ".join(f"{k} {v}" for k, v in rep["incomplete"].items()), ""]
    for split in ("all", "test_split"):
        lines += [f"## {'All cases' if split == 'all' else 'Test split only (excludes demo questions used in development)'}", "",
                  "| Condition | Verdict acc. | Precedent hit@1 | False reuse ↓ | False reconsider ↓ | Repeat error ↓ | Premise acc. | Flip acc. | Assumption F1 | Median ms |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for cond, v in rep["conditions"].items():
            m = v[split]
            ad = m.get("assumption_detection")
            lines.append(f"| {cond} | {_f(m['verdict_accuracy'])} | {_f(m['precedent_hit@1'])} | {_f(m['false_reuse_rate'])} | "
                         f"{_f(m['false_reconsider_rate'])} | {_f(m['repeat_error_rate'])} | {_f(m['premise_accuracy'])} | "
                         f"{_f(m['flip_accuracy'])} | {ad['f1'] if ad else '—'} | {m['median_ms']} |")
        lines.append("")
    if rep.get("mcnemar_vs_C"):
        lines += ["## Paired comparison with WHY (C), exact McNemar on verdict correctness", "",
                  "| vs | other right, C wrong | C right, other wrong | p |", "|---|---|---|---|"]
        lines += [f"| {k} | {v['other_right_C_wrong']} | {v['C_right_other_wrong']} | {v['p']} |" for k, v in rep["mcnemar_vs_C"].items()]
        lines.append("")
    if rep.get("tripwire"):
        t = rep["tripwire"]
        lines += ["## Tripwire", "", f"Precision {t['precision']} · recall {t['recall']} ({t['tp']} correct of {t['predicted']} raised, {t['gold']} expected)", ""]
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", nargs="*", default=[])
    ap.add_argument("--model", default=None, help="override LLM model, e.g. openai/gpt-oss-20b")
    ap.add_argument("--reseed", action="store_true", help="rebuild the demo memory bank before running")
    ap.add_argument("--report-only", action="store_true", help="rebuild results.json/md from the checkpoint; run nothing")
    a = ap.parse_args()
    if a.model:
        llm.use_model(a.model)
    asyncio.run(main(a.only, a.reseed, a.report_only))
