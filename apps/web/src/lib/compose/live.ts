/**
 * The draft panel's state as the stream builds it (S-04, S-04B; C-DRAFT-PANEL, C-DRAFT-LOADER; A-API.draft-stream;
 * BLD-C123). Starts from GET /api/drafts/:id; each event changes only what it names, so a part that did not change
 * keeps its value and never flickers (C-DRAFT-PANEL.behaviour/1, L-DRAFT.parts/4).
 */
import type {
  Draft,
  DraftPartKey,
  DraftStreamEvent,
  HiddenDetail,
  HiddenSpan,
  Part,
  SimilarMatch,
} from "@/lib/contracts";

import type { LoaderRun } from "./loader";

export type Parts = Draft["parts"];
export type SlotKey = "title" | "summary" | "often" | "who" | "value" | "area" | "similar";

export interface Live {
  parts: Parts;
  /** Parts being built again in the running run: their slots show a skeleton. */
  updating: DraftPartKey[];
  loader: LoaderRun | null;
  runId: string | null;
  running: boolean;
  receipt: string[];
  suggestions: string[];
  ready: boolean;
  hidden: HiddenDetail[];
  /** The newest `hidden` event's spans, in the run's message (S-04 underlines its box with them). */
  spans: HiddenSpan[] | null;
}

const EMPTY_PART = <T>(value: T): Part<T> => ({ state: "waiting", value });

export function emptyParts(): Parts {
  return {
    title: EMPTY_PART(""),
    summary: EMPTY_PART(""),
    often: EMPTY_PART<string | null>(null),
    who: EMPTY_PART<string[]>([]),
    value: EMPTY_PART([]),
    area: EMPTY_PART(""),
    similar: EMPTY_PART<SimilarMatch[]>([]),
  };
}

export function fromDraft(d: Draft | null): Live {
  const parts = d?.parts ? { ...emptyParts(), ...d.parts } : emptyParts();
  const running = d?.run?.state === "running";
  return {
    parts,
    updating: running
      ? (Object.keys(parts) as SlotKey[]).filter(
          (k): k is DraftPartKey => k !== "summary" && parts[k]?.state === "updating",
        )
      : [],
    loader: null,
    runId: d?.run?.id ?? null,
    running,
    receipt: d?.receipt ?? [],
    suggestions: d?.suggestions ?? [],
    ready: Boolean(d?.ready),
    hidden: d?.hidden ?? [],
    spans: null,
  };
}

/** A fresh read of the draft wins for everything it carries, except a run still being followed on the stream. */
export function withDraft(live: Live, d: Draft): Live {
  const next = fromDraft(d);
  if (live.running && live.runId && d.run?.id === live.runId && d.run.state === "running") {
    return { ...next, loader: live.loader, updating: live.updating, spans: live.spans };
  }
  // The run the loader showed has finished: keep it, so the strip can fill, say "All 6 parts are in" and fold.
  const same = live.loader && live.runId && d.run?.id === live.runId;
  return { ...next, loader: same ? live.loader : null, spans: live.spans };
}

/** One stream event. `now` is the page's clock (ms), for the loader. */
export function applyEvent(live: Live, e: DraftStreamEvent, now: number): Live {
  switch (e.event) {
    case "run": {
      const keys = e.data.parts.map((p) => p.key);
      const parts = { ...live.parts };
      for (const k of keys) {
        parts[k] = { ...parts[k], state: "updating" } as never;
        if (k === "title") parts.summary = { ...parts.summary, state: "updating" };
      }
      return {
        ...live,
        parts,
        updating: keys,
        loader: { parts: e.data.parts, startedAt: now, answered: {} },
        runId: e.data.run_id,
        running: true,
        ready: false,
      };
    }
    case "hidden":
      return { ...live, hidden: e.data.details ?? live.hidden, spans: e.data.spans ?? null };
    case "part": {
      const { key, state, value, why, source_quote } = e.data;
      const parts = { ...live.parts };
      const extra = { ...(why ? { why } : {}), ...(source_quote ? { source_quote } : {}) };
      if (key === "title") {
        const v = (value && typeof value === "object" ? value : {}) as { title?: unknown; summary?: unknown };
        parts.title = { state, value: typeof v.title === "string" ? v.title : "", ...extra };
        parts.summary = { state, value: typeof v.summary === "string" ? v.summary : "" };
      } else {
        parts[key] = { state, value: value ?? live.parts[key].value, ...extra } as never;
      }
      const loader = live.loader
        ? { ...live.loader, answered: { ...live.loader.answered, [key]: now } }
        : null;
      return { ...live, parts, loader, updating: live.updating.filter((k) => k !== key) };
    }
    case "receipt":
      return { ...live, receipt: e.data.lines ?? [], suggestions: e.data.suggestions ?? [] };
    case "done":
      return { ...live, running: false, updating: [], ready: Boolean(e.data.ready) };
    default:
      return live;
  }
}

/** A part to show as a value: filled, or changed by the person ("Your call"). */
export function hasValue(p: Part<unknown> | undefined): boolean {
  if (!p || (p.state !== "filled" && p.state !== "pinned")) return false;
  const v = p.value;
  if (v === null || v === undefined) return false;
  if (typeof v === "string") return v.trim().length > 0;
  if (Array.isArray(v)) return v.length > 0;
  return true;
}
