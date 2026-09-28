# WHY — 3-minute demo video script

**Before recording:** `python -m scripts.seed` (clean memory), start `uvicorn src.app:app --port 8000`, open http://localhost:8000, browser zoom 110–125%, close notifications. Record at 1080p (OBS). Do one practice run first.

---

## 0:00–0:30 · Intro (camera or voice over the Agent page)

**Say:** "Hi, I'm [NAME]. I built WHY, an agent that remembers why engineering decisions were made, and notices when the reasons stop being true. Teams write architecture decision records. What they don't write down is when the world those decisions depended on changes. That happens in other documents, by other people, years later."

**Show:** Agent page, empty. Hover the four tabs briefly.

## 0:30–1:00 · The problem: no memory

**Do:** Click the chip **"Postgres for a new ledger?"** (keep *compare with no memory* ticked).

**Say (while the orchestration runs):** "A new team is building a customs-duty ledger and asks: should we use Postgres, like the payments team did? First, the same model without memory…"

**Show:** Point at the grey *Same question, same model, no memory* card: **REUSE — "1.2k writes per second is well within Postgres' capabilities."** "Sounds reasonable. It's wrong."

## 1:00–2:00 · With memory: watch the orchestration

**Show:** Scroll to *Agent orchestration*. Walk the six steps top to bottom.

**Say:**
- "Step one is Hindsight: it recalls the precedent, ADR-007, from February 2023."
- "Step two: the assumptions that decision depended on, extracted from the ADR's own text. Each one has a quote."
- "Step three is Hindsight again, but it searches once *per assumption*. The question never mentions Snowflake, but the assumption about finance reporting does, so that's what finds the migration. And look: a 2022 note is struck out, because evidence from before the decision can't invalidate it."
- "Step four is the only place the model decides anything: holds or broken, with citations. Step five, code checks those citations. Step six, a fixed rule: critical assumption broken, reconsider."

**Show:** Verdict banner **RECONSIDER**, then the *Now* card: A1 BROKEN (3,140 writes/s), A3 BROKEN (Snowflake).

## 2:00–2:30 · It learns: same question, different answer

**Do:** Click **"Retry policy for a new integration?"** → **REUSE**. Then in *New documents* click **Ingest** on PM-2024-11. Click the same chip again → **RECONSIDER**.

**Say:** "Nothing contradicts our retry policy, so: reuse. Now I add the postmortem of a 47-minute outage caused by a retry storm. Same question, and the answer changes, citing the outage. That's the memory doing the work."

## 2:30–2:50 · Tripwire, then proof

**Do:** *Record a change*: "Consolidating all production into eu-central-1" → **Retain & scan**.

**Say:** "Nobody asked a question. Memory checked the past decisions and flagged ADR-007: the payments ledger assumed a single region, us-east-1."

**Show (quick):** *Evaluation* tab: the GOV.UK table, "3/3 real reversals caught, citing the record that changed them".

## 2:50–3:00 · Takeaway

**Say:** "What surprised me: the model didn't need to be smarter. It needed to remember *when* things happened and *what* a decision depended on. Hindsight holds the memory, code has the final word. Links are below."

---

## Title ideas
1. I built an agent that knows when your architecture decisions expire
2. Your ADR says Postgres. Here's why that's no longer true
3. Agent memory that changes its answer when the facts change
4. Catching dead engineering decisions with Hindsight agent memory
5. Same question, different answer: an agent that learns from postmortems

## Thumbnail prompt (Nano Banana, 16:9)
"Generate a viral YouTube thumbnail, 16:9. Left: [attach team photo], a developer looking surprised. Center: a big red stamp 'RECONSIDER' over a faded document titled 'ADR-007 · Postgres · 2023'. Right: bold white text 'YOUR DECISION EXPIRED'. Dark navy background, teal accents, high contrast, clean tech style."
