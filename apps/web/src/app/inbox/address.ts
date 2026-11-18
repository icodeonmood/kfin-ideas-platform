/**
 * S-H5's address (P-ROUTES.state, J-BROWSE/4 and /6): the Inbox keeps its tab and the open item in the query string,
 * as the review desk and My ideas keep theirs, so Back, a reload or a link shows the same view:
 * `/inbox?tab=needs_you&item=41`. On an item's own address (`/inbox/:itemId`, S-H2B) the same query follows the path
 * once the person moves, so the page is never swapped under them. The search is never in it, on either address
 * (DEC-110): it stays in this tab's memory of the history entry (`lib/search-memory`), and the list filters in the
 * browser, so its words go to no server at all.
 *
 * Read on the server and in the reader with the same rules, so the two always agree: a tab it does not know is All,
 * an item that is not a notification's number is none, and an item opens only if it is in the person's own list for
 * that tab (the worker scopes the list to the reader; the address never fetches an item by itself).
 */
import type { InboxTab } from "@/lib/contracts";
import { SEARCH_MAX } from "@/lib/search-memory";

/** The reader's view: the tab, the open item and the search (the search kept apart from the address). */
export type InboxView = { tab: InboxTab; item: string | null; q: string };

/** What an address asks for; `named` is false when it asks for nothing, so the page's own default holds. A `q` in an
 * older address is not read: a link never brings a search with it (J-BROWSE/6, DEC-110). */
export type InboxAddress = Omit<InboxView, "q"> & { named: boolean };

type Params = Pick<URLSearchParams, "get"> | Record<string, string | string[] | undefined> | null | undefined;

const TABS: readonly InboxTab[] = ["all", "needs_you", "unread", "archived"];
/** As `isItemId` in `server/inbox.ts`: an item is the notification's number. */
const ITEM = /^[0-9]{1,18}$/;
/** The Inbox's own addresses, the only ones the reader writes over. */
const PATH = /^\/inbox(?:\/[0-9]{1,18})?$/;

function one(params: Params, key: string): string | null {
  if (!params) return null;
  if (typeof params.get === "function") return (params as Pick<URLSearchParams, "get">).get(key);
  const v = (params as Record<string, string | string[] | undefined>)[key];
  return (Array.isArray(v) ? v[0] : v) ?? null;
}

export function readInboxAddress(params: Params): InboxAddress {
  const tab = one(params, "tab");
  const item = one(params, "item");
  return {
    named: tab !== null || item !== null,
    tab: TABS.find((t) => t === tab) ?? "all",
    item: item !== null && ITEM.test(item) ? item : null,
  };
}

/** The address for a view on the Inbox page the person is on (`/inbox` or `/inbox/:itemId`). The tab is always
 * written, so an item's own address that carries a query is read as the view the person moved to. Never the search. */
export function inboxHref(path: string, view: Omit<InboxView, "q">): string {
  const params = new URLSearchParams({ tab: view.tab });
  if (view.item) params.set("item", view.item);
  return `${PATH.test(path) ? path : "/inbox"}?${params.toString()}`;
}

export function isInboxPath(path: string): boolean {
  return PATH.test(path);
}

/** The item the address names, only when it is in the person's own list; anything else opens nothing. */
export function itemIn(item: string | null, items: readonly { id: string }[]): string | null {
  return item !== null && items.some((i) => i.id === item) ? item : null;
}

/** The search box's words as the Inbox keeps them. */
export function inboxSearch(q: string): string {
  return q.slice(0, SEARCH_MAX);
}
