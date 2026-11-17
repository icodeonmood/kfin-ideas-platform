/**
 * The Ones (DEC-034 to DEC-087), web side. Every read and write goes through the worker, which re-checks the
 * person's live grants; this module passes who is acting and turns refusals into codes (never echoed text).
 */
import type { CurrentUser } from "./auth/current";
import { getDb } from "./db";
import { log } from "./log";
import { SubmissionError } from "./submissions";
import { workerFetch } from "./worker";

export type Measures = Partial<
  Record<"time" | "money" | "effort" | "scale", { value: number; unit: string; finance_confirmed?: boolean }>
>;

export type Tiered = { tier: number; tier_name: string; tier_colour: string };

export type PublicOne = Tiered & {
  number: number;
  induction_no: number;
  name: string | null;
  founding: boolean;
  way_in: string;
  line: string | null;
  stage: string | null;
  brief: string | null;
  measures: Measures;
};

export type GlowUp = {
  id: number;
  from: Tiered;
  to: Tiered;
  up: boolean;
  story: {
    ideas_shared: number;
    ideas_picked: number;
    ideas_shipped: number;
    milestones: { on: string | null; what: string }[];
    measures: Measures;
  };
  messages: { from: "committee" | "ceo" | "peer"; name: string; text: string | null }[];
};

export type MyOne = Tiered & {
  active: boolean;
  number: number | null;
  induction_no: number;
  way_in: string;
  line: string | null;
  stage: string | null;
  since: string;
  swap_until: string;
  can_swap: boolean;
  brief: string | null;
  brief_pending: boolean;
  name_on_wall: boolean;
  measures: Measures;
  glow_up: GlowUp | null;
  showcase_updated: string | null;
};

export type ConsoleOne = Tiered & {
  id: number;
  induction_no: number;
  number: number | null;
  name: string;
  email: string;
  status: "active" | "retired";
  way_in: string;
  idea_id: string | null;
  line: string | null;
  stage: string | null;
  brief: string | null;
  measures: Measures;
  since: string;
  lapses_on: string;
  lapsed: boolean;
  retired_at: string | null;
  legend_number: number | null;
  announced: boolean;
  showcase_updated: string | null;
};

export type Proposal = {
  id: number;
  kind: "include" | "remove" | "tier_up" | "tier_down" | "impact_brief" | "legend";
  kind_words: string;
  state: "proposed" | "approved" | "declined" | "carried_out" | "withdrawn";
  one_id: number | null;
  subject: string | null;
  way_in: string | null;
  idea_id: string | null;
  tier_from: number | null;
  tier_to: number | null;
  tier_to_name: string | null;
  reason: string | null;
  text: string | null;
  proposed_by: string | null;
  proposed_by_id: string;
  proposed_at: string;
  approval: "chair" | "majority" | null;
  meeting_on: string | null;
  decided_by: string | null;
  decided_at: string | null;
  carried_out_by: string | null;
  messages: { from: string; name: string }[];
  invited: string[];
  committee_message: boolean;
};

export type OnesConsole = {
  ones: ConsoleOne[];
  proposals: Proposal[];
  resting: { number: number; until: string }[];
  legends: { number: number; one_id: number }[];
  last_allocated: number;
  screen_mode: "static" | "ambient";
  awards: { year: number; category: string; one_id: number; name: string }[];
  active: number;
};

export type ShowcaseBrief = Tiered & {
  one_id: number;
  number: number | null;
  name: string;
  measures: Measures;
  updated_at: string | null;
  parts: { key: string; own: string; from_record: string | null }[];
};

async function call<T>(
  path: string,
  init: RequestInit = {},
  fallback = "ones_unavailable",
  timeoutMs = 30_000,
): Promise<T> {
  const res = await workerFetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
    signal: AbortSignal.timeout(timeoutMs),
  });
  const out = (await res.json().catch(() => ({ error: fallback }))) as Record<string, unknown>;
  if (!res.ok) throw new SubmissionError(res.status, String(out.error ?? fallback));
  return out as T;
}

const post = <T>(path: string, body: Record<string, unknown>, method = "POST") =>
  call<T>(path, { method, body: JSON.stringify(body) });

const id = (value: string) => {
  if (!/^[0-9]{1,12}$/.test(value)) throw new SubmissionError(404, "not_found");
  return value;
};

const body = (input: unknown): Record<string, unknown> =>
  input && typeof input === "object" && !Array.isArray(input) ? (input as Record<string, unknown>) : {};

// --- Reads -------------------------------------------------------------------------------------------------------

export type OnesList = { paused: boolean; ones: PublicOne[] };

/** Who has hidden their name from the Wall in Profile (`person_settings.show_name_on_wall`, DEC-104). */
export interface WallNameSettings {
  /** The induction numbers, of those given, whose One has switched their name off. No row: not hidden. */
  hiddenFor(inductionNos: number[]): Promise<Set<number>>;
}

export const pgWallNameSettings: WallNameSettings = {
  async hiddenFor(inductionNos) {
    if (inductionNos.length === 0) return new Set();
    const rows = await getDb()
      .selectFrom("ones")
      .innerJoin("person_settings", "person_settings.user_id", "ones.user_id")
      .select("ones.induction_no")
      .where("ones.induction_no", "in", inductionNos)
      .where("person_settings.show_name_on_wall", "=", false)
      .execute();
    return new Set(rows.map((r) => r.induction_no));
  },
};

let nameSettings: WallNameSettings = pgWallNameSettings;

export function setWallNameSettings(next: WallNameSettings) {
  nameSettings = next;
}

/**
 * P-PRODUCT.privacy "The sharer's name on the Wall: their choice, in Profile" (DEC-104): a One who switched their
 * name off shows by number only, wherever the Ones are shown. The worker still leaves out a name it has no consent
 * for; this never puts one back. If the switches cannot be read, no name shows (fail closed).
 */
async function withNamesHidden(list: OnesList): Promise<OnesList> {
  if (list.paused || !list.ones.some((o) => o.name)) return list;
  let hidden: Set<number> | null;
  try {
    hidden = await nameSettings.hiddenFor(list.ones.map((o) => o.induction_no));
  } catch {
    log.warn("ones.name_settings_unavailable");
    hidden = null;
  }
  return {
    ...list,
    ones: list.ones.map((o) => (hidden && !hidden.has(o.induction_no) ? o : { ...o, name: null })),
  };
}

/** Every active One, for signed-in people (the Wall, Home, `GET /api/ones`), names as their owners chose. */
export const wallOnes = async () => withNamesHidden(await call<OnesList>("/internal/ones/public"));

/**
 * The Ones signed-out people see (S-01 Landing, S-01.rules/3, A-API.ones): only Ones whose brief is public (the
 * committee approved it, and it passed its checks), names as their owners chose. `ones.public` off: none.
 * Landing passes a short `timeoutMs` so a slow worker never holds the front door (BLD-A172).
 */
export async function publicOnes(timeoutMs?: number): Promise<OnesList> {
  const list = await call<OnesList>("/internal/ones/public", {}, undefined, timeoutMs);
  if (list.paused) return { paused: true, ones: [] };
  return withNamesHidden({ paused: false, ones: list.ones.filter((o) => Boolean(o.brief?.trim())) });
}

export const constellation = () =>
  call<{
    paused: boolean;
    mode: "static" | "ambient";
    sparks: (Tiered & { induction_no: number; active: boolean })[];
    cards: PublicOne[];
  }>("/internal/ones/constellation");

export const onesConsole = () => call<OnesConsole>("/internal/ones/console");

export const myOne = async (me: CurrentUser) =>
  (await call<{ one: MyOne | null }>(`/internal/me/${me.id}/one`)).one;

export async function leaderboard(me: CurrentUser) {
  const res = await workerFetch(`/internal/ones/leaderboard/${me.id}`);
  if (res.status === 403) return null;
  if (!res.ok) throw new SubmissionError(502, "leaderboard_unavailable");
  return (await res.json()) as {
    people: (Tiered & {
      rank: number;
      number: number;
      name: string | null;
      measures: Measures;
      you: boolean;
    })[];
    teams: {
      rank: number;
      lob: string;
      ones: number;
      top_tier: number;
      top_tier_name: string;
      measured: number;
    }[];
  };
}

export const myTeam = (me: CurrentUser) =>
  call<{
    people: {
      name: string;
      shared: number;
      building: number;
      shipped: number;
      one: (Tiered & { number: number }) | null;
    }[];
    totals: { shared: number; building: number; shipped: number };
    ones: number;
  }>(`/internal/me/${me.id}/team`);

export const showcaseFor = (oneId: string) => call<ShowcaseBrief>(`/internal/ones/${id(oneId)}/showcase`);

export async function myShowcase(me: CurrentUser) {
  const res = await workerFetch(`/internal/me/${me.id}/one/showcase`);
  if (res.status === 403) return null;
  if (!res.ok) throw new SubmissionError(502, "showcase_unavailable");
  return (await res.json()) as ShowcaseBrief;
}

export const inviteView = (me: CurrentUser, proposalId: string) =>
  call<{
    one_display: string;
    tier_to_name: string;
    as: "ceo" | "peer" | "committee" | null;
    written: boolean;
  }>(`/internal/ones/proposals/${id(proposalId)}/invite/${me.id}`);

// --- Writes ------------------------------------------------------------------------------------------------------

export const propose = (me: CurrentUser, input: unknown) =>
  post<{ id: number; state: string }>("/internal/ones/proposals", { ...body(input), actor_user_id: me.id });

export const decide = (me: CurrentUser, proposalId: string, input: unknown) =>
  post(`/internal/ones/proposals/${id(proposalId)}/decide`, { ...body(input), actor_user_id: me.id });

export const carryOut = (me: CurrentUser, proposalId: string) =>
  post(`/internal/ones/proposals/${id(proposalId)}/carry-out`, { actor_user_id: me.id });

export const withdraw = (me: CurrentUser, proposalId: string) =>
  post(`/internal/ones/proposals/${id(proposalId)}/withdraw`, { actor_user_id: me.id });

export const addMessage = (me: CurrentUser, proposalId: string, input: unknown) =>
  post(`/internal/ones/proposals/${id(proposalId)}/messages`, { ...body(input), actor_user_id: me.id });

export const invitePeer = (me: CurrentUser, proposalId: string, input: unknown) =>
  post(`/internal/ones/proposals/${id(proposalId)}/invites`, {
    email: body(input).email,
    actor_user_id: me.id,
  });

export const setMeasures = (me: CurrentUser, oneId: string, input: unknown) =>
  post(
    `/internal/ones/${id(oneId)}/measures`,
    { measures: body(input).measures, actor_user_id: me.id },
    "PUT",
  );

export const giveAward = (me: CurrentUser, oneId: string, input: unknown) =>
  post(`/internal/ones/${id(oneId)}/awards`, { ...body(input), actor_user_id: me.id });

export const setScreenMode = (me: CurrentUser, input: unknown) =>
  post("/internal/ones/screen-mode", { mode: body(input).mode, actor_user_id: me.id }, "PUT");

export const announce = (me: CurrentUser) => post("/internal/ones/announce", { actor_user_id: me.id });

export const swapNumber = (me: CurrentUser, input: unknown) =>
  post(`/internal/me/${me.id}/one/number`, { number: body(input).number });

export const proposeBrief = (me: CurrentUser, input: unknown) =>
  post(`/internal/me/${me.id}/one/brief`, { text: body(input).text });

export const glowUpSeen = (me: CurrentUser, glowId: string) =>
  post(`/internal/me/${me.id}/one/glow-up/${id(glowId)}/seen`, {});

export const saveShowcase = (me: CurrentUser, input: unknown) =>
  post(`/internal/me/${me.id}/one/showcase`, body(input), "PUT");
