# WHY — 3-minute demo video script

**Before recording:** `python -m scripts.seed` (clean memory), start `uvicorn src.app:app --port 8000`, open http://localhost:8000, browser zoom 110–125%, close notifications. Record at 1080p (OBS). Do one practice run first.

---

## 0:00–0:30 · Intro (camera or voice over the Agent page)

**Say:** "Hi, I'm Aryan. I built WHY, an agent that remembers why engineering decisions were made, and notices when the reasons stop being true. Teams write architecture decision records. What they don't write down is when the world those decisions depended on changes. That happens in other documents, by other people, years later."

**Show:** Agent page, empty. Hover the four tabs briefly.

## 0:30–1:30 · Ask, and watch the agent work

**Do:** Click the chip **"Postgres for a new ledger?"** (keep *compare with no memory* ticked). Scroll down a little so the *Agent orchestration* panel is in view while it runs.

**Say (while the steps light up):** "A new team is building a customs-duty ledger and asks: should we use Postgres, like the payments team did? Watch what the agent does."
- "Step one is Hindsight: it recalls the precedent, ADR-007, from February 2023."
- "Step two: the conditions that decision depended on, extracted from the ADR's own text, each with a quote."
- "Step three is Hindsight again, but it searches once *per assumption*. The question never mentions Snowflake, but the assumption about finance reporting does, so that's what finds the migration. And that struck-out 2022 note is older than the decision, so it isn't allowed to count against it."
- "Step four is the only place the model decides anything: holds or broken, with citations. Step five, code checks those citations. Step six, a fixed rule: a critical assumption broke, so reconsider."

## 1:30–2:00 · The answer, with and without memory

**Show:** Scroll back to the top: the **RECONSIDER** stamp, then the grey card underneath.

**Say:** "Same question, same model, no memory: *reuse it, 1.2k writes a second is well within capacity*. Sounds reasonable. It's wrong. With memory: reconsider. Writes hit 3,140 a second last Cyber Monday, and finance moved its reporting to Snowflake." Point at the *Now* column: A1 and A3 BROKEN, each with its evidence chip.

## 2:00–2:30 · It learns: same question, different answer

**Do:** Click **"Retry policy for a new integration?"** → **REUSE**. Then in *New documents* click **Ingest** on PM-2024-11. Click the same chip again → **RECONSIDER**.

**Say:** "Nothing contradicts our retry policy, so: reuse. Now I add the postmortem of a 47-minute outage caused by a retry storm. Same question, and the answer changes, citing the outage. That's the memory doing the work."

## 2:30–2:50 · Tripwire, then proof

**Do:** *Record a change*: "Consolidating all production into eu-central-1" → **Retain & scan**.

**Say:** "Nobody asked a question. Memory checked the past decisions and flagged ADR-007: the payments ledger assumed a single region, us-east-1."

**Show (quick):** *Evaluation* tab. Point at the top numbers (23/26 with WHY vs 8/26 without memory), then scroll to the per-question grid: "every answer from every method, green or red."

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
