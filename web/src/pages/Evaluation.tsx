import { useEffect, useState } from "react";

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
}
interface Real {
  model: string; as_of: string;
  extraction: { adrs: number; assumptions: number; critical: number; dropped_ungrounded: number };
  rows: { decision: string; title: string; date: string; changed_later: boolean; changed_by: string | null; history: string;
    verdict: string; flagged: boolean; cites_changing_record: boolean; cited: string[];
    reflect?: { verdict?: string; flagged?: boolean; mentions_changing_record?: boolean } }[];
}
interface Stat { n: number; p50: number; p95: number; mean: number; max: number }
interface Perf {
  run_at: string; model: string;
  memory_layer: { concurrency: number; latency_ms: Stat; throughput_per_s: number }[];
  end_to_end: { n: number; stages_ms: Record<string, Stat>; tokens_per_question: Stat; prompt_tokens_mean: number;
    completion_tokens_mean: number; llm_calls_per_question: number; hindsight_recalls_per_question: number } | null;
  derived: { llm_tpm_limit?: number; tokens_per_question_mean: number; max_questions_per_minute_under_tpm?: number;
    max_questions_per_minute?: number; limit_text?: string; note: string } | null;
}

const COND: Record<string, string> = {
  C: "WHY (assumptions extracted from prose)",
  "C-oracle": "WHY with hand-labelled assumptions",
  "C-1stage": "WHY, single question-keyed recall (ablation)",
  B3: "Hindsight reflect (structured output)",
  B2: "Hindsight recall → LLM, no decision structure",
  A: "Same LLM, no memory",
  "ALWAYS-R": "Always answers RECONSIDER (trivial)",
};
const pct = (f?: Frac) => (f && f.n ? `${Math.round((f.rate ?? 0) * 100)}%` : "—");
const frac = (f?: Frac) => (f && f.n ? `${f.x}/${f.n}` : "—");

function Bar({ f, good = "high" }: { f?: Frac; good?: "high" | "low" }) {
  if (!f || !f.n) return <span className="muted">—</span>;
  const r = f.rate ?? 0;
  return (
    <div className="mbar" title={`${f.x}/${f.n} · 95% CI ${f.ci95[0]}–${f.ci95[1]}`}>
      <div className={`mfill ${good === "low" ? "bad" : ""}`} style={{ width: `${r * 100}%` }} />
      <div className="mci" style={{ left: `${f.ci95[0] * 100}%`, width: `${(f.ci95[1] - f.ci95[0]) * 100}%` }} />
      <span className="mlabel">{pct(f)} <span className="muted">({frac(f)})</span></span>
    </div>
  );
}

export default function EvaluationPage() {
  const [d, setD] = useState<{ benchmark: Bench | null; real: Real | null; perf: Perf | null } | null>(null);
  const [split, setSplit] = useState<"all" | "test_split">("all");
  useEffect(() => { fetch("/api/evaluation").then((r) => r.json()).then(setD); }, []);
  if (!d) return <main className="page"><p className="muted">Loading…</p></main>;
  const b = d.benchmark, real = d.real, perf = d.perf;
  const conds = b ? Object.keys(COND).filter((c) => b.conditions[c]) : [];
  const m = (c: string) => b?.conditions[c]?.[split];
  const targets = real?.rows.filter((r) => r.changed_later) ?? [];
  const controls = real?.rows.filter((r) => !r.changed_later) ?? [];

  return (
    <main className="page">
      <section className="card">
        <div className="eyebrow">Evaluation</div>
        <h1>Does memory change the decision — correctly?</h1>
        <p className="lead">We don't score whether the right document was retrieved. We score whether the agent's <i>decision</i> changes correctly when the conditions behind a past decision change. Every number below is read from a result file produced by a script in <code>evaluation/</code>; nothing is typed in by hand.</p>
        <div className="stats">
          {m("C") && <div className="hero-stat"><b>{pct(m("C")!.verdict_accuracy)}</b><span>WHY verdict accuracy</span></div>}
          {m("A") && <div><b>{pct(m("A")!.verdict_accuracy)}</b><span>same model, no memory</span></div>}
          {m("A") && <div><b>{pct(m("A")!.false_reuse_rate)}</b><span>stale decisions reused without memory</span></div>}
          {real && <div><b>{targets.filter((r) => r.flagged && r.cites_changing_record).length}/{targets.length}</b><span>real GOV.UK reversals caught with the right citation</span></div>}
          {perf?.end_to_end && <div><b>{(perf.end_to_end.stages_ms.total.p50 / 1000).toFixed(1)} s</b><span>median time to a verdict</span></div>}
        </div>
      </section>

      <section className="card">
        <h2>1 · Controlled benchmark <span className="muted small">— {b ? `${b.n_cases} questions over the Keelwright memory` : "not run yet"}</span></h2>
        {b && (
          <>
            <div className="row">
              <span className="muted small">Assumption extraction <code>{b.extraction_model}</code> · report built {b.run_at}</span>
              <span className="seg">
                <button className={split === "all" ? "on" : ""} onClick={() => setSplit("all")}>all cases</button>
                <button className={split === "test_split" ? "on" : ""} onClick={() => setSplit("test_split")}>test split only</button>
              </span>
            </div>
            {b.note && <div className="status small">{b.note}</div>}
            {Object.keys(b.incomplete || {}).length > 0 && (
              <div className="status small"><b>Pending</b> (quota-limited; excluded until every case has run): {Object.entries(b.incomplete).map(([k, v]) => `${k} — ${COND[k] ?? k} (${v})`).join("; ")}</div>
            )}
            <div className="tablewrap">
              <table className="dt metrics">
                <thead><tr><th>Condition</th><th>Verdict accuracy</th><th>False reuse ↓<br /><span className="muted">stale decision reused</span></th><th>False reconsider ↓<br /><span className="muted">crying wolf</span></th><th>Precedent hit@1</th><th>Premise-laden</th><th>Flip</th></tr></thead>
                <tbody>
                  {conds.map((c) => (
                    <tr key={c} className={c === "C" ? "hl" : ""}>
                      <td><b>{c}</b><div className="muted small">{COND[c]}</div>
                        {b.models?.[c] && <div className="muted small"><code>{b.models[c].join(", ")}</code></div>}</td>
                      <td><Bar f={m(c)?.verdict_accuracy} /></td>
                      <td><Bar f={m(c)?.false_reuse_rate} good="low" /></td>
                      <td><Bar f={m(c)?.false_reconsider_rate} good="low" /></td>
                      <td>{frac(m(c)?.["precedent_hit@1"])}</td>
                      <td>{frac(m(c)?.premise_accuracy)}</td>
                      <td>{frac(m(c)?.flip_accuracy)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="muted small">Bars show the rate; the grey band is the Wilson 95% interval. Pilot scale: one run per condition. Benchmark runs are paced to the free-tier request limit, so see section 3 for latency.</p>
            {Object.keys(b.mcnemar_vs_C || {}).length > 0 && (
              <details className="more"><summary>Paired significance vs WHY (exact McNemar)</summary>
                <table className="dt"><thead><tr><th>vs</th><th>other right, WHY wrong</th><th>WHY right, other wrong</th><th>p</th></tr></thead>
                  <tbody>{Object.entries(b.mcnemar_vs_C).map(([k, v]) => <tr key={k}><td>{k}</td><td>{v.other_right_C_wrong}</td><td>{v.C_right_other_wrong}</td><td>{v.p}</td></tr>)}</tbody></table>
              </details>
            )}
            {b.tripwire && <p><b>Tripwire</b> (a change is recorded; which past decisions does it break?): precision <b>{b.tripwire.precision}</b>, recall <b>{b.tripwire.recall}</b> — {b.tripwire.tp} correct alerts of {b.tripwire.predicted} raised, {b.tripwire.gold} expected.</p>}
          </>
        )}
      </section>

      <section className="card">
        <h2>2 · Real decisions: GOV.UK, 2017–2022</h2>
        {!real ? <p className="muted">Not run yet.</p> : (
          <>
            <p>38 architecture decision records published by GOV.UK (<a href="https://github.com/alphagov/govuk-aws" target="_blank" rel="noreferrer">alphagov/govuk-aws</a>, MIT). Each decision is evaluated as of {real.as_of} using only <i>later</i> records as evidence. Ground truth is GOV.UK's own history; "superseded by" notes added to old records afterwards are stripped so the answer can't leak.</p>
            <div className="stats">
              <div><b>{real.extraction.assumptions}</b><span>assumptions recovered from {real.extraction.adrs} real ADRs</span></div>
              <div><b>{real.extraction.dropped_ungrounded}</b><span>dropped: quote not verbatim in source</span></div>
              <div><b>{targets.filter((r) => r.flagged).length}/{targets.length}</b><span>later-changed decisions flagged</span></div>
              <div><b>{targets.filter((r) => r.cites_changing_record).length}/{targets.length}</b><span>citing the record that changed them</span></div>
              <div><b>{controls.filter((r) => !r.flagged).length}/{controls.length}</b><span>untouched decisions left alone</span></div>
            </div>
            <div className="tablewrap">
              <table className="dt">
                <thead><tr><th>Decision</th><th>What actually happened</th><th>WHY</th><th>Cited</th><th>Hindsight reflect</th></tr></thead>
                <tbody>{real.rows.map((r) => (
                  <tr key={r.decision}>
                    <td><b>{r.decision}</b> {r.title}<div className="muted small">{r.date}</div></td>
                    <td>{r.history}</td>
                    <td><span className={`vpill v-${r.verdict}`}>{r.verdict}</span></td>
                    <td className="small">{r.cited.map((c) => <span key={c} className={`tagid ${c === r.changed_by ? "pick" : ""}`}>{c}</span>)}</td>
                    <td>{r.reflect?.verdict ? <span className={`vpill v-${r.reflect.verdict}`}>{r.reflect.verdict}</span> : "—"}
                      {r.changed_later && r.reflect?.verdict && <div className="muted small">{r.reflect.mentions_changing_record ? "names" : "does not name"} {r.changed_by}</div>}</td>
                  </tr>))}</tbody>
              </table>
            </div>
            <p className="muted small">Model {real.model}. 3 targets and 5 controls: a pilot, not a benchmark.</p>
          </>
        )}
      </section>

      <section className="card">
        <h2>3 · Performance: latency, throughput, cost per question</h2>
        {!perf ? <p className="muted">Not run yet: <code>python -m evaluation.run_perf</code>.</p> : (
          <>
            <div className="grid2">
              <div>
                <h3>Memory layer (Hindsight recall, no LLM)</h3>
                <table className="dt"><thead><tr><th>Concurrency</th><th>p50</th><th>p95</th><th>Throughput</th></tr></thead>
                  <tbody>{perf.memory_layer.map((r) => <tr key={r.concurrency}><td>{r.concurrency}</td><td>{r.latency_ms.p50} ms</td><td>{r.latency_ms.p95} ms</td><td><b>{r.throughput_per_s}</b> recalls/s</td></tr>)}</tbody></table>
              </div>
              {perf.end_to_end && (
                <div>
                  <h3>End to end (full pipeline, {perf.end_to_end.n} questions)</h3>
                  <table className="dt"><thead><tr><th>Stage</th><th>p50</th><th>p95</th></tr></thead>
                    <tbody>{Object.entries(perf.end_to_end.stages_ms).map(([k, s]) => <tr key={k} className={k === "total" ? "hl" : ""}><td>{k.replace("_", " ")}</td><td>{s.p50} ms</td><td>{s.p95} ms</td></tr>)}</tbody></table>
                </div>
              )}
            </div>
            {perf.end_to_end && (
              <div className="stats">
                <div><b>{perf.end_to_end.hindsight_recalls_per_question}</b><span>Hindsight recalls per question</span></div>
                <div><b>{perf.end_to_end.llm_calls_per_question}</b><span>LLM calls per question</span></div>
                <div><b>{Math.round(perf.end_to_end.tokens_per_question.mean)}</b><span>LLM tokens per question ({perf.end_to_end.prompt_tokens_mean} in / {perf.end_to_end.completion_tokens_mean} out)</span></div>
                {perf.derived && <div><b>{perf.derived.max_questions_per_minute ?? perf.derived.max_questions_per_minute_under_tpm}</b><span>questions/min at a {perf.derived.limit_text ?? `${perf.derived.llm_tpm_limit?.toLocaleString()} tokens/min LLM limit`}</span></div>}
              </div>
            )}
            {perf.derived && <p className="muted small">{perf.derived.note} Model {perf.model}, measured {perf.run_at}.</p>}
          </>
        )}
      </section>

      <section className="card">
        <h2>How to read these numbers</h2>
        <ul>
          <li>The Keelwright data and its labels were written by us. Demo questions used while developing prompts are marked <i>dev</i>; switch to "test split only" to exclude them.</li>
          <li>One run per condition, 26 questions: differences come with 95% intervals and an exact McNemar test, and most are not significant at this scale.</li>
          <li>The single-recall ablation performs as well as two-stage recall on this small corpus. The contribution we claim is the decision-state layer (assumptions, date admissibility, grounding, rule-based verdicts), not a better retriever.</li>
          <li>Hindsight <code>reflect</code> uses Hindsight's own model, so it is not a same-model comparison.</li>
        </ul>
      </section>
    </main>
  );
}
