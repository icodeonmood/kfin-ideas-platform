/**
 * The listen player's speech engine (C-LISTEN, L-LISTEN, BLD-B230): the browser reads the masked script with a
 * local voice, part by part. A hand-written speechSynthesis, utterance and clock stand in for the browser.
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import {
  CHARS_PER_SECOND,
  clock,
  estimate,
  forgetOffline,
  jumpLabel,
  LISTEN_ERROR,
  ListenEngine,
  loadOffline,
  nowLabel,
  OFFLINE_DAYS,
  PART_GAP_SECONDS,
  pickVoice,
  playLabel,
  progressLabel,
  pruneOffline,
  saveOffline,
  spokenText,
  type ListenPart,
  type ListenScript,
  type ListenState,
  type ListenStorage,
  type ListenSynth,
  type ListenUtterance,
  type ListenUtteranceCtor,
  type ListenVoice,
} from "@/lib/desk/listen";

// ----- Fakes -------------------------------------------------------------------------------------------------

type FakeEvent = { charIndex: number; error: string };

class FakeUtterance implements ListenUtterance {
  rate = 1;
  lang = "";
  voice: ListenVoice | null = null;
  private readonly handlers = new Map<string, ((event: FakeEvent) => void)[]>();

  constructor(readonly text: string) {}

  addEventListener(type: "boundary", listener: (event: { charIndex: number }) => void): void;
  addEventListener(type: "end", listener: () => void): void;
  addEventListener(type: "error", listener: (event: { error: string }) => void): void;
  addEventListener(type: string, listener: (event: FakeEvent) => void): void {
    this.handlers.set(type, [...(this.handlers.get(type) ?? []), listener]);
  }

  boundary(charIndex: number): void {
    this.fire("boundary", { charIndex, error: "" });
  }

  end(): void {
    this.fire("end", { charIndex: 0, error: "" });
  }

  fail(error: string): void {
    this.fire("error", { charIndex: 0, error });
  }

  private fire(type: string, event: FakeEvent): void {
    for (const listener of this.handlers.get(type) ?? []) listener(event);
  }
}

class FakeSynth implements ListenSynth {
  readonly spoken: FakeUtterance[] = [];
  cancels = 0;

  speak(utterance: ListenUtterance): void {
    if (utterance instanceof FakeUtterance) this.spoken.push(utterance);
  }

  /** Like Chrome: cancelling fires "interrupted" on the utterance being spoken, straight away. */
  cancel(): void {
    this.cancels += 1;
    this.spoken.at(-1)?.fail("interrupted");
  }

  get last(): FakeUtterance {
    const u = this.spoken.at(-1);
    if (!u) throw new Error("nothing spoken yet");
    return u;
  }
}

function fakeClock() {
  let t = 0;
  let tick: (() => void) | null = null;
  return {
    now: () => t,
    every: (fn: () => void) => {
      tick = fn;
      return () => {
        tick = null;
      };
    },
    advance(ms: number) {
      t += ms;
      tick?.();
    },
    running: () => tick !== null,
  };
}

const VOICE_IN: ListenVoice = { lang: "en-IN", localService: true };

const SCRIPT: ListenScript = {
  parts: [
    {
      part: "summary",
      title: "The problem",
      text: "Branch staff retype the same KYC form when the scan fails.",
    },
    { part: "often", title: "How often", text: "Every working day, at about forty branches." },
    { part: "who", title: "Who it affects", text: "Front desk staff and the investors waiting in line." },
    { part: "cost", title: "What it's worth", text: "About two hours a day per branch." },
    { part: "evidence", title: "Attached", text: "One file: a branch call log for November." },
    { part: "fix", title: "Fix", text: "No fix suggested. It was optional." },
  ],
};

const ONE_X = estimate(SCRIPT, 1);
const startOf = (i: number) => ONE_X.parts[i]?.start ?? NaN;
const spoken = (i: number) => {
  const p = SCRIPT.parts[i];
  if (!p) throw new Error(`no part ${i}`);
  return spokenText(p);
};

function setup(script: ListenScript = SCRIPT) {
  const synth = new FakeSynth();
  const time = fakeClock();
  const Utterance: ListenUtteranceCtor = FakeUtterance;
  const engine = new ListenEngine({
    synth,
    Utterance,
    script,
    voice: VOICE_IN,
    now: time.now,
    every: time.every,
  });
  const states: ListenState[] = [];
  engine.subscribe((s) => states.push(s));
  return { synth, time, engine, states, state: () => engine.state() };
}

/** n characters of filler words, with no space at either end. */
function filler(n: number): string {
  const s = "calls ".repeat(Math.ceil(n / 6)).slice(0, n);
  return s.endsWith(" ") ? `${s.slice(0, -1)}s` : s;
}

// ----- Voice --------------------------------------------------------------------------------------------------

describe("L-LISTEN/6 voice choice (BLD-B230: local voices only)", () => {
  it("prefers a local Indian English voice over other local English voices", () => {
    const gb = { name: "gb", lang: "en-GB", localService: true };
    const inRemote = { name: "in-remote", lang: "en-IN", localService: false };
    const inLocal = { name: "in-local", lang: "en-IN", localService: true };
    expect(pickVoice([gb, inRemote, inLocal])?.name).toBe("in-local");
  });

  it("reads Android's en_IN as Indian English", () => {
    const us = { name: "us", lang: "en-US", localService: true };
    const android = { name: "android", lang: "en_IN", localService: true };
    expect(pickVoice([us, android])?.name).toBe("android");
  });

  it("falls back to any local English voice", () => {
    const hi = { name: "hi", lang: "hi-IN", localService: true };
    const gb = { name: "gb", lang: "en-GB", localService: true };
    expect(pickVoice([hi, gb])?.name).toBe("gb");
  });

  it("returns null when there is no local English voice, so the player is hidden", () => {
    expect(pickVoice([])).toBeNull();
    expect(pickVoice([{ lang: "en-IN", localService: false }])).toBeNull();
    expect(pickVoice([{ lang: "hi-IN", localService: true }])).toBeNull();
  });

  it("the browser's own speechSynthesis, utterance and voices fit the engine's shapes", () => {
    const fits: [
      SpeechSynthesis extends ListenSynth ? true : false,
      typeof SpeechSynthesisUtterance extends ListenUtteranceCtor ? true : false,
      SpeechSynthesisVoice extends ListenVoice ? true : false,
    ] = [true, true, true];
    expect(fits).toEqual([true, true, true]);
  });
});

// ----- Timeline -----------------------------------------------------------------------------------------------

describe("L-LISTEN/1 the estimated timeline", () => {
  it("starts each part after the one before it plus a short pause, at about 15 characters a second", () => {
    expect(CHARS_PER_SECOND).toBe(15);
    expect(ONE_X.parts.map((p) => p.part)).toEqual(["summary", "often", "who", "cost", "evidence", "fix"]);
    expect(startOf(0)).toBe(0);
    expect(startOf(1)).toBeCloseTo(spoken(0).length / 15 + PART_GAP_SECONDS, 9);
    expect(startOf(2)).toBeCloseTo((spoken(0).length + spoken(1).length) / 15 + 2 * PART_GAP_SECONDS, 9);
    const chars = SCRIPT.parts.reduce((sum, p) => sum + spokenText(p).length, 0);
    expect(ONE_X.total).toBeCloseTo(chars / 15 + 5 * PART_GAP_SECONDS, 9);
  });

  it("speaks each part's title before its text", () => {
    expect(spoken(1)).toBe("How often. Every working day, at about forty branches.");
  });

  it("divides the speaking time by the rate; the pause stays", () => {
    const fast = estimate(SCRIPT, 2);
    expect(fast.parts[1]?.start).toBeCloseTo(spoken(0).length / 30 + PART_GAP_SECONDS, 9);
    expect(fast.total).toBeCloseTo((ONE_X.total - 5 * PART_GAP_SECONDS) / 2 + 5 * PART_GAP_SECONDS, 9);
  });

  it("C-LISTEN.anatomy rate 1 gives the clock '0:00 / 2:10' and a tick where each part starts", () => {
    // Six parts of 320 spoken characters: 1,920 / 15 = 128 s, plus five pauses of 0.5 s = 130.5 s.
    const parts = SCRIPT.parts.map((p) => ({ ...p, text: filler(320 - p.title.length - 2) }));
    const timeline = estimate({ parts }, 1);
    expect(parts.every((p) => spokenText(p).length === 320)).toBe(true);
    expect(`${clock(0)} / ${clock(timeline.total)}`).toBe("0:00 / 2:10");
    const step = 320 / 15 + PART_GAP_SECONDS;
    expect(timeline.parts.map((p) => p.start)).toEqual(
      [0, 1, 2, 3, 4, 5].map((i) => expect.closeTo(i * step, 9)),
    );
    expect(timeline.total).toBeCloseTo(130.5, 9);
  });
});

// ----- Playback -----------------------------------------------------------------------------------------------

describe("C-LISTEN.behaviour/2 play and pause", () => {
  it("plays the first part with the chosen voice, one utterance, at 1×", () => {
    const { synth, engine, state } = setup();
    expect(state()).toMatchObject({
      playing: false,
      position: 0,
      currentPart: "summary",
      rate: 1,
      error: false,
    });
    engine.play();
    expect(synth.spoken).toHaveLength(1);
    expect(synth.last.text).toBe(spoken(0));
    expect(synth.last.voice).toBe(VOICE_IN);
    expect(synth.last.lang).toBe("en-IN");
    expect(synth.last.rate).toBe(1);
    expect(state()).toMatchObject({ playing: true, position: 0, currentPart: "summary" });
  });

  it("pauses where it is and resumes from the start of that word", () => {
    const { synth, engine, state } = setup();
    engine.play();
    const at = spoken(0).indexOf("retype");
    synth.last.boundary(at + 3); // a boundary mid-word: resume goes back to the word's start
    const cancelsBefore = synth.cancels;
    engine.pause();
    expect(synth.cancels).toBe(cancelsBefore + 1);
    expect(state().playing).toBe(false);
    expect(state().position).toBeCloseTo((at + 3) / 15, 9);

    engine.toggle();
    expect(state().playing).toBe(true);
    expect(synth.last.text).toBe(spoken(0).slice(at));
    expect(state().position).toBeCloseTo(at / 15, 9);
  });

  it("emits every change to subscribers and stops after unsubscribe", () => {
    const { engine } = setup();
    const seen: boolean[] = [];
    const stop = engine.subscribe((s) => seen.push(s.playing));
    expect(seen).toEqual([false]);
    engine.play();
    stop();
    engine.pause();
    expect(seen).toEqual([false, true]);
  });
});

describe("C-LISTEN.behaviour/3 seek", () => {
  it("lands mid-part on the start of the word and re-speaks from there", () => {
    const { synth, engine, state } = setup();
    engine.play();
    const word = spoken(1).indexOf("working");
    engine.seek(startOf(1) + (word + 3) / 15); // three characters into "working"
    expect(synth.last.text).toBe("working day, at about forty branches.");
    expect(synth.last.rate).toBe(1);
    expect(state()).toMatchObject({ playing: true, currentPart: "often" });
    expect(state().position).toBeCloseTo(startOf(1) + word / 15, 9);
  });

  it("while paused, moves the playhead without speaking", () => {
    const { synth, engine, state } = setup();
    // One second in is character 15, the space after "Who it affects."; it snaps back to "affects."
    engine.seek(startOf(2) + 1);
    expect(synth.spoken).toHaveLength(0);
    expect(state()).toMatchObject({ playing: false, currentPart: "who" });
    engine.play();
    expect(synth.last.text).toBe(spoken(2).slice(spoken(2).indexOf("affects")));
  });

  it("a point in the pause after a part starts the next part", () => {
    const { synth, engine, state } = setup();
    engine.play();
    engine.seek(startOf(1) - PART_GAP_SECONDS / 2);
    expect(synth.last.text).toBe(spoken(1));
    expect(state().currentPart).toBe("often");
  });
});

describe("C-LISTEN.behaviour/1 the parts menu", () => {
  it("jumpTo starts a part from its beginning", () => {
    const { synth, engine, state } = setup();
    engine.play();
    engine.jumpTo("cost");
    expect(synth.last.text).toBe(spoken(3));
    expect(state()).toMatchObject({ playing: true, currentPart: "cost" });
    expect(state().position).toBeCloseTo(startOf(3), 9);
  });
});

describe("C-LISTEN.behaviour/2 speed", () => {
  it("cycles 1×, 1.25×, 1.5×, 2× and back to 1×", () => {
    const { engine, state } = setup();
    const rates = [state().rate];
    for (let i = 0; i < 4; i += 1) {
      engine.cycleSpeed();
      rates.push(state().rate);
    }
    expect(rates).toEqual([1, 1.25, 1.5, 2, 1]);
  });

  it("mid-part, cancels and re-speaks from the same word at the new speed (L-LISTEN/4)", () => {
    const { synth, engine, state } = setup();
    engine.play();
    const at = spoken(0).indexOf("same");
    synth.last.boundary(at);
    const position = state().position;
    const cancelsBefore = synth.cancels;
    engine.cycleSpeed();
    expect(synth.cancels).toBe(cancelsBefore + 1);
    expect(synth.spoken).toHaveLength(2);
    expect(synth.last.rate).toBe(1.25);
    expect(synth.last.text).toBe(spoken(0).slice(at));
    expect(state().position).toBeCloseTo(position, 9);
    expect(state()).toMatchObject({ playing: true, rate: 1.25 });
  });
});

describe("position tracking", () => {
  it("follows the voice's boundary events", () => {
    const { synth, engine, state } = setup();
    engine.jumpTo("often");
    engine.play();
    synth.last.boundary(15);
    expect(state().position).toBeCloseTo(startOf(1) + 1, 9);
  });

  it("falls back to the clock when no boundary events come, faster at a higher speed and held to the part", () => {
    const { time, engine, state } = setup();
    engine.cycleSpeed();
    engine.cycleSpeed();
    engine.cycleSpeed(); // 2×
    engine.play();
    time.advance(1000);
    expect(state().position).toBeCloseTo(2, 9);
    time.advance(60_000);
    expect(state().position).toBeCloseTo(spoken(0).length / 15, 9);
    expect(state().currentPart).toBe("summary");
  });

  it("stops using the clock once boundary events arrive", () => {
    const { synth, time, engine, state } = setup();
    engine.play();
    synth.last.boundary(15);
    time.advance(5000);
    expect(state().position).toBeCloseTo(1, 9);
  });
});

describe("C-LISTEN.behaviour/5 the end", () => {
  it("speaks the parts in order, one utterance each, then stops and returns to 0:00", () => {
    const { synth, time, engine, state } = setup();
    engine.play();
    for (let i = 0; i < 6; i += 1) {
      expect(synth.spoken).toHaveLength(i + 1);
      expect(synth.last.text).toBe(spoken(i));
      synth.last.end();
    }
    expect(synth.spoken).toHaveLength(6);
    expect(state()).toMatchObject({ playing: false, position: 0, currentPart: "summary" });
    expect(time.running()).toBe(false);
  });

  it("seeking to the very end does the same", () => {
    const { engine, state } = setup();
    engine.play();
    engine.seek(ONE_X.total + 10);
    expect(state()).toMatchObject({ playing: false, position: 0, currentPart: "summary" });
  });
});

describe("stale events from cancelled utterances", () => {
  it("ignores end, boundary and error from an utterance that was replaced", () => {
    const { synth, engine, state } = setup();
    engine.play();
    const old = synth.last;
    engine.jumpTo("who"); // the fake fires "interrupted" on `old` as it cancels
    expect(state()).toMatchObject({ playing: true, error: false, currentPart: "who" });
    const position = state().position;

    old.boundary(30);
    old.end();
    old.fail("synthesis-failed");
    expect(synth.spoken).toHaveLength(2);
    expect(state()).toMatchObject({ playing: true, error: false, currentPart: "who" });
    expect(state().position).toBe(position);
  });

  it("ignores events that arrive after a pause", () => {
    const { synth, engine, state } = setup();
    engine.play();
    const old = synth.last;
    engine.pause();
    old.end();
    expect(synth.spoken).toHaveLength(1);
    expect(state().playing).toBe(false);
  });
});

describe("L-LISTEN/7 the speech engine fails", () => {
  it("emits error: true and stops; the player's words are fixed", () => {
    const { synth, time, engine, state, states } = setup();
    engine.play();
    synth.last.fail("synthesis-failed");
    expect(state()).toMatchObject({ playing: false, error: true });
    expect(states.at(-1)?.error).toBe(true);
    expect(time.running()).toBe(false);
    expect(LISTEN_ERROR).toBe("Couldn’t prepare the audio. Try again.");
  });

  it("play again clears the error", () => {
    const { synth, engine, state } = setup();
    engine.play();
    synth.last.fail("voice-unavailable");
    engine.play();
    expect(state()).toMatchObject({ playing: true, error: false });
  });

  it("speech stopped by something else on the page is a pause, not an error", () => {
    const { synth, engine, state } = setup();
    engine.play();
    synth.last.fail("interrupted");
    expect(state()).toMatchObject({ playing: false, error: false });
  });
});

describe("dispose", () => {
  it("cancels speech, clears the clock and goes quiet", () => {
    const { synth, time, engine, states } = setup();
    engine.play();
    const cancelsBefore = synth.cancels;
    const emitted = states.length;
    engine.dispose();
    expect(synth.cancels).toBe(cancelsBefore + 1);
    expect(time.running()).toBe(false);
    engine.play();
    time.advance(1000);
    expect(synth.spoken).toHaveLength(1);
    expect(states).toHaveLength(emitted);
  });

  it("does not cancel anyone else's speech when it was not playing", () => {
    const { synth, engine } = setup();
    engine.dispose();
    expect(synth.cancels).toBe(0);
  });
});

// ----- Words ---------------------------------------------------------------------------------------------------

describe("C-LISTEN.behaviour/7 words for screen readers", () => {
  it("the play button carries the full length, singular and plural, dropping a zero part", () => {
    expect(playLabel(130)).toBe("Play the whole idea, 2 minutes 10 seconds");
    expect(playLabel(130.5)).toBe("Play the whole idea, 2 minutes 10 seconds");
    expect(playLabel(45)).toBe("Play the whole idea, 45 seconds");
    expect(playLabel(61)).toBe("Play the whole idea, 1 minute 1 second");
    expect(playLabel(120)).toBe("Play the whole idea, 2 minutes");
    expect(playLabel(1)).toBe("Play the whole idea, 1 second");
  });

  it("the line, the menu and the current part", () => {
    expect(progressLabel(42, 130)).toBe("Played 0:42 of 2:10");
    expect(jumpLabel("How often", 38)).toBe("Jump to How often, 0:38");
    expect(nowLabel("How often")).toBe("Now: How often");
  });

  it("the clock reads m:ss", () => {
    expect(clock(0)).toBe("0:00");
    expect(clock(5)).toBe("0:05");
    expect(clock(42.9)).toBe("0:42");
    expect(clock(130)).toBe("2:10");
    expect(clock(129.99999999)).toBe("2:10");
    expect(clock(-3)).toBe("0:00");
    expect(clock(Number.NaN)).toBe("0:00");
  });
});

// ----- Offline -------------------------------------------------------------------------------------------------

class MemoryStorage implements ListenStorage {
  readonly items = new Map<string, string>();
  get length(): number {
    return this.items.size;
  }
  key(index: number): string | null {
    return [...this.items.keys()][index] ?? null;
  }
  getItem(key: string): string | null {
    return this.items.get(key) ?? null;
  }
  setItem(key: string, value: string): void {
    this.items.set(key, value);
  }
  removeItem(key: string): void {
    this.items.delete(key);
  }
}

class BlockedStorage implements ListenStorage {
  get length(): number {
    throw new Error("SecurityError");
  }
  key(): string | null {
    throw new Error("SecurityError");
  }
  getItem(): string | null {
    throw new Error("SecurityError");
  }
  setItem(): void {
    throw new Error("QuotaExceededError");
  }
  removeItem(): void {
    throw new Error("SecurityError");
  }
}

const DAY = 86_400_000;
const SAVED_AT = Date.UTC(2026, 10, 16, 6, 30);

describe("C-LISTEN.behaviour/4 and L-LISTEN/5 save for offline", () => {
  it("keeps the masked script under listen:<ideaId> with the time it was saved, and reads it back", () => {
    const storage = new MemoryStorage();
    expect(saveOffline("idea-7", SCRIPT, storage, SAVED_AT)).toBe(true);
    expect([...storage.items.keys()]).toEqual(["listen:idea-7"]);
    expect(JSON.parse(storage.getItem("listen:idea-7") ?? "")).toEqual({ savedAt: SAVED_AT, script: SCRIPT });
    expect(loadOffline("idea-7", storage, SAVED_AT + DAY)).toEqual(SCRIPT);
  });

  it("stores nothing but the script's own fields", () => {
    const storage = new MemoryStorage();
    const parts: ListenPart[] = SCRIPT.parts.map((p) => ({ ...p, sharerWords: "not for the device" }));
    const script: ListenScript = Object.assign({ parts }, { ideaTitle: "not for the device" });
    saveOffline("idea-7", script, storage, SAVED_AT);
    const raw = storage.getItem("listen:idea-7") ?? "";
    expect(raw).not.toContain("not for the device");
    expect(loadOffline("idea-7", storage, SAVED_AT)).toEqual(SCRIPT);
  });

  it("reads an entry older than 30 days as absent and removes it", () => {
    const storage = new MemoryStorage();
    saveOffline("idea-7", SCRIPT, storage, SAVED_AT);
    expect(OFFLINE_DAYS).toBe(30);
    expect(loadOffline("idea-7", storage, SAVED_AT + 30 * DAY)).toEqual(SCRIPT);
    expect(loadOffline("idea-7", storage, SAVED_AT + 30 * DAY + 1)).toBeNull();
    expect(storage.items.size).toBe(0);
  });

  it("forgets on request (the idea was decided) and returns null when nothing is saved", () => {
    const storage = new MemoryStorage();
    saveOffline("idea-7", SCRIPT, storage, SAVED_AT);
    forgetOffline("idea-7", storage);
    expect(loadOffline("idea-7", storage, SAVED_AT)).toBeNull();
    expect(loadOffline("idea-8", storage, SAVED_AT)).toBeNull();
  });

  it("removes an unreadable entry", () => {
    const storage = new MemoryStorage();
    storage.setItem("listen:idea-7", "{not json");
    storage.setItem(
      "listen:idea-8",
      JSON.stringify({ savedAt: SAVED_AT, script: { parts: [{ part: "x" }] } }),
    );
    expect(loadOffline("idea-7", storage, SAVED_AT)).toBeNull();
    expect(loadOffline("idea-8", storage, SAVED_AT)).toBeNull();
    expect(storage.items.size).toBe(0);
  });

  it("prunes every expired script and leaves everything else alone", () => {
    const storage = new MemoryStorage();
    saveOffline("old", SCRIPT, storage, SAVED_AT - 31 * DAY);
    saveOffline("new", SCRIPT, storage, SAVED_AT - DAY);
    storage.setItem("theme", "light");
    pruneOffline(storage, SAVED_AT);
    expect([...storage.items.keys()].sort()).toEqual(["listen:new", "theme"]);
  });

  it("never throws when storage is blocked, as in a private window", () => {
    const storage = new BlockedStorage();
    expect(saveOffline("idea-7", SCRIPT, storage, SAVED_AT)).toBe(false);
    expect(loadOffline("idea-7", storage, SAVED_AT)).toBeNull();
    expect(() => forgetOffline("idea-7", storage)).not.toThrow();
    expect(() => pruneOffline(storage, SAVED_AT)).not.toThrow();
  });
});

describe("L-LISTEN/1 the worker's chapters match the engine's estimate", () => {
  it("reads services/worker/desk/listen_vector.json and lands on the same ticks", () => {
    const vector = JSON.parse(
      readFileSync(path.resolve(__dirname, "../../../../services/worker/desk/listen_vector.json"), "utf8"),
    ) as { script: ListenScript; chapters: { part: string; at: number }[]; total_seconds: number };
    const timeline = estimate(vector.script);
    expect(timeline.parts.map((p) => ({ part: p.part, at: Math.round(p.start * 10) / 10 }))).toEqual(
      vector.chapters,
    );
    expect(Math.round(timeline.total * 10) / 10).toBe(vector.total_seconds);
  });
});
