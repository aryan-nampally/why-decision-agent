# How WHY uses Hindsight memory

WHY is a decision-memory agent. [Hindsight](https://github.com/vectorize-io/hindsight) is where its memory lives: every architecture decision, incident postmortem and environment change is retained there, and every answer starts with recall. Everything WHY knows about the organization's past reaches it through Hindsight recall. The local SQLite store only turns a recalled `document_id` back into the full record that was written; code then applies the date filter and the verdict rules to what was recalled.

## The memory lifecycle

```
retain ── ADRs, postmortems, change notes ─────────────► Hindsight bank
                                                             │
ask ── recall(question, kind:adr) ─── stage 1: which past decision is this? ◄┘
   └── recall(assumption, kind:signal|postmortem) ─── stage 2: what changed since? (one per assumption)
         │
         ▼
   per-assumption judgement → rule-based verdict (REUSE / ADAPT / RECONSIDER / INSUFFICIENT_EVIDENCE)
         │
accept ── retain(new decision, supersedes old) ──────────► Hindsight bank   (tomorrow's precedent)
signal ── retain(change) + recall(change, kind:adr) ─────► tripwire alerts  (no question needed)
ingest ── retain(postmortem) ───────────────────────────► the next answer changes
```

## Hindsight features we rely on

| Feature | Where (code) | Why it matters |
|---|---|---|
| `create_bank(mission, retain_mission, disposition)` | `src/memory.py: reset_bank` | Steers fact extraction toward decisions, the conditions they relied on, incident causes and changes, instead of generic facts. High skepticism, low empathy. |
| `retain(timestamp=<real historical date>)` | `src/memory.py: retain` | The bank knows ADR-007 was decided in February 2023 and that reporting moved to Snowflake in August 2025. |
| `retain(document_id=<record ID>)` | every retain | Each recalled fact maps back to its source record, which is how provenance survives recall. |
| `retain(tags=["kind:adr" / "kind:postmortem" / "kind:signal", "team:*"])` | every retain | One bank holds decisions and changes; recall is scoped per stage. |
| `retain(metadata=...)` | every retain | Record ID, kind and date come back with each fact and are shown in the UI's memory trace. |
| `recall(tags=..., tags_match="any_strict")` | `src/reasoning.py`, `src/learn.py` | Stage 1 searches decisions only; stage 2 searches changes and incidents only. |
| `RecallResult.scores` | `src/memory.py: recall` | Reranker score per fact, shown in the memory trace. |
| `reflect(response_schema=...)` | `src/baseline.py` | Used as a strong baseline (condition B3) in the benchmark. |

## Why recall per assumption

The evidence that invalidates a decision is rarely similar to the question. "Should the customs ledger use Postgres?" is about databases; "month-end close now runs in Snowflake" is about analytics. WHY first recalls the decision, recovers the assumptions it depended on (for example *"Finance's month-end close runs … SQL reports that JOIN … directly on the primary database"*), and then recalls **with each assumption as the query**, scoped by tag to change notes and postmortems. The assumption is close to both the decision and the change, so it bridges them, and each recall shows up as its own lane in the UI trace.

**What we measured:** on our 37-record bank, a single question-keyed recall scored the same (23/26 vs 23/26). It missed the Snowflake note on one of the two Postgres questions and found it on the other. At this size, one recall already reaches most of the bank; the accuracy comes from what WHY does with recalled memories (assumptions, date admissibility, grounded citations, rule-based verdicts). Per-assumption recall is kept because it makes every piece of evidence traceable to the assumption it tests, and because it should matter more as a bank grows. That is untested so far.

## What changes because of memory

| | Without memory | With WHY |
|---|---|---|
| "Postgres for the new ledger, like payments?" | "Yes, PostgreSQL should work … the expected 1.2k writes per second is within its proven capacity, so you can reuse the same approach." → REUSE | ADR-007 from Feb 2023; write volume 3,140/s vs the ~1,800/s it assumed; reporting moved to Snowflake → **RECONSIDER** |
| Same retry question, before and after PM-2024-11 is retained | Same answer both times | **REUSE**, then **RECONSIDER** citing the 47-minute retry-storm outage |
| "Consolidating all production into eu-central-1" | Nothing happens | Tripwire: ADR-007's assumption that the ledger runs in a single region, us-east-1, is flagged. One LLM call checks every candidate decision. |

## Where the code is

- `src/memory.py` — bank setup, retain, recall, reflect
- `src/reasoning.py` — two-stage recall and the evaluation pipeline
- `src/learn.py` — ingest, tripwire, accept (all the writes)
- `scripts/seed.py` — builds the bank from `data/corpus/`

## Measured effect of memory

Same model, 26 questions with answers fixed in advance: **8/26 without memory, 13/26 with recalled memories pasted into the prompt, 17/26 with Hindsight `reflect`, 23/26 with WHY.** Details and every individual answer: the Evaluation page in the app and `evaluation/results/results.md`.
