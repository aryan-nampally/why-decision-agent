// Mirrors src/schema.py (API contracts).

export type Verdict = "REUSE" | "ADAPT" | "RECONSIDER" | "INSUFFICIENT_EVIDENCE";
export type Status = "HOLDS" | "BROKEN" | "UNKNOWN";
export type Basis = "confirmed" | "no_change_recorded" | "contradicted" | "ambiguous";

export interface Assumption {
  id: string;
  statement: string;
  critical: boolean;
  quote: string;
  origin: string;
}

export interface Decision {
  id: string;
  title: string;
  date: string;
  team: string;
  authors: string[];
  status: "accepted" | "superseded" | "deprecated";
  context: string;
  options: string[];
  decision: string;
  rationale: string;
  assumptions: Assumption[];
  supersedes: string | null;
  superseded_by: string | null;
  source_ref: string;
}

export interface AssumptionCheck {
  assumption_id: string;
  statement: string;
  critical: boolean;
  quote: string;
  status: Status;
  basis: Basis;
  explanation: string;
  evidence_ids: string[];
}

export interface EvidenceItem {
  id: string;
  kind: string;
  date: string;
  title: string;
  detail: string;
  source_ref: string;
}

export interface MemoryHit {
  stage: string;
  text: string;
  type: string | null;
  document_id: string | null;
  kind: string | null;
  occurred: string | null;
  score: number | null;
}

export interface Candidate {
  id: string;
  title: string;
  score: number;
}

export interface AskResponse {
  verdict: Verdict;
  headline: string;
  recommendation: string;
  decision: Decision | null;
  decision_age: string | null;
  precedent_failed: boolean;
  failure_evidence: string[];
  health: number | null;
  assumption_checks: AssumptionCheck[];
  evidence: EvidenceItem[];
  candidates: Candidate[];
  ambiguous: boolean;
  memory_hits: MemoryHit[];
  warnings: string[];
  timings_ms: Record<string, number>;
}

export interface StatelessResponse {
  answer: string;
  verdict: string;
  timings_ms: Record<string, number>;
}

export interface TripwireAlert {
  decision_id: string;
  decision_title: string;
  decision_date: string;
  assumption_id: string;
  statement: string;
  critical: boolean;
  explanation: string;
}

export interface SignalResponse {
  signal: { id: string; title: string; date: string };
  alerts: TripwireAlert[];
  scanned: string[];
  timings_ms: Record<string, number>;
}

export interface TimelineItem {
  id: string;
  kind: "adr" | "postmortem" | "signal";
  date: string;
  title: string;
  status: string | null;
}

export interface HoldbackDoc {
  id: string;
  title: string;
  date: string;
  ingested: boolean;
}
