/** L-DRAFT, A-API.draft-stream (BLD-C075): the events of one run, in the contract's order, each sent once. */
import { describe, expect, it } from "vitest";

import { freshSent, nextEvents, partValue, sse, type LiveRunView } from "@/lib/draft-stream";

const run = (over: Partial<LiveRunView> = {}): LiveRunView => ({
  id: "run-1",
  state: "running",
  parts: [
    { key: "title", mean_ms: 1800 },
    { key: "often", mean_ms: 900 },
  ],
  part_ms: {},
  receipt: [],
  suggestions: [],
  ready: false,
  hidden: {
    spans: [{ start: 50, end: 60, kind: "folio" }],
    details: [{ id: "h1", kind: "folio", masked: "Folio ••••89", state: "hidden" }],
  },
  ...over,
});

describe("L-DRAFT stream (A-API.draft-stream)", () => {
  it("L-DRAFT.stream/1: run with the loader's means, then hidden before any part", () => {
    const sent = freshSent("run-1");
    const events = nextEvents(run(), {}, sent);
    expect(events.map((e) => e.event)).toEqual(["run", "hidden"]);
    expect(events[0]!.data).toEqual({
      run_id: "run-1",
      parts: [
        { key: "title", mean_ms: 1800 },
        { key: "often", mean_ms: 900 },
      ],
    });
    expect(nextEvents(run(), {}, sent)).toEqual([]); // nothing twice
  });

  it("L-DRAFT.stream/2: each part once, as it lands, in whatever order; the title carries its summary", () => {
    const sent = freshSent("run-1");
    nextEvents(run(), {}, sent);
    const parts = {
      often: {
        state: "filled",
        value: "About 40 calls a day",
        why: "From your words: “about 40 calls a day”",
        source_quote: "about 40 calls a day",
      },
    };
    const first = nextEvents(run({ part_ms: { often: 640 } }), parts, sent);
    expect(first).toEqual([
      {
        event: "part",
        data: {
          key: "often",
          state: "filled",
          value: "About 40 calls a day",
          why: "From your words: “about 40 calls a day”",
          source_quote: "about 40 calls a day",
          took_ms: 640,
        },
      },
    ]);
    const title = {
      state: "filled",
      value: { title: "Investors call about rejections", summary: "Two lines.", pinned: [] },
      why: "From your first sentence.",
      source_quote: null,
    };
    const second = nextEvents(run({ part_ms: { often: 640, title: 1500 } }), { ...parts, title }, sent);
    expect(second).toHaveLength(1);
    expect(second[0]!.data).toMatchObject({
      key: "title",
      value: { title: "Investors call about rejections", summary: "Two lines." },
    });
  });

  it("L-DRAFT.stream/3: a part that failed says so; then receipt and done close the run", () => {
    const sent = freshSent("run-1");
    const events = nextEvents(
      run({
        state: "done",
        part_ms: { title: 0 },
        receipt: ["Hid 1 personal detail from everyone but you: Folio ••••89."],
        suggestions: ["Say how often it happens"],
        ready: false,
      }),
      { title: { state: "failed", value: null, why: null, source_quote: null } },
      sent,
    );
    expect(events.map((e) => e.event)).toEqual(["run", "hidden", "part", "part", "receipt", "done"]);
    expect(events[2]!.data).toMatchObject({
      key: "title",
      state: "failed",
      value: { title: null, summary: null },
    });
    expect(events[3]!.data).toMatchObject({ key: "often", state: "filled", value: null, took_ms: 0 });
    expect(events[5]!.data).toEqual({ ready: false });
    expect(sent.done).toBe(true);
    expect(nextEvents(run({ state: "done" }), {}, sent)).toEqual([]);
  });

  it("L-DRAFT.stream/4: another run's view sends nothing for this one", () => {
    expect(nextEvents(run({ id: "run-2" }), {}, freshSent("run-1"))).toEqual([]);
  });

  it("formats server-sent events and part values", () => {
    expect(sse({ event: "done", data: { ready: true } })).toBe('event: done\ndata: {"ready":true}\n\n');
    expect(partValue("who", ["Investors"])).toEqual(["Investors"]);
    expect(partValue("area", undefined)).toBeNull();
  });
});
