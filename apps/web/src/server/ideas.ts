/**
 * The public pages (B7): the wall, My ideas and the idea page. The worker builds each view; this module decides
 * which view a person gets, from the same policy as every other permission (§3.1):
 *
 * - The person who shared the idea, the review desk, the core committee and admins get the full view, with
 *   values restored as `restoreMode` decides (the owner and the core committee see real values; the reviewer
 *   handling it too; anyone else on the desk, and admins without a logged reason, see neutral labels).
 * - Everyone else gets the public view, which the worker gives only for ideas the desk has accepted and
 *   everyone may see: the neutral summary, area, stage, colleague count and milestones (BLD-094).
 */
import type { CurrentUser } from "./auth/current";
import { getDb } from "./db";
import { restoreMode } from "./restore";
import { SubmissionError } from "./submissions";
import { workerFetch } from "./worker";

const IDEA_ID = /^IDEA-[0-9]{4}-[0-9]{6}$/;
const FULL_VIEW_ROLES = ["reviewer", "core_committee", "core_chair", "admin"];

export type PublicCard = {
  idea_id?: string;
  cluster_id?: string;
  summary: string;
  area: string | null;
  stage: string;
  colleagues: number;
  names?: string[];
};

export type Solution = {
  solution_id: string;
  title: string;
  description: string;
  owner_team: string | null;
  shipped_on: string | null;
};

export type Wall =
  | { paused: true }
  | {
      paused: false;
      recent: PublicCard[];
      picked: PublicCard[];
      in_garage: PublicCard[];
      shipped: PublicCard[];
      showcase: Solution[];
    };

export type MyIdea = {
  id: string;
  idea_id: string | null;
  one_line: string | null;
  area: string | null;
  shared_on: string;
  draft: boolean;
  stage: string;
  next_step: string;
  due: string | null;
};

export type Joined = {
  how: string;
  summary: string | null;
  with_desk: boolean;
  area: string | null;
  stage: string;
  idea_id: string | null;
};

export type MyIdeas = { ideas: MyIdea[]; joined: Joined[]; name_on_wall: boolean };

export type TimelineRow = { when: string; event: string; what: string; by?: string; note?: string };

export type IdeaPage =
  | { view: "public"; card: PublicCard; timeline: TimelineRow[] }
  | {
      view: "full";
      owner: boolean;
      idea_id: string;
      uuid?: string;
      card: Record<string, unknown>;
      area: string | null;
      visibility: string;
      strength: number | null;
      status: { stage: string; next_step: string | null; due: string | null };
      timeline: TimelineRow[];
      question?: { text: string; due: string } | null;
      can_disagree?: boolean;
    };

export async function wall(): Promise<Wall> {
  const res = await workerFetch("/internal/wall");
  if (!res.ok) throw new SubmissionError(502, "wall_unavailable");
  return (await res.json()) as Wall;
}

export async function myIdeas(me: CurrentUser): Promise<MyIdeas> {
  const res = await workerFetch(`/internal/me/${encodeURIComponent(me.id)}/ideas`);
  if (!res.ok) throw new SubmissionError(502, "ideas_unavailable");
  return (await res.json()) as MyIdeas;
}

export async function setNameOnWall(me: CurrentUser, on: unknown): Promise<{ name_on_wall: boolean }> {
  if (typeof on !== "boolean") throw new SubmissionError(400, "bad_request");
  const res = await workerFetch(`/internal/me/${encodeURIComponent(me.id)}/name-on-wall`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ on }),
  });
  if (!res.ok) throw new SubmissionError(502, "prefs_unavailable");
  return (await res.json()) as { name_on_wall: boolean };
}

/** Which view of an idea this person gets, and in which restore mode. */
export async function viewFor(
  me: CurrentUser,
  ideaId: string,
): Promise<{ view: "full" | "public"; mode: "real" | "neutral" } | null> {
  const idea = await getDb()
    .selectFrom("ideas")
    .select(["contributor_code"])
    .where("idea_id", "=", ideaId)
    .executeTakeFirst();
  if (!idea) return null;
  const owner = Boolean(me.contributorCode && me.contributorCode === idea.contributor_code);
  const desk = FULL_VIEW_ROLES.some((r) => me.roles.has(r));
  if (!owner && !desk) return { view: "public", mode: "neutral" };
  const item = await getDb()
    .selectFrom("review_items")
    .select(["assigned_to", "state"])
    .where("ref_id", "=", ideaId)
    .where("item_type", "=", "idea")
    .orderBy("id", "desc")
    .executeTakeFirst();
  const mode = restoreMode(
    { id: me.id, contributorCode: me.contributorCode, roles: [...me.roles] },
    {
      contributorCode: idea.contributor_code,
      reviewItem: item ? { assignedTo: item.assigned_to, state: item.state } : null,
    },
  );
  return { view: "full", mode };
}

export async function ideaPage(me: CurrentUser, ideaId: string): Promise<IdeaPage> {
  if (!IDEA_ID.test(ideaId)) throw new SubmissionError(404, "not_found");
  const choice = await viewFor(me, ideaId);
  if (!choice) throw new SubmissionError(404, "not_found");
  const q = new URLSearchParams({ view: choice.view, mode: choice.mode, user_id: me.id });
  const res = await workerFetch(`/internal/ideas/${ideaId}/page?${q.toString()}`);
  if (res.status === 404) throw new SubmissionError(404, "not_found");
  if (!res.ok) throw new SubmissionError(502, "idea_unavailable");
  return (await res.json()) as IdeaPage;
}
