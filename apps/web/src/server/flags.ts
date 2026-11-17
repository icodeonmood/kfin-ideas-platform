/**
 * The S1 to S3 experiments, server side only (P-DECISIONS.experiments; BLD-C170 to C179). One reader for all three
 * flags: `variantFor(userId, key)` says which variant a person sees, and the page hands it to the screen as a prop.
 * The client never picks its own variant and the URL never carries one.
 *
 *   - A flag whose state is 'off' gives 'default' and logs no exposure.
 *   - A flag_assignments row (an admin's, or one written by the rule) wins.
 *   - Otherwise a stable hash of the user id against `alternative_percent` decides, and the answer is written as an
 *     assignment (`assigned_by 'rule'`) so it never flips. At 0 % nothing is written: no one is in the experiment
 *     yet, so raising the percentage later reaches people who have already used the screen (BLD-C171).
 *   - Any database error gives 'default'. A flag never fails a page.
 *
 * Exposures and events carry IDs and codes only, never words (non-negotiable 3). Kill switches beat flags: the
 * screens check them first (S3's voice first runs only while voice can run).
 */
import { createHash } from "node:crypto";

import {
  FLAG_SCREENS,
  NO_INTERVIEW,
  placeFrom,
  type ComposeFlags,
  type FlagKey,
  type InterviewPlace,
  type Variant,
} from "@/lib/flags";

import { getDb } from "./db";
import { isOn, switchStates } from "./killswitch";
import { log } from "./log";

export {
  FLAG_EVENTS,
  FLAG_SCREENS,
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

/** The person's bucket, 0 to 99, for one flag: the same every time, and independent between flags. */
export function bucketOf(userId: string, key: FlagKey): number {
  return createHash("sha256").update(`${key}:${userId}`).digest().readUInt32BE(0) % 100;
}

const asVariant = (v: unknown): Variant => (v === "alternative" ? "alternative" : "default");

type Resolved = { variant: Variant; on: boolean };

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

async function resolve(userId: string, key: FlagKey): Promise<Resolved> {
  try {
    const db = getDb();
    const flag = await db
      .selectFrom("flags")
      .select(["state", "alternative_percent"])
      .where("key", "=", key)
      .executeTakeFirst();
    if (!flag || flag.state !== "on") return { variant: "default", on: false };
    const given = await db
      .selectFrom("flag_assignments")
      .select("variant")
      .where("flag_key", "=", key)
      .where("user_id", "=", userId)
      .executeTakeFirst();
    if (given) return { variant: asVariant(given.variant), on: true };
    const percent = Math.max(0, Math.min(100, Number(flag.alternative_percent) || 0));
    if (percent === 0) return { variant: "default", on: true };
    const variant: Variant = bucketOf(userId, key) < percent ? "alternative" : "default";
    const made = await db
      .insertInto("flag_assignments")
      .values({ flag_key: key, user_id: userId, variant, assigned_by: "rule" })
      .onConflict((oc) => oc.columns(["flag_key", "user_id"]).doNothing())
      .returning("variant")
      .executeTakeFirst();
    if (made) return { variant: asVariant(made.variant), on: true };
    const raced = await db
      .selectFrom("flag_assignments")
      .select("variant")
      .where("flag_key", "=", key)
      .where("user_id", "=", userId)
      .executeTakeFirst();
    return { variant: asVariant(raced?.variant), on: true };
  } catch (err) {
    failed(key, err);
    return { variant: "default", on: false };
  }
}

/** Which variant this person sees. Never throws: any failure is 'default'. */
export async function variantFor(userId: string, key: FlagKey): Promise<Variant> {
  return (await resolve(userId, key)).variant;
}

/** One exposure: the screen that differs was rendered for this person. None while the flag is off, or for a screen
 * the flag does not change. Returns the variant logged, or null. */
export async function logExposure(userId: string, key: FlagKey, screen: string): Promise<Variant | null> {
  if (!FLAG_SCREENS[key].includes(screen)) return null;
  const { variant, on } = await resolve(userId, key);
  if (!on) return null;
  try {
    await getDb()
      .insertInto("flag_exposures")
      .values({ flag_key: key, user_id: userId, variant, screen })
      .execute();
    return variant;
  } catch (err) {
    failed(key, err);
    return null;
  }
}

/** A draft of this person's (by their contributor code), still a draft. Events name only their own drafts. */
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

/** One deciding event, codes only. Logged only while the flag is on; never throws. `once` keeps a second row for
 * the same draft and event out (S1, by the unique index). Returns whether a row was written. */
export async function logFlagEvent(input: {
  userId: string;
  key: FlagKey;
  variant?: Variant;
  event: string;
  outcome: string;
  screen: string;
  draftId?: string | null;
}): Promise<boolean> {
  let variant = input.variant;
  if (!variant) {
    const r = await resolve(input.userId, input.key);
    if (!r.on) return false;
    variant = r.variant;
  }
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
    return Number(out.numInsertedOrUpdatedRows ?? 0) > 0;
  } catch (err) {
    failed(input.key, err);
    return false;
  }
}

// ---------------------------------------------------------------------------------------------------------------
// S1, the interview: its place, kept with the draft (L-DRAFT.parts/10)
// ---------------------------------------------------------------------------------------------------------------

/** Where this person's interview on this draft stands; NO_INTERVIEW when it never started or cannot be read. */
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

// ---------------------------------------------------------------------------------------------------------------
// S3: voice first runs only while voice can run (kill switches beat flags)
// ---------------------------------------------------------------------------------------------------------------

/** The switches a voice note needs on the drafts' voice routes (killswitch-routes: capture.voice, speech.hosted and
 * submissions). Unreadable counts as off. */
export async function voiceCanRun(): Promise<boolean> {
  try {
    const states = await switchStates();
    return isOn(states, "capture.voice") && isOn(states, "speech.hosted") && isOn(states, "submissions");
  } catch {
    return false;
  }
}

/** What Tell it (S-04, S-04B) is given for its two flags: S1 and S3 (kill switches first). */
export async function composeFlags(userId: string): Promise<ComposeFlags> {
  const [s1, s3] = await Promise.all([variantFor(userId, "s1"), variantFor(userId, "s3")]);
  const voiceFirst = s3 === "alternative" ? ((await voiceCanRun()) ? "listen" : "voice_off") : null;
  return { interview: s1 === "alternative", voiceFirst };
}
