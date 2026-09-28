import { useCallback, useEffect, useState } from "react";
import { api, type StageEvent } from "../api";
import { Orchestration } from "../components/Orchestration";
import { Evidence, NoMemory, Now, Recommendation, Then, Trace, VerdictBanner } from "../components/Result";
import { NewDocuments, RecordChange, Timeline } from "../components/Sidebar";
import type { AskResponse, HoldbackDoc, StatelessResponse, TimelineItem } from "../types";

const SCENARIOS = [
  { label: "Postgres for a new ledger?", q: "We're building the customs-duty ledger. Should we use Postgres like the payments ledger did?", c: "Expected ~1.2k writes/s at launch." },
  { label: "Retry policy for a new integration?", q: "Should the new customs-broker integration retry failed calls with exponential backoff, up to 5 retries, like our carrier integration does?", c: "" },
  { label: "Sync call to pricing?", q: "The new rate-comparison widget needs a live price at checkout. Should it call pricing synchronously over REST like booking does?", c: "" },
  { label: "No precedent", q: "Which mobile app framework should we use for the new driver app, React Native or Flutter?", c: "" },
];

const VERDICTS: [string, string][] = [
  ["REUSE", "the conditions it depended on still hold"],
  ["ADAPT", "a minor condition changed, or a key one can't be checked"],
  ["RECONSIDER", "a load-bearing condition no longer holds, or the approach failed"],
  ["INSUFFICIENT_EVIDENCE", "no past decision covers this question"],
];

function HowItWorks() {
  return (
    <>
      <div className="how">
        <div className="card"><div className="n">01 · Hindsight</div><h4>Recall the precedent</h4>
          <p>Find the past decision this question is really about, from ADRs retained with their real dates.</p></div>
        <div className="card"><div className="n">02 · Hindsight + LLM</div><h4>Check its assumptions</h4>
          <p>Recall once per assumption for anything that changed <i>after</i> the decision, then judge each one: holds, broken or unknown.</p></div>
        <div className="card"><div className="n">03 · Code</div><h4>Decide by rule</h4>
          <p>Invented citations are removed and a fixed rule picks the verdict. The model never picks it directly.</p></div>
      </div>
      <div className="card">
        <h3>Four possible answers</h3>
        <div className="legend">
          {VERDICTS.map(([v, d]) => <div key={v}><span className={`vpill v-${v}`}>{v.replace("_", " ")}</span>{d}</div>)}
        </div>
      </div>
    </>
  );
}

type Off = StatelessResponse | "loading" | { error: string } | null;

export default function AgentPage() {
  const [question, setQuestion] = useState("");
  const [context, setContext] = useState("");
  const [compare, setCompare] = useState(true);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<{ msg: string; err?: boolean } | null>(null);
  const [result, setResult] = useState<AskResponse | null>(null);
  const [asked, setAsked] = useState("");
  const [off, setOff] = useState<Off>(null);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [fresh, setFresh] = useState<Set<string>>(new Set());
  const [holdback, setHoldback] = useState<HoldbackDoc[]>([]);
  const [events, setEvents] = useState<StageEvent[]>([]);

  const refresh = useCallback(async (highlight?: string) => {
    const [t, h] = await Promise.all([api.timeline().catch(() => []), api.holdback().catch(() => [])]);
    setTimeline((prev) => {
      const known = new Set(prev.map((x) => x.id));
      const added = t.filter((x) => prev.length && !known.has(x.id)).map((x) => x.id);
      setFresh(new Set([...added, ...(highlight ? [highlight] : [])]));
      return t;
    });
    setHoldback(h);
  }, []);

  const ask = useCallback(async (q: string, c: string) => {
    if (q.trim().length < 3) return;
    setBusy(true);
    setAsked(q);
    setEvents([]);
    setResult(null);
    setStatus(null);
    const offP = compare ? api.askStateless(q, c).catch((e: Error) => ({ error: e.message })) : null;
    setOff(compare ? "loading" : null);
    try {
      setResult(await api.askStream(q, c, (ev) => setEvents((prev) => [...prev, ev])));
    } catch (e) {
      setStatus({ msg: (e as Error).message, err: true });
    } finally {
      setBusy(false);
    }
    if (offP) setOff(await offP);
  }, [compare]);

  useEffect(() => {
    refresh();
    const m = location.hash.match(/scenario=(\d)/); // deep link used for the recorded demo
    if (m && SCENARIOS[+m[1]]) {
      const s = SCENARIOS[+m[1]];
      setQuestion(s.q);
      setContext(s.c);
      ask(s.q, s.c);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <>
      <main className="layout">
        <section>
          <form className="card ask" onSubmit={(e) => { e.preventDefault(); ask(question, context); }}>
            <h1>Should we do it the way we did last time?</h1>
            <p className="lead">WHY finds the past decision, checks whether the conditions it depended on still hold, and says whether to reuse, adapt or reconsider it.</p>
            <label htmlFor="q">Engineering question</label>
            <textarea id="q" rows={2} value={question} onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. Should the new customs-duty ledger use Postgres like the payments ledger did?" />
            <label htmlFor="ctx">Current context <span className="muted">(optional)</span></label>
            <input id="ctx" value={context} onChange={(e) => setContext(e.target.value)} placeholder="e.g. Expected ~1.2k writes/s at launch" />
            <div className="row">
              <div className="chips">
                <span className="chips-k">try</span>
                {SCENARIOS.map((s) => (
                  <button key={s.label} type="button" className="chip" disabled={busy}
                    onClick={() => { setQuestion(s.q); setContext(s.c); ask(s.q, s.c); }}>{s.label}</button>
                ))}
              </div>
              <label className="toggle"><input type="checkbox" checked={compare} onChange={(e) => setCompare(e.target.checked)} /> compare with no memory</label>
              <button type="submit" disabled={busy}>{busy ? "Thinking…" : "Ask WHY"}</button>
            </div>
          </form>

          {status && <div className={`status ${status.err ? "err" : ""}`}>{status.msg}</div>}

          {events.length === 0 && !result && !busy && <HowItWorks />}

          {result && <VerdictBanner r={result} />}
          {result && off && <NoMemory off={off} />}

          {events.length > 0 && <Orchestration events={events} live={busy} />}

          {result && (
            <>
              <div className="thennow">
                <Then r={result} />
                <div className="bridge"><span>{result.decision_age ? `${result.decision_age.replace(/ ago$/, "")} later` : "today"}</span></div>
                <Now r={result} />
              </div>
              <Recommendation key={asked + result.headline} r={result} question={asked}
                onAccepted={(msg, id) => { setStatus({ msg }); refresh(id); }} />
              <Evidence r={result} />
              <Trace r={result} />
            </>
          )}
        </section>

        <aside>
          <RecordChange onRetained={(id) => refresh(id)} />
          <NewDocuments docs={holdback} onIngested={(id) => refresh(id)} />
          <Timeline items={timeline} fresh={fresh} onReset={() => { setResult(null); setEvents([]); setOff(null); setStatus({ msg: "Demo memory restored to its starting state." }); refresh(); }} />
        </aside>
      </main>
    </>
  );
}
