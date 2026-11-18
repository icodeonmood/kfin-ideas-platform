"use client";

import { usePathname } from "next/navigation";
import { useEffect, useLayoutEffect, useRef } from "react";

import { reducedMotion } from "@/lib/motion/flip";

/**
 * Hand-overs between screens (F-MOTION.handover), for the app router. A click on a link records what was tapped;
 * when the next screen mounts, it grows out of it, before its first paint:
 *   - Grow from the card: a row or card opens into the next screen (a ghost of its surface grows to the content
 *     area), and the screen's content starts 380 ms later.
 *   - Flood from the button: ink spreads from "Share a problem" (or any ink link that starts a flow) and lifts off
 *     the new screen; content starts 420 ms later.
 *   - Fade through for the sidebar and tab bar, slide forward for Next and Continue, slide back for Back.
 * Every effect is one short animation on the effects layer that ends invisible, so nothing ever covers the page while
 * it waits for the server. The sidebar and tab bar never move. Reduced motion: none of it (F-MOTION.reduced/2).
 */
export type HandoverKind = "expand" | "portal" | "peer" | "fwd" | "back";

type Record = {
  kind: HandoverKind;
  at: number;
  x: number;
  y: number;
  rect: DOMRect;
  radius: number;
  bg: string;
};

const KINDS: HandoverKind[] = ["expand", "portal", "peer", "fwd", "back"];

/** On <html> while the new screen's content waits for the hand-over to play (motion.css sets --mo-base under it). */
export const ARRIVAL_WAIT = "mo-a-wait";
/** Longer than any arrival takes after the longest wait: a showcase screen's last block starts at 420 + 6 × 80 ms and
 * runs 1,000 ms (1,900 ms in all), so the wait never comes off while a block is still arriving. */
export const ARRIVAL_WAIT_MS = 2_000;

export function classifyLink(a: HTMLAnchorElement): HandoverKind {
  if (a.closest(".sb-new, .ptab.share")) return "portal";
  if (a.closest(".sbar .sb-nav, .sbar .sb-top, .sbar .sb-va, .ptabs, .ptop, .acct-menu")) return "peer";
  if (a.closest(".back, .pback, [rel='prev']") || /^(‹|<|←)?\s*back\b/i.test(a.textContent?.trim() ?? "")) {
    return "back";
  }
  if (a.closest("[data-handover='expand'], .card-link, .idea, .match")) return "expand";
  if (a.classList.contains("btn-primary")) return "portal";
  return "fwd";
}

function surfaceOf(a: HTMLAnchorElement): HTMLElement {
  return a.closest<HTMLElement>("[data-handover='expand'], .card-link, .idea, .match") ?? a;
}

function solidBackground(el: HTMLElement): string {
  let n: HTMLElement | null = el;
  for (let guard = 0; n && guard < 8; guard++, n = n.parentElement) {
    const c = getComputedStyle(n).backgroundColor;
    const m = /rgba?\(([^)]+)\)/.exec(c);
    if (m) {
      const parts = m[1]!
        .split(/[ ,/]+/)
        .filter(Boolean)
        .map(Number);
      if ((parts[3] ?? 1) >= 0.55) return `rgb(${parts[0]}, ${parts[1]}, ${parts[2]})`;
    }
  }
  return "#ffffff";
}

export function Handover() {
  const pathname = usePathname();
  const pending = useRef<Record | null>(null);
  const first = useRef(true);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const a = (e.target as Element | null)?.closest?.("a[href]") as HTMLAnchorElement | null;
      if (!a || a.target === "_blank" || a.hasAttribute("download")) return;
      const url = new URL(a.href, location.href);
      if (url.origin !== location.origin || (url.pathname === location.pathname && url.hash)) return;
      const kind = classifyLink(a);
      const surface = kind === "expand" ? surfaceOf(a) : a;
      const rect = surface.getBoundingClientRect();
      pending.current = {
        kind,
        at: Date.now(),
        x: e.clientX || rect.left + rect.width / 2,
        y: e.clientY || rect.top + rect.height / 2,
        rect,
        radius: parseFloat(getComputedStyle(surface).borderTopLeftRadius) || 0,
        bg: kind === "expand" ? solidBackground(surface) : "",
      };
    };
    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, []);

  // Before the new screen's first paint: set its arrival, and play the hand-over on the effects layer.
  useLayoutEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    const html = document.documentElement;
    // Every navigation clears the last arrival first, so Back (which records nothing) never inherits a direction
    html.classList.remove(ARRIVAL_WAIT, ...KINDS.map((k) => `mo-a-${k}`));
    const rec = pending.current;
    pending.current = null;
    if (!rec || Date.now() - rec.at > 5_000 || reducedMotion()) return;
    // The arrival's class stays until the next navigation. Taking it off sooner changes the blocks' animation-name,
    // and a new name restarts the animation: the whole screen would vanish and rise out of the blur a second time
    // (BLD-D015). Only the wait for the hand-over (--mo-base) comes off, since a new delay never restarts anything.
    html.classList.add(`mo-a-${rec.kind}`, ARRIVAL_WAIT);
    const clear = window.setTimeout(() => html.classList.remove(ARRIVAL_WAIT), ARRIVAL_WAIT_MS);

    const fx = document.getElementById("mo-fx");
    if (fx && rec.kind === "portal") {
      const r = Math.hypot(Math.max(rec.x, innerWidth - rec.x), Math.max(rec.y, innerHeight - rec.y));
      const flood = document.createElement("i");
      flood.className = "mo-flood";
      flood.style.width = flood.style.height = `${r * 2}px`;
      fx.appendChild(flood);
      const at = `translate(${rec.x - r}px, ${rec.y - r}px)`;
      flood
        .animate(
          [
            { transform: `${at} scale(0)`, opacity: 1 },
            { transform: `${at} scale(1)`, opacity: 1, offset: 0.45 },
            { transform: `${at} scale(1) translateY(0)`, opacity: 1, offset: 0.55 },
            { transform: `${at} scale(1) translateY(-100%)`, opacity: 0 },
          ],
          { duration: 880, easing: "cubic-bezier(.05,.7,.1,1)", fill: "forwards" },
        )
        .finished.then(
          () => flood.remove(),
          () => flood.remove(),
        );
    }
    if (fx && rec.kind === "expand") {
      const main = document.getElementById("main");
      const to = main?.getBoundingClientRect() ?? new DOMRect(0, 0, innerWidth, innerHeight);
      const ghost = document.createElement("i");
      ghost.className = "mo-ghost";
      ghost.style.width = `${to.width}px`;
      ghost.style.height = `${Math.min(to.height, innerHeight)}px`;
      ghost.style.background = rec.bg;
      fx.appendChild(ghost);
      const sx = rec.rect.width / to.width;
      const sy = rec.rect.height / Math.min(to.height, innerHeight);
      ghost
        .animate(
          [
            {
              transform: `translate(${rec.rect.left}px, ${rec.rect.top}px) scale(${sx}, ${sy})`,
              transformOrigin: "0 0",
              borderRadius: `${rec.radius}px`,
              opacity: 1,
            },
            {
              transform: `translate(${to.left}px, ${Math.max(0, to.top)}px) scale(1, 1)`,
              transformOrigin: "0 0",
              borderRadius: "20px",
              opacity: 1,
              offset: 0.55,
            },
            {
              transform: `translate(${to.left}px, ${Math.max(0, to.top)}px) scale(1, 1)`,
              transformOrigin: "0 0",
              borderRadius: "20px",
              opacity: 0,
            },
          ],
          { duration: 700, easing: "cubic-bezier(.16,1,.3,1)", fill: "forwards" },
        )
        .finished.then(
          () => ghost.remove(),
          () => ghost.remove(),
        );
    }
    return () => window.clearTimeout(clear);
  }, [pathname]);

  return null;
}
