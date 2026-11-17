"use client";

import Link from "next/link";
import { createContext, useContext, useEffect, useState, useSyncExternalStore, type ReactNode } from "react";

/** The page's way back: the breadcrumb (S-06) or the Back link (S-09), as the server drew it. */
export type Way = { label: string; to: string };

/** How the server was given `from` and `back` for this render: kept for the visit, once only (`from=share`, the
 * first arrival after sharing, S-06.rules/6), or not at all (a plain visit, a reload or a refresh). */
export type Carried = "keep" | "once" | null;

const KEY = "ipWayBack";
const WayContext = createContext<Way | null>(null);

/** The way back this visit was given, kept across a reload and a refresh (BLD-E021). */
export function useWay(fallback: Way): Way {
  return useContext(WayContext) ?? fallback;
}

/** This history entry's way back, if one was kept for this page. A path on this site only. */
function savedWay(path: string): Way | null {
  const s = (window.history.state as Record<string, unknown> | null)?.[KEY] as
    { path?: unknown; way?: { label?: unknown; to?: unknown } } | undefined;
  const label = s?.way?.label;
  const to = s?.way?.to;
  if (s?.path !== path || typeof label !== "string" || typeof to !== "string") return null;
  if (!to.startsWith("/") || to.startsWith("//")) return null;
  return { label, to };
}

/**
 * The way back for one visit: the one the server drew from `from` and `back`, or, on a reload of the clean address,
 * the one this history entry kept. Read through useSyncExternalStore, so the server's render and hydration agree
 * and the kept way shows straight after.
 */
function wayStore(given: Way | null, keep: boolean) {
  let held = given;
  let persist = keep;
  return {
    subscribe: () => () => undefined,
    get: (): Way | null => {
      if (!held) {
        const saved = savedWay(window.location.pathname);
        if (saved) {
          held = saved;
          persist = true;
        }
      }
      return held;
    },
    server: (): Way | null => given,
    persists: () => persist,
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
 */
export function WayBack({ way, carried, children }: { way: Way; carried: Carried; children: ReactNode }) {
  const [store] = useState(() => wayStore(carried ? way : null, carried === "keep"));
  const kept = useSyncExternalStore(store.subscribe, store.get, store.server) ?? way;

  // After every render: Next rewrites the entry's state on a refresh, so the way back is written again when missing
  useEffect(() => {
    const path = window.location.pathname;
    const url = new URL(window.location.href);
    const held = store.persists() ? store.get() : null;
    if (url.searchParams.has("from") || url.searchParams.has("back")) {
      url.searchParams.delete("from");
      url.searchParams.delete("back");
      // Without the router's own keys, so the router takes the clean address too and a refresh asks for it. The
      // router copies its keys in; ours stays. No new history entry, and browser Back is untouched.
      window.history.replaceState(
        held ? { [KEY]: { path, way: held } } : {},
        "",
        url.pathname + url.search + url.hash,
      );
      return;
    }
    const saved = savedWay(path);
    if (held && (saved?.to !== held.to || saved?.label !== held.label)) {
      // The router's keys are in the current state, so it leaves this write alone
      window.history.replaceState(
        { ...(window.history.state ?? {}), [KEY]: { path, way: held } },
        "",
        window.location.href,
      );
    }
  });

  return <WayContext.Provider value={kept}>{children}</WayContext.Provider>;
}

/** The Back link: the whole label on desktop, the short one on a phone ("Back to the Wall", "Wall"). */
export function BackLink({ label, to }: { label: string; to: string }) {
  const short = label.replace(/^Back to (the )?/, "");
  return (
    <Link className="back ip-back" href={to} aria-label={label}>
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
