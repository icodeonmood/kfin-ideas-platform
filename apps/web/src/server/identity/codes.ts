/**
 * Contributor codes and the employee-ID hash (§2.3). Same algorithm as services/worker/identity/codes.py;
 * tests/unit/codes.test.ts pins both to one shared vector.
 *   contributor code = "CTR-" + first 6 hex of HMAC-SHA256(employee ID, secret)   (8 on a collision)
 *   users.emp_id_hash = HMAC-SHA256("emp:" + employee ID, secret)                 (unlinkable to the code)
 * The secret comes only from the environment.
 */
import { createHmac } from "node:crypto";

import type { Kysely, Transaction } from "kysely";

import type { DB } from "../db-types";

export class SecretMissing extends Error {}

function secret(): string {
  const value = process.env.CONTRIBUTOR_HMAC_SECRET;
  if (!value) throw new SecretMissing("CONTRIBUTOR_HMAC_SECRET is not set");
  // Fail closed: only dev and test may use the placeholder.
  if (!["dev", "test"].includes(process.env.APP_ENV ?? "") && (value === "change-me" || value.length < 32)) {
    throw new SecretMissing("CONTRIBUTOR_HMAC_SECRET is a placeholder or too short for this environment");
  }
  return value;
}

export const normaliseEmployeeId = (id: string) => id.trim().toUpperCase();
const hmacHex = (message: string) => createHmac("sha256", secret()).update(message, "utf8").digest("hex");

export const contributorCode = (key: string, length = 6) =>
  "CTR-" + hmacHex(normaliseEmployeeId(key)).slice(0, length);
export const empIdHash = (employeeId: string) => hmacHex("emp:" + normaliseEmployeeId(employeeId));
export const emailKeyHash = (email: string) => hmacHex("email:" + email.trim().toLowerCase());

/** Give the user a code, extending to 8 characters if the 6-character one is someone else's. */
export async function assignContributorCode(
  db: Kysely<DB> | Transaction<DB>,
  userId: string,
  key: string,
): Promise<string> {
  const existing = await db
    .selectFrom("contributor_map")
    .select("contributor_code")
    .where("user_id", "=", userId)
    .executeTakeFirst();
  if (existing) return existing.contributor_code;
  for (const length of [6, 8]) {
    const code = contributorCode(key, length);
    const taken = await db
      .selectFrom("contributor_map")
      .select("user_id")
      .where("contributor_code", "=", code)
      .executeTakeFirst();
    if (!taken) {
      await db.insertInto("contributor_map").values({ contributor_code: code, user_id: userId }).execute();
      return code;
    }
  }
  throw new Error("contributor code collision at 8 characters");
}
