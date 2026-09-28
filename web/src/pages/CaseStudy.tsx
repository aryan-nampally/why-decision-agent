import { useEffect, useState } from "react";

interface Profile {
  name: string; fictional: boolean; tagline: string; profile: [string, string][];
  teams: { name: string; people: string[]; owns: string }[]; problem: string;
  story: { date: string; kind: string; text: string }[];
  dataset: { adrs: number; postmortems: number; change_notes: number; held_out_for_demo: string[]; distractors: string; construction: string[] };
}
interface Health {
  generated_at: string; as_of: string; model: string;
  decisions: { id: string; title: string; date: string; team: string; verdict: string; health: number | null; age: string;
    headline: string; broken: { id: string; statement: string; critical: boolean; evidence: string[]; explanation: string }[];
    failures: string[]; assumptions: number }[];
}
interface Rec { id: string; kind: string; date: string; title: string; who: string; status: string | null; assumptions: number }

export default function CaseStudyPage() {
  const [data, setData] = useState<{ profile: Profile | null; health: Health | null; records: Rec[] } | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { fetch("/api/casestudy").then((r) => r.json()).then(setData).catch((e) => setErr(String(e))); }, []);
  if (err) return <main className="page"><div className="status err">{err}</div></main>;
  if (!data?.profile) return <main className="page"><p className="muted">Loading…</p></main>;
  const p = data.profile;
  const count = (k: string) => data.records.filter((r) => r.kind === k).length;
  const decayed = data.health?.decisions.filter((d) => d.verdict !== "REUSE") ?? [];

  return (
    <main className="page">
      <section className="hero card">
        <div className="eyebrow">Case study {p.fictional && <span className="badge">fictional company · synthetic data</span>}</div>
        <h1>{p.name}</h1>
        <p className="lead">{p.tagline}</p>
        <div className="grid2">
          <table className="kvt"><tbody>{p.profile.map(([k, v]) => <tr key={k}><th>{k}</th><td>{v}</td></tr>)}</tbody></table>
          <div>
            <h3>Teams</h3>
            {p.teams.map((t) => <div key={t.name} className="team"><b>{t.name}</b> <span className="muted">— {t.people.join(", ")} · owns {t.owns}</span></div>)}
          </div>
        </div>
      </section>

      <section className="card">
        <h2>The problem</h2>
        <p>{p.problem}</p>
      </section>

      <section className="card">
        <h2>Three years in one timeline</h2>
        <p className="muted small">Decisions, the changes that quietly undermined them, and the incidents that followed. No change note names the decision it breaks.</p>
        <ol className="story">
          {p.story.map((s, i) => (
            <li key={i} className={`k-${s.kind}`}>
              <span className="sdate">{s.date}</span><span className={`skind k-${s.kind}`}>{s.kind}</span><span>{s.text}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="card">
        <h2>Decision health board {data.health && <span className="muted small">— WHY evaluated every active decision as of {data.health.as_of}</span>}</h2>
        {!data.health ? <p className="muted">Not generated yet: run <code>python -m scripts.casestudy_health</code>.</p> : (
          <>
            <p><b>{decayed.length} of {data.health.decisions.length}</b> active decisions no longer rest on the conditions they were made under. Nobody asked a question: this is what WHY finds when it checks the whole decision log.</p>
            <div className="board">
              {[...data.health.decisions].sort((a, b) => (a.health ?? 1) - (b.health ?? 1)).map((d) => (
                <div key={d.id} className={`hcard v-${d.verdict}`}>
                  <div className="hhead"><b>{d.id}</b> <span className={`vpill v-${d.verdict}`}>{d.verdict.replace("_", " ")}</span></div>
                  <div className="htitle">{d.title}</div>
                  <div className="muted small">{d.team} · {d.date} ({d.age})</div>
                  {d.health != null && <div className="bar mini"><div className="fill" style={{ width: `${d.health * 100}%` }} /></div>}
                  {d.broken.map((b) => (
                    <div key={b.id} className="hbroken">{b.statement}{b.critical && <span className="crit">CRITICAL</span>}
                      <span className="muted"> ← {b.evidence.join(", ")}</span></div>
                  ))}
                  {d.failures.length > 0 && <div className="hbroken">recorded failure: {d.failures.join(", ")}</div>}
                  {d.verdict === "REUSE" && <div className="muted small">All {d.assumptions} assumptions still hold.</div>}
                </div>
              ))}
            </div>
            <p className="muted small">Generated {data.health.generated_at} with {data.health.model}; regenerate with <code>python -m scripts.casestudy_health</code>.</p>
          </>
        )}
      </section>

      <section className="card">
        <h2>The synthetic dataset</h2>
        <div className="stats">
          <div><b>{count("adr")}</b><span>decision records</span></div>
          <div><b>{count("postmortem")}</b><span>postmortems</span></div>
          <div><b>{count("signal")}</b><span>change notes</span></div>
          <div><b>{p.dataset.held_out_for_demo.length}</b><span>held out for the live demo</span></div>
          <div><b>{data.records.reduce((n, r) => n + r.assumptions, 0)}</b><span>grounded assumptions extracted</span></div>
        </div>
        <h3>How it was built</h3>
        <ul>{p.dataset.construction.map((c) => <li key={c}>{c}</li>)}<li>Noise: {p.dataset.distractors}.</li></ul>
        <details className="more">
          <summary>All {data.records.length} records in memory</summary>
          <div className="tablewrap">
            <table className="dt">
              <thead><tr><th>ID</th><th>Kind</th><th>Date</th><th>Title</th><th>By</th></tr></thead>
              <tbody>{data.records.map((r) => <tr key={r.id}><td>{r.id}</td><td><span className="kind">{r.kind}</span></td><td>{r.date}</td><td>{r.title}</td><td className="muted">{r.who}</td></tr>)}</tbody>
            </table>
          </div>
        </details>
      </section>
    </main>
  );
}
