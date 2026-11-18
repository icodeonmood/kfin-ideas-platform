/**
 * P-DECISIONS.experiments, lane C's part on lane A's reader (BLD-A216; BLD-C170, C172, C174, C175): the variants the
 * pages hand Tell it and Check it (lane A's `flagVariant`, any failure read as the default), the kill switches S3
 * needs, the deciding events as codes (nothing while a flag is off, S1's steps once per draft) and S1's place read
 * back. An in-memory stand-in for the two tables these read and write. Synthetic ids only; no words anywhere.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

type Row = Record<string, unknown>;
const tables: Record<string, Row[]> = {};
let failing = false;
const variants = new Map<string, "default" | "alternative">();
let readerFails = false;
let readerHangs = false;
const exposures: string[] = [];

function fakeDb() {
  const select = (table: string) => {
    const filters: [string, unknown][] = [];
    const q = {
      select: () => q,
      where: (col: string, _op: string, val: unknown) => {
        filters.push([col, val]);
        return q;
      },
      orderBy: () => q,
      execute: async () => {
        if (failing) throw new Error("db down");
        return (tables[table] ?? []).filter((r) => filters.every(([c, v]) => r[c] === v));
      },
      executeTakeFirst: async () => (await q.execute())[0],
    };
    return q;
  };
  const insert = (table: string) => {
    let row: Row = {};
    const q = {
      values: (v: Row) => {
        row = v;
        return q;
      },
      onConflict: () => q,
      executeTakeFirst: async () => {
        if (failing) throw new Error("db down");
        const list = (tables[table] ??= []);
        const dup =
          table === "flag_events" &&
          row.flag_key === "s1" &&
          list.some((r) => r.draft_id === row.draft_id && r.event === row.event);
        if (!dup) list.push({ ...row });
        return { numInsertedOrUpdatedRows: BigInt(dup ? 0 : 1) };
      },
    };
    return q;
  };
  return { selectFrom: select, insertInto: insert };
}

vi.mock("@/server/db", () => ({ getDb: () => fakeDb() }));
vi.mock("@/server/flags", () => ({
  flagVariant: async (user: { id: string }, key: string, screen: string) => {
    if (readerFails) throw new Error("db down");
    if (readerHangs) return new Promise(() => undefined);
    exposures.push(`${key}:${screen}`);
    return variants.get(`${key}:${user.id}`) ?? "default";
  },
  flagsFor: async (userId: string) =>
    Object.fromEntries(["s1", "s2", "s3"].map((k) => [k, variants.get(`${k}:${userId}`) ?? "default"])),
}));
const switches = new Map<string, "on" | "off">();
vi.mock("@/server/killswitch", () => ({
  switchStates: async () => switches,
  isOn: (s: Map<string, string>, n: string) => s.get(n) === "on",
}));

const ev = await import("@/server/flag-events");
const { placeFrom, nextQuestion, waitingToBuild, FLAG_EVENTS } = await import("@/lib/flags");

const U1 = { id: "0b9c2d1e-1111-4a2b-8c3d-000000000001" };
const U2 = { id: "0b9c2d1e-1111-4a2b-8c3d-000000000002" };
const DRAFT = "6f1c2a8e-3b4d-4e5f-8a9b-0c1d2e3f4a5b";

beforeEach(() => {
  for (const k of Object.keys(tables)) delete tables[k];
  tables.flags = ["s1", "s2", "s3"].map((key) => ({ key, state: "on" }));
  tables.flag_events = [];
  failing = false;
  readerFails = false;
  readerHangs = false;
  exposures.length = 0;
  variants.clear();
  switches.clear();
  for (const n of ["capture.voice", "speech.hosted", "submissions"]) switches.set(n, "on");
});

describe("P-DECISIONS.experiments: the variants the pages hand over (lane A's reader, BLD-C170)", () => {
  it("Tell it gets S1 from flagVariant for its own screen (the exposure) and S3 without one; a failure is the default", async () => {
    variants.set(`s1:${U1.id}`, "alternative");
    expect(await ev.composeFlags(U1, "S-04")).toEqual({ interview: true, voiceFirst: null });
    expect(await ev.composeFlags(U2, "S-04B")).toEqual({ interview: false, voiceFirst: null });
    // S3's exposure waits for the browser to know it is a phone (BLD-C173)
    expect(exposures).toEqual(["s1:S-04", "s1:S-04B"]);
    readerFails = true;
    expect(await ev.composeFlags(U1, "S-04")).toEqual({ interview: false, voiceFirst: null });
    expect(await ev.variantOn(U1, "s2", "S-05")).toBe("default");
  });

  it("a hung reader never holds up the page: the default after FLAG_WAIT_MS", async () => {
    vi.useFakeTimers();
    try {
      readerHangs = true;
      const flags = ev.composeFlags(U1, "S-04");
      const s2 = ev.variantOn(U1, "s2", "S-05");
      await vi.advanceTimersByTimeAsync(ev.FLAG_WAIT_MS);
      expect(await flags).toEqual({ interview: false, voiceFirst: null });
      expect(await s2).toBe("default");
    } finally {
      vi.useRealTimers();
    }
  });

  it("S3: kill switches beat the flag; voice first only while voice can run (BLD-C175)", async () => {
    variants.set(`s3:${U1.id}`, "alternative");
    expect((await ev.composeFlags(U1, "S-04")).voiceFirst).toBe("listen");
    switches.set("speech.hosted", "off");
    expect((await ev.composeFlags(U1, "S-04")).voiceFirst).toBe("voice_off");
    switches.set("speech.hosted", "on");
    switches.set("capture.voice", "off");
    expect((await ev.composeFlags(U1, "S-04")).voiceFirst).toBe("voice_off");
    switches.set("capture.voice", "on");
    switches.set("submissions", "off");
    expect((await ev.composeFlags(U1, "S-04")).voiceFirst).toBe("voice_off");
  });

  it("S1's route asks without logging: in the alternative only while the flag is on", async () => {
    variants.set(`s1:${U1.id}`, "alternative");
    expect(await ev.inAlternative(U1.id, "s1")).toBe(true);
    expect(await ev.inAlternative(U2.id, "s1")).toBe(false);
    tables.flags!.find((f) => f.key === "s1")!.state = "off";
    expect(await ev.inAlternative(U1.id, "s1")).toBe(false);
  });
});

describe("the deciding events, codes only (BLD-C174)", () => {
  it("logged with the person's variant while the flag is on; nothing while it is off", async () => {
    variants.set(`s3:${U1.id}`, "alternative");
    const base = {
      userId: U1.id,
      key: "s3" as const,
      event: "s3.note",
      outcome: "corrected",
      screen: "S-04",
    };
    expect(await ev.logFlagEvent(base)).toBe("written");
    expect(tables.flag_events).toEqual([
      {
        flag_key: "s3",
        user_id: U1.id,
        variant: "alternative",
        draft_id: null,
        screen: "S-04",
        event: "s3.note",
        outcome: "corrected",
      },
    ]);
    tables.flags!.find((f) => f.key === "s3")!.state = "off";
    expect(await ev.logFlagEvent(base)).toBe("off");
    expect(tables.flag_events).toHaveLength(1);
  });

  it("S1's steps are kept once per draft: a retry writes nothing", async () => {
    const step = {
      userId: U1.id,
      key: "s1" as const,
      variant: "alternative" as const,
      screen: "S-04B",
      draftId: DRAFT,
    };
    expect(await ev.logFlagEvent({ ...step, event: "s1.often", outcome: "answered" })).toBe("written");
    expect(await ev.logFlagEvent({ ...step, event: "s1.often", outcome: "answered" })).toBe("exists");
    expect(tables.flag_events).toHaveLength(1);
  });

  it("a database error never fails the screen", async () => {
    failing = true;
    expect(
      await ev.logFlagEvent({
        userId: U1.id,
        key: "s2",
        variant: "default",
        event: "s2.check",
        outcome: "opened",
        screen: "S-05",
      }),
    ).toBe("failed");
    expect(await ev.interviewPlace(U1.id, DRAFT)).toEqual({ started: false, done: {}, ended: null });
    expect(await ev.ownDraft("CTR-0a1b2c", DRAFT)).toBe(false);
  });

  it("the events route takes only listed codes; S1's go through the interview's route", () => {
    expect(FLAG_EVENTS.s1).toEqual({});
    expect(FLAG_EVENTS.s3["s3.note"]).toEqual(["as_heard", "corrected"]);
    expect(FLAG_EVENTS.s3["s3.listen"]).toContain("typed_instead");
    expect(FLAG_EVENTS.s2["s2.check"]).toEqual(["opened", "close_match"]);
    expect(FLAG_EVENTS.s3["s3.exposure"]).toEqual(["shown"]);
    expect(FLAG_EVENTS.s2["s2.compare"]).toEqual([
      "shown",
      "moved_on",
      "kept_separate",
      "merge_asked",
      "mine_is_different",
    ]);
  });
});

describe("S1, the interview's place (L-DRAFT.parts/10, BLD-C172)", () => {
  it("is read from its steps: started, each question answered or skipped, then finished or left", () => {
    const place = placeFrom([
      { event: "s1.start", outcome: "started" },
      { event: "s1.often", outcome: "answered" },
    ]);
    expect(place).toEqual({ started: true, done: { often: "answered" }, ended: null });
    expect(nextQuestion(place)).toBe("who");
    expect(waitingToBuild(place)).toBe(true);
    const skipped = placeFrom([
      { event: "s1.start", outcome: "started" },
      { event: "s1.often", outcome: "skipped" },
      { event: "s1.who", outcome: "skipped" },
    ]);
    expect(nextQuestion(skipped)).toBe("size");
    expect(waitingToBuild(skipped)).toBe(false);
    const ended = placeFrom([
      { event: "s1.start", outcome: "started" },
      { event: "s1.end", outcome: "left" },
    ]);
    expect(nextQuestion(ended)).toBeNull();
    expect(ended.ended).toBe("left");
    expect(nextQuestion(placeFrom([]))).toBeNull();
  });

  it("is kept with the draft: read back for its own person and draft", async () => {
    tables.flag_events!.push(
      { flag_key: "s1", user_id: U1.id, draft_id: DRAFT, event: "s1.start", outcome: "started" },
      { flag_key: "s1", user_id: U1.id, draft_id: DRAFT, event: "s1.often", outcome: "skipped" },
      { flag_key: "s1", user_id: U2.id, draft_id: DRAFT, event: "s1.who", outcome: "answered" },
    );
    expect(await ev.interviewPlace(U1.id, DRAFT)).toEqual({
      started: true,
      done: { often: "skipped" },
      ended: null,
    });
  });
});
