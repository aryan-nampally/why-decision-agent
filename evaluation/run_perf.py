"""Performance: latency, throughput and per-question cost.

    python -m evaluation.run_perf --model qwen/qwen3.8-27b --e2e 8

1. Memory layer (Hindsight recall only, no LLM): latency p50/p95 and throughput at concurrency 1, 4, 8.
2. End to end (full WHY pipeline): per-stage latency p50/p95, LLM tokens and Hindsight calls per question.
3. Derived: sustainable questions/minute under the LLM provider's tokens-per-minute limit.

Read-only against the demo bank. Results: evaluation/results/perf.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from datetime import date, datetime, timezone

from src import llm, memory
from src.config import ROOT
from src.reasoning import Pipeline

OUT = ROOT / "evaluation" / "results" / "perf.json"
QUERIES = [
    "Should the customs-duty ledger use Postgres like the payments ledger?",
    "retry policy for carrier API calls",
    "Is the single-region quote cache still right for EU shippers?",
    "Kafka for the returns event stream",
    "Is self-hosted Keycloak still the right identity provider?",
    "nightly invoice batch window",
    "synchronous call from booking to pricing",
    "feature flag service tier limits",
]
E2E = [
    ("We're building the customs-duty ledger. Should we use Postgres like the payments ledger did?", "Expected ~1.2k writes/s at launch."),
    ("Should the new customs-broker integration retry failed calls with exponential backoff, up to 5 retries?", ""),
    ("Can the new customs-duty service call pricing synchronously during booking?", ""),
    ("We're adding SSO for a new enterprise customer. Is self-hosted Keycloak still the right identity provider?", ""),
    ("Should credit notes be generated in the nightly invoice batch like invoices are?", ""),
    ("Which payroll provider should we use for our European employees?", ""),
    ("Pricing wants a quote cache for the EU shipper portal. Should we reuse the us-east-1 Redis design?", ""),
    ("Should we keep running Kafka on MSK as the backbone for shipment events?", ""),
]


def pct(xs: list[float], p: float) -> float:
    xs = sorted(xs)
    k = max(0, min(len(xs) - 1, round(p / 100 * (len(xs) - 1))))
    return round(xs[k], 1)


def summary(xs: list[float]) -> dict:
    return {"n": len(xs), "p50": pct(xs, 50), "p95": pct(xs, 95), "mean": round(statistics.mean(xs), 1), "max": round(max(xs), 1)}


async def memory_layer(n_per_level: int = 40) -> list[dict]:
    out = []
    for conc in (1, 4, 8):
        sem = asyncio.Semaphore(conc)
        lat: list[float] = []

        async def one(i: int):
            async with sem:
                t = time.perf_counter()
                await memory.recall(QUERIES[i % len(QUERIES)], ["adr"], stage="perf")
                lat.append((time.perf_counter() - t) * 1000)

        t0 = time.perf_counter()
        await asyncio.gather(*(one(i) for i in range(n_per_level)))
        wall = time.perf_counter() - t0
        row = {"concurrency": conc, "latency_ms": summary(lat), "throughput_per_s": round(n_per_level / wall, 2)}
        out.append(row)
        print(f"  recall concurrency {conc}: p50 {row['latency_ms']['p50']} ms · p95 {row['latency_ms']['p95']} ms · "
              f"{row['throughput_per_s']} recalls/s", flush=True)
    return out


async def end_to_end(n: int, pace: float = 0.0) -> dict:
    pipe = Pipeline(today=date(2026, 9, 28))
    stages = {"recall_precedent": [], "recall_changes": [], "judge": [], "total": []}
    per_q = []
    for i, (q, c) in enumerate((E2E * 2)[:n]):
        if i and pace:
            await asyncio.sleep(pace)  # stay under the provider's tokens/minute limit so we time the system, not the throttle
        u0, h0 = dict(llm.USAGE), dict(memory.CALLS)
        t = time.perf_counter()
        r = await pipe.ask(q, c)
        total = (time.perf_counter() - t) * 1000
        for k in ("recall_precedent", "recall_changes", "judge"):
            if k in r.timings_ms:
                stages[k].append(r.timings_ms[k])
        stages["total"].append(total)
        per_q.append({"verdict": r.verdict.value, "ms": round(total),
                      "prompt_tokens": llm.USAGE["prompt_tokens"] - u0["prompt_tokens"],
                      "completion_tokens": llm.USAGE["completion_tokens"] - u0["completion_tokens"],
                      "llm_calls": llm.USAGE["calls"] - u0["calls"], "hindsight_recalls": memory.CALLS["recall"] - h0["recall"]})
        print(f"  e2e {r.verdict.value:22} {total:7.0f} ms · {per_q[-1]['prompt_tokens'] + per_q[-1]['completion_tokens']} tokens · "
              f"{per_q[-1]['hindsight_recalls']} recalls", flush=True)
    tok = [q["prompt_tokens"] + q["completion_tokens"] for q in per_q]
    return {"n": n, "paced_s": pace, "stages_ms": {k: summary(v) for k, v in stages.items() if v},
            "tokens_per_question": summary(tok),
            "prompt_tokens_mean": round(statistics.mean(q["prompt_tokens"] for q in per_q)),
            "completion_tokens_mean": round(statistics.mean(q["completion_tokens"] for q in per_q)),
            "llm_calls_per_question": round(statistics.mean(q["llm_calls"] for q in per_q), 2),
            "hindsight_recalls_per_question": round(statistics.mean(q["hindsight_recalls"] for q in per_q), 2),
            "questions": per_q}


async def main(model: str | None, e2e_n: int, tpm_limit: int, pace: float, rpm_limit: float = 0) -> None:
    if model:
        llm.use_model(model)
    print("memory layer (Hindsight recall, no LLM)…", flush=True)
    mem = await memory_layer()
    print(f"end to end ({e2e_n} questions, model {llm.current_model()})…", flush=True)
    e2e = await end_to_end(e2e_n, pace) if e2e_n else None
    derived = None
    if e2e:
        t = e2e["tokens_per_question"]["mean"]
        derived = {"llm_tpm_limit": tpm_limit, "tokens_per_question_mean": t,
                   "max_questions_per_minute_under_tpm": round(tpm_limit / t, 2) if t else None,
                   "note": "On the free tier the LLM tokens-per-minute limit, not Hindsight, bounds sustained throughput."}
        if rpm_limit:
            calls = e2e["llm_calls_per_question"] or 1
            derived.update({"llm_rpm_limit": rpm_limit, "max_questions_per_minute": round(rpm_limit / calls, 2),
                            "limit_text": f"{rpm_limit:g} requests/min LLM limit",
                            "note": "On the free tier the LLM requests-per-minute limit, not Hindsight, bounds sustained throughput."})
            derived.pop("llm_tpm_limit"); derived.pop("max_questions_per_minute_under_tpm")
    report = {"run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "model": llm.current_model(),
              "memory_layer": mem, "end_to_end": e2e, "derived": derived}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "end_to_end"}, indent=2))
    if e2e:
        print(json.dumps({k: v for k, v in e2e.items() if k != "questions"}, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=None)
    ap.add_argument("--e2e", type=int, default=8)
    ap.add_argument("--tpm", type=int, default=8000, help="LLM tokens-per-minute limit of the account (Groq free tier: 8000)")
    ap.add_argument("--rpm", type=float, default=0, help="LLM requests-per-minute limit, if that binds instead (Cerebras free: 5)")
    ap.add_argument("--pace", type=float, default=25.0, help="seconds between end-to-end questions (0 = back-to-back)")
    a = ap.parse_args()
    asyncio.run(main(a.model, a.e2e, a.tpm, a.pace, a.rpm))
