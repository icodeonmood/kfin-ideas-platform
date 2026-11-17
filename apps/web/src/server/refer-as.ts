/**
 * `person_settings.refer_as`, the person's own (BLD-C111). Read and written for the signed-in person only; never
 * logged, never returned to anyone else.
 */
import { storedReferAs, wireReferAs, type ReferAs } from "@/lib/refer-as";

import type { CurrentUser } from "./auth/current";
import { getDb } from "./db";

export async function getReferAs(me: CurrentUser): Promise<{ refer_as: ReferAs }> {
  const row = await getDb()
    .selectFrom("person_settings")
    .select("refer_as")
    .where("user_id", "=", me.id)
    .executeTakeFirst();
  return { refer_as: wireReferAs(row?.refer_as) };
}

export async function setReferAs(me: CurrentUser, value: ReferAs): Promise<{ refer_as: ReferAs }> {
  const refer_as = storedReferAs(value);
  await getDb()
    .insertInto("person_settings")
    .values({ user_id: me.id, refer_as })
    .onConflict((oc) => oc.column("user_id").doUpdateSet({ refer_as, updated_at: new Date() }))
    .execute();
  return { refer_as: wireReferAs(refer_as) };
}
