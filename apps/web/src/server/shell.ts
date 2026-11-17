/**
 * What the signed-in shell shows around every screen (C-SIDEBAR.rules/4, C-PHONE-TABS): the person's initials and
 * tier, the unread Inbox count, up to two drafts and up to three of their ideas. Fed from today's loaders until the
 * shared contracts land (A-API.me, A-API.inbox-count, A-API.my-drafts, A-API.my-ideas). The shell never stops a page
 * from rendering: each part that cannot be read in time is simply left out.
 */
import type { CurrentUser } from "./auth/current";
import { myIdeas, type MyIdea } from "./ideas";
import { messagesFor } from "./inbox";
import { myOne } from "./ones";

/** A row in a sidebar section. `tone` is the status dot (C-SIDEBAR.anatomy/4): warn for "needs you", blue for
 * active, neutral otherwise; drafts take the hollow dot. */
export type ShellRow = {
  href: string;
  title: string;
  meta?: string;
  tone: "draft" | "warn" | "blue" | "bad" | "neutral";
};

export type ShellData = {
  name: string;
  initials: string;
  /** 1 to 7 when the person is a One (F-COLOR.tiers/1: their own account button keeps the tier ring). */
  tier: number | null;
  tierName: string | null;
  inboxUnread: number;
  drafts: ShellRow[];
  ideas: ShellRow[];
  /** Reviewer: "Waiting on sharers"; committee: "Closing soonest". Filled by lanes B once L-REVIEW and L-COMMITTEE land. */
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

export async function shellData(me: CurrentUser): Promise<ShellData> {
  const [mine, messages, one] = await Promise.all([
    inTime(myIdeas(me)),
    inTime(messagesFor(me)),
    inTime(myOne(me)),
  ]);
  const ideas = mine?.ideas ?? [];
  const drafts = ideas
    .filter((i) => i.draft)
    .slice(0, 2)
    .map<ShellRow>((i) => ({
      href: `/share/${i.id}`,
      title: titleOf(i),
      meta: whenSaved(i.shared_on),
      tone: "draft",
    }));
  const shared = ideas
    .filter((i) => !i.draft && i.idea_id)
    .slice(0, 3)
    .map<ShellRow>((i) => ({ href: `/ideas/${i.idea_id}`, title: titleOf(i), tone: toneFor(i.stage_key) }));
  const active = one?.active ? one : null;
  return {
    name: me.name,
    initials: initialsOf(me.name),
    tier: active?.tier ?? null,
    tierName: active?.tier_name ?? null,
    inboxUnread: messages?.filter((m) => !m.read).length ?? 0,
    drafts,
    ideas: shared,
  };
}
