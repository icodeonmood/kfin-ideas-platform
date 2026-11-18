/**
 * L-AUDIT.flags: the S1 to S3 experiments (P-DECISIONS.experiments), per person or by percentage, with exposure
 * logged (lane A, BLD-A216). The worker has the same rules in `services/worker/programme/flags.py`; a shared test
 * vector keeps the two buckets equal.
 *
 * - An admin sets each flag's state (on or off) and the share of people who get the alternative (0 to 100).
 * - A person an admin assigned gets that variant. Everyone else is placed by a deterministic bucket: the first four
 *   bytes of SHA-256 of "<key>:<user id>", as an unsigned number, modulo 100; below `alternative_percent` means the
 *   alternative. Raising the percentage only adds people.
 * - A flag that is off, or unknown, gives the default and logs nothing.
 * - `flagVariant(user, key, screen)` logs one exposure per person, screen and variant (`flag_exposures_once`).
 *   `flagsFor` (for `GET /api/config`) logs nothing: a screen logs when it shows a variant.
 * - Every admin change is written to `audit_log` with its reason.
 */
import { createHash } from "node:crypto";

import { sql } from "kysely";

import { getDb } from "./db";

export type Variant = "default" | "alternative";
export const FLAG_KEYS = ["s1", "s2", "s3"] as const;

export class FlagError extends Error {
  constructor(
    public code: string,
    public status: number,
    public text: string,
    public field?: string,
  ) {
    super(code);
  }
  body() {
    return { error: { code: this.code, message: this.text, ...(this.field ? { field: this.field } : {}) } };
  }
}

export function bucket(key: string, userId: string): number {
  return createHash("sha256").update(`${key}:${userId}`).digest().readUInt32BE(0) % 100;
}

type FlagRow = { key: string; state: string; alternative_percent: number };

function decide(flag: FlagRow | undefined, assigned: string | undefined, userId: string): Variant | null {
  if (!flag || flag.state !== "on") return null;
  if (assigned) return assigned === "alternative" ? "alternative" : "default";
  return bucket(flag.key, userId) < flag.alternative_percent ? "alternative" : "default";
}

/** What `screen` (a screen ID such as "S-04") shows this person; logs the exposure the first time. */
export async function flagVariant(user: { id: string }, key: string, screen: string): Promise<Variant> {
  const db = getDb();
  const flag = await db
    .selectFrom("flags")
    .select(["key", "state", "alternative_percent"])
    .where("key", "=", key)
    .executeTakeFirst();
  const assigned = await db
    .selectFrom("flag_assignments")
    .select("variant")
    .where("flag_key", "=", key)
    .where("user_id", "=", user.id)
    .executeTakeFirst();
  const variant = decide(flag, assigned?.variant, user.id);
  if (!variant) return "default";
  await sql`INSERT INTO flag_exposures (flag_key, user_id, variant, screen)
            VALUES (${key}, ${user.id}, ${variant}, ${screen})
            ON CONFLICT (flag_key, user_id, screen, variant) DO NOTHING`.execute(db);
  return variant;
}

/** Every flag's variant for this person, for `GET /api/config`. Logs nothing. */
export async function flagsFor(userId: string): Promise<Record<string, Variant>> {
  const db = getDb();
  const flags = await db.selectFrom("flags").select(["key", "state", "alternative_percent"]).execute();
  const assigned = await db
    .selectFrom("flag_assignments")
    .select(["flag_key", "variant"])
    .where("user_id", "=", userId)
    .execute();
  const mine = new Map(assigned.map((a) => [a.flag_key, a.variant]));
  return Object.fromEntries(flags.map((f) => [f.key, decide(f, mine.get(f.key), userId) ?? "default"]));
}

export type AdminFlag = {
  key: string;
  description: string;
  state: "on" | "off";
  alternative_percent: number;
  changed_at: string;
  people: Array<{ user_id: string; name: string; email: string; variant: Variant }>;
  exposures: { default: number; alternative: number };
};

/** The flags with their per-person assignments and exposure counts, for the admin page. */
export async function listFlags(): Promise<AdminFlag[]> {
  const db = getDb();
  const flags = await db.selectFrom("flags").selectAll().orderBy("key").execute();
  const people = await db
    .selectFrom("flag_assignments as a")
    .innerJoin("users as u", "u.id", "a.user_id")
    .select(["a.flag_key", "a.user_id", "a.variant", "u.name", "u.email"])
    .orderBy("u.name")
    .execute();
  const counts = await db
    .selectFrom("flag_exposures")
    .select(["flag_key", "variant", sql<number>`count(DISTINCT user_id)::int`.as("n")])
    .groupBy(["flag_key", "variant"])
    .execute();
  return flags.map((f) => ({
    key: f.key,
    description: f.description,
    state: f.state === "on" ? "on" : "off",
    alternative_percent: f.alternative_percent,
    changed_at: new Date(f.changed_at).toISOString(),
    people: people
      .filter((p) => p.flag_key === f.key)
      .map((p) => ({
        user_id: p.user_id,
        name: p.name,
        email: p.email,
        variant: p.variant === "alternative" ? "alternative" : "default",
      })),
    exposures: {
      default: counts.find((c) => c.flag_key === f.key && c.variant === "default")?.n ?? 0,
      alternative: counts.find((c) => c.flag_key === f.key && c.variant === "alternative")?.n ?? 0,
    },
  }));
}

const REASON_MIN = 10;
const REASON_MAX = 500;

function reasonOf(value: unknown): string {
  const reason = typeof value === "string" ? value.trim() : "";
  if (reason.length < REASON_MIN || reason.length > REASON_MAX)
    throw new FlagError("reason_required", 422, "Give a reason of at least 10 characters.", "reason");
  return reason;
}

function knownKey(key: string): string {
  if (!(FLAG_KEYS as readonly string[]).includes(key))
    throw new FlagError("not_found", 404, "There is no such experiment.");
  return key;
}

/** An admin changes a flag's state or share; audited with before and after. */
export async function setFlag(input: {
  key: string;
  state: unknown;
  alternativePercent: unknown;
  reason: unknown;
  actorUserId: string;
}) {
  const key = knownKey(input.key);
  const reason = reasonOf(input.reason);
  if (input.state !== "on" && input.state !== "off")
    throw new FlagError("state_required", 422, "Choose on or off.", "state");
  // An empty field is not 0 per cent (BLD-A216): only a number, or a string of digits, counts.
  const raw = input.alternativePercent;
  const percent =
    typeof raw === "number" ? raw : typeof raw === "string" && /^\s*\d+\s*$/.test(raw) ? Number(raw) : NaN;
  if (!Number.isInteger(percent) || percent < 0 || percent > 100)
    throw new FlagError(
      "percent_not_valid",
      422,
      "Enter a whole number from 0 to 100.",
      "alternative_percent",
    );
  await getDb()
    .transaction()
    .execute(async (trx) => {
      const before = await trx
        .selectFrom("flags")
        .select(["state", "alternative_percent"])
        .where("key", "=", key)
        .forUpdate()
        .executeTakeFirst();
      if (!before) throw new FlagError("not_found", 404, "There is no such experiment.");
      await trx
        .updateTable("flags")
        .set({
          state: input.state as string,
          alternative_percent: percent,
          changed_by: `user:${input.actorUserId}`,
          changed_at: new Date(),
        })
        .where("key", "=", key)
        .execute();
      await trx
        .insertInto("audit_log")
        .values({
          actor: `user:${input.actorUserId}`,
          action: "flag.changed",
          entity: `flag:${key}`,
          before: JSON.stringify(before),
          after: JSON.stringify({ state: input.state, alternative_percent: percent }),
          reason,
        })
        .execute();
    });
}

/** An admin puts one person on a variant, or back on the rule (`variant: null`); audited. */
export async function assignFlag(input: {
  key: string;
  email: unknown;
  variant: unknown;
  reason: unknown;
  actorUserId: string;
}) {
  const key = knownKey(input.key);
  const reason = reasonOf(input.reason);
  const email = typeof input.email === "string" ? input.email.trim().toLowerCase() : "";
  if (!email || email.length > 320)
    throw new FlagError("email_required", 422, "Enter a work email.", "email");
  const variant = input.variant;
  if (variant !== null && variant !== "default" && variant !== "alternative")
    throw new FlagError("variant_required", 422, "Choose which version they see.", "variant");
  await getDb()
    .transaction()
    .execute(async (trx) => {
      const user = await trx
        .selectFrom("users")
        .select(["id"])
        .where(sql`lower(email)`, "=", email)
        .where("active", "=", true)
        .executeTakeFirst();
      if (!user) throw new FlagError("no_such_person", 404, "No one active has that work email.", "email");
      const before = await trx
        .selectFrom("flag_assignments")
        .select("variant")
        .where("flag_key", "=", key)
        .where("user_id", "=", user.id)
        .executeTakeFirst();
      if (variant === null) {
        await trx
          .deleteFrom("flag_assignments")
          .where("flag_key", "=", key)
          .where("user_id", "=", user.id)
          .execute();
      } else {
        await trx
          .insertInto("flag_assignments")
          .values({
            flag_key: key,
            user_id: user.id,
            variant: variant as string,
            assigned_by: `user:${input.actorUserId}`,
          })
          .onConflict((oc) =>
            oc.columns(["flag_key", "user_id"]).doUpdateSet({
              variant: variant as string,
              assigned_by: `user:${input.actorUserId}`,
              assigned_at: new Date(),
            }),
          )
          .execute();
      }
      await trx
        .insertInto("audit_log")
        .values({
          actor: `user:${input.actorUserId}`,
          action: "flag.assigned",
          entity: `flag:${key}`,
          before: JSON.stringify({ user_id: user.id, variant: before?.variant ?? null }),
          after: JSON.stringify({ user_id: user.id, variant }),
          reason,
        })
        .execute();
    });
}
