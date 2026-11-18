"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import {
  createContext,
  useContext,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
  type Dispatch,
  type ReactNode,
  type MouseEvent,
  type SetStateAction,
} from "react";

import { backToSearchedList } from "@/lib/search-memory";

/** The page's way back: the breadcrumb (S-06) or the Back link (S-09), as the server drew it. */
export type Way = { label: string; to: string };

/** How the server was given `from` and `back` for this render: kept for the visit, once only (`from=share`, the
 * first arrival after sharing, S-06.rules/6), or not at all (a plain visit, a reload or a refresh). */
export type Carried = "keep" | "once" | null;

const KEY = "ipWayBack";
const WayContext = createContext<Way | null>(null);

/** The lists a kept way back may return to: the worker's `safe_back` allows these and no others
 * (services/worker/ideapage/shape.py, sharer.py and colleague.py). */
const BACK_TO = ["/wall", "/my-ideas"] as const;
/** A joined idea's way back to its lead idea, as the worker's `back_link` draws it from `REF` (colleague.py,
 * S-09.layout/1): the idea's page by its reference, with no query and nothing after it. */
const BACK_TO_LEAD = /^\/ideas\/IDEA-[0-9]{4}-[0-9]{6}$/;
const BACK_MAX = 600;

/** The way back this visit was given, kept across a reload and a refresh (BLD-E021). */
export function useWay(fallback: Way): Way {
  return useContext(WayContext) ?? fallback;
}

/**
 * A way back the page may restore from history (BLD-E044): `/wall` or `/my-ideas`, or a path under either, with its
 * query (the list's view), or exactly a lead idea's page, `/ideas/IDEA-YYYY-NNNNNN` (S-09.layout/1). Anything else is
 * refused, so `//host`, `/\host`, another scheme, a control character or a page outside these can never come back as
 * a link.
 */
export function allowedBack(to: string): boolean {
  if (!to || to.length > BACK_MAX || /[\\\u0000-\u001f\u007f]/.test(to)) return false;
  if (BACK_TO_LEAD.test(to)) return true;
  const end = to.search(/[?#]/);
  const path = end === -1 ? to : to.slice(0, end);
  return BACK_TO.some((list) => path === list || path.startsWith(`${list}/`));
}

/** This history entry's way back, if one was kept for this idea's page. Read only after mount, in an effect. */
function savedWay(path: string): Way | null {
  const s = (window.history.state as Record<string, unknown> | null)?.[KEY] as
    { path?: unknown; way?: { label?: unknown; to?: unknown } } | undefined;
  const label = s?.way?.label;
  const to = s?.way?.to;
  if (s?.path !== path || typeof label !== "string" || typeof to !== "string") return null;
  return allowedBack(to) ? { label, to } : null;
}

/** The way back this entry kept, loaded from history by an effect after mount and handed to render through
 * useSyncExternalStore, so a render never reads history (and the server's render and hydration agree). */
function keptStore() {
  let kept: Way | null = null;
  const listeners = new Set<() => void>();
  return {
    subscribe: (listener: () => void) => {
      listeners.add(listener);
      return () => void listeners.delete(listener);
    },
    get: (): Way | null => kept,
    load: (path: string) => {
      const s = savedWay(path);
      if (s?.to === kept?.to && s?.label === kept?.label) return;
      kept = s;
      listeners.forEach((l) => l());
    },
  };
}

/**
 * Where the person came from (P-ROUTES.state, BLD-E021). A list or the Wall opens `/ideas/:id?from=…&back=…`; the
 * server reads both and draws the way back to that exact view. Then:
 *
 * - `from` and `back` leave the address, so a copied or shared link is the idea's own (`/ideas/IDEA-2026-001481`);
 * - the way back is kept in this history entry's state, so a reload of the clean address, and the refresh after
 *   Withdraw or Restore, still go back to the same view. Another tab or another person opening the link has no such
 *   state and gets the default (My ideas for the sharer, the Wall for anyone else);
 * - `from=share` is the first arrival after sharing: its "Home" holds for this visit, a refresh included, and is never
 *   kept, so a reload does not arrive for the first time again.
 *
 * The kept way is keyed on this page's own route (`/ideas/:id` from useParams), never on window.location, and history
 * is read only in an effect after mount (BLD-E044). On a client move from one idea to the next, the address and the
 * history state are still the previous idea's while the next one first renders; reading them then would carry the
 * previous idea's way back over and write it into the new entry.
 */
export function WayBack({ way, carried, children }: { way: Way; carried: Carried; children: ReactNode }) {
  const { id } = useParams<{ id: string }>();
  const path = `/ideas/${id}`;
  // What the server drew from `from` and `back` on arrival holds for the visit, a refresh without them included
  const [given] = useState<Way | null>(() => (carried ? way : null));
  const [persist] = useState(carried === "keep");
  const [store] = useState(keptStore);
  const saved = useSyncExternalStore(store.subscribe, store.get, store.get);
  const held = given ?? saved;

  // Once mounted, with nothing given: take the way back this entry kept for this idea (a reload, a refresh)
  useEffect(() => {
    if (!given) store.load(path);
  }, [given, path, store]);

  // After every render: Next rewrites the entry's state on a refresh, so the way back is written again when missing
  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.pathname !== path && safeDecode(url.pathname) !== safeDecode(path)) return; // not this idea's entry
    // Only a way back a reload may take again is kept: a list's view, or a joined idea's lead (S-09.layout/1)
    const keep = (persist || saved) && held && allowedBack(held.to) ? held : null;
    if (url.searchParams.has("from") || url.searchParams.has("back")) {
      url.searchParams.delete("from");
      url.searchParams.delete("back");
      // Without the router's own keys, so the router takes the clean address too and a refresh asks for it. The
      // router copies its keys in; ours stays. No new history entry, and browser Back is untouched.
      window.history.replaceState(
        keep ? { [KEY]: { path, way: keep } } : {},
        "",
        url.pathname + url.search + url.hash,
      );
      return;
    }
    const now = savedWay(path);
    if (keep && (now?.to !== keep.to || now?.label !== keep.label)) {
      // The router's keys are in the current state, so it leaves this write alone
      window.history.replaceState(
        { ...(window.history.state ?? {}), [KEY]: { path, way: keep } },
        "",
        window.location.href,
      );
    }
  });

  return <WayContext.Provider value={held ?? way}>{children}</WayContext.Provider>;
}

function safeDecode(p: string): string {
  try {
    return decodeURIComponent(p);
  } catch {
    return p;
  }
}

/** A way back to a list (the Back link, S-06's breadcrumb): when the list the person came from holds a search this tab
 * keeps (My ideas), go back in history as browser Back does, so the search comes back with it; the link's own address
 * never holds one (J-BROWSE/3, DEC-110). Otherwise the link opens its address as it always has. */
export function backToList(to: string) {
  return (e: MouseEvent<HTMLAnchorElement>) => {
    if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    if (backToSearchedList(to)) e.preventDefault();
  };
}

/** The Back link: the whole label on desktop, the short one on a phone ("Back to the Wall", "Wall"). */
export function BackLink({ label, to }: { label: string; to: string }) {
  const short = label.replace(/^Back to (the )?/, "");
  return (
    <Link className="back ip-back" href={to} aria-label={label} onClick={backToList(to)}>
      <span className="ip-desk">{label}</span>
      <span className="ip-phone">{short}</span>
    </Link>
  );
}

/** S-09's Back link, from the way back this visit was given. */
export function KeptBackLink({ label, to }: Way) {
  const way = useWay({ label, to });
  return <BackLink label={way.label} to={way.to} />;
}

/** PhoneStatus.md (Controls, `copyAria`, `copyLive`): the reference button's name, and the polite line once copied. */
export const COPY_REF = {
  label: (ref: string) => `Copy reference ${ref}`,
  done: "Reference copied",
  said: (ref: string) => `Reference ${ref} copied`,
  // The browser would not copy: the line says so and gives the reference to note down
  // NOT DRAWN (BLD-E044): HR sign-off
  failed: (ref: string) => `Couldn't copy the reference. It's ${ref}.`,
};
const COPIED_FOR_MS = 2_500;

/**
 * S-06's phone reference by the way back, which copies itself (PhoneStatus.md). Copied, the button is named
 * "Reference copied" for a moment and the page's polite line says "Reference IDEA-… copied"; if the browser will not
 * copy, the line says so in plain words. `say` writes the page's status line.
 */
export function CopyRef({ value, say }: { value: string; say: Dispatch<SetStateAction<string>> }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);

  const copy = async () => {
    window.clearTimeout(timer.current);
    try {
      if (!navigator.clipboard) throw new Error("no clipboard");
      await navigator.clipboard.writeText(value);
    } catch {
      setCopied(false);
      say(COPY_REF.failed(value));
      return;
    }
    const line = COPY_REF.said(value);
    setCopied(true);
    say(line);
    timer.current = window.setTimeout(() => {
      setCopied(false);
      // Cleared with the button, so a second copy is said again
      say((s) => (s === line ? "" : s));
    }, COPIED_FOR_MS);
  };

  return (
    <button
      type="button"
      className="ip-copyref"
      aria-label={copied ? COPY_REF.done : COPY_REF.label(value)}
      onClick={() => void copy()}
    >
      {copied ? COPY_REF.done : value}
    </button>
  );
}
