/**
 * Where a person was going when they signed in (L-AUTH.rules/4, P-ROUTES.state). The destination, and for a
 * draft its id and step, is kept on the server against the sign-in attempt, not only in the browser, so it survives
 * the round trip to the identity provider and a switch from single sign-on to an email code.
 *
 * The browser holds only a random attempt key in an HttpOnly cookie; the table keeps its SHA-256, like sessions.
 * Storage sits behind `IntentStore`: `sign_in_intents` from lane E's cut-over (20261121500100), and an in-memory
 * twin for the unit tests.
 */
import { createHash, randomBytes } from "node:crypto";

import { isEnumValue } from "@/lib/contracts/enums";

import { getDb } from "../db";
import { safeNext } from "./session";

export const ATTEMPT_COOKIE = "ideas_attempt";
const FOREIGN_KEY_VIOLATION = "23503";
export const INTENT_TTL_MINUTES = 30;
/** Rows older than this are deleted when a new one is written (BLD-A177). Used rows go at once. */
export const INTENT_KEEP_HOURS = 24;

export type Intent = { to: string; draftId: string | null; step: string | null };

export interface IntentStore {
  /** Keeps the intent, and deletes rows older than INTENT_KEEP_HOURS on the way. */
  save(keyHash: string, intent: Intent, now: Date): Promise<void>;
  /** The intent for this attempt, if it is unused and not older than the TTL. */
  find(keyHash: string, now: Date): Promise<Intent | null>;
  /** Removes the intent and returns it, once. A second call (a replayed callback) gets null. */
  use(keyHash: string, now: Date): Promise<Intent | null>;
}

export const newAttemptKey = () => randomBytes(32).toString("base64url");
export const attemptKeyHash = (key: string) => createHash("sha256").update(key, "utf8").digest("hex");

const DRAFT_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
/** E-ENUMS draft steps (`draft_step` in contracts/1pc/enums.json), as `sign_in_intents.step` allows them. */
export const isDraftStep = (value: unknown): value is string => isEnumValue("draft_step", value);

/**
 * A clean intent from untrusted input: `to` is a same-site path (never another site), the draft id a UUID and the
 * step one the composer knows. A draft path in `to` fills in the draft id and step when they are not given.
 */
export function cleanIntent(input: { to?: unknown; draftId?: unknown; step?: unknown }): Intent {
  let to = safeNext(typeof input.to === "string" ? input.to : null);
  // Never back to a sign-in page or route: that would loop.
  if (/^\/(?:sign-in|signed-out|auth)(?:[/?#]|$)/.test(to)) to = "/";
  const fromPath = draftFromPath(to);
  const draftId =
    typeof input.draftId === "string" && DRAFT_ID.test(input.draftId)
      ? input.draftId.toLowerCase()
      : (fromPath?.draftId ?? null);
  const step = isDraftStep(input.step) ? input.step : (fromPath?.step ?? null);
  return { to, draftId, step: draftId ? (step ?? "tell") : null };
}

/**
 * `/share/<draft id>` is Tell it (S-04B); `/share/<draft id>/check` is Check it, then send it (S-05), per
 * P-ROUTES.screens. A path alone does not say which part of Check it, so it is the first.
 */
export function draftFromPath(path: string): { draftId: string; step: string } | null {
  const m = /^\/share\/([0-9a-f-]{36})(?:\/(check))?\/?(?:[?#].*)?$/i.exec(path);
  if (!m || !DRAFT_ID.test(m[1]!)) return null;
  return { draftId: m[1]!.toLowerCase(), step: m[2] ? "check:1" : "tell" };
}

/** Check it and Send it are both on S-05. */
export const isCheckStep = (step: string | null | undefined) =>
  Boolean(step && (step.startsWith("check:") || step === "send"));

/**
 * Whether an intent is worth a row: somewhere other than `/`, or a draft (BLD-A177). Signing in with nowhere in
 * particular to go keeps nothing; the callback then lands on `/`.
 */
export const worthKeeping = (intent: Intent) => intent.draftId !== null || intent.to !== "/";

/** Where to land after signing in: the draft at its step, else the kept path (S-04 after "Share a problem"). */
export function destination(intent: Intent | null): string {
  if (!intent) return "/";
  if (intent.draftId) return `/share/${intent.draftId}${isCheckStep(intent.step) ? "/check" : ""}`;
  return safeNext(intent.to);
}

/** Which "Next:" line S-02 shows (the `cameFrom` tweak): the composer, Home, or none for anywhere else. */
export function nextScreen(intent: Intent | null): "share" | "home" | null {
  const to = destination(intent);
  if (to === "/share" || to.startsWith("/share/") || to.startsWith("/share?")) return "share";
  if (to === "/" || to === "/home") return "home";
  return null;
}

export const attemptCookieOptions = (secure: boolean, maxAge = INTENT_TTL_MINUTES * 60) => ({
  httpOnly: true,
  secure,
  sameSite: "lax" as const,
  path: "/",
  maxAge,
});

// ---- stores ---------------------------------------------------------------------------------------------------

const expired = (createdAt: Date, now: Date) =>
  now.getTime() - createdAt.getTime() > INTENT_TTL_MINUTES * 60_000;
const keptSince = (now: Date) => new Date(now.getTime() - INTENT_KEEP_HOURS * 3_600_000);

/** For unit tests and for dev before the cut-over: one process, nothing survives a restart. */
export class MemoryIntentStore implements IntentStore {
  rows = new Map<string, { intent: Intent; createdAt: Date }>();

  async save(keyHash: string, intent: Intent, now: Date) {
    for (const [k, row] of this.rows) if (row.createdAt < keptSince(now)) this.rows.delete(k);
    this.rows.set(keyHash, { intent: { ...intent }, createdAt: now });
  }

  async find(keyHash: string, now: Date) {
    const row = this.rows.get(keyHash);
    return row && !expired(row.createdAt, now) ? { ...row.intent } : null;
  }

  async use(keyHash: string, now: Date) {
    const row = this.rows.get(keyHash);
    if (!row) return null;
    this.rows.delete(keyHash);
    return expired(row.createdAt, now) ? null : { ...row.intent };
  }
}

/**
 * `sign_in_intents` (lane E's cut-over, 20261121500100): attempt_key (the SHA-256 here), destination, draft_id
 * (references ideas), step (E-ENUMS draft step), created_at, used_at. A used row is deleted, so `used_at` stays
 * empty; rows nobody used are deleted a day later, when another is written (BLD-A177).
 */
export class PgIntentStore implements IntentStore {
  async save(keyHash: string, intent: Intent, now: Date) {
    await getDb().deleteFrom("sign_in_intents").where("created_at", "<", keptSince(now)).execute();
    const insert = (draftId: string | null, step: string | null) =>
      getDb()
        .insertInto("sign_in_intents")
        .values({ attempt_key: keyHash, destination: intent.to, draft_id: draftId, step, created_at: now })
        .execute();
    try {
      await insert(intent.draftId, intent.step);
    } catch (err) {
      // `draft_id` references ideas(id): a draft that is not there (a stale or edited link) keeps only the path.
      if ((err as { code?: unknown }).code !== FOREIGN_KEY_VIOLATION) throw err;
      await insert(null, null);
    }
  }

  async find(keyHash: string, now: Date) {
    const row = await getDb()
      .selectFrom("sign_in_intents")
      .select(["destination", "draft_id", "step"])
      .where("attempt_key", "=", keyHash)
      .where("used_at", "is", null)
      .where("created_at", ">", oldest(now))
      .executeTakeFirst();
    return row ? { to: row.destination, draftId: row.draft_id, step: row.step } : null;
  }

  async use(keyHash: string, now: Date) {
    const row = await getDb()
      .deleteFrom("sign_in_intents")
      .where("attempt_key", "=", keyHash)
      .returning(["destination", "draft_id", "step", "created_at", "used_at"])
      .executeTakeFirst();
    if (!row || row.used_at || new Date(row.created_at) <= oldest(now)) return null;
    return { to: row.destination, draftId: row.draft_id, step: row.step };
  }
}

const oldest = (now: Date) => new Date(now.getTime() - INTENT_TTL_MINUTES * 60_000);

let store: IntentStore | undefined;

export function intentStore(): IntentStore {
  store ??= new PgIntentStore();
  return store;
}

export function setIntentStoreForTests(s: IntentStore | undefined) {
  store = s;
}
