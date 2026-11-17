/**
 * What the signed-in shell shows around every screen (C-SIDEBAR.rules/4, C-PHONE-TABS): the person's initials and
 * tier, the unread Inbox count, up to two drafts and up to three of their ideas. Fed from today's loaders until the
 * shared contracts land (A-API.me, A-API.inbox-count, A-API.my-drafts, A-API.my-ideas). The shell never stops a page
 * from rendering: each part that cannot be read in time is simply left out.
 */
import { cookies, headers } from "next/headers";

import { DEVICE_COOKIE } from "@/lib/compose/client";
import type { CommitteeResponse, DeskResponse, DraftListItem } from "@/lib/contracts";
import { TIER_NAME } from "@/lib/contracts/enums";

import type { CurrentUser } from "./auth/current";
import { getDb } from "./db";
import { deskRead } from "./desk";
import { drafts as draftApi, type DeviceInfo } from "./drafts";
import { myIdeas, type MyIdea } from "./ideas";
import { inboxCounts } from "./inbox";

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

const QUIET = new Set([
  "shipped",
  "not_now",
  "not_picked",
  "declined",
  "withdrawn",
  "merged",
  "closed",
  "archived",
  "redirected",
]);
const NEEDS_YOU = new Set(["needs_info", "needs_you", "asked"]);

export function toneFor(stageKey: string): ShellRow["tone"] {
  if (NEEDS_YOU.has(stageKey)) return "warn";
  if (QUIET.has(stageKey)) return "neutral";
  return "blue";
}

/** When a draft was last saved, in the sidebar's words: "Today", "Yesterday", "Friday", else "12 Nov". India time. */
export function whenSaved(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "";
  const then = new Date(iso);
  if (Number.isNaN(then.getTime())) return "";
  const dayKey = (d: Date) => d.toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
  const days = Math.round((Date.parse(dayKey(now)) - Date.parse(dayKey(then))) / 86_400_000);
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days < 7) return then.toLocaleDateString("en-IN", { weekday: "long", timeZone: "Asia/Kolkata" });
  return then.toLocaleDateString("en-IN", { day: "numeric", month: "short", timeZone: "Asia/Kolkata" });
}

function titleOf(idea: MyIdea): string {
  return idea.one_line?.trim() || (idea.draft ? "Untitled draft" : "Your idea");
}

const PHONE_UA = /Mobi|Android|iPhone|iPod|Windows Phone/i;
const DEVICE_ID = /^[A-Za-z0-9_-]{8,64}$/;

/** The device asking, from the request (as `deviceOf` in server/drafts.ts), so a draft reads "on your phone" or
 * "on this laptop". A page load sends no `X-Device-Id`, so the browser's id comes from the `device_id` cookie the
 * draft client sets (BLD-C147). Outside a request (tests) it is a laptop with no id. */
export async function askingDevice(): Promise<DeviceInfo> {
  try {
    const h = await headers();
    const jar = await cookies();
    const said = h.get("x-device");
    const kind =
      said === "phone" || said === "laptop"
        ? said
        : PHONE_UA.test(h.get("user-agent") ?? "")
          ? "phone"
          : "laptop";
    const id = h.get("x-device-id") ?? jar.get(DEVICE_COOKIE)?.value ?? null;
    return { kind, id: id && DEVICE_ID.test(id) ? id : null };
  } catch {
    return { kind: "laptop", id: null };
  }
}

/** C-SIDEBAR "Drafts": up to two of the person's drafts (L-DRAFT, `GET /api/drafts`), newest first, each with when
 * and where it was saved ("Friday, on your phone"), opening S-04B on that draft (P-ROUTES.nav/5, BLD-C147). */
export function draftRows(items: DraftListItem[] | null | undefined): ShellRow[] {
  return (items ?? [])
    .filter((d) => !d.archived)
    .slice(0, 2)
    .map<ShellRow>((d) => ({
      href: `/share/${d.id}`,
      title: d.title?.trim() || "Untitled draft",
      meta: d.saved_labels?.sidebar ?? whenSaved(d.saved_at),
      tone: "draft",
    }));
}

/** C-SIDEBAR.anatomy, "Your ideas": the dot's words are the idea's own stage, as its page names it. */
export function ideaRow(idea: MyIdea): ShellRow {
  return {
    href: `/ideas/${idea.idea_id}`,
    title: titleOf(idea),
    tone: toneFor(idea.stage_key),
    words: idea.stage.trim() || undefined,
  };
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
 * closing soonest; each opens its row in place on the committee's page. */
export function committeeRows(committee: Pick<CommitteeResponse, "items"> | null): ShellRow[] {
  return (committee?.items ?? [])
    .filter((r) => r.window.state === "open" || r.window.state === "extended")
    .slice(0, 3)
    .map((r) => ({
      href: `/committee?open=${encodeURIComponent(r.window_id)}`,
      title: r.idea.title,
      meta: r.window.left ?? undefined,
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
  const device = await askingDevice();
  // Each section only for whoever has its sidebar item (policy/rbac.yaml navigation:), so a read the worker would
  // refuse (BLD-B232) is never made.
  const onNav = (key: string) => me.nav.some((n) => n.key === key);
  const [mine, counts, tier, saved, desk, committee] = await Promise.all([
    inTime(myIdeas(me)),
    inTime(inboxCounts(me)),
    inTime(myTier(me)),
    me.contributorCode
      ? inTime(
          draftApi.list(me, device, false).then((r) => (r.body as { items?: DraftListItem[] }).items ?? []),
        )
      : Promise.resolve(null),
    onNav("desk")
      ? inTime(deskRead<DeskResponse>(me, "/internal/desk", { tab: "waiting", sort: "time_left" }))
      : null,
    onNav("committee")
      ? inTime(deskRead<CommitteeResponse>(me, "/internal/committee", { tab: "window", sort: "closing" }))
      : null,
  ]);
  const ideas = mine?.ideas ?? [];
  const drafts = draftRows(saved);
  const shared = ideas
    .filter((i) => !i.draft && i.idea_id)
    .slice(0, 3)
    .map(ideaRow);
  return {
    name: me.name,
    initials: initialsOf(me.name),
    tier,
    tierName: tierName(tier),
    inboxUnread: counts?.unread ?? 0, // L-INBOX.rules/1: the Inbox's own unread count
    drafts,
    ideas: shared,
    ...(desk ? { desk: deskRows(desk) } : {}),
    ...(committee ? { committee: committeeRows(committee) } : {}),
  };
}
