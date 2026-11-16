"use client";

import { useEffect, type RefObject } from "react";

/**
 * A display covers the whole window (L-DISPLAY): while it is open, everything outside it (the header, banners,
 * footer, whatever shell the page sits in) leaves the tab order and the reading order, so focus never lands
 * somewhere hidden behind it. Walks up from the display, so it does not depend on the shell's class names.
 */
export function useDisplaySurface(root: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const made: HTMLElement[] = [];
    for (let el = root.current; el?.parentElement && el !== document.body; el = el.parentElement) {
      for (const sibling of Array.from(el.parentElement.children)) {
        if (sibling === el || !(sibling instanceof HTMLElement)) continue;
        // Scripts, styles and the framework's own custom elements (the route announcer) stay as they are.
        if (/^(SCRIPT|STYLE|TEMPLATE|LINK)$/.test(sibling.tagName) || sibling.tagName.includes("-")) continue;
        if (sibling.hasAttribute("inert")) continue;
        sibling.setAttribute("inert", "");
        made.push(sibling);
      }
    }
    return () => made.forEach((el) => el.removeAttribute("inert"));
  }, [root]);
}

/** Full screen on the display itself; a refusal (no gesture, not allowed) leaves the page as it is. */
export function fullScreen(el: HTMLElement | null) {
  el?.requestFullscreen?.().catch(() => undefined);
}

/** Whether the person asked for reduced motion, read once on the client. */
export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
