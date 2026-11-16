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

const APP_NEWS = { asked: "app_news.asked", withdrawn: "app_news.withdrawn" } as const;
const entity = (me: CurrentUser) => `person:${me.id}`;

/**
 * Whether the person asked to hear when the 1% Club app is out (L-NOTIFY/7), the latest choice winning.
 * TODO(cut-over, lane E): move to the person's own settings (E-ENTITIES.person.settings) when the cut-over gives
 * them a place; until then each choice is an audit row with IDs only, which is also the record L-AUDIT wants.
 */
export async function wantsAppNews(me: CurrentUser): Promise<boolean> {
  const row = await getDb()
    .selectFrom("audit_log")
    .select("action")
    .where("entity", "=", entity(me))
    .where("action", "in", [APP_NEWS.asked, APP_NEWS.withdrawn])
    .orderBy("id", "desc")
    .limit(1)
    .executeTakeFirst();
  return row?.action === APP_NEWS.asked;
}

export async function setAppNews(me: CurrentUser, want: boolean, ip: string | null): Promise<boolean> {
  await getDb()
    .insertInto("audit_log")
    .values({
      actor: `user:${me.id}`,
      action: want ? APP_NEWS.asked : APP_NEWS.withdrawn,
      entity: entity(me),
      before: null,
      after: JSON.stringify({ app_news: want }),
      reason: null,
      ip,
    })
    .execute();
  return want;
}
