import { Fragment, useEffect, useState } from "react";

interface Frac { x: number; n: number; rate: number | null; ci95: [number, number] }
interface Metrics {
  verdict_accuracy: Frac; "precedent_hit@1": Frac; false_reuse_rate: Frac; false_reconsider_rate: Frac;
  repeat_error_rate: Frac; premise_accuracy: Frac; flip_accuracy: Frac; median_ms: number | null; errors: number;
}
interface Bench {
  run_at: string; model: string; extraction_model: string; note: string | null; n_cases: number; models?: Record<string, string[]>;
  conditions: Record<string, { all: Metrics; test_split: Metrics }>; incomplete: Record<string, string>;
  mcnemar_vs_C: Record<string, { other_right_C_wrong: number; C_right_other_wrong: number; p: number }>;
  tripwire: { precision: number; recall: number; tp: number; predicted: number; gold: number } | null;
  rows: { case: string; condition: string; verdict: string }[];
}
interface Case {
  id: string; split: string; phase: string; premise?: boolean; question: string; context?: string;
  precedent: string | null; verdict: string; pair?: string; failed?: boolean;
}
interface Real {
  model: string; as_of: string;
  extraction: { adrs: number; assumptions: number; critical: number; dropped_ungrounded: number };
  rows: { decision: string; title: string; date: string; changed_later: boolean; changed_by: string | null; history: string;
    verdict: string; flagged: boolean; cites_changing_record: boolean; cited: string[];
    reflect?: { verdict?: string; flagged?: boolean; mentions_changing_record?: boolean } }[];
}
interface RealRun { label: string; model: string; code: string; targets: number; flagged: number; cited: number; controls: number; left_alone: number }
interface Stat { n: number; p50: number; p95: number; mean: number; max: number }
interface Perf {
  run_at: string; model: string;
  memory_layer: { concurrency: number; latency_ms: Stat; throughput_per_s: number }[];
  end_to_end: { n: number; stages_ms: Record<string, Stat>; tokens_per_question: Stat; prompt_tokens_mean: number;
    completion_tokens_mean: number; llm_calls_per_question: number; hindsight_recalls_per_question: number } | null;
  derived: { llm_tpm_limit?: number; tokens_per_question_mean: number; max_questions_per_minute_under_tpm?: number;
    max_questions_per_minute?: number; limit_text?: string; note: string } | null;
}

/* Contestants in display order. Codes stay as small tags so they match results.md and the README. */
const CONTESTANTS: { code: string; name: string; short: string; group: "why" | "base"; what: string }[] = [
  { code: "C", name: "WHY", short: "WHY", group: "why",
    what: "The full agent: assumptions extracted from the ADR's prose, one Hindsight recall per assumption, a date filter, the LLM judges each assumption, a fixed rule picks the verdict." },
  { code: "C-oracle", name: "WHY + hand-written assumptions", short: "WHY+gold", group: "why",
    what: "Same agent, given assumptions a human wrote instead of extracted ones. The gap to WHY is the cost of extraction mistakes." },
  { code: "C-1stage", name: "WHY, single recall", short: "WHY-1", group: "why",
    what: "Same agent, but one Hindsight recall keyed on the question instead of one per assumption. Tests whether the two-stage recall matters." },
  { code: "B3", name: "Hindsight reflect", short: "reflect", group: "base",
    what: "Hindsight's built-in reasoning over the same memory bank, asked for a verdict in a structured format. Uses Hindsight's own model." },
  { code: "B2", name: "Memories pasted into the LLM", short: "recall+LLM", group: "base",
    what: "The 15 memories Hindsight recalls for the question, pasted into the same LLM. Memory, but no decision structure." },
  { code: "A", name: "No memory", short: "no mem", group: "base",
    what: "The same LLM, given only the question. What you get today by asking a chatbot." },
  { code: "ALWAYS-R", name: "Always says “reconsider”", short: "always-R", group: "base",
    what: "A dummy. It never reuses a stale decision, which shows why that one number alone can be gamed." },
];
const NAME = Object.fromEntries(CONTESTANTS.map((c) => [c.code, c.name]));

const VSHORT: Record<string, string> = { REUSE: "reuse", ADAPT: "adapt", RECONSIDER: "reconsider", INSUFFICIENT_EVIDENCE: "no precedent", ERROR: "error" };

type Kind = { key: string; label: string; answer: string; tests: string };
const KINDS: Kind[] = [
  { key: "stale", label: "Stale decision", answer: "RECONSIDER", tests: "A load-bearing reason behind the past decision has since broken. Reusing it would repeat a mistake." },
  { key: "partial", label: "Partly changed", answer: "ADAPT", tests: "Something minor changed, or a key condition can't be checked. Reuse it, with changes." },
  { key: "valid", label: "Still valid", answer: "REUSE", tests: "Nothing that matters has changed. Warning here is a false alarm." },
  { key: "none", label: "No precedent", answer: "INSUFFICIENT_EVIDENCE", tests: "No past decision covers the question. The agent must not invent one." },
  { key: "after", label: "After a new postmortem", answer: "RECONSIDER", tests: "Asked after a retry-storm postmortem is added mid-test. The answer must change because memory changed." },
];
function kindOf(c: Case): string {
  if (c.phase === "after") return "after";
  return ({ RECONSIDER: "stale", ADAPT: "partial", REUSE: "valid", INSUFFICIENT_EVIDENCE: "none" } as Record<string, string>)[c.verdict] ?? "stale";
}

const pct = (f?: Frac) => (f && f.n ? `${Math.round((f.rate ?? 0) * 100)}%` : "—");
const frac = (f?: Frac) => (f && f.n ? `${f.x}/${f.n}` : "—");

function Bar({ f, good = "high" }: { f?: Frac; good?: "high" | "low" }) {
  if (!f || !f.n) return <span className="muted">—</span>;
  const r = f.rate ?? 0;
  return (
    <div className="mbar" title={`${f.x} of ${f.n} · 95% interval ${Math.round(f.ci95[0] * 100)}–${Math.round(f.ci95[1] * 100)}%`}>
      <div className={`mfill ${good === "low" ? "bad" : ""}`} style={{ width: `${r * 100}%` }} />
      <div className="mci" style={{ left: `${f.ci95[0] * 100}%`, width: `${(f.ci95[1] - f.ci95[0]) * 100}%` }} />
      <span className="mlabel">{f.x}/{f.n} <span className="muted">· {pct(f)}</span></span>
    </div>
  );
}

function Who({ code }: { code: string }) {
  return <><b className="who">{NAME[code] ?? code}</b> <span className="code">{code}</span></>;
}

function jump(id: string) {
  return (e: React.MouseEvent) => { e.preventDefault(); document.getElementById(id)?.scrollIntoView({ behavior: "smooth" }); };
}

export default function EvaluationPage() {
  const [d, setD] = useState<{ benchmark: Bench | null; cases: { ask: Case[] } | null; real: Real | null;
    real_runs: { note: string; runs: RealRun[] } | null; perf: Perf | null } | null>(null);
  const [split, setSplit] = useState<"all" | "test_split">("all");
  const [openQ, setOpenQ] = useState<string | null>(null);
  useEffect(() => { fetch("/api/evaluation").then((r) => r.json()).then(setD); }, []);
  if (!d) return <main className="page"><p className="muted">Loading…</p></main>;
  const b = d.benchmark, real = d.real, perf = d.perf;
  const cases = d.cases?.ask ?? [];
  const codes = b ? CONTESTANTS.map((c) => c.code).filter((c) => b.conditions[c]) : [];
  const m = (c: string) => b?.conditions[c]?.[split];
  const all = (c: string) => b?.conditions[c]?.all;
  const verdictOf = new Map((b?.rows ?? []).map((r) => [`${r.condition}/${r.case}`, r.verdict]));
  const shownCases = cases.filter((c) => split === "all" || c.split === "test");
  const targets = real?.rows.filter((r) => r.changed_later) ?? [];
  const controls = real?.rows.filter((r) => !r.changed_later) ?? [];
  const mc = b?.mcnemar_vs_C ?? {};
  const sig = (p?: number) => p != null && p < 0.05;
  const stage = perf?.end_to_end?.stages_ms;

  return (
    <main className="page">
      <section className="card">
        <div className="eyebrow">Evaluation</div>
        <h1>Does memory make the agent decide better?</h1>
        <p className="lead">Most memory demos check whether the right document came back. We check what matters: when the reasons behind a past decision have changed, does the agent <i>change its advice</i>? And does it stay quiet when nothing changed? Every number on this page is read from result files written by the scripts in <code>evaluation/</code>.</p>
        {b && all("C") && all("A") && (
          <div className="stats">
            <div className="hero-stat"><b>{frac(all("C")!.verdict_accuracy)}</b><span>questions WHY answered correctly</span></div>
            <div><b>{frac(all("A")!.verdict_accuracy)}</b><span>same model without memory</span></div>
            <div><b>{all("A")!.false_reuse_rate.x} → {all("C")!.false_reuse_rate.x}</b><span>stale decisions recommended for reuse, without memory → with WHY (out of {all("C")!.false_reuse_rate.n})</span></div>
            {real && <div><b>{real.extraction.assumptions}</b><span>assumptions recovered from {real.extraction.adrs} real GOV.UK decision records, each grounded in a verbatim quote</span></div>}
            {stage && <div><b>{(stage.total.p50 / 1000).toFixed(1)} s</b><span>typical time to an answer</span></div>}
          </div>
        )}
        <nav className="toc">
          <a href="#/evaluation" onClick={jump("ev-how")}>1 · How the test works</a>
          <a href="#/evaluation" onClick={jump("ev-res")}>2 · Results</a>
          <a href="#/evaluation" onClick={jump("ev-grid")}>3 · Every question</a>
          <a href="#/evaluation" onClick={jump("ev-real")}>4 · Real GOV.UK decisions</a>
          <a href="#/evaluation" onClick={jump("ev-perf")}>5 · Speed and cost</a>
        </nav>
      </section>

      {/* 1 ---------------------------------------------------------------- */}
      <section className="card" id="ev-how">
        <h2>1 · How the test works</h2>
        <div className="steps3">
          <div><span className="n">The exam</span>
            <p><b>{cases.length} questions</b> an engineer at Keelwright Freight might ask, like <i>“Should we use Postgres like payments did?”</i>. For each one we wrote the correct answer <b>before</b> running anything: one of four verdicts, and which past decision it's about.</p></div>
          <div><span className="n">The contestants</span>
            <p><b>{codes.length} ways of answering</b>, all over the same memory of 37 records: WHY, two variants of WHY that isolate its parts, and four baselines. Every LLM contestant uses the same model.</p></div>
          <div><span className="n">The marking</span>
            <p><b>Exact match, no AI grader.</b> A contestant scores when its verdict equals the answer key. No LLM grades anything, so nothing is open to interpretation.</p></div>
        </div>

        <h3>Five kinds of question</h3>
        <div className="tablewrap">
          <table className="dt">
            <thead><tr><th>Kind</th><th>How many</th><th>Right answer</th><th>What it tests</th><th>Example</th></tr></thead>
            <tbody>{KINDS.map((k) => {
              const cs = cases.filter((c) => kindOf(c) === k.key);
              const ex = cs.find((c) => c.split === "test") ?? cs[0];
              return (
                <tr key={k.key}>
                  <td><b className="who">{k.label}</b></td><td>{cs.length}</td>
                  <td><span className={`vpill v-${k.answer}`}>{VSHORT[k.answer]}</span></td>
                  <td className="small">{k.tests}</td>
                  <td className="small"><i>“{ex?.question}”</i>{ex?.context && <div className="muted">context: {ex.context}</div>}</td>
                </tr>
              );
            })}</tbody>
          </table>
        </div>
        <p className="muted small">{cases.filter((c) => c.premise).length} of the questions are also <b>leading questions</b> that assume the old answer (“…like the shipper portal, right?”). {cases.filter((c) => c.split === "dev").length} were used while building the demo; “test questions only” leaves them out.</p>

        <h3>The contestants</h3>
        <div className="contest">
          {CONTESTANTS.filter((c) => codes.includes(c.code)).map((c) => (
            <div key={c.code} className={c.group === "why" ? "why" : ""}>
              <div><b>{c.name}</b> <span className="code">{c.code}</span></div>
              <p>{c.what}</p>
            </div>
          ))}
        </div>
      </section>

      {/* 2 ---------------------------------------------------------------- */}
      <section className="card" id="ev-res">
        <div className="row" style={{ marginTop: 0, marginBottom: 6 }}>
          <h2 style={{ margin: 0 }}>2 · Results</h2>
          <span className="seg">
            <button className={split === "all" ? "on" : ""} onClick={() => setSplit("all")}>all {cases.length} questions</button>
            <button className={split === "test_split" ? "on" : ""} onClick={() => setSplit("test_split")}>test questions only</button>
          </span>
        </div>
        {!b ? <p className="muted">Not run yet.</p> : (
          <>
            {b.note && <div className="status small">{b.note}</div>}
            {m("C") && m("A") && m("B3") && m("C-1stage") && (
              <div className="takeaways">
                <h3>What the numbers say</h3>
                <ol>
                  <li><b>Structured memory beats no memory.</b> WHY answered {frac(m("C")!.verdict_accuracy)} correctly; the same model without memory {frac(m("A")!.verdict_accuracy)}{split === "all" && mc.A && <> (a real difference, p = {mc.A.p})</>}.</li>
                  <li><b>It rarely reuses a stale decision, without crying wolf.</b> Without memory the model recommended a decision whose reasons had expired {m("A")!.false_reuse_rate.x} times out of {m("A")!.false_reuse_rate.n}; WHY {m("C")!.false_reuse_rate.x}. On the {m("C")!.false_reconsider_rate.n} still-valid decisions WHY raised {m("C")!.false_reconsider_rate.x} false alarm{m("C")!.false_reconsider_rate.x === 1 ? "" : "s"}.</li>
                  <li><b>It learns.</b> Asked the same question before and after a retry-storm postmortem is added to memory, WHY was right both times in {frac(m("C")!.flip_accuracy)} pairs; no memory in {frac(m("A")!.flip_accuracy)}.</li>
                  <li><b>Raw memory isn't enough.</b> Pasting recalled memories into the same model scored {frac(m("B2")?.verdict_accuracy)}. Hindsight's own <code>reflect</code> scored {frac(m("B3")!.verdict_accuracy)}: behind WHY, but {sig(mc.B3?.p) ? "significantly" : <>the gap is <b>not</b> statistically significant with this few questions</>}.</li>
                  <li><b>The decision layer is what matters, not the retriever.</b> The single-recall variant scored {frac(m("C-1stage")!.verdict_accuracy)}, level with WHY. The assumptions, the date filter and the verdict rules do the work.</li>
                </ol>
              </div>
            )}

            <h3>Scoreboard</h3>
            <div className="tablewrap">
              <table className="dt metrics">
                <thead><tr>
                  <th>Contestant</th>
                  <th>Correct answers ↑<br /><span className="muted">verdict matches the answer key</span></th>
                  <th>Reused a stale decision ↓<br /><span className="muted">said “reuse” when the right answer was adapt or reconsider</span></th>
                  <th>False alarm ↓<br /><span className="muted">said “reconsider” when the decision was still fine</span></th>
                </tr></thead>
                <tbody>
                  {codes.map((c) => (
                    <tr key={c} className={c === "C" ? "hl" : ""}>
                      <td><Who code={c} />{b.models?.[c]?.some((x) => x && x !== "—") && <div className="muted small">model: {b.models[c].join(", ")}</div>}</td>
                      <td><Bar f={m(c)?.verdict_accuracy} /></td>
                      <td><Bar f={m(c)?.false_reuse_rate} good="low" /></td>
                      <td><Bar f={m(c)?.false_reconsider_rate} good="low" /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="muted small">The dark line under each bar is the 95% confidence interval: with this few questions, any value along it is plausible. Look at the dummy: it never reuses a stale decision, but it raises a false alarm every time. That's why both columns are reported.</p>

            <h3>Harder tests</h3>
            <div className="tablewrap">
              <table className="dt">
                <thead><tr>
                  <th>Contestant</th>
                  <th>Changed its answer when memory changed<br /><span className="muted">same question before and after the postmortem; both must be right</span></th>
                  <th>Held firm on leading questions<br /><span className="muted">“…like payments did, right?”</span></th>
                  <th>Didn't repeat a failed approach<br /><span className="muted">after the postmortem, the approach that failed is proposed again</span></th>
                  <th>Found the right past decision<br /><span className="muted">ranked it first, when one exists</span></th>
                </tr></thead>
                <tbody>{codes.map((c) => {
                  const r = m(c)?.repeat_error_rate;
                  return (
                    <tr key={c} className={c === "C" ? "hl" : ""}>
                      <td><Who code={c} /></td>
                      <td>{frac(m(c)?.flip_accuracy)}</td>
                      <td>{frac(m(c)?.premise_accuracy)}</td>
                      <td>{r && r.n ? `${r.n - r.x}/${r.n}` : "—"}</td>
                      <td>{c === "ALWAYS-R" || c === "A" ? <span className="muted">n/a, no memory</span> : frac(m(c)?.["precedent_hit@1"])}</td>
                    </tr>
                  );
                })}</tbody>
              </table>
            </div>

            {split === "all" && Object.keys(mc).length > 0 && (
              <>
                <h3>Is the difference real, or luck?</h3>
                <p className="small">For each pair we count the questions where only one of the two was right (an exact McNemar test). A p-value below 0.05 means the difference is unlikely to be chance.</p>
                <div className="tablewrap">
                  <table className="dt">
                    <thead><tr><th>WHY vs</th><th>only WHY right</th><th>only the other right</th><th>p</th><th>Reading</th></tr></thead>
                    <tbody>{Object.entries(mc).map(([k, v]) => (
                      <tr key={k}><td><Who code={k} /></td><td>{v.C_right_other_wrong}</td><td>{v.other_right_C_wrong}</td><td>{v.p}</td>
                        <td>{Math.abs(v.C_right_other_wrong - v.other_right_C_wrong) <= 1 ? <span className="muted">about the same</span>
                          : v.C_right_other_wrong > v.other_right_C_wrong
                            ? (sig(v.p) ? <b className="good">WHY is better</b> : <span className="muted">WHY ahead, could be chance</span>)
                            : (sig(v.p) ? <b>{NAME[k] ?? k} is better</b> : <span className="muted">{NAME[k] ?? k} ahead, could be chance</span>)}</td></tr>
                    ))}</tbody>
                  </table>
                </div>
              </>
            )}

            {b.tripwire && (
              <>
                <h3>Tripwire: warning before anyone asks</h3>
                <p className="small">We record 5 changes, e.g. <i>“Northline cuts our rate limit from 100 to 40 requests/s”</i>, and check which past assumptions WHY says each one breaks. The answer key lists {b.tripwire.gold} breakages. WHY caught <b>{b.tripwire.tp} of {b.tripwire.gold}</b> ({Math.round(b.tripwire.recall * 100)}% recall), and <b>{b.tripwire.tp} of its {b.tripwire.predicted} alerts</b> were on the key ({Math.round(b.tripwire.precision * 100)}% precision). So it rarely misses a breakage, but about half its alerts would be noise to a human reviewer.</p>
              </>
            )}
          </>
        )}
      </section>

      {/* 3 ---------------------------------------------------------------- */}
      {b && (
        <section className="card" id="ev-grid">
          <h2>3 · Every question, every contestant</h2>
          <p className="small">Green: matches the answer key. Red: doesn't. Click a question to see its context and which past decision it's about.</p>
          <div className="tablewrap">
            <table className="dt qgrid">
              <thead><tr><th>Question</th><th>Right answer</th>{codes.map((c) => <th key={c} title={NAME[c]}>{CONTESTANTS.find((x) => x.code === c)?.short}</th>)}</tr></thead>
              <tbody>
                <tr className="qsum"><td colSpan={2}><b>Correct</b></td>{codes.map((code) => (
                  <td key={code}><b>{shownCases.filter((c) => verdictOf.get(`${code}/${c.id}`) === c.verdict).length}</b>/{shownCases.length}</td>))}</tr>
                {shownCases.map((c) => (
                  <Fragment key={c.id}>
                    <tr className="qrow" onClick={() => setOpenQ(openQ === c.id ? null : c.id)}>
                      <td><span className="code">{c.id}</span> <span className="qkind">{KINDS.find((k) => k.key === kindOf(c))?.label}{c.premise ? " · leading" : ""}{c.context ? " · with context" : ""}</span>
                        <div className="qtext">{c.question}</div></td>
                      <td><span className={`vpill v-${c.verdict}`}>{VSHORT[c.verdict]}</span></td>
                      {codes.map((code) => {
                        const v = verdictOf.get(`${code}/${c.id}`);
                        return <td key={code} className={`cell ${v == null ? "" : v === c.verdict ? "ok" : "bad"}`}>{v ? VSHORT[v] ?? v : "—"}</td>;
                      })}
                    </tr>
                    {openQ === c.id && (
                      <tr className="qopen"><td colSpan={2 + codes.length}>
                        <b>{c.question}</b>{c.context && <div>Context given: {c.context}</div>}
                        <div className="muted small">Past decision it's about: {c.precedent ?? "none"} · {c.phase === "after" ? "asked after PM-2024-11 was added to memory" : "asked before the postmortem"} · {c.split === "dev" ? "used during development" : "test question"}</div>
                      </td></tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* 4 ---------------------------------------------------------------- */}
      <section className="card" id="ev-real">
        <h2>4 · Real decisions: GOV.UK, 2017–2022</h2>
        {!real ? <p className="muted">Not run yet.</p> : (
          <>
            <p>We wrote the Keelwright data ourselves, so we also tried WHY on something we didn't write: the <b>{real.extraction.adrs} architecture decision records</b> GOV.UK published in <a href="https://github.com/alphagov/govuk-aws" target="_blank" rel="noreferrer">alphagov/govuk-aws</a> (MIT). The answer key is GOV.UK's own history: which decisions it later replaced.</p>
            <div className="steps3">
              <div><span className="n">Rewind</span><p>Each decision is judged as of {real.as_of}, using only records written <i>after</i> it. “Superseded by” notes added to old records later are stripped, so the answer can't leak.</p></div>
              <div><span className="n">Changed later · {targets.length}</span><p>Decisions GOV.UK went on to replace. WHY should flag them, ideally naming the record that replaced them.</p></div>
              <div><span className="n">Never revisited · {controls.length}</span><p>Decisions GOV.UK never changed. WHY should leave them alone.</p></div>
            </div>
            <div className="stats">
              <div><b>{real.extraction.assumptions}</b><span>assumptions recovered from real prose</span></div>
              <div><b>{real.extraction.dropped_ungrounded}</b><span>rejected because the quote wasn't verbatim</span></div>
              <div className="hero-stat"><b>{targets.filter((r) => r.flagged && r.cites_changing_record).length}/{targets.length}</b><span>changed decisions flagged, citing the right record</span></div>
              <div><b>{controls.filter((r) => !r.flagged).length}/{controls.length}</b><span>untouched decisions left alone</span></div>
            </div>
            <div className="tablewrap">
              <table className="dt">
                <thead><tr><th>Decision</th><th>What GOV.UK actually did later</th><th>WHY said</th><th>Records WHY cited</th><th>Hindsight reflect said</th></tr></thead>
                <tbody>{real.rows.map((r) => (
                  <tr key={r.decision}>
                    <td><b>{r.decision}</b> {r.title}<div className="muted small">{r.date}</div></td>
                    <td>{r.history}</td>
                    <td><span className={`vpill v-${r.verdict}`}>{VSHORT[r.verdict] ?? r.verdict}</span></td>
                    <td className="small">{r.cited.map((c) => <span key={c} className={`tagid ${c === r.changed_by ? "pick" : ""}`}>{c}</span>)}</td>
                    <td>{r.reflect?.verdict ? <span className={`vpill v-${r.reflect.verdict}`}>{VSHORT[r.reflect.verdict] ?? r.reflect.verdict}</span> : "—"}
                      {r.changed_later && r.reflect?.verdict && <div className="muted small">{r.reflect.mentions_changing_record ? "names" : "does not name"} {r.changed_by}</div>}</td>
                  </tr>))}</tbody>
              </table>
            </div>
            <p className="muted small">Highlighted citation: the record that actually replaced the decision. Judge model {real.model} (the same model as the benchmark).</p>

            {d.real_runs && (
              <>
                <h3>Does it hold across runs? Not yet.</h3>
                <p className="small">Same 8 decisions, same extracted assumptions; only the judging model or code version changes. The verdicts swing a lot, so we report every run rather than the best one.</p>
                <div className="tablewrap">
                  <table className="dt">
                    <thead><tr><th>Run</th><th>Changed decisions flagged, citing the right record</th><th>Untouched decisions left alone</th></tr></thead>
                    <tbody>{d.real_runs.runs.map((r) => (
                      <tr key={r.label} className={r.model === real.model && r.code === "current" ? "hl" : ""}>
                        <td><b className="who">{r.label}</b> <span className="code">{r.model}</span></td>
                        <td>{r.cited}/{r.targets}</td><td>{r.left_alone}/{r.controls}</td>
                      </tr>))}</tbody>
                  </table>
                </div>
                <p className="small"><b>Honest reading.</b> Extraction transfers to real prose: {real.extraction.assumptions} assumptions from someone else's ADRs, only {real.extraction.dropped_ungrounded} rejected for not being verbatim. Judging a real, sparse decision history is the open problem. With 8 decisions, one model is cautious (misses reversals, never cries wolf) and another is eager (finds reversals, flags untouched decisions too). This pilot can't yet separate WHY from the model it runs on.</p>
              </>
            )}
          </>
        )}
      </section>

      {/* 5 ---------------------------------------------------------------- */}
      <section className="card" id="ev-perf">
        <h2>5 · Speed and cost</h2>
        {!perf ? <p className="muted">Not run yet: <code>python -m evaluation.run_perf</code>.</p> : (
          <>
            {perf.end_to_end && stage && (
              <>
                <div className="stats">
                  <div className="hero-stat"><b>{(stage.total.p50 / 1000).toFixed(1)} s</b><span>typical time from question to verdict</span></div>
                  <div><b>{perf.end_to_end.llm_calls_per_question}</b><span>LLM call per question</span></div>
                  <div><b>{Math.round(perf.end_to_end.tokens_per_question.mean).toLocaleString()}</b><span>LLM tokens per question</span></div>
                  <div><b>{perf.end_to_end.hindsight_recalls_per_question}</b><span>Hindsight recalls per question</span></div>
                </div>
                <h3>Where the time goes · {perf.end_to_end.n} questions</h3>
                <div className="tablewrap">
                  <table className="dt">
                    <thead><tr><th>Step</th><th>Who</th><th>Typical (median)</th><th>Slowest 5% (p95)</th></tr></thead>
                    <tbody>
                      {([["recall_precedent", "Find the past decision", "Hindsight"], ["recall_changes", "Find what changed since (one recall per assumption, in parallel)", "Hindsight"],
                        ["judge", "Judge each assumption", "LLM"], ["total", "Total, including date filter, citation check and verdict rule", ""]] as const).map(([k, label, who]) => stage[k] && (
                        <tr key={k} className={k === "total" ? "hl" : ""}><td>{label}</td><td className="muted">{who}</td><td>{(stage[k].p50 / 1000).toFixed(2)} s</td><td>{(stage[k].p95 / 1000).toFixed(2)} s</td></tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <p className="muted small">The slow tail comes from occasional slow Hindsight Cloud recalls, not from the model.</p>
              </>
            )}
            <h3>Memory under load · Hindsight recall only, no LLM</h3>
            <div className="tablewrap">
              <table className="dt">
                <thead><tr><th>Requests at once</th><th>Typical latency</th><th>Slowest 5%</th><th>Recalls per second</th></tr></thead>
                <tbody>{perf.memory_layer.map((r) => <tr key={r.concurrency}><td>{r.concurrency}</td><td>{Math.round(r.latency_ms.p50)} ms</td><td>{Math.round(r.latency_ms.p95)} ms</td><td><b>{r.throughput_per_s}</b></td></tr>)}</tbody>
              </table>
            </div>
            <p className="muted small">Throughput grows almost in step with concurrency, so memory isn't the bottleneck. On a free LLM tier the limit is the provider's {perf.derived?.limit_text ?? "rate limit"}, about {perf.derived?.max_questions_per_minute ?? perf.derived?.max_questions_per_minute_under_tpm} questions a minute. Model {perf.model}, measured {perf.run_at.slice(0, 10)}.</p>
          </>
        )}
      </section>

      <section className="card">
        <h2>Caveats</h2>
        <ul>
          <li>The Keelwright company, its records and the answer key were written by us. That's why the GOV.UK track exists.</li>
          <li>{cases.length} questions, one run per contestant: a pilot. Intervals and significance tests are shown so nobody over-reads small gaps.</li>
          <li>Hindsight <code>reflect</code> runs on Hindsight's own model, so that comparison isn't same-model.</li>
          <li>The GOV.UK track ran on {real?.model ?? "another model"}, before the switch to the current provider.</li>
        </ul>
      </section>
    </main>
  );
}
