/**
 * Search words live in the tab's own page memory, never in a URL (DEC-110). A search can hold an idea's words or a
 * customer's details (non-negotiable 3, DEC-103), and a full request line can be written to a proxy's access log, to
 * browser history, to synced history and to every pasted link. So the words of My ideas (S-07), the review desk (S-R1)
 * and the Inbox (S-H5) are kept for the history entry the person searched on, and nowhere else: not the address bar,
 * not an API request's URL, not an idea page's `back=`, not sign-in's `next=`, never localStorage, a cookie or the
 * server. Tab, filter, sort, row and item stay in the URL as fixed choices and IDs (P-ROUTES.state), so a shared or
 * pasted link reproduces the view without the search (J-BROWSE/6).
 *
 * Two places, read in this order:
 *
 * 1. This tab's sessionStorage, keyed by the list and the history entry's own key (the Navigation API's
 *    `navigation.currentEntry.key`, the same across a reload and every `replaceState`, different for each entry). The
 *    App Router writes a history entry's state afresh on its own navigations (`router.replace`, `router.refresh`), so
 *    the state alone can lose the words; this record does not. A few recent entries are kept, then the oldest go.
 * 2. `window.history.state` of the entry, for a browser without the Navigation API. Every screen writes its words
 *    again after each change, so a state the router rewrote gets them back.
 *
 * A fresh visit (the sidebar, a typed or pasted address, another tab) is a new entry with neither, so its search is
 * empty. Back and a reload return to the same entry, so the search comes back with it (J-BROWSE/1 and /3).
 */

/** The search box's limit, on the client and again on the server. */
export const SEARCH_MAX = 200;

/** A list whose search this tab keeps: its path (`/inbox/:itemId`, S-H2B, is the Inbox's). */
export type SearchList = "/my-ideas" | "/desk" | "/inbox";

const LISTS: readonly SearchList[] = ["/my-ideas", "/desk", "/inbox"];
/** The key in a history entry's state. */
const STATE_KEY = "kfinSearch";
/** The one sessionStorage item, and how many entries it keeps. */
const STORE_KEY = "kfin.search";
const KEEP = 24;
/** The App Router's own keys in a history entry's state. */
const ROUTER_KEYS = ["__NA", "__PRIVATE_NEXTJS_INTERNALS_TREE"] as const;

type Kept = Record<string, { q: string; t: number }>;
type Entry = { key: string; index: number; url: string | null };
type NavigationLike = {
  currentEntry: Entry | null;
  canGoBack?: boolean;
  entries(): Entry[];
  /** How this document arrived on its entry (Navigation API). */
  activation?: { entry?: { key?: string } | null; navigationType?: string } | null;
};

/** The list a path belongs to, or null. */
export function listOf(pathname: string): SearchList | null {
  return LISTS.find((l) => pathname === l || pathname.startsWith(`${l}/`)) ?? null;
}

/** Words as a search box keeps them: at most SEARCH_MAX characters. */
export function clampSearch(q: unknown): string {
  return typeof q === "string" ? q.slice(0, SEARCH_MAX) : "";
}

function navigationApi(): NavigationLike | null {
  if (typeof window === "undefined") return null;
  const nav = (window as unknown as { navigation?: NavigationLike }).navigation;
  return nav && typeof nav.entries === "function" ? nav : null;
}

function entryKey(): string | null {
  const key = navigationApi()?.currentEntry?.key;
  return typeof key === "string" && key ? key : null;
}

const recordKey = (list: SearchList, key: string) => `${list} ${key}`;

function loadKept(): Kept {
  try {
    const raw = window.sessionStorage.getItem(STORE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? (parsed as Kept) : {};
  } catch {
    return {};
  }
}

function saveKept(kept: Kept): void {
  const newest = Object.entries(kept)
    .filter(([, v]) => v && typeof v.q === "string" && v.q && typeof v.t === "number")
    .sort(([, a], [, b]) => b.t - a.t)
    .slice(0, KEEP);
  try {
    if (newest.length) window.sessionStorage.setItem(STORE_KEY, JSON.stringify(Object.fromEntries(newest)));
    else window.sessionStorage.removeItem(STORE_KEY);
  } catch {
    // storage full or blocked: the entry's state still holds the words
  }
}

/** A page opened afresh onto an entry (a link or an address in the same tab) can take that entry's slot, and its
 * key, from the page before it: words kept there before this page loaded are not this visit's (J-BROWSE/6). A reload
 * and Back or Forward to a page arrive as "reload" and "traverse", and keep them. */
function fromBeforeThisPage(key: string, t: number): boolean {
  const a = navigationApi()?.activation;
  if (!a?.entry || a.entry.key !== key) return false;
  if (a.navigationType !== "push" && a.navigationType !== "replace") return false;
  return t < (typeof performance !== "undefined" ? performance.timeOrigin : 0);
}

function keptFor(list: SearchList, key: string): string | null {
  const v = loadKept()[recordKey(list, key)];
  if (!v || typeof v.q !== "string" || typeof v.t !== "number" || fromBeforeThisPage(key, v.t)) return null;
  return clampSearch(v.q);
}

function stateWords(list: SearchList): string | null {
  const s = (typeof window !== "undefined" ? window.history.state : null) as Record<string, unknown> | null;
  const mine = s?.[STATE_KEY] as Record<string, unknown> | undefined;
  return mine && typeof mine[list] === "string" ? clampSearch(mine[list]) : null;
}

/** For `useSyncExternalStore(noSubscription, () => readSearch(list), () => "")`: the server renders without a search,
 * and the browser's first render after hydration, or on a client move, reads the kept words. Nothing outside the
 * screen changes them while it is open, so there is nothing to listen to. */
export function noSubscription(): () => void {
  return () => undefined;
}

/** The words this tab keeps for the list on the current history entry, or "" when it keeps none. */
export function readSearch(list: SearchList): string {
  if (typeof window === "undefined") return "";
  const key = entryKey();
  const kept = key ? keptFor(list, key) : null;
  return kept ?? stateWords(list) ?? "";
}

/** Keeps the words for the list on the current history entry; "" forgets them. The address is left as it is. */
export function writeSearch(list: SearchList, q: string): void {
  if (typeof window === "undefined") return;
  const words = clampSearch(q);
  const key = entryKey();
  if (key) {
    const kept = loadKept();
    if (words) kept[recordKey(list, key)] = { q: words, t: Date.now() };
    else delete kept[recordKey(list, key)];
    saveKept(kept);
  }
  if ((stateWords(list) ?? "") === words) return;
  const s = (window.history.state ?? {}) as Record<string, unknown>;
  const mine = { ...((s[STATE_KEY] as Record<string, string> | undefined) ?? {}) };
  if (words) mine[list] = words;
  else delete mine[list];
  try {
    // The router's keys stay in, so the router leaves this write alone; the address does not change
    window.history.replaceState({ ...s, [STATE_KEY]: mine }, "", window.location.href);
  } catch {
    // a browser that limits how often history may be written: sessionStorage holds them
  }
}

/**
 * Replaces the address in the same history entry, keeping what the entry holds (its search words among them). The
 * App Router's own keys are left out, so the router takes the new address and copies its keys back in; nothing is
 * fetched and no entry is added. `href` names fixed choices and IDs only; any `q` in it is dropped.
 */
export function replaceAddress(href: string): void {
  if (typeof window === "undefined") return;
  const own = { ...((window.history.state ?? {}) as Record<string, unknown>) };
  for (const k of ROUTER_KEYS) delete own[k];
  try {
    window.history.replaceState(own, "", withoutSearch(href));
  } catch {
    // the next change writes it
  }
}

/** An older address that still names a search (`?q=`, from before DEC-110) loses it at once, so the words leave the
 * address bar and this history entry. The words themselves are not taken from it (J-BROWSE/6). */
export function cleanAddress(): void {
  if (typeof window === "undefined") return;
  if (!new URLSearchParams(window.location.search).has("q")) return;
  replaceAddress(window.location.pathname + window.location.search + window.location.hash);
}

/** A path and query on this site with any `q` taken out (an older link, a `back=` or a `next=`), as a path. */
export function withoutSearch(href: string): string {
  const hash = href.indexOf("#");
  const base = hash >= 0 ? href.slice(0, hash) : href;
  const tail = hash >= 0 ? href.slice(hash) : "";
  const at = base.indexOf("?");
  if (at < 0) return href;
  const params = new URLSearchParams(base.slice(at + 1));
  if (!params.has("q")) return href;
  params.delete("q");
  const qs = params.toString();
  return `${base.slice(0, at)}${qs ? `?${qs}` : ""}${tail}`;
}

/** Sign-in's and the privacy notice's `next=`: where to go afterwards, this path and query without a search's words
 * (an older link may still carry a `q`), encoded for the query string. */
export function nextParam(pathname: string, search: string): string {
  return encodeURIComponent(withoutSearch(pathname + search));
}

/**
 * The page's own Back link to a list (J-BROWSE/3, "browser or the page's own link"): when the entry before this one
 * is that list and it holds a search, go back to it as browser Back does, so the search comes back with it. Says
 * whether it did; when it did not (no Navigation API, another page before this one, no search there), the link
 * opens its address as before, with an empty search.
 */
export function backToSearchedList(to: string): boolean {
  if (typeof window === "undefined") return false;
  const nav = navigationApi();
  const current = nav?.currentEntry;
  if (!nav || !current || nav.canGoBack === false || current.index < 1) return false;
  let target: URL;
  try {
    target = new URL(to, window.location.href);
  } catch {
    return false;
  }
  const list = listOf(target.pathname);
  if (!list || target.origin !== window.location.origin) return false;
  const prev = nav.entries()[current.index - 1];
  if (!prev?.url) return false;
  const at = new URL(prev.url);
  if (at.origin !== window.location.origin || listOf(at.pathname) !== list) return false;
  if (!keptFor(list, prev.key)) return false;
  window.history.back();
  return true;
}
