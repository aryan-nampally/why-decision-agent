import { useState } from "react";
import { api } from "../api";
import type { HoldbackDoc, SignalResponse, TimelineItem } from "../types";

export function RecordChange({ onRetained }: { onRetained: (id: string) => void }) {
  const [title, setTitle] = useState("");
  const [detail, setDetail] = useState("");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<SignalResponse | null>(null);
  const [err, setErr] = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (title.trim().length < 3) return;
    setBusy(true);
    setErr("");
    setRes(null);
    try {
      const r = await api.signal(title.trim(), detail.trim());
      setRes(r);
      onRetained(r.signal.id);
    } catch (x) {
      setErr((x as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const decisions = res ? new Set(res.alerts.map((a) => a.decision_id)).size : 0;
  return (
    <div className="card side">
      <h3>Record a change</h3>
      <p className="muted small">Something changed in the org? WHY retains it and checks which past decisions it puts at risk.</p>
      <form onSubmit={submit}>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Consolidating all production into eu-central-1" />
        <textarea rows={2} value={detail} onChange={(e) => setDetail(e.target.value)} placeholder="Details (optional)" />
        <button type="submit" className="secondary" disabled={busy}>{busy ? "Retaining & scanning…" : "Retain & scan"}</button>
      </form>
      {err && <p className="warnings">{err}</p>}
      {res && (
        <>
          <p className="small"><b>{decisions ? `${decisions} past decision(s) depended on something this changes:` : "No past decision depends on this."}</b></p>
          {res.alerts.map((a) => (
            <div key={`${a.decision_id}/${a.assumption_id}`} className={`alert ${a.critical ? "" : "minor"}`}>
              <b>{a.decision_id}</b> {a.decision_title} <span className="muted">({a.decision_date})</span>
              <div>{a.assumption_id}{a.critical && <span className="crit">CRITICAL</span>}: {a.statement}</div>
              <div className="muted">{a.explanation}</div>
            </div>
          ))}
          <p className="muted small">scanned {res.scanned.join(", ")} · {res.timings_ms.total} ms</p>
        </>
      )}
    </div>
  );
}

export function NewDocuments({ docs, onIngested }: { docs: HoldbackDoc[]; onIngested: (id: string) => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState("");
  async function ingest(id: string) {
    setBusy(id);
    setErr("");
    try {
      await api.ingestHoldback(id);
      onIngested(id);
    } catch (x) {
      setErr((x as Error).message);
    } finally {
      setBusy(null);
    }
  }
  return (
    <div className="card">
      <h3>New documents</h3>
      {docs.length === 0 && <p className="muted small">None waiting.</p>}
      {docs.map((d) => (
        <div className="hb" key={d.id}>
          <span><b>{d.id}</b> {d.title} <span className="muted">({d.date})</span></span>
          {d.ingested ? <span className="muted small">in memory</span>
            : <button className="secondary" disabled={busy === d.id} onClick={() => ingest(d.id)}>{busy === d.id ? "Retaining…" : "Ingest"}</button>}
        </div>
      ))}
      {err && <p className="warnings">{err}</p>}
    </div>
  );
}

export function Timeline({ items, fresh, onReset }: { items: TimelineItem[]; fresh: Set<string>; onReset: () => void }) {
  const [arm, setArm] = useState(false);
  const [busy, setBusy] = useState(false);
  async function reset() {
    if (!arm) { setArm(true); setTimeout(() => setArm(false), 4000); return; }
    setBusy(true);
    try { await api.resetDemo(); onReset(); } finally { setBusy(false); setArm(false); }
  }
  return (
    <div className="card">
      <h3>Organizational memory <span className="muted">({items.length})</span></h3>
      <div className="timeline">
        {[...items].reverse().map((r) => (
          <div key={r.id} className={`tl ${fresh.has(r.id) ? "new" : ""} ${r.status === "superseded" ? "superseded" : ""}`}>
            <span className="date">{r.date}</span>
            <span><span className="kind">{r.kind}</span> <b>{r.id}</b> <span className="title">{r.title}</span></span>
          </div>
        ))}
      </div>
      <button type="button" className="linkbtn" disabled={busy} onClick={reset}>
        {busy ? "Rebuilding the memory bank (about 40 s)…" : arm ? "Click again to reset the demo memory" : "Reset demo memory"}
      </button>
    </div>
  );
}
