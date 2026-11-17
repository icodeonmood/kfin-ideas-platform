/**
 * What the signed-in shell shows around every screen (C-SIDEBAR.rules/4, C-PHONE-TABS): the person's initials and
 * tier, the unread Inbox count, up to two drafts and up to three of their ideas. Drafts and ideas come from A-API.me's
 * shell lists (lane E, BLD-E047), ordered and dotted by S-07's own helpers so the sidebar and My ideas agree. The shell
 * never stops a page from rendering: each part that cannot be read in time is simply left out.
 */
import type { CommitteeResponse, DeskResponse, ShellResponse } from "@/lib/contracts";
import { TIER_NAME } from "@/lib/contracts/enums";

import type { CurrentUser } from "./auth/current";
import { getDb } from "./db";
import { deskRead } from "./desk";
import { inboxCounts } from "./inbox";
import { workerFetch } from "./worker";

/** A row in a sidebar section. `tone` is the status dot (C-SIDEBAR.anatomy/4): warn for "needs you", blue for
 * active, neutral otherwise; drafts take the hollow dot. `words` says what the dot means in this section, so it is
 * never colour alone (F-A11Y.rules/4); without it the sidebar uses its own words for the tone. */
export type ShellRow = {
  href: string;
  title: string;
  meta?: string;
  tone: "draft" | "warn" | "blue" | "bad" | "neutral";
  words?: string;
};

export type ShellData = {
  name: string;
  initials: string;
  /** 1 to 7 for everyone (L-ONES.rules/4); null only when it cannot be read. Their own account button keeps the tier
   * ring (F-COLOR.tiers/1) and says "Tier 3, Flame" (C-SIDEBAR.anatomy/5). */
  tier: number | null;
  /** The tier's name from E-ENUMS.tier ("Flame"). */
  tierName: string | null;
  inboxUnread: number;
  drafts: ShellRow[];
  ideas: ShellRow[];
  /** Reviewer: "Waiting on sharers"; committee: "Closing soonest" (lane B: `deskRows`, `committeeRows`), up to 3 each. */
  desk?: ShellRow[];
  committee?: ShellRow[];
};

const WAIT_MS = 2_500;

function inTime<T>(work: Promise<T>): Promise<T | null> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const late = new Promise<null>((resolve) => {
    timer = setTimeout(() => resolve(null), WAIT_MS);
  });
  return Promise.race([work.catch(() => null), late]).finally(() => clearTimeout(timer));
}

/** "KM" from "Kavya Menon"; one name gives its first two letters. */
export function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  const letters = parts.length === 1 ? parts[0]!.slice(0, 2) : parts[0]![0]! + parts[parts.length - 1]![0]!;
  return letters.toUpperCase();
}

/** A-API.me (shell), lane E's `GET /internal/me/{id}/shell-lists` (BLD-E047): up to two drafts and three ideas.
 * `status_label` is the idea's stage in S-07's words; until the read sends it, the sidebar says the tone's own words. */
export type ShellLists = {
  drafts: ShellResponse["drafts"];
  ideas: (ShellResponse["ideas"][number] & { status_label?: string })[];
};

/** `deviceId` is the browser's id (lane C's `device_id` cookie), so a draft reads "on your phone" or "on this laptop". */
export async function shellLists(me: CurrentUser, deviceId?: string | null): Promise<ShellLists> {
  const query = deviceId ? `?device_id=${encodeURIComponent(deviceId)}` : "";
  const res = await workerFetch(`/internal/me/${encodeURIComponent(me.id)}/shell-lists${query}`, {
    cache: "no-store",
  });
  if (!res.ok) throw new Error("shell_lists_unavailable");
  return (await res.json()) as ShellLists;
}

const IDEA_DOTS: ReadonlySet<string> = new Set(["warn", "blue", "neutral"]);

/** C-SIDEBAR.anatomy/4: "Drafts" (hollow dot, "Friday, on your phone") link to Tell it; "Your ideas" link to the idea,
 * their dot as S-07 sets it and, when sent, the stage in words so the dot is never colour alone (F-A11Y.rules/4). */
export function listRows(lists: ShellLists | null): { drafts: ShellRow[]; ideas: ShellRow[] } {
  const drafts = (lists?.drafts ?? []).slice(0, 2).map<ShellRow>((d) => ({
    href: `/share/${encodeURIComponent(d.id)}`,
    title: d.title,
    ...(d.saved_label ? { meta: d.saved_label } : {}),
    tone: "draft",
  }));
  const ideas = (lists?.ideas ?? []).slice(0, 3).map<ShellRow>((i) => ({
    href: `/ideas/${encodeURIComponent(i.id)}`,
    title: i.title,
    tone: IDEA_DOTS.has(i.status_dot) ? (i.status_dot as ShellRow["tone"]) : "neutral",
    ...(i.status_label?.trim() ? { words: i.status_label.trim() } : {}),
  }));
  return { drafts, ideas };
}

/** C-SIDEBAR.anatomy, the review desk's "Waiting on sharers": the three most urgent, as the desk read sorts them
 * (L-REVIEW.queue). Dots: blue normal, amber under a day, red overdue (S-R1.rules/5). */
const DESK_TONE: Record<DeskResponse["waiting_on_sharers"][number]["dot"], ShellRow["tone"]> = {
  blue: "blue",
  amber: "warn",
  red: "bad",
};

/** The dots in words, from the desk's own copy (reference/copy/Desk.md): its tab "Waiting on the sharer" and its
 * summary line ("One is overdue and one has under a day left"). Amber here is not "Needs you". */
const DESK_WORDS: Record<DeskResponse["waiting_on_sharers"][number]["dot"], string> = {
  blue: "Waiting on the sharer",
  amber: "Under a day left",
  red: "Overdue",
};

export function deskRows(desk: Pick<DeskResponse, "waiting_on_sharers"> | null): ShellRow[] {
  return (desk?.waiting_on_sharers ?? []).slice(0, 3).map((w) => ({
    href: `/desk/ideas/${encodeURIComponent(w.idea_id)}`,
    title: w.title,
    tone: DESK_TONE[w.dot],
    words: DESK_WORDS[w.dot],
  }));
}

/** C-SIDEBAR.anatomy, the Ones Committee's "Closing soonest" (S-R4.rules/4): the first three in the window, sorted by
 * closing soonest; each opens its row in place on the committee's page. Title only, as the Committee board draws
 * them: the countdown stays on S-R4 itself. */
export function committeeRows(committee: Pick<CommitteeResponse, "items"> | null): ShellRow[] {
  return (committee?.items ?? [])
    .filter((r) => r.window.state === "open" || r.window.state === "extended")
    .slice(0, 3)
    .map((r) => ({
      href: `/committee?open=${encodeURIComponent(r.window_id)}`,
      title: r.idea.title,
      tone: "blue",
    }));
}

/** L-ONES.rules/3–4: an active One's tier, else the person's own (`users.tier`, never null). One read, and nothing
 * else of the One or of points; myOne() stays for the One-only screens. */
export async function myTier(me: CurrentUser): Promise<number | null> {
  const row = await getDb()
    .selectFrom("users as u")
    .leftJoin("ones as o", (join) =>
      join.onRef("o.user_id", "=", "u.id").on("o.status", "=", "active").on("o.number", "is not", null),
    )
    .select((eb) => eb.fn.coalesce("o.tier", "u.tier").as("tier"))
    .where("u.id", "=", me.id)
    .executeTakeFirst();
  return row?.tier ?? null;
}

const tierName = (tier: number | null): string | null =>
  tier === null ? null : (TIER_NAME[String(tier) as keyof typeof TIER_NAME] ?? null);

export async function shellData(me: CurrentUser): Promise<ShellData> {
  // Each section only for whoever has its sidebar item (policy/rbac.yaml navigation:), so a read the worker would
  // refuse (BLD-B232) is never made.
  const onNav = (key: string) => me.nav.some((n) => n.key === key);
  const [lists, counts, tier, desk, committee] = await Promise.all([
    inTime(shellLists(me)),
    inTime(inboxCounts(me)),
    inTime(myTier(me)),
    onNav("desk")
      ? inTime(deskRead<DeskResponse>(me, "/internal/desk", { tab: "waiting", sort: "time_left" }))
      : null,
    onNav("committee")
      ? inTime(deskRead<CommitteeResponse>(me, "/internal/committee", { tab: "window", sort: "closing" }))
      : null,
  ]);
  const { drafts, ideas } = listRows(lists);
  return {
    name: me.name,
    initials: initialsOf(me.name),
    tier,
    tierName: tierName(tier),
    inboxUnread: counts?.unread ?? 0, // L-INBOX.rules/1: the Inbox's own unread count
    drafts,
    ideas,
    ...(desk ? { desk: deskRows(desk) } : {}),
    ...(committee ? { committee: committeeRows(committee) } : {}),
  };
}
