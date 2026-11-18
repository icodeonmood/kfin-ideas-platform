/**
 * A-API.draft-stream as pure steps (L-DRAFT, BLD-C075): from the worker's live view of one run, the events not yet
 * sent, in the contract's order: `run` (the parts being built and the means the loader uses), `hidden` before any
 * part, one `part` per part as it lands, then `receipt` and `done`. The route polls; this decides what to send.
 */
import type { DraftStreamEvent } from "@/lib/contracts/api";
import type { DraftPartKey } from "@/lib/contracts/enums";

export interface LivePartView {
  state: string;
  value: unknown;
  why: string | null;
  source_quote: string | null;
}
export interface LiveRunView {
  id: string;
  state: string;
  parts: { key: string; mean_ms: number }[];
  part_ms: Record<string, number>;
  receipt: string[];
  suggestions: string[];
  ready: boolean;
  hidden: { spans: unknown[]; details: unknown[] };
}

export interface Sent {
  runId: string;
  run: boolean;
  hidden: boolean;
  parts: Set<string>;
  done: boolean;
}

export const freshSent = (runId: string): Sent => ({
  runId,
  run: false,
  hidden: false,
  parts: new Set(),
  done: false,
});

/** The value a part event carries: the title rides with its summary (E-ENUMS.draft has no separate summary key). */
export function partValue(key: string, value: unknown): unknown {
  if (key === "title") {
    const v = (value && typeof value === "object" ? value : {}) as { title?: unknown; summary?: unknown };
    return { title: v.title ?? null, summary: v.summary ?? null };
  }
  return value ?? null;
}

function partEvent(key: string, took: number, part: LivePartView | undefined): DraftStreamEvent {
  return {
    event: "part",
    data: {
      key: key as DraftPartKey,
      state: part?.state === "failed" ? "failed" : "filled",
      value: partValue(key, part?.value),
      ...(part?.why ? { why: part.why } : {}),
      ...(part?.source_quote ? { source_quote: part.source_quote } : {}),
      took_ms: took,
    },
  };
}

/** The events to send now for this run, and the record of what has been sent (mutated). */
export function nextEvents(
  run: LiveRunView,
  parts: Record<string, LivePartView> | undefined,
  sent: Sent,
): DraftStreamEvent[] {
  if (sent.done || run.id !== sent.runId) return [];
  const out: DraftStreamEvent[] = [];
  if (!sent.run) {
    out.push({
      event: "run",
      data: {
        run_id: run.id,
        parts: run.parts.map((p) => ({ key: p.key as DraftPartKey, mean_ms: p.mean_ms })),
      },
    });
    sent.run = true;
  }
  if (!sent.hidden) {
    out.push({ event: "hidden", data: run.hidden as Extract<DraftStreamEvent, { event: "hidden" }>["data"] });
    sent.hidden = true;
  }
  const finished = run.state !== "running";
  for (const { key } of run.parts) {
    if (sent.parts.has(key)) continue;
    const took = run.part_ms[key];
    if (took === undefined && !finished) continue; // still building
    out.push(partEvent(key, took ?? 0, parts?.[key]));
    sent.parts.add(key);
  }
  if (finished) {
    out.push({ event: "receipt", data: { lines: run.receipt, suggestions: run.suggestions } });
    out.push({ event: "done", data: { ready: run.ready } });
    sent.done = true;
  }
  return out;
}

export function sse(e: DraftStreamEvent): string {
  return `event: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`;
}
