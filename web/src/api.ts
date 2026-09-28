import type { AskResponse, Decision, HoldbackDoc, SignalResponse, StatelessResponse, TimelineItem } from "./types";

async function call<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, body === undefined ? undefined : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((data as { detail?: string }).detail || `HTTP ${res.status}`);
  return data as T;
}

export interface StageEvent {
  stage: string;
  actor?: "hindsight" | "llm" | "code" | "store";
  status?: "running" | "done";
  [key: string]: unknown;
}

/** POST /api/ask/stream: calls onEvent for every pipeline stage as it happens, resolves with the final answer. */
async function askStream(question: string, current_context: string, onEvent: (e: StageEvent) => void): Promise<AskResponse> {
  const res = await fetch("/api/ask/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, current_context }),
  });
  if (!res.ok || !res.body) {
    const data = await res.json().catch(() => ({}));
    throw new Error((data as { detail?: string }).detail || `HTTP ${res.status}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let cut: number;
    while ((cut = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, cut);
      buffer = buffer.slice(cut + 2);
      if (!chunk.startsWith("data: ")) continue;
      const e = JSON.parse(chunk.slice(6)) as StageEvent;
      if (e.stage === "result") return e.data as AskResponse;
      if (e.stage === "error") throw new Error(String(e.detail));
      onEvent(e);
    }
  }
  throw new Error("stream ended without a result");
}

export const api = {
  askStream,
  health: () => call<{ hindsight: boolean; records: number }>("/health"),
  ask: (question: string, current_context: string) => call<AskResponse>("/api/ask", { question, current_context }),
  askStateless: (question: string, current_context: string) =>
    call<StatelessResponse>("/api/ask/stateless", { question, current_context }),
  signal: (title: string, detail: string) => call<SignalResponse>("/api/signals", { title, detail }),
  holdback: () => call<HoldbackDoc[]>("/api/holdback"),
  ingestHoldback: (id: string) => call<{ record: { id: string } }>(`/api/holdback/${id}`, {}),
  timeline: () => call<TimelineItem[]>("/api/timeline"),
  resetDemo: () => call<{ records: number }>("/api/demo/reset", {}),
  accept: (body: { question: string; title: string; decision: string; rationale: string; based_on: string | null; team: string }) =>
    call<Decision>("/api/decisions/accept", body),
};
