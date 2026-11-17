import type { CurrentUser } from "./auth/current";
import { getDb } from "./db";
import { isOn, switchStates } from "./killswitch";

/**
 * S-H3 "Share another way": the other routes in (L-DRAFT.channels), what has arrived by them, and "Tell me when
 * it's out" for the app (L-NOTIFY/7).
 */

export type Channels = {
  email: { on: boolean; address: string | null };
  teams: { on: boolean; link: string | null };
};

export const INTAKE_SWITCHES = { email: "intake.email", teams: "intake.teams" } as const;

const EMAIL = /^[^\s@<>"]+@[^\s@<>"]+\.[^\s@<>"]+$/;

/** The 1% Club mailbox and the Teams app link come from IT (P-DECISIONS.signoff/5); anything malformed counts as
 * not given, and a Teams link must be https, so the page never links to anything else. */
export function intakeAddresses(env: Record<string, string | undefined> = process.env) {
  const address = env.INTAKE_EMAIL_ADDRESS?.trim() ?? "";
  const link = env.TEAMS_APP_LINK?.trim() ?? "";
  let teams: string | null = null;
  try {
    teams = link && new URL(link).protocol === "https:" ? link : null;
  } catch {
    teams = null;
  }
  return { address: EMAIL.test(address) ? address : null, link: teams };
}

/**
 * Each way in is open only while its switch is on and IT has given its address (DEC-105: built, and off until
 * IT approves the mailbox and the Teams app). The switches are `intake.email` and `intake.teams`
 * (L-AUDIT.flags); a switch the table does not know counts as off, so both are off until a migration adds them.
 */
export async function channels(): Promise<Channels> {
  const states = await switchStates().catch(() => new Map<string, "on" | "off">());
  const { address, link } = intakeAddresses();
  return {
    email: { on: isOn(states, INTAKE_SWITCHES.email) && address !== null, address },
    teams: { on: isOn(states, INTAKE_SWITCHES.teams) && link !== null, link },
  };
}

export type Arrival = { draft_id: string; channel: "email" | "teams"; title: string; detail: string };

/**
 * Drafts that arrived by email or Teams and wait for the person to check them, newest first.
 * TODO(cut-over, lane E): drafts carry their channel only after the cut-over (E-ENTITIES.draft, E-ENUMS.draft;
 * `ideas.channel` and `ideas.origin_encrypted` in 20261121500100). Read the person's unarchived drafts with channel
 * `email` or `teams` here then, with the "From your email, today 9:14 am. One customer detail hidden." line built
 * from the origin (L-DRAFT.channels). Until then nothing can arrive, so the list is empty.
 */
export async function arrivals(me: CurrentUser): Promise<Arrival[]> {
  void me;
  return [];
}

/**
 * Whether the person asked to hear when the 1% Club app is out (L-NOTIFY/7): one row per person, the latest choice
 * (`app_news_requests`, 20261122100200). No row means they have not asked.
 */
export async function wantsAppNews(me: CurrentUser): Promise<boolean> {
  const row = await getDb()
    .selectFrom("app_news_requests")
    .select("wants")
    .where("user_id", "=", me.id)
    .executeTakeFirst();
  return row?.wants === true;
}

/** Ask, or withdraw the ask: an upsert, so pressing again always reflects the latest choice. */
export async function setAppNews(me: CurrentUser, want: boolean): Promise<boolean> {
  await getDb()
    .insertInto("app_news_requests")
    .values({ user_id: me.id, wants: want })
    .onConflict((oc) => oc.column("user_id").doUpdateSet({ wants: want }))
    .execute();
  return want;
}
