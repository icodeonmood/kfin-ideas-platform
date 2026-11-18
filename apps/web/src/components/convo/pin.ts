/**
 * S-08's box on a phone and the "Say hello" arrival, kept apart from the screen so each is tested on its own.
 *
 * - Pinned (S-08.rules/4, BLD-F068): at 640px and narrower the box is fixed at the bottom of the screen, above the tab
 *   bar where the shell still shows one, and above the keyboard while it is open. The timeline keeps room for it, so
 *   its last line, and anything focused in it, never sits behind the box (WCAG 2.4.11). The browser's own layout is
 *   measured: the box's height, the tab bar, the keyboard and the padding the shell already keeps under the page.
 * - Say hello (L-TEAMUP.rules/9, BLD-F069): a "Say hello" link ends in `#say-hello`, a hint that carries no words.
 *   When the person can write here, the cursor lands in the box; the hint then comes off the address, so a reload or
 *   Back does not do it again.
 */
import { useEffect, type RefObject } from "react";

/** The hint on every "Say hello" link to a conversation (lane F's in teamup/, others' on request). */
export const SAY_HELLO = "#say-hello";

/** Room left between the timeline's last line and the top of the box. */
export const PIN_GAP = 16;

/** A difference smaller than this between the window and what is visible is the browser's own bars, not a keyboard. */
const KEYBOARD_MIN = 100;

/** How far up an open on-screen keyboard reaches, in CSS pixels: 0 when there is none, or the page is zoomed. */
export function keyboardInset(
  vv: Pick<VisualViewport, "height" | "offsetTop" | "scale"> | null | undefined,
  innerHeight: number,
): number {
  if (!vv || Math.abs(vv.scale - 1) > 0.01) return 0;
  const inset = Math.round(innerHeight - vv.height - vv.offsetTop);
  return inset >= KEYBOARD_MIN ? inset : 0;
}

export interface PinInput {
  /** Whether the box is fixed (a phone); on a wider screen it sits under the timeline and nothing is kept. */
  fixed: boolean;
  /** The box's own height. */
  box: number;
  /** The tab bar's height where the shell shows one (0 where the conversation is a task screen). */
  tabs: number;
  /** An open keyboard's height (`keyboardInset`). */
  keyboard: number;
  /** The padding the shell already keeps under the page (`main#main`). */
  mainPad: number;
}

export interface Pin {
  /** How far the box sits above the bottom of the screen: the keyboard, else the tab bar. */
  at: number;
  /** How much of the screen's bottom the box and whatever is under it cover. */
  cover: number;
  /** The room the timeline adds under its last line, on top of the shell's padding. */
  room: number;
  /** 1 when the box is at the very bottom and so takes the safe area (a home indicator); 0 above a bar or keyboard. */
  safe: 0 | 1;
}

export function pinMetrics({ fixed, box, tabs, keyboard, mainPad }: PinInput): Pin {
  if (!fixed) return { at: 0, cover: 0, room: 0, safe: 1 };
  const at = Math.max(keyboard, tabs);
  const cover = Math.ceil(box + at);
  return { at, cover, room: Math.max(0, cover - Math.floor(mainPad)) + PIN_GAP, safe: at > 0 ? 0 : 1 };
}

/** Write the pin into CSS variables on the screen's root (`--cv-at`, `--cv-cover`, `--cv-room`, `--cv-safe`). */
function apply(root: HTMLElement, pin: Pin | null) {
  const names = ["--cv-at", "--cv-cover", "--cv-room", "--cv-safe"] as const;
  if (!pin) {
    for (const n of names) root.style.removeProperty(n);
    return;
  }
  root.style.setProperty("--cv-at", `${pin.at}px`);
  root.style.setProperty("--cv-cover", `${pin.cover}px`);
  root.style.setProperty("--cv-room", `${pin.room}px`);
  root.style.setProperty("--cv-safe", String(pin.safe));
}

/**
 * Keep the pinned box's measurements current: on the box's own resize (it grows with its words, an error under it, the
 * line about open questions), the window's, and the visible part's (the keyboard). `on` is false once the box is gone
 * (a merged idea's conversation): the variables come off and the timeline keeps no room.
 */
export function usePinnedBox(
  rootRef: RefObject<HTMLElement | null>,
  boxRef: RefObject<HTMLElement | null>,
  on: boolean,
): void {
  useEffect(() => {
    const root = rootRef.current;
    const box = boxRef.current;
    if (!on || !root || !box) return;
    const vv = window.visualViewport ?? null;
    let frame = 0;
    const measure = () => {
      frame = 0;
      const main = root.closest("main");
      const tabs = document.querySelector<HTMLElement>(".ptabs");
      apply(
        root,
        pinMetrics({
          fixed: getComputedStyle(box).position === "fixed",
          box: box.offsetHeight,
          tabs: tabs?.offsetHeight ?? 0,
          keyboard: keyboardInset(vv, window.innerHeight),
          mainPad: main ? Number.parseFloat(getComputedStyle(main).paddingBottom) || 0 : 0,
        }),
      );
    };
    const soon = () => {
      if (!frame) frame = requestAnimationFrame(measure);
    };
    measure();
    const seen = typeof ResizeObserver === "function" ? new ResizeObserver(soon) : null;
    seen?.observe(box);
    window.addEventListener("resize", soon);
    vv?.addEventListener("resize", soon);
    vv?.addEventListener("scroll", soon);
    return () => {
      if (frame) cancelAnimationFrame(frame);
      seen?.disconnect();
      window.removeEventListener("resize", soon);
      vv?.removeEventListener("resize", soon);
      vv?.removeEventListener("scroll", soon);
      apply(root, null);
    };
  }, [rootRef, boxRef, on]);
}

/** The box grows with its words up to its CSS `max-height`, then scrolls; it never shows a resize grip. */
export function grow(box: HTMLTextAreaElement | null): void {
  if (!box) return;
  box.style.height = "auto";
  const h = box.scrollHeight;
  box.style.height = h ? `${h}px` : "";
}

/**
 * "Say hello" lands with the cursor in the box (BLD-F069). On arrival with `#say-hello`, focus goes to the box when
 * the person can write here (the box is open and writing is not paused); otherwise focus stays where it is. Either way
 * the hint comes off the address, keeping the router's own history state. Words carried over from the edit page
 * (S-06B.rules/2, BLD-C165) reach the box just after the focus; setting a box's words puts the cursor at their end
 * (HTML, the value setter), so the person carries on writing after them. Nothing is sent.
 */
export function useSayHello(box: RefObject<HTMLTextAreaElement | null>, canWrite: boolean): void {
  useEffect(() => {
    if (window.location.hash !== SAY_HELLO) return;
    if (canWrite) box.current?.focus();
    const { pathname, search } = window.location;
    window.history.replaceState(window.history.state, "", pathname + search);
  }, [box, canWrite]);
}
