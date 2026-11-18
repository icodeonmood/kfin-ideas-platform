/**
 * The S1 to S3 experiments (P-DECISIONS.experiments; BLD-C170 to C179), the part both sides share: the flags' names
 * and screens, the events a screen may log (codes only), the S1 interview's place, and the browser's two calls. The
 * server decides every variant (`server/flags.ts`) and hands it to the screen as a prop; the browser only says what it
 * rendered and what the person did, and never sends a word they typed or said. No React here: the server reads this
 * file too; the browser's calls are in `flags-client.ts`.
 */
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
  s2: {
    // S-05 opened for a draft, in either variant; close_match when a close similar idea is found on a Check it
    // opened fresh: the moment the other version reorders the page, so the exposure is logged then (BLD-C173).
    "s2.check": ["opened", "close_match"],
    // The comparison put first, and what the person did with it.
    "s2.compare": ["shown", "moved_on", "kept_separate", "merge_asked", "mine_is_different"],
  },
  s3: {
    // A phone's new S-04 was shown: the exposure, logged by lane A's reader (only the browser knows it is a phone).
    "s3.exposure": ["shown"],
    // On the phone's S-04: listening started at once, or the screen began with typing, and why.
    "s3.listen": ["started", "typed_instead", "no_permission", "voice_off", "failed"],
    // A draft sent with a voice note as heard, or with its words changed first.
    "s3.note": ["as_heard", "corrected"],
  },
};

/** Events that log an exposure (lane A's `flagVariant`) for the screen they name, not a row of flag_events, or as
 * well as one: S3's phone S-04, and S2's close match on a fresh Check it. */
export const EXPOSURE_EVENTS: Record<string, { flag: FlagKey; screen: string; outcome: string }> = {
  "s3.exposure": { flag: "s3", screen: "S-04", outcome: "shown" },
  "s2.check": { flag: "s2", screen: "S-05", outcome: "close_match" },
};

/** Events that must name a draft of the person's own: every S2 event, and S3's notes (one row per draft). */
export function needsDraft(event: string): boolean {
  return event.startsWith("s2.") || event === "s3.note";
}

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
