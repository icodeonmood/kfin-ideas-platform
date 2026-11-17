import { useLayoutEffect, useRef } from "react";

/**
 * Motion helpers for what CSS cannot do alone (F-MOTION; BLD-E005: no animation library, the Web Animations API and a
 * small FLIP helper instead). Every helper checks reduced motion itself, because the stylesheet's reduced-motion rule
 * cannot stop script-driven animation (F-MOTION.reduced).
 */

/** True when the person has asked for less motion. Server render and tests without a window count as "no". */
export function reducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export type Box = { left: number; top: number; width: number; height: number };
export type Inverse = { dx: number; dy: number; sx: number; sy: number };

/** FLIP's Invert step: the move and scale that put an element laid out at `last` back where it was at `first`. */
export function invert(first: Box, last: Box): Inverse {
  return {
    dx: first.left - last.left,
    dy: first.top - last.top,
    sx: last.width === 0 ? 1 : first.width / last.width,
    sy: last.height === 0 ? 1 : first.height / last.height,
  };
}

export function isStill(t: Inverse): boolean {
  return (
    Math.abs(t.dx) < 0.5 && Math.abs(t.dy) < 0.5 && Math.abs(t.sx - 1) < 0.005 && Math.abs(t.sy - 1) < 0.005
  );
}

/** A layout morph measures at most this many elements per change (F-MOTION.rules/7). */
export const FLIP_LIMIT = 180;

export type FlipOptions = {
  /** How an element is matched before and after the change. Default: its data-flip attribute. Rows must keep the
   * same key when the order changes (F-MOTION.inside, "Lists re-sort"). */
  key?: (el: HTMLElement) => string | undefined;
  /** 560 ms on the standard curve for lists re-sorting; pass --mo-move (460 ms) for a layout morph. */
  duration?: number;
  easing?: string;
  /** Also animate size (a tile changing width). Off by default: moving is enough for rows. */
  scale?: boolean;
};

/**
 * First, Last, Invert, Play. Measures the elements `get` returns, runs `change` (which must update the DOM before it
 * resolves: in React, wrap the state update in flushSync), then glides every matched element from where it was to
 * where it is. New elements fade in. Under reduced motion the change simply happens. Any key, click or wheel ends the
 * glide at once, so motion never blocks input (F-MOTION.rules/5).
 */
export async function flip(
  get: () => Iterable<HTMLElement>,
  change: () => void | Promise<void>,
  {
    key = (el) => el.dataset.flip,
    duration = 560,
    easing = "cubic-bezier(.2,0,0,1)",
    scale = false,
  }: FlipOptions = {},
): Promise<void> {
  if (reducedMotion() || typeof document === "undefined") {
    await change();
    return;
  }

  const first = new Map<string, DOMRect>();
  let seen = 0;
  for (const el of get()) {
    if (seen++ >= FLIP_LIMIT) break;
    const k = key(el);
    if (k) first.set(k, el.getBoundingClientRect());
  }

  await change();

  const running: Animation[] = [];
  seen = 0;
  for (const el of get()) {
    if (seen++ >= FLIP_LIMIT) break;
    const k = key(el);
    const was = k ? first.get(k) : undefined;
    if (!was) {
      running.push(
        el.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 260, easing: "cubic-bezier(.16,1,.3,1)" }),
      );
      continue;
    }
    const t = invert(was, el.getBoundingClientRect());
    if (isStill(t)) continue;
    const from = scale
      ? `translate(${t.dx}px, ${t.dy}px) scale(${t.sx}, ${t.sy})`
      : `translate(${t.dx}px, ${t.dy}px)`;
    running.push(
      el.animate(
        [
          { transform: from, transformOrigin: "0 0" },
          { transform: "none", transformOrigin: "0 0" },
        ],
        { duration, easing },
      ),
    );
  }
  if (running.length === 0) return;

  const finishAll = () => running.forEach((a) => a.finish());
  const events = ["keydown", "pointerdown", "wheel"] as const;
  events.forEach((e) => window.addEventListener(e, finishAll, { capture: true, passive: true }));
  try {
    await Promise.allSettled(running.map((a) => a.finished));
  } finally {
    events.forEach((e) => window.removeEventListener(e, finishAll, { capture: true }));
  }
}

/**
 * Lists re-sort (F-MOTION.inside): call in a component that renders a list whose order can change. Every row carries
 * data-flip with a key that stays the same when the order changes; when `key` changes (the sort, a filter), rows glide
 * from their old place to their new one (560 ms, the standard curve) and new rows fade in. React only; reduced motion
 * and server render do nothing.
 */
export function useFlipList(container: { current: HTMLElement | null }, key: unknown) {
  // Positions in page coordinates, so scrolling between two sorts never reads as movement
  const last = useRef<Map<string, Box>>(new Map());
  useLayoutEffect(() => {
    const el = container.current;
    if (!el) return;
    const rows = Array.from(el.querySelectorAll<HTMLElement>("[data-flip]")).slice(0, FLIP_LIMIT);
    // A glide still running from a quick earlier sort ends first, so the new one starts from where rows really are
    rows.forEach((r) => r.getAnimations().forEach((a) => a.finish()));
    const page = (r: HTMLElement): Box => {
      const b = r.getBoundingClientRect();
      return { left: b.left + window.scrollX, top: b.top + window.scrollY, width: b.width, height: b.height };
    };
    const now = new Map<string, Box>();
    for (const r of rows) now.set(r.dataset.flip!, page(r));
    const before = last.current;
    last.current = now;
    if (before.size === 0 || reducedMotion()) return;
    const running: Animation[] = [];
    for (const r of rows) {
      const was = before.get(r.dataset.flip!);
      const is = now.get(r.dataset.flip!)!;
      if (!was) {
        running.push(
          r.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 260, easing: "cubic-bezier(.16,1,.3,1)" }),
        );
        continue;
      }
      const t = invert(was, is);
      if (isStill(t)) continue;
      running.push(
        r.animate([{ transform: `translate(${t.dx}px, ${t.dy}px)` }, { transform: "none" }], {
          duration: 560,
          easing: "cubic-bezier(.2,0,0,1)",
        }),
      );
    }
    if (running.length === 0) return;
    // Motion never blocks input: a key, a click or the wheel ends the glide (F-MOTION.rules/5)
    const finishAll = () => running.forEach((a) => a.finish());
    const events = ["keydown", "pointerdown", "wheel"] as const;
    events.forEach((ev) => window.addEventListener(ev, finishAll, { capture: true, passive: true }));
    const done = Promise.allSettled(running.map((a) => a.finished)).then(() =>
      events.forEach((ev) => window.removeEventListener(ev, finishAll, { capture: true })),
    );
    void done;
    // Only a change of `key` should animate; layout moves from scrolling or resizing are not re-sorts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
}
