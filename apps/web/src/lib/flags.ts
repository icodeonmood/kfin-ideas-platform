/**
 * The S1 to S3 experiments (P-DECISIONS.experiments; BLD-C170 to C179), the part both sides share: the flags' names
 * and screens, the events a screen may log (codes only), the S1 interview's place, and the browser's two calls. The
 * server decides every variant (`server/flags.ts`) and hands it to the screen as a prop; the browser only says what it
 * rendered and what the person did, and never sends a word they typed or said.
 */
import { useEffect, useRef } from "react";

export type FlagKey = "s1" | "s2" | "s3";
export type Variant = "default" | "alternative";

export const FLAG_KEYS: readonly FlagKey[] = ["s1", "s2", "s3"];

export const isFlagKey = (v: unknown): v is FlagKey =>
  typeof v === "string" && (FLAG_KEYS as readonly string[]).includes(v);

/** The screens where each flag's two variants differ. An exposure names one of them. */
export const FLAG_SCREENS: Record<FlagKey, readonly string[]> = {
  s1: ["S-04", "S-04B"],
  s2: ["S-05"],
  s3: ["S-04", "S-04B"],
};

/** The events a screen may log through `/api/flags/events`, and their outcomes (BLD-C174). S1's go through the
 * interview's own route (`/api/drafts/:id/interview`), so none are open here. */
export const FLAG_EVENTS: Record<FlagKey, Record<string, readonly string[]>> = {
  s1: {},
  s2: {},
  s3: {
    // On the phone's S-04: listening started at once, or the screen began with typing, and why.
    "s3.listen": ["started", "typed_instead", "no_permission", "voice_off", "failed"],
    // A voice note sent as heard, or with its words changed first.
    "s3.note": ["as_heard", "corrected"],
  },
};

/** What Tell it (S-04, S-04B) is given by the server for the two flags it carries. */
export type ComposeFlags = {
  /** S1 "Interview". */
  interview: boolean;
  /** S3 "Voice first" on a phone: "listen" when it may start listening, "voice_off" when the person is in the
   * alternative but voice cannot run (the phone starts with typing, as the default does), null otherwise. */
  voiceFirst: "listen" | "voice_off" | null;
};

// ── S1, the interview's place, kept with the draft (L-DRAFT.parts/10) ───────────────────────────────────────────

export const INTERVIEW_QUESTIONS = ["often", "who", "size"] as const;
export type InterviewQuestion = (typeof INTERVIEW_QUESTIONS)[number];

export const isInterviewQuestion = (v: unknown): v is InterviewQuestion =>
  typeof v === "string" && (INTERVIEW_QUESTIONS as readonly string[]).includes(v);

export type InterviewPlace = {
  started: boolean;
  /** Each question the person answered or skipped, by key. */
  done: Partial<Record<InterviewQuestion, "answered" | "skipped">>;
  /** Finished (all three), or left (moved on before the last). */
  ended: "finished" | "left" | null;
};

export const NO_INTERVIEW: InterviewPlace = { started: false, done: {}, ended: null };

/** The question to ask now, or null: not started, ended, or all three handled. */
export function nextQuestion(place: InterviewPlace): InterviewQuestion | null {
  if (!place.started || place.ended) return null;
  return INTERVIEW_QUESTIONS.find((q) => !place.done[q]) ?? null;
}

/** An answer kept without building yet (`defer_run`): the one build follows the interview. */
export function waitingToBuild(place: InterviewPlace): boolean {
  return place.started && !place.ended && Object.values(place.done).includes("answered");
}

/** The place from its logged steps (`s1.start`, `s1.often` …, `s1.end`). */
export function placeFrom(rows: readonly { event: string; outcome: string }[]): InterviewPlace {
  const place: InterviewPlace = { started: false, done: {}, ended: null };
  for (const r of rows) {
    if (r.event === "s1.start") place.started = true;
    else if (r.event === "s1.end") place.ended = r.outcome === "left" ? "left" : "finished";
    else {
      const q = r.event.slice(3);
      if (isInterviewQuestion(q)) place.done[q] = r.outcome === "answered" ? "answered" : "skipped";
    }
  }
  return place;
}

// ── the browser's calls: fire and forget, never in the way of the screen ────────────────────────────────────────

function post(path: string, body: Record<string, unknown>): void {
  try {
    void fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      keepalive: true,
      cache: "no-store",
    }).catch(() => undefined);
  } catch {
    // logging never fails a screen
  }
}

/** One deciding event, as codes. */
export function flagEvent(
  flag: FlagKey,
  event: string,
  outcome: string,
  screen: string,
  draftId?: string | null,
): void {
  post("/api/flags/events", { flag, event, outcome, screen, ...(draftId ? { draft_id: draftId } : {}) });
}

/** One exposure per page load, once `when` is true: the screen that differs for this flag was rendered. */
export function useFlagExposure(flag: FlagKey, screen: string, when: boolean): void {
  const sent = useRef<string | null>(null);
  useEffect(() => {
    if (!when) return;
    const key = `${flag}:${screen}`;
    if (sent.current === key) return;
    sent.current = key;
    post("/api/flags/exposure", { flag, screen });
  }, [flag, screen, when]);
}
