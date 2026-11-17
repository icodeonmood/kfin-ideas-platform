/**
 * S-03 Home's first visit (BLD-C148, A-API.home `first_visit`): true only the first time Home is shown to the person.
 * Read first, so a returning visit writes nothing; the first one is marked in one statement, so two tabs opened at
 * once cannot both see it. A router prefetch is not a visit. The person's own setting (`person_settings.home_seen_at`,
 * migration 20261122300800); never logged.
 */
import { sql } from "kysely";

import type { CurrentUser } from "./auth/current";
import { getDb } from "./db";

export async function firstHomeVisit(me: CurrentUser, prefetch = false): Promise<boolean> {
  if (prefetch) return false;
  try {
    const db = getDb();
    const seen = await db
      .selectFrom("person_settings")
      .select("home_seen_at")
      .where("user_id", "=", me.id)
      .executeTakeFirst();
    if (seen?.home_seen_at) return false;
    const row = await db
      .insertInto("person_settings")
      .values({ user_id: me.id, home_seen_at: sql<Date>`now()` })
      .onConflict((oc) =>
        oc.column("user_id").doUpdateSet({
          home_seen_at: sql<Date>`coalesce(person_settings.home_seen_at, now())`,
        }),
      )
      .returning(sql<boolean>`home_seen_at = now()`.as("first"))
      .executeTakeFirst();
    return Boolean(row?.first);
  } catch {
    return false; // Home never fails over this: the returning view is the safe one
  }
}
