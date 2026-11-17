import { expect, type Page, type TestInfo } from "@playwright/test";
import { Client } from "pg";

import { signIn } from "./helpers";

/** Shared by the P-DECISIONS.experiments specs (variants.spec.ts, variants-voice.spec.ts): a new synthetic person
 * with one flag forced to the alternative through a flag_assignments row, and the removal of that row and of their
 * exposures and events (rule 14). */

const DATABASE_URL =
  process.env.E2E_DATABASE_URL || "postgres://ideas:ideas@localhost:5432/ideas?sslmode=disable";
export const isPhone = (page: Page) => (page.viewportSize()?.width ?? 1280) <= 640;

export async function sql<T = Record<string, unknown>>(text: string, values: unknown[] = []): Promise<T[]> {
  const client = new Client({ connectionString: DATABASE_URL });
  await client.connect();
  try {
    return (await client.query(text, values)).rows as T[];
  } finally {
    await client.end();
  }
}

/** A new person, signed in, with `flag` forced to the alternative for them. Returns their users.id. */
export async function personWithFlag(page: Page, flag: "s1" | "s3", info: TestInfo): Promise<string> {
  const id = `SYN-EV${flag.toUpperCase()}${info.workerIndex}${Date.now().toString(36).toUpperCase()}`;
  const email = `${id.toLowerCase()}@kfintech.example`;
  await signIn(page, id, { employeeId: id, email, name: "Synthetic Variant" });
  const [me] = await sql<{ id: string }>("SELECT id FROM users WHERE lower(email) = $1", [email]);
  expect(me, "the person exists once signed in").toBeTruthy();
  await sql(
    "INSERT INTO flag_assignments (flag_key, user_id, variant, assigned_by) VALUES ($1, $2, 'alternative', 'e2e') " +
      "ON CONFLICT (flag_key, user_id) DO UPDATE SET variant = 'alternative', assigned_by = 'e2e'",
    [flag, me!.id],
  );
  return me!.id;
}

/** The test's own flag rows, removed (rule 14). The person's drafts stay, as in the other Tell it specs. */
export async function removeFlagRows(userId: string | null): Promise<void> {
  if (!userId) return;
  await sql("DELETE FROM flag_events WHERE user_id = $1", [userId]);
  await sql("DELETE FROM flag_exposures WHERE user_id = $1", [userId]);
  await sql("DELETE FROM flag_assignments WHERE user_id = $1", [userId]);
}

export async function events(userId: string, flag: string): Promise<string[]> {
  const rows = await sql<{ event: string; outcome: string }>(
    "SELECT event, outcome FROM flag_events WHERE user_id = $1 AND flag_key = $2 ORDER BY id",
    [userId, flag],
  );
  return rows.map((r) => `${r.event}:${r.outcome}`);
}
