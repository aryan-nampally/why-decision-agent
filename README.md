# WHY — state-aware decision memory

**WHY remembers why your organization made each engineering decision, notices when the assumptions behind it stop being true, and changes its recommendation because of what it remembers.**

Architecture decision records capture *what* was decided. They don't notice when the world that justified the decision moves on — and the evidence that it moved on usually lives in other documents, written by other people, years later. WHY keeps decisions, incidents and environment changes in [Hindsight](https://github.com/vectorize-io/hindsight) memory, recovers the implicit assumptions each decision depended on, and checks them against everything that happened since.

```
Q: We're building the customs-duty ledger. Should we use Postgres like the payments ledger did?

RECONSIDER — critical assumptions behind ADR-007 no longer hold.

Then  ADR-007 (2023-02-14, 3 years 7 months ago) · PostgreSQL 14 on RDS, Multi-AZ, us-east-1
Now   BROKEN  write volume stays near the ~1,800/s projection    ← SIG-2025-12: peaked at 3,140/s, 4,500/s projected
      BROKEN  finance reporting runs SQL JOINs on the primary     ← SIG-2025-08: close moved to Snowflake; direct queries disabled
      HOLDS   payment processing runs only in us-east-1           ← SIG-2025-01 confirms ledger stayed in us-east-1
```

Without memory, the same model answers "the expected 1.2k writes per second is within its proven capacity, so you can reuse the same approach."

![WHY answering the Postgres question: live agent orchestration, then the verdict](docs/img/agent.png)

> Keelwright Freight is a **fictional** company. Its ADRs, postmortems and change notes in `data/` are synthetic, written to read like real engineering records.

## What it does

![Decision health board: WHY checks every active decision](docs/img/health.png)

| | |
|---|---|
| **Ask** | Recall the precedent decision, recall what changed for each of its assumptions, return REUSE / ADAPT / RECONSIDER / INSUFFICIENT_EVIDENCE with cited evidence. |
| **Learn** | Ingest a postmortem or accept a new decision; it is retained and the next answer changes. |
| **Tripwire** | Record a change ("consolidating into eu-central-1"); WHY finds the past decisions whose assumptions it breaks — nobody has to ask. |

## How it works

```
                 ┌──────────── React UI (web/, Vite + TypeScript) ────────────┐
                 │ Ask · Then vs Now · Evidence · Memory trace · Tripwire │
                 └──────────────────────────┬───────────────────────────┘
                                            │ FastAPI (src/app.py)
   ┌────────────────────────────────────────┴────────────────────────────────────────┐
   │ 1 recall precedent (kind:adr) → 2 recall changes per assumption (kind:signal/pm) │
   │ 3 LLM judges each assumption → 4 code grounds citations → 5 rule-based verdict    │
   └──────────┬───────────────────────────────┬────────────────────────────┬──────────┘
        Hindsight Cloud                 SQLite record store             LLM (OpenAI-compatible)
   retain / recall / reflect        canonical records by ID        openai/gpt-oss-120b
   what is relevant, and when       what was actually written      narrow JSON judgements
```

Design rules that keep it auditable:

- **Assumptions are recovered, not hand-written.** ADRs are prose. `src/ingest.py` extracts the premises each decision depends on, and keeps an assumption only if its supporting quote appears verbatim in the source.
- **Only later evidence counts.** Evidence dated before the decision was part of its context and cannot invalidate it.
- **The LLM judges; code decides.** The model labels each assumption HOLDS / BROKEN / UNKNOWN with citations. Code drops citations it was never given, downgrades uncited BROKEN claims, and applies the verdict rules in `src/rules.py`. Adding contradicting evidence can never make WHY *more* confident in reuse (tested exhaustively in `tests/test_rules.py`).
- **Fail safe.** If the model's output is invalid after one retry, every assumption becomes UNKNOWN, which yields ADAPT, never REUSE.

See [HINDSIGHT.md](HINDSIGHT.md) for exactly how Hindsight memory is used.

## Quick start

```bash
python -m venv .venv && .venv/Scripts/activate      # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                                # add your Hindsight and LLM keys (Cerebras, Groq or any OpenAI-compatible API)
python -m scripts.seed                              # builds the memory bank (~40 s)
cd web && npm install && npm run build && cd ..     # React UI (served by FastAPI from web/dist)
uvicorn src.app:app --port 8000                     # open http://localhost:8000
```

Tests (no network): `python -m pytest -q tests` · UI development with hot reload: `cd web && npm run dev` (proxies the API on :8000)

## Demo

1. Click **Postgres for a new ledger?** — memory ON vs OFF, ADR-007, two broken assumptions, RECONSIDER.
2. Click **Retry policy for a new integration?** — REUSE. Under *New documents*, **Ingest** PM-2024-11. Ask again — RECONSIDER, citing the outage.
3. Under *Record a change*, enter "Consolidating all production into eu-central-1" — tripwire alerts.
4. **Accept & remember** a recommendation — it appears in the memory timeline and supersedes the old decision.

`POST /api/demo/reset` (or `python -m scripts.seed`) restores the starting state.

## Evaluation

![Evaluation page](docs/img/evaluation.png)

`python -m evaluation.run_benchmark` runs 26 questions and 5 tripwire scenarios against seven conditions and writes `evaluation/results/results.{json,md}`. Scoring is exact-match against hand-written labels in `evaluation/cases.json`; no LLM grades anything.

| Condition | What it is |
|---|---|
| A | same model, no memory |
| B2 | Hindsight recall over the same bank, top facts in the prompt, no decision structure |
| B3 | Hindsight `reflect` with a structured output schema |
| C | WHY (assumptions extracted from prose) |
| C-oracle | WHY with hand-labelled assumptions |
| C-1stage | WHY with a single question-keyed recall |
| ALWAYS-R | always answers RECONSIDER (shows why false-reuse rate alone is not enough) |

Results (all conditions on `gpt-oss-120b` via Cerebras; `reflect` uses Hindsight's own model; one run each):

| Condition | Verdict accuracy | False reuse ↓ | False reconsider ↓ | Flip after new evidence | Test split only |
|---|---|---|---|---|---|
| **C — WHY** | **21/26 (81%)** | **0/16** | 1/7 | 1/3 | **18/21** |
| C-oracle | 22/26 (85%) | 1/16 | 1/7 | 1/3 | 19/21 |
| C-1stage (ablation) | 22/26 (85%) | 0/16 | 1/7 | 2/3 | 18/21 |
| B3 — Hindsight `reflect` | 17/26 (65%) | 0/16 | 0/7 | 0/3 | 15/21 |
| B2 — recall → LLM | 13/26 (50%) | 4/16 | 0/7 | 1/3 | 11/21 |
| A — no memory | 8/26 (31%) | 4/16 | 1/7 | 0/3 | 6/21 |
| ALWAYS-R | 10/26 (39%) | 0/16 | 7/7 | 0/3 | 8/21 |

- Paired exact McNemar vs WHY: no memory p = 0.002, recall → LLM p = 0.039, `reflect` p = 0.39 (not significant), ablation p = 1.0.
- Tripwire (5 recorded changes, which past assumptions do they break?): precision 0.50, recall 0.83.
- Performance (`python -m evaluation.run_perf`): median **3.4 s** per question end to end (0.9 s of it the LLM), 1 LLM call, ~2,350 tokens and 5.6 Hindsight recalls per question. Hindsight recall p50 ≈ 0.45 s; throughput 1.3 → 5.8 → 10.0 recalls/s at concurrency 1 → 4 → 8.
- Honest reading: memory with decision structure clearly beats no memory and flat recall; it beats `reflect` on this set but not significantly; the single-recall ablation ties the two-stage method. Full tables: `evaluation/results/results.md`.

### Real-data track: GOV.UK's published decisions

Synthetic data can't answer "does this work on decisions someone else wrote?", so WHY is also run on the 38 real architecture decision records GOV.UK published between 2017 and 2022 ([alphagov/govuk-aws](https://github.com/alphagov/govuk-aws), MIT). `python -m scripts.import_govuk && python -m evaluation.run_real` does two things:

1. **Extraction on real prose** — recover grounded assumptions from ADRs written by GOV.UK engineers.
2. **Retrospective** — evaluate decisions as of December 2022 using only *later* ADRs as evidence. Targets are decisions GOV.UK itself later superseded or reversed; controls are decisions its record never revisits. The ground truth is GOV.UK's own history. The "Superseded by" notes later added to old records are stripped on import so the answer cannot leak.

Results (`evaluation/results/real_govuk.md`, model `qwen3.8-27b`):

- **109 grounded assumptions** extracted from 38 real ADRs; only 3 dropped because the quote was not verbatim.
- Decisions GOV.UK later changed: WHY flagged **3/3**, citing the record that changed them **3/3** (Hindsight `reflect`: flagged 3/3, named the changing record 1/3). One of the three, the 2017 Content Store → shared Mongo decision, was only reversed implicitly by a 2019 DocumentDB ADR.
- Decisions never revisited: WHY left **4/5** alone (`reflect`: 3/5).
- 8 cases: a pilot, not a benchmark.

## Limitations

- **Small, synthetic pilot.** 26 questions over one fictional organization, one run per condition. Differences are reported with confidence intervals and a paired significance test; most are not significant at this scale.
- **The author wrote both the data and the labels.** Demo questions used during development are marked `split: dev` and results are also reported on the untouched test split.
- **Assumption extraction is the weak link.** It recovers most premises, but its "critical" labels can disagree with a human's, which changes verdicts. C vs C-oracle measures that gap.
- **Inertia.** An assumption nothing in memory talks about is treated as still holding (shown as *no change recorded*). If the invalidating change was never written down, WHY cannot know.

## Repository layout

```
src/          schema, config, memory (Hindsight), store, llm, ingest, rules, reasoning, learn, baseline, app
web/          React + TypeScript UI (Vite); built to web/dist and served by FastAPI
data/corpus/  adrs/, postmortems/, signals/   (synthetic)      data/holdback/  ingested live in the demo
data/real/    govuk-aws/  38 real GOV.UK ADRs (MIT), imported by scripts/import_govuk.py
evaluation/   cases.json, gold_assumptions.json, run_benchmark.py, results/
scripts/      seed.py
tests/        test_rules.py, test_ingest.py, test_api.py
```

## Links

- Hindsight: [GitHub](https://github.com/vectorize-io/hindsight) · [Docs](https://hindsight.vectorize.io/) · [What is agent memory?](https://vectorize.io/what-is-agent-memory)
