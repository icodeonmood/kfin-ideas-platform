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

/** A press holds a glide at most this long, so a press that never ends cannot leave it paused (BLD-D038). */
export const HOLD_MAX_MS = 2_000;
/** After a press ends with no click (dragged off, the right button), the held glide ends this much later. A phone's
 * tap can send its click a frame after the press ends, so the glide never ends on the release itself (BLD-D038). */
export const PRESS_GRACE_MS = 250;

/**
 * Motion never blocks input (F-MOTION.rules/5). A key or the wheel ends a running glide at once. A press holds it
 * exactly where it is drawn, so the row the person pressed is still under the pointer when they let go, and the click
 * ends it once the click has reached the row's link (BLD-D038, J-BROWSE/4). Ending the glide on the press moved the
 * row out from under the pointer and the click landed on the list instead. A press that ends with no click ends the
 * glide after PRESS_GRACE_MS; a cancelled press or the window losing focus ends it at once; a press holds it at most
 * HOLD_MAX_MS. Resolves once every animation has settled, however it ended (a new re-sort finishing it included), and
 * leaves no listener or timer behind.
 */
export function yieldToInput(running: readonly Animation[]): Promise<void> {
  if (running.length === 0 || typeof window === "undefined") return Promise.resolve();
  let soon: number | undefined; // the click's 0 ms timer or the release's grace
  let hold: number | undefined; // the longest a press holds the glide
  const clear = () => {
    window.clearTimeout(soon);
    window.clearTimeout(hold);
    soon = hold = undefined;
  };
  const finishAll = () => {
    clear();
    running.forEach((a) => a.finish());
  };
  const finishIn = (ms: number) => {
    window.clearTimeout(soon);
    soon = window.setTimeout(finishAll, ms);
  };
  const onPress = () => {
    clear();
    // Only a glide still running is held: pausing a finished one would put it back to "paused"
    running.forEach((a) => {
      if (a.playState === "running") a.pause();
    });
    hold = window.setTimeout(finishAll, HOLD_MAX_MS);
  };
  // The click reaches the row's link and its handler first; the glide ends on the next task
  const onClick = () => finishIn(0);
  const onRelease = () => finishIn(PRESS_GRACE_MS);
  // The window losing focus ends it; focus leaving an element inside the page (a press moves it) does not
  const onBlur = (e: Event) => {
    if (e.target === e.currentTarget) finishAll();
  };
  const on: [string, (e: Event) => void][] = [
    ["keydown", finishAll],
    ["wheel", finishAll],
    ["pointercancel", finishAll],
    ["blur", onBlur],
    ["pointerdown", onPress],
    ["pointerup", onRelease],
    ["click", onClick],
  ];
  on.forEach(([ev, fn]) => window.addEventListener(ev, fn, { capture: true, passive: true }));
  return Promise.allSettled(running.map((a) => a.finished)).then(() => {
    on.forEach(([ev, fn]) => window.removeEventListener(ev, fn, { capture: true }));
    clear();
  });
}

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
 * where it is. New elements fade in. Under reduced motion the change simply happens. A key or the wheel ends the glide
 * at once; a press holds it where it is and the click ends it, so motion never blocks input (F-MOTION.rules/5,
 * BLD-D038; see yieldToInput).
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
  await yieldToInput(running);
}

/**
 * Lists re-sort (F-MOTION.inside): call in a component that renders a list whose order can change. Every row carries
 * data-flip with a key that stays the same when the order changes; when `key` changes (the sort, a filter), rows glide
 * from their old place to their new one (560 ms, the standard curve) and new rows fade in. A key or the wheel ends the
 * glide at once; a press holds it where it is and the click ends it (F-MOTION.rules/5, BLD-D038; see yieldToInput).
 * React only; reduced motion and server render do nothing.
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
    // Motion never blocks input: a key or the wheel ends the glide, a press holds it and the click ends it
    void yieldToInput(running);
    // Only a change of `key` should animate; layout moves from scrolling or resizing are not re-sorts.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
}
