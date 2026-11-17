/**
 * The 1% Club seed for the screen tests (`make demo DEMO_SET=1pc`, services/worker/bootstrap/club_seed.py). Screens
 * that read their first view on the server (S-07, S-06, S-09) are checked on the seed's people and ideas: tests read
 * it and never change it. Without the seed those tests skip and say why; lane G's journeys run on it in CI.
 * Synthetic data only (non-negotiable 11).
 */
import { Client } from "pg";

export const DATABASE_URL =
  process.env.E2E_DATABASE_URL || "postgres://ideas:ideas@localhost:5432/ideas?sslmode=disable";

/** The seed's cast, by employee ID (club_seed.PEOPLE). */
export const CLUB = {
  tanvi: "SYN-10001", // sharer with ideas at every stage
  rekha: "SYN-10009", // leads R2, which Tanvi teamed up on
  naveen: "SYN-10014", // nothing of Tanvi's on his own lists
} as const;

/** Seeded ideas by seed key (club_seed.SPECS). */
export const IDEAS = {
  T5: "Redemption status is not visible to the branch", // with the desk, not opened: edit window open
  T6: "PAN mismatch holds new folios for days", // questions sent: Needs you
  T7: "Plain words for transaction rejection codes", // picked
  T8: "A paid express change-of-bank service", // not now
  T9: "Dividend bank mandate reminders go out too late", // not picked, reversed to picked by the committee
  T10: "Token slips at the branch run out by noon", // withdrawn
  T11: "Investors call twice about failed SIP debits", // merged by the desk into R2
  R2: "One clear message after a failed SIP debit", // Rekha's; Tanvi teamed up
  A1: "Pre-fill nominee details from CKYC", // being built, someone else's
} as const;
export type IdeaKey = keyof typeof IDEAS;

/** Each sharer's own words, as club_seed.SPECS types them (a part without a hidden detail): they reach the sharer, the
 * review desk and the Ones Committee only, never the Wall or a colleague (P-PRODUCT.privacy, DEC-104). */
export const OWN_WORDS: Partial<Record<IdeaKey, string>> = {
  T6: "New folios are held when the PAN name and the form name differ by one letter.",
  T7: "Rejection letters show only a code like R07. Investors cannot read it and call us.",
  T9: "The reminder to update the bank mandate goes out after the record date.",
};

/** The seed's Ones by number (club_seed.ONES). */
export const ONES = { indira: { number: 30, name: "Indira Natarajan" } } as const;

export type Seeded = { uuid: string; ref: string; title: string; status: string; summary: string };

async function query<T>(sql: string, args: unknown[]): Promise<T[]> {
  const client = new Client({ connectionString: DATABASE_URL });
  await client.connect();
  try {
    return (await client.query(sql, args)).rows as T[];
  } finally {
    await client.end();
  }
}

/** True when the seed is loaded (its last idea is there). */
export async function clubLoaded(): Promise<boolean> {
  try {
    const rows = await query<{ n: number }>("SELECT count(*)::int AS n FROM ideas WHERE title = ANY($1)", [
      [IDEAS.T5, IDEAS.T9, IDEAS.R2],
    ]);
    return rows[0]?.n === 3;
  } catch {
    return false;
  }
}

export const NO_SEED = "needs the 1% Club seed: make demo DEMO_SET=1pc";

/** A seeded idea as it is now (read only). */
export async function seededIdea(key: IdeaKey): Promise<Seeded> {
  const rows = await query<{ id: string; idea_id: string; title: string; status: string; summary: string }>(
    "SELECT id, idea_id, title, status, coalesce(summary, '') AS summary FROM ideas WHERE title = $1 " +
      "ORDER BY created_at DESC LIMIT 1",
    [IDEAS[key]],
  );
  const r = rows[0];
  if (!r) throw new Error(`seed idea ${key} is missing: ${NO_SEED}`);
  return {
    uuid: String(r.id),
    ref: String(r.idea_id),
    title: String(r.title),
    status: String(r.status),
    summary: String(r.summary),
  };
}

/**
 * Sets whether a seeded person (by name) shows their name on the Wall (DEC-104), and returns how to put it back as it
 * was. The one change these screen tests make to the seed, always undone in the same test.
 */
export async function showNameOnWall(name: string, show: boolean): Promise<() => Promise<void>> {
  const rows = await query<{ id: string; had: boolean | null }>(
    "SELECT u.id, s.show_name_on_wall AS had FROM users u LEFT JOIN person_settings s ON s.user_id = u.id " +
      "WHERE u.name = $1",
    [name],
  );
  const r = rows[0];
  if (!r) throw new Error(`seed person ${name} is missing: ${NO_SEED}`);
  await query(
    "INSERT INTO person_settings (user_id, show_name_on_wall) VALUES ($1, $2) " +
      "ON CONFLICT (user_id) DO UPDATE SET show_name_on_wall = $2",
    [r.id, show],
  );
  return async () => {
    if (r.had === null) await query("DELETE FROM person_settings WHERE user_id = $1", [r.id]);
    else await query("UPDATE person_settings SET show_name_on_wall = $2 WHERE user_id = $1", [r.id, r.had]);
  };
}

/** Removes a person a test signed in as (their grants, settings and Inbox cascade), so no row outlives the test. */
export async function removePerson(email: string): Promise<void> {
  await query("DELETE FROM users WHERE email = $1", [email]);
}

export function esc(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
