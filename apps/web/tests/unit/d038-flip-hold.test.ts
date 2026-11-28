// @vitest-environment jsdom
/**
 * F-MOTION.rules/5, J-BROWSE/4 (BLD-D038): motion never blocks input, and a press never moves a gliding row out from
 * under the pointer. `yieldToInput` ends a re-sort glide at once on a key or the wheel, holds it where it is on a press
 * and ends it once the click has reached the row's link. jsdom has no `Element.animate`, so these use small stand-ins
 * with a play state, `pause()`, `finish()` and a `finished` promise.
 *
 * BLD-D039: finish() throws on an animation that never ends, so every place that ends a glide goes through
 * `finishGlide`, which leaves a loop (a skeleton's shimmer, a spinner) running.
 */
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import { finishGlide, flip, HOLD_MAX_MS, PRESS_GRACE_MS, yieldToInput } from "@/lib/motion/flip";

type Glide = {
  playState: AnimationPlayState;
  finished: Promise<unknown>;
  pause: Mock<() => void>;
  finish: Mock<() => void>;
  cancel: () => void;
};

let made: Glide[] = [];
let waits: Promise<void>[] = [];

/** A stand-in for a running Animation. Like the real one, pause() on a finished glide puts it back to "paused". */
function glide(): Glide {
  let done!: () => void;
  let fail!: (e: unknown) => void;
  const g: Glide = {
    playState: "running",
    finished: new Promise((res, rej) => {
      done = () => res(g);
      fail = rej;
    }),
    pause: vi.fn(() => {
      g.playState = "paused";
    }),
    finish: vi.fn(() => {
      g.playState = "finished";
      done();
    }),
    cancel: () => {
      g.playState = "idle";
      fail(new DOMException("The animation was cancelled.", "AbortError"));
    },
  };
  made.push(g);
  return g;
}

function hold(...glides: Glide[]): Promise<void> {
  const p = yieldToInput(glides as unknown as Animation[]);
  waits.push(p);
  return p;
}

const fire = (type: string) => window.dispatchEvent(new Event(type));

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(async () => {
  // Every glide a case left running ends, so no case leaves listeners behind for the next
  made.forEach((g) => g.playState !== "finished" && g.playState !== "idle" && g.finish());
  await Promise.all(waits);
  made = [];
  waits = [];
  vi.useRealTimers();
});

describe("BLD-D038 yieldToInput (lib/motion/flip)", () => {
  it("BLD-D038, F-MOTION.rules/5: keydown finishes at once", async () => {
    const a = glide();
    const b = glide();
    const p = hold(a, b);
    fire("keydown");
    expect(a.finish).toHaveBeenCalledTimes(1);
    expect(b.finish).toHaveBeenCalledTimes(1);
    await p;
  });

  it("BLD-D038, F-MOTION.rules/5: wheel finishes at once", async () => {
    const a = glide();
    const p = hold(a);
    fire("wheel");
    expect(a.finish).toHaveBeenCalledTimes(1);
    await p;
  });

  it("BLD-D038, F-MOTION.rules/5: pointerdown pauses and does not finish", () => {
    const a = glide();
    const b = glide();
    hold(a, b);
    fire("pointerdown");
    expect(a.pause).toHaveBeenCalledTimes(1);
    expect(b.pause).toHaveBeenCalledTimes(1);
    expect(a.playState).toBe("paused");
    expect(a.finish).not.toHaveBeenCalled();
    expect(b.finish).not.toHaveBeenCalled();
  });

  it("BLD-D038, F-MOTION.rules/5: click after pointerdown finishes after a 0 ms timer, not synchronously", async () => {
    const a = glide();
    const p = hold(a);
    fire("pointerdown");
    fire("pointerup");
    fire("click");
    expect(a.finish).not.toHaveBeenCalled();
    vi.advanceTimersByTime(0);
    expect(a.finish).toHaveBeenCalledTimes(1);
    await p;
    expect(vi.getTimerCount()).toBe(0);
  });

  it("BLD-D038, F-MOTION.rules/5: pointerup with no click finishes after 250 ms and not before", async () => {
    const a = glide();
    const p = hold(a);
    fire("pointerdown");
    fire("pointerup");
    expect(PRESS_GRACE_MS).toBe(250);
    vi.advanceTimersByTime(PRESS_GRACE_MS - 1);
    expect(a.finish).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(a.finish).toHaveBeenCalledTimes(1);
    await p;
  });

  it("BLD-D038, F-MOTION.rules/5: pointercancel finishes at once", async () => {
    const a = glide();
    const p = hold(a);
    fire("pointerdown");
    fire("pointercancel");
    expect(a.finish).toHaveBeenCalledTimes(1);
    await p;
  });

  it("BLD-D038, F-MOTION.rules/5: window blur finishes at once", async () => {
    const a = glide();
    const p = hold(a);
    fire("pointerdown");
    window.dispatchEvent(new FocusEvent("blur"));
    expect(a.finish).toHaveBeenCalledTimes(1);
    await p;
  });

  it("BLD-D038, F-MOTION.rules/5: focus leaving an element inside the page (the press moves it) does not finish", () => {
    const button = document.createElement("button");
    document.body.append(button);
    const a = glide();
    hold(a);
    fire("pointerdown");
    button.dispatchEvent(new FocusEvent("blur"));
    expect(a.finish).not.toHaveBeenCalled();
    button.remove();
  });

  it("BLD-D038, F-MOTION.rules/5: a press with no pointerup finishes at 2,000 ms and not before", async () => {
    const a = glide();
    const p = hold(a);
    fire("pointerdown");
    expect(HOLD_MAX_MS).toBe(2_000);
    vi.advanceTimersByTime(HOLD_MAX_MS - 1);
    expect(a.finish).not.toHaveBeenCalled();
    vi.advanceTimersByTime(1);
    expect(a.finish).toHaveBeenCalledTimes(1);
    await p;
  });

  it("BLD-D038, F-MOTION.rules/5: a new pointerdown clears the pending grace timer", () => {
    const a = glide();
    hold(a);
    fire("pointerdown");
    fire("pointerup");
    vi.advanceTimersByTime(PRESS_GRACE_MS - 50);
    fire("pointerdown");
    vi.advanceTimersByTime(100);
    expect(a.finish).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(1); // only the new press's hold
  });

  it("BLD-D038, F-MOTION.rules/5: listeners are removed once all settle (a later keydown does nothing)", async () => {
    const a = glide();
    const p = hold(a);
    fire("keydown");
    await p;
    fire("keydown");
    fire("pointerdown");
    expect(a.finish).toHaveBeenCalledTimes(1);
    expect(a.pause).not.toHaveBeenCalled();
    expect(vi.getTimerCount()).toBe(0);
  });

  it("BLD-D038, F-MOTION.rules/5: an animation that rejects (cancelled) still settles", async () => {
    const a = glide();
    const b = glide();
    const p = hold(a, b);
    a.cancel();
    fire("keydown");
    await expect(p).resolves.toBeUndefined();
  });

  it("BLD-D038, F-MOTION.rules/5: a glide finished early by another route, then a pointerdown: pause() is not called on it, and no timer is pending once all settle", async () => {
    const a = glide();
    const p = hold(a);
    // A new re-sort finishes the glide at the top of useFlipList's effect; the press comes before it settles
    a.finish();
    fire("pointerdown");
    expect(a.pause).not.toHaveBeenCalled();
    expect(a.playState).toBe("finished");
    await p;
    expect(vi.getTimerCount()).toBe(0);
  });

  it("BLD-D038, F-MOTION.rules/5: nothing to hold resolves at once", async () => {
    await expect(yieldToInput([])).resolves.toBeUndefined();
    expect(vi.getTimerCount()).toBe(0);
  });
});

describe("BLD-D038 flip (lib/motion/flip)", () => {
  it("BLD-D038, F-MOTION.rules/5: flip() ends a glide still running on its elements before it measures them", async () => {
    // A press on My ideas' sort button holds the earlier sort's glide mid-way, then its click calls flip()
    vi.stubGlobal("matchMedia", (q: string) => ({ matches: false, media: q }) as MediaQueryList);
    const list = document.createElement("ul");
    let moved = 0; // the new order lands 100 px lower
    const rows = ["a", "b"].map((k, i) => {
      const el = document.createElement("li");
      el.dataset.flip = k;
      const old = glide();
      old.pause();
      // Held mid-glide, the row is drawn 37 px from where the earlier sort puts it
      const rect = vi.fn(
        () =>
          ({
            left: 0,
            top: i * 40 + moved + (old.playState === "finished" ? 0 : 37),
            width: 200,
            height: 40,
          }) as DOMRect,
      );
      const animate = vi.fn(() => {
        const g = glide();
        g.finish();
        return g as unknown as Animation;
      });
      Object.assign(el, {
        getAnimations: () => (old.playState === "finished" ? [] : [old as unknown as Animation]),
        getBoundingClientRect: rect,
        animate,
      });
      list.append(el);
      return { old, rect, animate };
    });
    document.body.append(list);
    try {
      await flip(
        () => list.querySelectorAll<HTMLElement>("[data-flip]"),
        () => {
          moved = 100;
        },
      );
      for (const { old, rect, animate } of rows) {
        expect(old.finish).toHaveBeenCalledTimes(1);
        expect(old.finish.mock.invocationCallOrder[0]).toBeLessThan(rect.mock.invocationCallOrder[0] ?? 0);
        // The new glide starts from where the row really ended, not from the held mid-glide place
        expect(animate).toHaveBeenCalledTimes(1);
        expect(animate.mock.calls[0]).toEqual([
          [
            { transform: "translate(0px, -100px)", transformOrigin: "0 0" },
            { transform: "none", transformOrigin: "0 0" },
          ],
          expect.anything(),
        ]);
      }
    } finally {
      list.remove();
      vi.unstubAllGlobals();
    }
  });
});

/** A stand-in for an animation with an end (`endTime`) or a loop (Infinity), whose finish() throws as the real one
 * does: "InvalidStateError" on a loop. Not in `made`, so the shared clean-up never finishes it. */
function timed(endTime: number) {
  const a = {
    playState: "running" as AnimationPlayState,
    effect: { getComputedTiming: () => ({ endTime }) },
    finish: vi.fn(() => {
      if (!Number.isFinite(endTime)) throw new DOMException("The animation never ends.", "InvalidStateError");
      a.playState = "finished";
    }),
  };
  return a;
}

describe("BLD-D039 finishGlide (lib/motion/flip)", () => {
  it("BLD-D039, F-MOTION.rules/5: an animation with an end is finished", () => {
    const a = timed(560);
    finishGlide(a as unknown as Animation);
    expect(a.finish).toHaveBeenCalledTimes(1);
    expect(a.playState).toBe("finished");
  });

  it("BLD-D039, F-MOTION.rules/5: a loop is left running and nothing throws", () => {
    const a = timed(Infinity);
    expect(() => finishGlide(a as unknown as Animation)).not.toThrow();
    expect(a.finish).not.toHaveBeenCalled();
    expect(a.playState).toBe("running");
  });

  it("BLD-D039, F-MOTION.rules/5: an animation with no effect is finished as before (its end is 0, so finish() cannot throw on it; the D038 stand-ins have none)", () => {
    const a = glide();
    finishGlide(a as unknown as Animation);
    expect(a.finish).toHaveBeenCalledTimes(1);
    expect(a.playState).toBe("finished");
  });

  it("BLD-D039, F-MOTION.rules/5: a loop on a row does not make flip() throw and keeps running, while a glide with an end on the same row is finished before it is measured", async () => {
    vi.stubGlobal("matchMedia", (q: string) => ({ matches: false, media: q }) as MediaQueryList);
    const list = document.createElement("ul");
    const row = document.createElement("li");
    row.dataset.flip = "a";
    const loop = timed(Infinity);
    const old = timed(560);
    const rect = vi.fn(() => ({ left: 0, top: 0, width: 200, height: 40 }) as DOMRect);
    Object.assign(row, {
      getAnimations: () => [loop, old] as unknown as Animation[],
      getBoundingClientRect: rect,
      animate: vi.fn(),
    });
    list.append(row);
    document.body.append(list);
    try {
      await expect(
        flip(
          () => list.querySelectorAll<HTMLElement>("[data-flip]"),
          () => undefined,
        ),
      ).resolves.toBeUndefined();
      expect(loop.finish).not.toHaveBeenCalled();
      expect(loop.playState).toBe("running");
      expect(old.finish).toHaveBeenCalledTimes(1);
      expect(old.finish.mock.invocationCallOrder[0]).toBeLessThan(rect.mock.invocationCallOrder[0] ?? 0);
    } finally {
      list.remove();
      vi.unstubAllGlobals();
    }
  });
});
