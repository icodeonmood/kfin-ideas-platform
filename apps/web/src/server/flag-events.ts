/**
 * Lane C's part of the S1 to S3 experiments (P-DECISIONS.experiments; BLD-C170 to C176), server side only, on lane
 * A's flag reader (`server/flags.ts`, L-AUDIT.flags, BLD-A216): which variant a person sees, and the exposure, are
 * lane A's `flagVariant`; this file only
 *
 *   - hands Tell it (S-04, S-04B) and Check it (S-05) their variants, so the client never picks one and the URL never
 *     carries one, and turns any failure into the default (a flag never fails a page);
 *   - checks the kill switches S3 needs (they beat the flag);
 *   - logs the deciding events the tables do not already hold, as codes (`flag_events`), and reads S1's interview
 *     place back from them.
 *
 * Nothing here logs words (non-negotiable 3).
 */
import {
  NO_INTERVIEW,
  placeFrom,
  type ComposeFlags,
  type FlagKey,
  type InterviewPlace,
  type Variant,
} from "@/lib/flags";

import { sql } from "kysely";

import { getDb } from "./db";
import { flagsFor, flagVariant } from "./flags";
import { isOn, switchStates } from "./killswitch";
import { log } from "./log";

export {
  EXPOSURE_EVENTS,
  FLAG_EVENTS,
  FLAG_SCREENS,
  needsDraft,
  INTERVIEW_QUESTIONS,
  isFlagKey,
  nextQuestion,
  waitingToBuild,
  type ComposeFlags,
  type FlagKey,
  type InterviewPlace,
  type InterviewQuestion,
  type Variant,
} from "@/lib/flags";

function failed(key: FlagKey, err: unknown): void {
  try {
    log.warn("flags.read_failed", {
      flag_key: key,
      error_type: err instanceof Error ? err.constructor.name : "unknown",
    });
  } catch {
    // the default stands either way
  }
}

/** How long a page waits for a flag before it renders the default (a hung database call never blocks render). */
export const FLAG_WAIT_MS = 1500;

class FlagTimeout extends Error {}

function within<T>(p: Promise<T>, ms: number = FLAG_WAIT_MS): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const late = new Promise<never>((_, reject) => {
    timer = setTimeout(() => reject(new FlagTimeout()), ms);
  });
  return Promise.race([p, late]).finally(() => clearTimeout(timer));
}

/** Lane A's `flagVariant` (it logs the exposure, once per person, screen and variant), with any failure, or no answer
 * within FLAG_WAIT_MS, read as the default: a flag never fails or holds up a page. */
export async function variantOn(user: { id: string }, key: FlagKey, screen: string): Promise<Variant> {
  try {
    return await within(flagVariant(user, key, screen));
  } catch (err) {
    failed(key, err);
    return "default";
  }
}

/** This person's variant without logging an exposure (lane A's `flagsFor`), the same fallback. For a screen whose
 * exposure is logged later, when the browser knows the variant changes something (S2, S3; BLD-C173). */
export async function quietVariant(userId: string, key: FlagKey): Promise<Variant> {
  try {
    return (await within(flagsFor(userId)))[key] === "alternative" ? "alternative" : "default";
  } catch (err) {
    failed(key, err);
    return "default";
  }
}

/** This person's variant without logging an exposure, or null while the flag is off: the events of a flag that is
 * off are not logged. */
async function liveVariant(userId: string, key: FlagKey): Promise<Variant | null> {
  try {
    const db = getDb();
    const flag = await within(
      db.selectFrom("flags").select("state").where("key", "=", key).executeTakeFirst(),
    );
    if (flag?.state !== "on") return null;
    return (await within(flagsFor(userId)))[key] === "alternative" ? "alternative" : "default";
  } catch (err) {
    failed(key, err);
    return null;
  }
}

/** S1's route asks this: is the person in the interview now? Logs nothing. */
export async function inAlternative(userId: string, key: FlagKey): Promise<boolean> {
  return (await liveVariant(userId, key)) === "alternative";
}

/** A draft of this person's (by their contributor code). Events name only their own drafts. */
export async function ownDraft(contributorCode: string | null, draftId: string): Promise<boolean> {
  if (!contributorCode) return false;
  try {
    const row = await getDb()
      .selectFrom("ideas")
      .select("id")
      .where("id", "=", draftId)
      .where("contributor_code", "=", contributorCode)
      .executeTakeFirst();
    return Boolean(row);
  } catch {
    return false;
  }
}

/** What a write of a deciding event came to: written; already there (a retry, or one per draft); not logged because
 * the flag is off; or failed. */
export type EventWrite = "written" | "exists" | "off" | "failed";

/** One deciding event, codes only. Logged only while the flag is on; never throws. S1's steps, S2's events and S3's
 * notes are kept once per draft (the unique indexes), so a retry writes nothing. */
export async function logFlagEvent(input: {
  userId: string;
  key: FlagKey;
  variant?: Variant;
  event: string;
  outcome: string;
  screen: string;
  draftId?: string | null;
}): Promise<EventWrite> {
  const variant = input.variant ?? (await liveVariant(input.userId, input.key));
  if (!variant) return "off";
  try {
    const out = await getDb()
      .insertInto("flag_events")
      .values({
        flag_key: input.key,
        user_id: input.userId,
        variant,
        draft_id: input.draftId ?? null,
        screen: input.screen,
        event: input.event,
        outcome: input.outcome,
      })
      .onConflict((oc) => oc.doNothing())
      .executeTakeFirst();
    return Number(out.numInsertedOrUpdatedRows ?? 0) > 0 ? "written" : "exists";
  } catch (err) {
    failed(input.key, err);
    return "failed";
  }
}

/** Where this person's interview on this draft stands (S1, L-DRAFT.parts/10); NO_INTERVIEW when it never started
 * or cannot be read. */
export async function interviewPlace(userId: string, draftId: string): Promise<InterviewPlace> {
  try {
    const rows = await getDb()
      .selectFrom("flag_events")
      .select(["event", "outcome"])
      .where("flag_key", "=", "s1")
      .where("draft_id", "=", draftId)
      .where("user_id", "=", userId)
      .orderBy("id")
      .execute();
    return placeFrom(rows);
  } catch (err) {
    failed("s1", err);
    return NO_INTERVIEW;
  }
}

/** S1: has the draft been built since its last answer was kept? Then the one build after the questions has happened
 * (a retry after its end could not be logged must not build again, BLD-C172). Unreadable counts as not built. */
export async function builtSinceAnswers(draftId: string): Promise<boolean> {
  try {
    const out = await sql<{ built: boolean }>`
      SELECT EXISTS (
        SELECT 1 FROM draft_runs r
        WHERE r.idea_uuid = ${draftId}
          AND r.started_at >= (SELECT max(e.at) FROM flag_events e
                               WHERE e.draft_id = ${draftId} AND e.flag_key = 's1' AND e.outcome = 'answered')
      ) AS built`.execute(getDb());
    return Boolean(out.rows[0]?.built);
  } catch (err) {
    failed("s1", err);
    return false;
  }
}

/** S3: the switches a voice note needs on the drafts' voice routes (capture.voice, speech.hosted and submissions).
 * Unreadable counts as off. Kill switches beat flags. */
export async function voiceCanRun(): Promise<boolean> {
  try {
    const states = await switchStates();
    return isOn(states, "capture.voice") && isOn(states, "speech.hosted") && isOn(states, "submissions");
  } catch {
    return false;
  }
}

/** What Tell it is given for its two flags. S1's exposure is logged as the screen renders (lane A's `flagVariant`);
 * S3's only from a phone's new S-04, by the browser, which alone knows it is a phone (BLD-C173). */
export async function composeFlags(user: { id: string }, screen: "S-04" | "S-04B"): Promise<ComposeFlags> {
  const [s1, s3] = await Promise.all([variantOn(user, "s1", screen), quietVariant(user.id, "s3")]);
  const voiceFirst = s3 === "alternative" ? ((await voiceCanRun()) ? "listen" : "voice_off") : null;
  return { interview: s1 === "alternative", voiceFirst };
}
