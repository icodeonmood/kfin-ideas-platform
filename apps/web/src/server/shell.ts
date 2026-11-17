/**
 * What the signed-in shell shows around every screen (C-SIDEBAR.rules/4, C-PHONE-TABS): the person's initials and
 * tier, the unread Inbox count, up to two drafts and up to three of their ideas. Fed from today's loaders until the
 * shared contracts land (A-API.me, A-API.inbox-count, A-API.my-drafts, A-API.my-ideas). The shell never stops a page
 * from rendering: each part that cannot be read in time is simply left out.
 */
import { headers } from "next/headers";

import type { DraftListItem } from "@/lib/contracts";

import type { CurrentUser } from "./auth/current";
import { drafts as draftApi, type DeviceInfo } from "./drafts";
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

const PHONE_UA = /Mobi|Android|iPhone|iPod|Windows Phone/i;
const DEVICE_ID = /^[A-Za-z0-9_-]{8,64}$/;

/** The device asking, from the request (as `deviceOf` in server/drafts.ts), so a draft reads "on your phone" or
 * "on this laptop". Outside a request (tests) it is a laptop with no id. */
async function askingDevice(): Promise<DeviceInfo> {
  try {
    const h = await headers();
    const said = h.get("x-device");
    const kind =
      said === "phone" || said === "laptop"
        ? said
        : PHONE_UA.test(h.get("user-agent") ?? "")
          ? "phone"
          : "laptop";
    const id = h.get("x-device-id");
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

export async function shellData(me: CurrentUser): Promise<ShellData> {
  const device = await askingDevice();
  const [mine, messages, one, saved] = await Promise.all([
    inTime(myIdeas(me)),
    inTime(messagesFor(me)),
    inTime(myOne(me)),
    me.contributorCode
      ? inTime(
          draftApi.list(me, device, false).then((r) => (r.body as { items?: DraftListItem[] }).items ?? []),
        )
      : Promise.resolve(null),
  ]);
  const ideas = mine?.ideas ?? [];
  const drafts = draftRows(saved);
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
