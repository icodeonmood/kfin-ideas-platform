/**
 * Where a person was going when they signed in (L-AUTH.rules/4, P-ROUTES.state). The destination, and for a
 * draft its id and step, is kept on the server against the sign-in attempt, not only in the browser, so it survives
 * the round trip to the identity provider and a switch from single sign-on to an email code.
 *
 * The browser holds only a random attempt key in an HttpOnly cookie; the table keeps its SHA-256, like sessions.
 * Storage sits behind `IntentStore`: `sign_in_intents` arrives in lane E's cut-over (20261121500100), and the
 * in-memory store backs the unit tests until then.
 */
import { createHash, randomBytes } from "node:crypto";

import { sql } from "kysely";

import { getDb } from "../db";
import { safeNext } from "./session";
import { withTableFallback } from "./table-fallback";

export const ATTEMPT_COOKIE = "ideas_attempt";
const FOREIGN_KEY_VIOLATION = "23503";
export const INTENT_TTL_MINUTES = 30;

export type Intent = { to: string; draftId: string | null; step: string | null };

export interface IntentStore {
  save(keyHash: string, intent: Intent, now: Date): Promise<void>;
  /** The intent for this attempt, if it is unused and not older than the TTL. */
  find(keyHash: string, now: Date): Promise<Intent | null>;
  /** Marks the intent used and returns it, once. A second call (a replayed callback) gets null. */
  use(keyHash: string, now: Date): Promise<Intent | null>;
}

export const newAttemptKey = () => randomBytes(32).toString("base64url");
export const attemptKeyHash = (key: string) => createHash("sha256").update(key, "utf8").digest("hex");

const DRAFT_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
/** E-ENUMS draft steps, as `sign_in_intents.step` and `ideas.step` allow them (lane E's cut-over). */
export const DRAFT_STEPS: ReadonlySet<string> = new Set([
  "tell",
  "check:1",
  "check:2",
  "check:3",
  "check:4",
  "check:5",
  "check:6",
  "check:7",
  "send",
]);

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
  const step =
    typeof input.step === "string" && DRAFT_STEPS.has(input.step) ? input.step : (fromPath?.step ?? null);
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

/** For unit tests and for dev before the cut-over: one process, nothing survives a restart. */
export class MemoryIntentStore implements IntentStore {
  private rows = new Map<string, { intent: Intent; createdAt: Date; usedAt: Date | null }>();

  async save(keyHash: string, intent: Intent, now: Date) {
    this.rows.set(keyHash, { intent: { ...intent }, createdAt: now, usedAt: null });
  }

  async find(keyHash: string, now: Date) {
    const row = this.rows.get(keyHash);
    return row && !row.usedAt && !expired(row.createdAt, now) ? { ...row.intent } : null;
  }

  async use(keyHash: string, now: Date) {
    const row = this.rows.get(keyHash);
    if (!row || row.usedAt || expired(row.createdAt, now)) return null;
    row.usedAt = now;
    return { ...row.intent };
  }
}

/**
 * `sign_in_intents` (lane E's cut-over, 20261121500100): attempt_key (the SHA-256 here, text), destination,
 * draft_id (uuid, references ideas), step (E-ENUMS draft step), created_at, used_at. Raw SQL so this file does not
 * depend on generated types before the table is on `main`.
 */
export class PgIntentStore implements IntentStore {
  async save(keyHash: string, intent: Intent, now: Date) {
    const insert = (draftId: string | null, step: string | null) =>
      sql`
        INSERT INTO sign_in_intents (attempt_key, destination, draft_id, step, created_at)
        VALUES (${keyHash}, ${intent.to}, ${draftId}, ${step}, ${now})
      `.execute(getDb());
    try {
      await insert(intent.draftId, intent.step);
    } catch (err) {
      // `draft_id` references ideas(id): a draft that is not there (a stale or edited link) keeps only the path.
      if ((err as { code?: unknown }).code !== FOREIGN_KEY_VIOLATION) throw err;
      await insert(null, null);
    }
  }

  async find(keyHash: string, now: Date) {
    const r = await sql<{ destination: string; draft_id: string | null; step: string | null }>`
      SELECT destination, draft_id, step FROM sign_in_intents
      WHERE attempt_key = ${keyHash} AND used_at IS NULL
        AND created_at > ${now}::timestamptz - make_interval(mins => ${INTENT_TTL_MINUTES})
    `.execute(getDb());
    const row = r.rows[0];
    return row ? { to: row.destination, draftId: row.draft_id, step: row.step } : null;
  }

  async use(keyHash: string, now: Date) {
    const r = await sql<{ destination: string; draft_id: string | null; step: string | null }>`
      UPDATE sign_in_intents SET used_at = ${now}
      WHERE attempt_key = ${keyHash} AND used_at IS NULL
        AND created_at > ${now}::timestamptz - make_interval(mins => ${INTENT_TTL_MINUTES})
      RETURNING destination, draft_id, step
    `.execute(getDb());
    const row = r.rows[0];
    return row ? { to: row.destination, draftId: row.draft_id, step: row.step } : null;
  }
}

let store: IntentStore | undefined;

/** The table; in process memory while the table is missing (before the cut-over, BLD-A173). */
export function intentStore(): IntentStore {
  store ??= withTableFallback<IntentStore>("sign_in_intents", new PgIntentStore(), new MemoryIntentStore());
  return store;
}

export function setIntentStoreForTests(s: IntentStore | undefined) {
  store = s;
}
