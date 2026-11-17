"use client";

import { useEffect } from "react";

/**
 * Once the page has read `from` and `back` (where the person came from, P-ROUTES.state), they leave the address, so
 * the idea's link is its own (`/ideas/IDEA-2026-001481`) when someone copies it to a colleague. The page keeps the
 * way back it was given; Back in the browser is untouched (BLD-E021).
 */
export function CleanAddress() {
  useEffect(() => {
    const url = new URL(window.location.href);
    if (!url.searchParams.has("from") && !url.searchParams.has("back")) return;
    url.searchParams.delete("from");
    url.searchParams.delete("back");
    window.history.replaceState(window.history.state, "", url.pathname + url.search + url.hash);
  }, []);
  return null;
}
