/**
 * First and later sign-ins (§3.1 step 2, AT-B2-01): match the person to the HR record by employee ID, or by
 * email when SSO does not release the employee ID (open point O2). Someone not yet in the HR export gets a
 * `users` row from the claims (source "sign_in"); the next HR import adopts them. People HR has marked as
 * leavers cannot sign in.
 */
import { sql } from "kysely";

import { oidcConfig } from "../config";
import { getDb } from "../db";
import { assignContributorCode, emailKeyHash, empIdHash } from "../identity/codes";
import type { Claims } from "./oidc";

export class SignInRefused extends Error {
  constructor(public code: "no_email" | "inactive") {
    super(code);
  }
}

export async function userFromClaims(claims: Claims): Promise<{ id: string; created: boolean }> {
  const db = getDb();
  // In dev the mock IdP's username is the synthetic employee ID (SYN-00001…). Never in Entra mode.
  const employeeId = claims.employeeId ?? (oidcConfig().mode === "mock" ? claims.subject : undefined);
  const email = claims.email?.toLowerCase();

  return db.transaction().execute(async (trx) => {
    let row = employeeId
      ? await trx
          .selectFrom("users")
          .select(["id", "active", "email", "name"])
          .where("emp_id_hash", "=", empIdHash(employeeId))
          .executeTakeFirst()
      : undefined;
    if (!row && email) {
      row = await trx
        .selectFrom("users")
        .select(["id", "active", "email", "name"])
        .where(sql`lower(email)`, "=", email)
        .executeTakeFirst();
    }

    if (row) {
      if (!row.active) throw new SignInRefused("inactive");
      await trx
        .updateTable("users")
        .set({ entra_oid: claims.objectId ?? null, last_sign_in_at: new Date() })
        .where("id", "=", row.id)
        .execute();
      await assignContributorCode(trx, row.id, employeeId ?? `email:${row.email}`);
      return { id: row.id, created: false };
    }

    if (!email) throw new SignInRefused("no_email");
    const created = await trx
      .insertInto("users")
      .values({
        emp_id_hash: employeeId ? empIdHash(employeeId) : emailKeyHash(email),
        entra_oid: claims.objectId ?? null,
        name: claims.name ?? email.split("@")[0]!,
        email,
        source: "sign_in",
        last_sign_in_at: new Date(),
      })
      .returning("id")
      .executeTakeFirstOrThrow();
    await assignContributorCode(trx, created.id, employeeId ?? `email:${email}`);
    return { id: created.id, created: true };
  });
}
