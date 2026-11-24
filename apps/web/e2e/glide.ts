/**
 * BLD-D038 checks shared by the S-R1 desk and S-WALL tests (F-MOTION.rules/5, J-BROWSE/4): a re-sort glide never
 * moves a row out from under a press. A press holds the glide where it is drawn and the click opens the row; a key or
 * the wheel ends the glide at once. Only the glide `lib/motion/flip.ts` starts is read: a row's CSS transitions and
 * animations (a hover colour) are not glides.
 */
import { expect, type Page } from "@playwright/test";

/** A row gliding now: its key (data-flip, the idea's reference) and the centre of its link where it is drawn. */
export type Gliding = { id: string; x: number; y: number };

/**
 * Slows every animation on the page tenfold, as DevTools' animation speed does, so a step taken while a glide runs
 * lands where the test read the row. Both projects are Chrome.
 */
export async function slowGlides(page: Page): Promise<void> {
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Animation.enable");
  await cdp.send("Animation.setPlaybackRate", { playbackRate: 0.1 });
}

/**
 * Waits until a row of `list` glides at least 20 px from its place and says which one moves furthest. With `hit`, only
 * a row whose link is the element under its own centre counts, so a press there lands on the link.
 */
export async function glidingRow(page: Page, list: string, { hit = true } = {}): Promise<Gliding> {
  const found = await page.waitForFunction(
    ({ list, hit }) => {
      let best: { id: string; x: number; y: number; d: number } | null = null;
      for (const row of Array.from(document.querySelectorAll<HTMLElement>(`${list} [data-flip]`))) {
        const gliding = row
          .getAnimations()
          .some(
            (a) => !(a instanceof CSSTransition) && !(a instanceof CSSAnimation) && a.playState === "running",
          );
        const link = row.querySelector("a");
        const box = link?.getClientRects()[0];
        if (!gliding || !link || !box) continue;
        const m = new DOMMatrixReadOnly(getComputedStyle(row).transform);
        const d = Math.hypot(m.m41, m.m42);
        const x = box.left + box.width / 2;
        const y = box.top + box.height / 2;
        const under = document.elementFromPoint(x, y);
        if (d < 20 || (hit && !(under && link.contains(under))) || (best && best.d >= d)) continue;
        best = { id: row.dataset.flip ?? "", x, y, d };
      }
      return best;
    },
    { list, hit },
    { timeout: 15_000 },
  );
  const row = await found.jsonValue();
  expect(row, `a row of ${list} glides`).not.toBeNull();
  return { id: row!.id, x: row!.x, y: row!.y };
}

/**
 * The press holds: once the pause has taken hold, over three frames the row's glide stays "paused", its link moves
 * less than 0.5 px and is still the element under the pointer.
 */
export async function expectHeld(page: Page, list: string, at: Gliding): Promise<void> {
  const held = await page.evaluate(
    async ({ list, at }) => {
      const row = document.querySelector<HTMLElement>(`${list} [data-flip="${CSS.escape(at.id)}"]`);
      const link = row?.querySelector("a");
      if (!row || !link) return null;
      // pause() takes hold on the next frame (the Web Animations pending pause); `ready` says when it has
      await Promise.all(
        row
          .getAnimations()
          .filter((a) => !(a instanceof CSSTransition) && !(a instanceof CSSAnimation))
          .map((a) => a.ready),
      );
      const box = () => link.getClientRects()[0]!;
      const was = box();
      for (let i = 0; i < 3; i += 1) await new Promise((r) => requestAnimationFrame(r));
      const now = box();
      const under = document.elementFromPoint(at.x, at.y);
      return {
        states: row
          .getAnimations()
          .filter((a) => !(a instanceof CSSTransition) && !(a instanceof CSSAnimation))
          .map((a) => a.playState),
        moved: Math.hypot(now.left - was.left, now.top - was.top),
        under: !!under && link.contains(under),
      };
    },
    { list, at },
  );
  expect(held, `the row ${at.id} is in ${list}`).not.toBeNull();
  expect(held!.states.length, "the row has its glide").toBeGreaterThan(0);
  expect(held!.states, "the press pauses the glide; it does not finish it").toEqual(
    held!.states.map(() => "paused"),
  );
  expect(held!.moved, "the held link stays where it is drawn").toBeLessThan(0.5);
  expect(held!.under, "the link is still under the pointer").toBe(true);
}

/** On the next frame no row of `list` has a glide still running. */
export async function expectNoGlideRunning(page: Page, list: string): Promise<void> {
  const running = await page.evaluate(async (list) => {
    await new Promise((r) => requestAnimationFrame(r));
    return Array.from(document.querySelectorAll<HTMLElement>(`${list} [data-flip]`))
      .flatMap((r) => r.getAnimations())
      .filter(
        (a) => !(a instanceof CSSTransition) && !(a instanceof CSSAnimation) && a.playState === "running",
      ).length;
  }, list);
  expect(running, "a key or the wheel ends the glide at once").toBe(0);
}
