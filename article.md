# The ADR said Postgres. Hindsight remembered why it expired

In February 2023 a payments team chose PostgreSQL for its ledger, for two good reasons: finance ran month-end reports as SQL JOINs directly on that database, and peak writes were projected to stay under about 1,800 per second. By December 2025 both reasons were gone. Finance had moved to Snowflake in August, and Cyber Monday pushed the ledger to 3,140 writes per second. Neither change mentioned the ADR. So when a new team asked "should the customs-duty ledger use Postgres, like payments did?", the honest answer lived in three documents, written by three people, over three years.

That team belongs to Keelwright Freight, the logistics company whose engineering history I use throughout this post. It's fictional; I wrote its 37 records to read like real ones, and I test on real GOV.UK decisions further down.

I built WHY for that question. It remembers the conditions each decision depended on, and checks whether they still hold before anyone reuses it.

![WHY answering the Postgres question: verdict first, then the agent's trace](docs/img/agent.png)

## What it does

Ask an engineering question and WHY answers **REUSE**, **ADAPT**, **RECONSIDER** or **INSUFFICIENT_EVIDENCE**, showing the past decision it matched, each assumption with the sentence it came from, what changed since, and the rule that fired. It also runs the other way: record a change, such as "we're consolidating production into eu-central-1", and WHY warns you which past decisions assumed otherwise.

The memory is [Hindsight](https://github.com/vectorize-io/hindsight). ADRs, postmortems and change notes are all retained there, and every answer starts with a Hindsight recall.

## The gap I was trying to close

Research on agent memory keeps hitting the same wall. The STALE benchmark (Chao et al., 2026) found that agents struggle to notice when a stored memory is invalidated by a later observation that never mentions it; the best model managed 55.2%. Su et al. (2026) tested LLMs on 980 ADRs: they catch *code* that violates a decision, but struggle when the decision rests on deployment or organizational knowledge. CTIM-Rover (2025) gave a coding agent episodic memory, and it didn't help: distracting memories added noise. And decision-memory tools like Varve ask whether the code still follows a decision, not whether the decision still fits the world.

Here's how WHY answers each one:

- **Implicit invalidation.** Assumptions are explicit targets, and only evidence dated after a decision may break one. The Snowflake note never mentions ADR-007; it doesn't have to.
- **Organizational knowledge.** Postmortems, traffic reports and team changes live in Hindsight next to the decisions they affect.
- **Memory noise.** The judge sees a few recalled items per assumption, and code deletes any citation it wasn't given.
- **Evaluation.** I score whether the *decision* changes correctly, not whether retrieval found a document.

## Assumptions are the unit of memory

Real ADRs don't list their assumptions; they're buried in the Context section. At ingest, WHY asks an LLM to extract them, and keeps one only if its supporting quote appears **verbatim** in the source. I learned the hard way that this check must normalize typography: my first run dropped the two most important assumptions because the model wrote "month‑end" with a non-breaking hyphen.

Assumptions then become search queries. A note about month-end reporting isn't similar to "should we use Postgres?", but the assumption in between, "finance reporting runs SQL JOINs directly on the ledger database", is similar to both. So after finding the precedent, WHY recalls once per assumption, scoped to change notes and postmortems:

```python
# src/reasoning.py: one Hindsight recall per assumption
queries = [f"{a.statement}. ({rec.title})" for a in assumptions]
results = await asyncio.gather(*(
    memory.recall(q, ["signal", "postmortem"], stage=f"change:{i}", bank_id=self.bank)
    for i, q in enumerate(queries)))
```

I expected this to be the big win. It wasn't, and I'll come back to why.

## Time is a field, not metadata

A fact only counts against a decision if it happened *after* the decision. Hindsight makes this easy because `retain` takes a timestamp. Every record goes in with its real date, its ID as `document_id`, and a kind tag that lets recall be scoped:

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

The LLM never picks the verdict. It makes one narrow judgment per assumption: HOLDS, BROKEN or UNKNOWN, citing evidence IDs. Then code deletes citations to evidence it never supplied, downgrades a BROKEN claim left without evidence, and applies fixed rules:

```python
# src/rules.py
if precedent_failed or any(c.critical and c.status == Status.BROKEN for c in checks):
    return Verdict.RECONSIDER
if not evaluation_complete or any((not c.critical and c.status == Status.BROKEN)
                                  or (c.critical and c.status == Status.UNKNOWN) for c in checks):
    return Verdict.ADAPT
return Verdict.REUSE
```

Plain rules can be tested exhaustively: a worse assumption status never yields a more confident verdict. One test caught a real bug, where a failed model call on non-critical assumptions returned REUSE. It can't anymore. And an UNKNOWN now has to cite the evidence that makes it unclear; otherwise it means "no change recorded".

## What happens in practice

Same question, same model, with and without memory:

> **Without memory:** "Yes, PostgreSQL should work for the customs-duty ledger as it did for the payments ledger; the expected 1.2k writes per second is within its proven capacity, so you can reuse the same approach." → REUSE
>
> **With WHY:** ADR-007, decided 3 years 7 months ago. *Write volume stays near 1,800/s*: BROKEN, peak hit 3,140/s in December 2025. *Finance reporting runs on the same database*: BROKEN, moved to Snowflake in August 2025. *Single region*: HOLDS. → RECONSIDER

The part I like most is watching it learn. Ask whether a new integration should reuse the carrier retry policy (5 retries, exponential backoff) and WHY says REUSE: nothing in memory contradicts it. Retain the postmortem of a 47-minute outage caused by a retry storm against a carrier's rate limit, ask the identical question, and the answer becomes RECONSIDER, citing the outage. Same question, different answer, because memory changed.

![Decision health board: WHY checks every active decision](docs/img/health.png)

Run across Keelwright's whole decision log, WHY flagged 5 of its 10 active decisions as no longer resting on the conditions they were made under.

## The numbers, including the ones I didn't expect

I wrote 26 questions with the correct verdict fixed in advance and scored exact matches; no LLM grades anything. Every contestant uses the same model. No memory got 8 right, and recommended a decision whose reasons had expired in 4 of 16 cases. Pasting recalled memories into the prompt got 13. Hindsight's own `reflect` got 17, a strong baseline. WHY got **23** (vs no memory, p = 0.0003), with no false alarms on the 7 still-valid decisions and the right answer before and after the postmortem in all 3 pairs. Its lead over `reflect` isn't statistically significant at this size, and its three misses disappear with hand-written assumptions.

Then the surprise. A variant with **one** question-keyed recall, instead of one per assumption, also scored 23. It missed the Snowflake note on one Postgres question and found it on the other. With 37 records, one recall already reaches most of what matters. The accuracy comes from the decision layer: assumptions, dates, grounded citations and fixed rules.

On GOV.UK's 38 published ADRs from [alphagov/govuk-aws](https://github.com/alphagov/govuk-aws), extraction held up: 109 assumptions grounded in verbatim quotes, only 3 rejected. A median question takes **3.4 seconds** with one LLM call, and recall throughput rose from 1.3 to 10 per second as concurrency went from 1 to 8, so memory isn't the bottleneck.

## What I learned

1. **Store the conditions, not just the decision.** Everyone retrieves the decision. The assumptions are what change.
2. **Dates are evidence.** "Recorded after the decision" removes a whole class of wrong answers, and it only works because Hindsight retains real timestamps.
3. **Let code have the last word.** A narrow LLM judgment plus fixed rules gave me behavior I could test, explain, and audit for invented citations.
4. **Run the ablation you don't want to run.** Mine showed my favorite idea wasn't where the accuracy came from.

## What's still open

Three gaps remain. If a change was never written down, WHY can't know; it says "no change recorded", never "confirmed". Extraction sometimes rates a minor assumption critical, which is where its wrong verdicts come from. And on GOV.UK's real history, judging which decisions were later reversed still depends on the model: one caught 1 of 3 reversals and left all 5 untouched decisions alone, another caught 2 of 3 but flagged 4 that nobody changed. A larger real-data evaluation is the next step.

## Links

- [Hindsight on GitHub](https://github.com/vectorize-io/hindsight): the agent memory layer used here
- [Hindsight documentation](https://hindsight.vectorize.io/) for retain, recall and reflect
- [What is agent memory?](https://vectorize.io/what-is-agent-memory) from Vectorize
- WHY source code: https://github.com/aryan-nampally/why-decision-agent
