// @vitest-environment jsdom
/**
 * F-MOTION.rules/5, J-BROWSE/4 (BLD-D038): motion never blocks input, and a press never moves a gliding row out from
 * under the pointer. `yieldToInput` ends a re-sort glide at once on a key or the wheel, holds it where it is on a press
 * and ends it once the click has reached the row's link. jsdom has no `Element.animate`, so these use small stand-ins
 * with a play state, `pause()`, `finish()` and a `finished` promise.
 */
import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import { HOLD_MAX_MS, PRESS_GRACE_MS, yieldToInput } from "@/lib/motion/flip";

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
