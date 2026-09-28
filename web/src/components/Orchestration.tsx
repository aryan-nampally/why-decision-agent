import type { StageEvent } from "../api";

type Actor = "hindsight" | "store" | "llm" | "code";

const STEPS: { stage: string; actor: Actor; title: string; what: string }[] = [
  { stage: "precedent", actor: "hindsight", title: "Recall the precedent", what: "Which past decision is this question about?" },
  { stage: "assumptions", actor: "store", title: "Load its assumptions", what: "What had to be true for that decision to be right?" },
  { stage: "changes", actor: "hindsight", title: "Recall what changed", what: "One recall per assumption: what happened since?" },
  { stage: "judge", actor: "llm", title: "Judge each assumption", what: "HOLDS, BROKEN or UNKNOWN, citing evidence IDs" },
  { stage: "ground", actor: "code", title: "Check the citations", what: "Remove evidence the model was never given" },
  { stage: "verdict", actor: "code", title: "Apply the verdict rule", what: "Deterministic rules decide, not the model" },
];

const ACTOR: Record<Actor, string> = { hindsight: "Hindsight", store: "Record store", llm: "LLM", code: "Code" };

const ids = (v: unknown) => (Array.isArray(v) ? (v as string[]) : []);

function Detail({ e }: { e: StageEvent }) {
  switch (e.stage) {
    case "precedent": {
      const c = (e.candidates as { id: string; score: number }[]) ?? [];
      return (
        <div className="od">
          {String(e.facts)} facts recalled from <code>kind:adr</code> · scored by record:{" "}
          {c.map((x) => <span key={x.id} className={`tagid ${x.id === e.picked ? "pick" : ""}`}>{x.id} {x.score.toFixed(2)}</span>)}
          {e.picked ? <> → <b>{String(e.picked)}</b></> : <> → <b>no precedent</b></>}
        </div>
      );
    }
    case "assumptions": {
      const a = (e.assumptions as { id: string; statement: string; critical: boolean }[]) ?? [];
      return (
        <div className="od">
          <b>{String(e.decision)}</b> ({String(e.date)}) depended on {a.length} conditions recovered from its prose, each with a verbatim quote:
          <ul>{a.map((x) => <li key={x.id}><b>{x.id}</b>{x.critical && <span className="crit">CRITICAL</span>} {x.statement}</li>)}</ul>
        </div>
      );
    }
    case "changes": {
      const q = (e.queries as { for: string; facts: number; found: string[] }[]) ?? [];
      const filtered = ids(e.filtered_before_decision);
      return (
        <div className="od">
          {q.map((x) => (
            <div key={x.for} className="lane">
              <span className="lane-k">{x.for}</span>
              <span className="muted">{x.facts} facts →</span>{" "}
              {x.found.length ? x.found.map((id) => <span key={id} className="tagid">{id}</span>) : <span className="muted">nothing relevant</span>}
            </div>
          ))}
          {filtered.length > 0 && (
            <div className="lane filtered">
              <span className="lane-k">date filter</span>
              {filtered.map((id) => <span key={id} className="tagid strike">{id}</span>)}
              <span className="muted"> dated before {String(e.after)}, so part of the original context and not allowed to invalidate it</span>
            </div>
          )}
          {ids(e.failures).length > 0 && <div className="lane"><span className="lane-k">outcome</span> {ids(e.failures).join(", ")} records this approach failing</div>}
        </div>
      );
    }
    case "judge": {
      const st = (e.statuses as { id: string; status: string; evidence: string[] }[]) ?? [];
      return (
        <div className="od">
          {!e.ok && <div className="warnings">model call failed: every assumption set to UNKNOWN (fail-safe)</div>}
          {e.relevant === false && <div className="warnings">judge: this precedent does not address the question</div>}
          {st.map((x) => (
            <span key={x.id} className="judged"><span className={`pill s-${x.status}`}>{x.id} {x.status}</span>
              {x.evidence.length > 0 && <span className="muted"> ← {x.evidence.join(", ")}</span>}</span>
          ))}
        </div>
      );
    }
    case "ground": {
      const ch = ids(e.changes);
      return <div className="od">{ch.length ? ch.map((c) => <div key={c} className="warnings">✂ {c}</div>)
        : <span>all citations point to evidence that was actually provided ({String(e.provided)} items incl. your context)</span>}</div>;
    }
    case "verdict":
      return <div className="od rule">{String(e.rule)}</div>;
    default:
      return null;
  }
}

export function Orchestration({ events, live }: { events: StageEvent[]; live: boolean }) {
  const latest = new Map<string, StageEvent>();
  for (const e of events) latest.set(e.stage, e);
  const reached = STEPS.filter((s) => latest.has(s.stage));
  const lastIdx = reached.length ? STEPS.indexOf(reached[reached.length - 1]) : -1;
  const stopped = latest.get("verdict")?.status === "done";
  const states = STEPS.map((s, i) => {
    const e = latest.get(s.stage);
    return e?.status === "done" ? "done" : e ? "run" : !e && stopped ? "skip" : i === lastIdx + 1 && live ? "next" : "wait";
  });
  return (
    <div className="card orch">
      <h3>Agent orchestration {live ? <span className="live">● LIVE</span> : <span className="muted">— how WHY reached this answer</span>}</h3>
      <div className="progress">{states.map((st, i) => <span key={i} className={st} />)}</div>
      <div className="actors">
        {(Object.keys(ACTOR) as Actor[]).map((a) => <span key={a}><i className={`a-${a}`} />{ACTOR[a]}</span>)}
      </div>
      <ol className="steps-v">
        {STEPS.map((s, i) => {
          const e = latest.get(s.stage);
          const state = states[i];
          return (
            <li key={s.stage} className={`ostep ${state}`}>
              <div className="ohead">
                <span className={`actor a-${s.actor}`}>{ACTOR[s.actor]}</span>
                <b>{i + 1}. {s.title}</b>
                <span className="muted small"> — {s.what}</span>
                <span className="oms">{state === "done" && e?.ms != null ? `${e.ms} ms` : state === "run" ? "running…" : state === "skip" ? "not needed" : ""}</span>
              </div>
              {e?.status === "running" && e.detail != null && <div className="od muted">{String(e.detail)}</div>}
              {e?.status === "done" && <Detail e={e} />}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
