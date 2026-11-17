/**
 * L-INBOX (S-H5, A-API.inbox): the person's Inbox from the worker, which renders every item for them from IDs and
 * the HR-signed templates. The tab counts, the unread total and Home's "Needs you" come from the same rows, so the
 * sidebar, the tab bar, Home and the Inbox always agree (L-INBOX.rules/1, V-ACC.track/8). Only the E-ENUMS.inbox
 * kinds are Inbox items; messages the old routes still write go by email (BLD-A186, BLD-A202).
 */
import type { Action, InboxItem, InboxTab, PersonRef } from "@/lib/contracts";

import type { CurrentUser } from "./auth/current";
import { workerFetch } from "./worker";

/** L-HIDE/7's kind, agreed with lane C (BLD-A205); it joins `InboxKind` when lane C's c/hide adds it to the enums. */
export type InboxEntryKind = InboxItem["kind"] | "detail_hidden_by_desk";

export type InboxEntry = Omit<InboxItem, "kind" | "body"> & {
  kind: InboxEntryKind;
  body: {
    /** The reader's kind line: "Questions from the review desk", "Merge request". */
    heading: string;
    /** The reader's short note: "Answer by Thursday 19 November, 6 pm." */
    note: string;
    /** The sender as the row shows them: "Meera from the review desk", "1% Club", "The review desk". */
    sender: string;
    count?: number;
    set_id?: string;
    decision_id?: string;
    request_id?: string;
    merge_id?: string;
    window_id?: string;
    entry_id?: string;
    worth_id?: string;
  };
};

export type InboxCounts = Record<InboxTab, number>;
export type InboxList = { items: InboxEntry[]; total: number; counts: InboxCounts; unread: number };
export type { Action, PersonRef };

export const TABS: readonly InboxTab[] = ["all", "needs_you", "unread", "archived"];

export function isTab(value: string | null | undefined): value is InboxTab {
  return !!value && (TABS as readonly string[]).includes(value);
}

/** Item IDs are the notification's number; anything else is refused before it reaches the worker. */
export function isItemId(id: string): boolean {
  return /^[0-9]{1,18}$/.test(id);
}

const base = (me: CurrentUser) => `/internal/inbox/${encodeURIComponent(me.id)}`;

export async function inboxFor(me: CurrentUser, tab: InboxTab = "all"): Promise<InboxList> {
  const res = await workerFetch(`${base(me)}?tab=${tab}`);
  if (!res.ok) throw new Error(`inbox ${res.status}`);
  return (await res.json()) as InboxList;
}

/** Every tab's count: `unread` is the sidebar and tab-bar number, `needs_you` Home's total (L-INBOX.rules/1). */
export async function inboxCounts(me: CurrentUser): Promise<InboxCounts> {
  const res = await workerFetch(`${base(me)}/counts`);
  if (!res.ok) throw new Error(`inbox counts ${res.status}`);
  return (await res.json()) as InboxCounts;
}

export async function needsYou(me: CurrentUser): Promise<{ total: number; top: InboxEntry[] }> {
  const res = await workerFetch(`${base(me)}/needs-you`);
  if (!res.ok) throw new Error(`inbox needs-you ${res.status}`);
  return (await res.json()) as { total: number; top: InboxEntry[] };
}

/** `read`, `unread`, `archive`, `read-all` or `actions/<op>`: the worker's answer, passed on as it is. */
export async function inboxWrite(me: CurrentUser, id: string | null, verb: string): Promise<Response> {
  const path = id === null ? `${base(me)}/${verb}` : `${base(me)}/${id}/${verb}`;
  return workerFetch(path, { method: "POST" });
}
