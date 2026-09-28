import { useState } from "react";
import { api } from "../api";
import type { AskResponse, AssumptionCheck, Basis, Decision, EvidenceItem, StatelessResponse } from "../types";

const BASIS: Record<Basis, string> = {
  confirmed: "confirmed by later evidence",
  no_change_recorded: "no change recorded",
  contradicted: "contradicted",
  ambiguous: "evidence ambiguous",
};

function scrollToEvidence(id: string) {
  const el = document.getElementById(`ev-${id}`);
  if (!el) return;
  const details = el.closest("details");
  if (details) details.open = true;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.add("flash");
  setTimeout(() => el.classList.remove("flash"), 1500);
}

const MEANING: Record<string, string> = {
  REUSE: "its reasons still hold",
  ADAPT: "mostly holds; adjust it",
  RECONSIDER: "a load-bearing reason is gone",
  INSUFFICIENT_EVIDENCE: "nothing in memory to go on",
};

export function VerdictBanner({ r }: { r: AskResponse }) {
  const t = r.timings_ms;
  return (
    <div className={`banner v-${r.verdict}`}>
      <div className="stampbox">
        <div className="stamp">{r.verdict.replace("_", " ")}</div>
        <div className="stampnote">{MEANING[r.verdict]}</div>
      </div>
      <div className="h">
        {r.headline}
        <div className="meta">
          precedent recall {t.recall_precedent ?? "–"} ms · change recall {t.recall_changes ?? "–"} ms · judge {t.judge ?? "–"} ms
        </div>
      </div>
      {r.health != null && (
        <div className="ringbox">
          <div className="ring" style={{ ["--p" as string]: r.health }}><b>{Math.round(r.health * 100)}%</b></div>
          assumption health
        </div>
      )}
    </div>
  );
}

export function NoMemory({ off }: { off: StatelessResponse | "loading" | { error: string } }) {
  return (
    <div className="card offline">
      <h3>Same question, same model, no memory</h3>
      {off === "loading" ? <p className="muted small">Asking the same model with no memory…</p>
        : "error" in off ? <p className="warnings">{off.error}</p>
        : <>
            <span className={`vpill v-${off.verdict}`}>{off.verdict.replace("_", " ")}</span>
            <p className="said">“{off.answer}”</p>
            <p className="muted small">No record of past decisions, their assumptions, or what changed since.</p>
          </>}
    </div>
  );
}

export function Then({ r }: { r: AskResponse }) {
  const d = r.decision;
  if (!d) {
    return (
      <div className="card">
        <h3>Then <span className="muted">— what we decided and why</span></h3>
        <p className="muted">No precedent in memory.</p>
        {r.candidates.length > 0 && (
          <div className="kv">closest: {r.candidates.slice(0, 3).map((c) => `${c.id} ${c.title}`).join("; ")}</div>
        )}
      </div>
    );
  }
  const chosen = d.decision.toLowerCase().slice(0, 14);
  return (
    <div className="card">
      <h3>Then <span className="muted">— what we decided and why</span></h3>
      <span className="dec-id">{d.id}</span>
      <div className="dtitle">{d.title}</div>
      <div className="kv">
        {d.date} ({r.decision_age}) · {d.team} · {d.authors.join(", ")}
        {d.status !== "accepted" && <b> · {d.status}</b>}
      </div>
      <div className="decision">{d.decision}</div>
      {d.options.map((o) => (
        <div key={o} className={`opt ${o.toLowerCase().includes(chosen.slice(0, 10)) ? "" : "rej"}`}>{o}</div>
      ))}
      <details className="more">
        <summary>Context and rationale as written</summary>
        <p>{d.context}{"\n\n"}{d.rationale}</p>
      </details>
      <div className="kv">source: {d.source_ref}{r.ambiguous && <b> · ambiguous precedent</b>}</div>
      {r.candidates.length > 1 && (
        <div className="kv">other candidates: {r.candidates.slice(1, 4).map((c) => c.id).join(", ")}</div>
      )}
    </div>
  );
}

function Check({ c }: { c: AssumptionCheck }) {
  return (
    <div className="check">
      <div className="head">
        <span className={`pill s-${c.status}`}>{c.status}</span>
        <div>
          <span className="aid">{c.assumption_id}</span>{c.statement}
          {c.critical && <span className="crit">CRITICAL</span>}
          <div className="basis">{BASIS[c.basis]}</div>
        </div>
      </div>
      {c.quote && <div className="quote">“{c.quote}”</div>}
      {c.explanation && <div className="expl">{c.explanation}</div>}
      <div>
        {c.evidence_ids.map((id) => (
          <button key={id} type="button" className="ev-chip" onClick={() => scrollToEvidence(id)}>{id}</button>
        ))}
      </div>
    </div>
  );
}

export function Now({ r }: { r: AskResponse }) {
  return (
    <div className="card">
      <h3>Now <span className="muted">— do its assumptions still hold?</span></h3>
      {r.assumption_checks.length ? r.assumption_checks.map((c) => <Check key={c.assumption_id} c={c} />)
        : <p className="muted">Nothing to check.</p>}
    </div>
  );
}

function EvidenceRow({ e, cited }: { e: EvidenceItem; cited: boolean }) {
  return (
    <div className={`ev ${cited ? "cited" : ""}`} id={`ev-${e.id}`}>
      <span className="kind">{e.kind}</span> <span className="t">{e.id} · {e.title}</span> <span className="d">{e.date}</span>
      {cited && <div>{e.detail.slice(0, 420)}</div>}
    </div>
  );
}

export function Evidence({ r }: { r: AskResponse }) {
  const cited = new Set([...r.assumption_checks.flatMap((c) => c.evidence_ids), ...r.failure_evidence]);
  const sorted = [...r.evidence].sort((a, b) => b.date.localeCompare(a.date));
  const used = sorted.filter((e) => cited.has(e.id));
  const other = sorted.filter((e) => !cited.has(e.id));
  return (
    <div className="card">
      <h3>Evidence <span className="muted">— recorded after the decision</span></h3>
      {used.length ? used.map((e) => <EvidenceRow key={e.id} e={e} cited />)
        : <p className="muted small">No later record contradicts or confirms these assumptions.</p>}
      {other.length > 0 && (
        <details className="more">
          <summary>{other.length} other records were recalled but not relevant</summary>
          {other.map((e) => <EvidenceRow key={e.id} e={e} cited={false} />)}
        </details>
      )}
    </div>
  );
}

export function Recommendation({ r, question, onAccepted }: { r: AskResponse; question: string; onAccepted: (msg: string, id: string) => void }) {
  const [open, setOpen] = useState(false);
  const d: Decision | null = r.decision;
  const [title, setTitle] = useState("");
  const [decision, setDecision] = useState("");
  const [rationale, setRationale] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  function start() {
    setTitle(d ? `${d.title} (revisited)` : "");
    setDecision("");
    setRationale(r.recommendation);
    setOpen(true);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const rec = await api.accept({ question, title, decision: decision || title, rationale,
        based_on: d?.id ?? null, team: d?.team || "Platform" });
      setOpen(false);
      onAccepted(`${rec.id} retained. It supersedes ${d?.id ?? "nothing"} and carries ${rec.assumptions.length} assumptions of its own — tomorrow's tripwires.`, rec.id);
    } catch (x) {
      setErr((x as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card rec">
      <h3>Recommendation</h3>
      <p>{r.recommendation}</p>
      {r.warnings.length > 0 && <div className="warnings">{r.warnings.map((w) => <div key={w}>⚠ {w}</div>)}</div>}
      {d && !open && <button type="button" className="secondary" onClick={start}>Accept &amp; remember as a new decision</button>}
      {open && (
        <form className="accept" onSubmit={submit}>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title" />
          <textarea rows={2} value={decision} onChange={(e) => setDecision(e.target.value)} placeholder="Decision" autoFocus />
          <textarea rows={3} value={rationale} onChange={(e) => setRationale(e.target.value)} placeholder="Rationale" />
          <button type="submit" disabled={busy}>{busy ? "Retaining in Hindsight…" : "Retain in memory"}</button>
          {err && <div className="warnings">{err}</div>}
        </form>
      )}
    </div>
  );
}

export function Trace({ r }: { r: AskResponse }) {
  return (
    <details className="card trace">
      <summary>Memory trace — raw Hindsight recall <span className="muted">({r.memory_hits.length} facts)</span></summary>
      <div className="tablewrap">
        <table>
          <thead><tr><th>stage</th><th>record</th><th>type</th><th>score</th><th>fact</th></tr></thead>
          <tbody>
            {r.memory_hits.map((h, i) => (
              <tr key={i}>
                <td>{h.stage}</td><td>{h.document_id}</td><td>{h.type}</td>
                <td>{h.score == null ? "" : h.score.toFixed(2)}</td><td>{h.text.slice(0, 220)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
