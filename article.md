# The ADR said Postgres. Hindsight remembered why it expired

In February 2023 a payments team chose PostgreSQL for its ledger, for two good reasons: finance ran month-end reports as SQL JOINs directly on that database, and peak writes were projected to stay under about 1,800 per second. By December 2025 both reasons were gone. Finance had moved to Snowflake in August, and Cyber Monday pushed the ledger to 3,140 writes per second. Neither change mentioned the ADR. So when a new team asked "should the customs-duty ledger use Postgres, like payments did?", the honest answer lived in three documents, written by three people, over three years.

That team belongs to Keelwright Freight, the logistics company whose engineering history I use throughout this post. It's fictional; I wrote its 37 records to read like real ones, and I test on real GOV.UK decisions further down. The problem is real in every company I know: we record *what* we decided, and nobody notices when the reasons expire.

I built WHY for that question. It remembers the conditions each decision depended on, and checks whether they still hold before anyone reuses it.

![WHY answering the Postgres question: verdict first, then the agent's trace](docs/img/agent.png)

## What it does

Ask an engineering question and WHY answers **REUSE**, **ADAPT**, **RECONSIDER** or **INSUFFICIENT_EVIDENCE**, showing the past decision it matched, each assumption with the sentence it came from, what changed since, and the rule that fired.

It also runs the other way. Record a change, such as "we're consolidating production into eu-central-1", and WHY warns you which past decisions assumed otherwise. Nobody has to ask.

The memory is [Hindsight](https://github.com/vectorize-io/hindsight). ADRs, postmortems and change notes are all retained there, and every answer starts with a Hindsight recall. A small SQLite store only turns a recalled record ID back into the full document.

## Assumptions are the unit of memory

Real ADRs don't list their assumptions; they're buried in the Context section. At ingest, WHY asks an LLM to extract them, and keeps one only if its supporting quote appears **verbatim** in the source. The model may elide with "...", but every fragment has to match. I learned the hard way that this check must normalize typography: my first run dropped the two most important assumptions because the model wrote "month‑end" with a non-breaking hyphen.

Assumptions then become search queries. The change that breaks a decision rarely looks like the question: a note about month-end reporting isn't similar to "should we use Postgres?". The assumption in between, "finance reporting runs SQL JOINs directly on the ledger database", is similar to both. So after finding the precedent, WHY recalls once per assumption, scoped to change notes and postmortems:

```python
# src/reasoning.py: one Hindsight recall per assumption
queries = [f"{a.statement}. ({rec.title})" for a in assumptions]
results = await asyncio.gather(*(
    memory.recall(q, ["signal", "postmortem"], stage=f"change:{i}", bank_id=self.bank)
    for i, q in enumerate(queries)))
```

I expected this to be the big win. It wasn't, and I'll come back to why.

## Time is a field, not metadata

A fact only counts against a decision if it happened *after* the decision. A 2022 note was part of the world the 2023 decision was made in, so it can't invalidate it. Hindsight makes this easy because `retain` takes a timestamp. Every record goes in with its real date, its ID as `document_id`, and a kind tag that lets recall be scoped:

```python
# src/memory.py
await client().aretain(
    bank_id=bank_id, content=_content(rec, raw_text),
    timestamp=datetime.combine(rec.date, time(12, 0)),   # when it happened, not when we ingested it
    context=CONTEXT[rec.kind], document_id=rec.id,
    tags=[f"kind:{rec.kind}"],
    metadata={"record_id": rec.id, "kind": rec.kind, "date": rec.date.isoformat()},
)
```

## The model judges; code decides

The LLM never picks the verdict. It makes one narrow judgment per assumption: HOLDS, BROKEN or UNKNOWN, citing evidence IDs. Then code takes over. It deletes citations to evidence it never supplied, downgrades a BROKEN claim left without evidence, and applies fixed rules:

```python
# src/rules.py
if precedent_failed or any(c.critical and c.status == Status.BROKEN for c in checks):
    return Verdict.RECONSIDER
if not evaluation_complete or any((not c.critical and c.status == Status.BROKEN)
                                  or (c.critical and c.status == Status.UNKNOWN) for c in checks):
    return Verdict.ADAPT
return Verdict.REUSE
```

Plain rules can be tested exhaustively. One test walks every combination of assumption states and checks that a worse status never yields a more confident verdict. Another caught a real bug: when the model call failed and every assumption was non-critical, the old rules returned REUSE. Now a failed evaluation can't.

The discipline cuts both ways. The model sometimes called an assumption UNKNOWN while citing nothing, so WHY hedged on decisions nothing had challenged. Now an UNKNOWN has to point at the evidence that makes it unclear; otherwise it means "no change recorded".

## What happens in practice

Same question, same model, with and without memory:

> **Without memory:** "Yes, PostgreSQL should work for the customs-duty ledger as it did for the payments ledger; the expected 1.2k writes per second is within its proven capacity, so you can reuse the same approach." → REUSE
>
> **With WHY:** ADR-007, decided 3 years 7 months ago. *Write volume stays near 1,800/s*: BROKEN, peak hit 3,140/s in December 2025. *Finance reporting runs on the same database*: BROKEN, moved to Snowflake in August 2025. *Single region*: HOLDS. → RECONSIDER

The part I like most is watching it learn. Ask whether a new integration should reuse the carrier retry policy (5 retries, exponential backoff) and WHY says REUSE: nothing in memory contradicts it. Retain the postmortem of a 47-minute outage caused by a retry storm against a carrier's rate limit, ask the identical question, and the answer becomes RECONSIDER, citing the outage. Same question, different answer, because memory changed.

![Decision health board: WHY checks every active decision](docs/img/health.png)

Run across Keelwright's whole decision log, WHY flagged 5 of its 10 active decisions as no longer resting on the conditions they were made under.

## The numbers, including the ones I didn't expect

I wrote 26 questions with the correct verdict fixed in advance, and scored exact matches; no LLM grades anything. Every contestant uses the same model.

- **No memory:** 8 of 26 right, and it recommended a decision whose reasons had expired in 4 of 16 cases.
- **Recalled memories pasted into the prompt:** 13 of 26.
- **Hindsight's own `reflect`:** 17 of 26, a strong baseline.
- **WHY:** 23 of 26 (vs no memory, p = 0.0003), no false alarms on the 7 still-valid decisions, and the right answer both before and after the postmortem in all 3 pairs.

WHY's lead over `reflect` is not statistically significant with 26 questions. Its three misses all disappear when it's given hand-written assumptions, so extraction is where the remaining errors come from.

Then the surprise. A variant that makes **one** question-keyed recall, instead of one per assumption, also scored 23 of 26. It missed the Snowflake note on one of the two Postgres questions and found it on the other. With 37 records, one recall already finds most of what matters. The per-assumption recall is still what makes the trace readable, but the accuracy comes from the decision layer: assumptions, dates, grounded citations and fixed rules.

Real data was humbling too. On GOV.UK's 38 published ADRs from [alphagov/govuk-aws](https://github.com/alphagov/govuk-aws), extraction held up: 109 assumptions grounded in verbatim quotes, only 3 rejected. Judging which decisions GOV.UK later reversed did not. On 8 decisions, the model I benchmarked caught 1 of 3 reversals and left all 5 untouched decisions alone; another model caught 2 of 3 but flagged 4 decisions nobody changed. I report both runs. Eight cases can't yet separate WHY from the model it runs on.

A question takes a median of **3.4 seconds** end to end, with one LLM call and five or six Hindsight recalls. Memory isn't the bottleneck: recall throughput rose from 1.3 to 10 per second as concurrency went from 1 to 8.

## What I learned

1. **Store the conditions, not just the decision.** Everyone retrieves the decision. The assumptions are what change.
2. **Dates are evidence.** "Recorded after the decision" removes a whole class of wrong answers, and it only works because Hindsight retains real timestamps.
3. **Let code have the last word.** A narrow LLM judgment plus fixed rules gave me behavior I could test, explain, and audit for invented citations.
4. **Measure the decision, not the retrieval.** Scoring verdicts, flips and leading questions ("like payments did, right?") told me more than any recall metric.
5. **Run the ablation you don't want to run.** Mine showed my favorite idea wasn't where the accuracy came from, which was worth knowing before I claimed it.

## Limitations

If a change was never written down, WHY can't know. It labels those assumptions "no change recorded", never "confirmed", so the gap is at least visible.

## Links

- [Hindsight on GitHub](https://github.com/vectorize-io/hindsight): the agent memory layer used here
- [Hindsight documentation](https://hindsight.vectorize.io/) for retain, recall and reflect
- [What is agent memory?](https://vectorize.io/what-is-agent-memory) from Vectorize
- WHY source code: https://github.com/aryan-nampally/why-decision-agent
