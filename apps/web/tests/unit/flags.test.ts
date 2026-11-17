/**
 * P-DECISIONS.experiments, the flag reader (BLD-C170 to C174): `variantFor` and `logExposure` against an in-memory
 * stand-in for the four tables, the S1 interview's place, the exposure and event routes, and the routes' gates.
 * Synthetic ids only; no words anywhere.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

type Row = Record<string, unknown>;
const tables: Record<string, Row[]> = {};
let failing = false;

/** Just the query shapes server/flags.ts uses: select … where = … executeTakeFirst/execute; insert … onConflict. */
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
    let ignore = false;
    const q = {
      values: (v: Row) => {
        row = v;
        return q;
      },
      onConflict: () => {
        ignore = true;
        return q;
      },
      returning: () => q,
      execute: async () => {
        if (failing) throw new Error("db down");
        const list = (tables[table] ??= []);
        const key =
          table === "flag_assignments"
            ? ["flag_key", "user_id"]
            : table === "flag_events" && row.flag_key === "s1"
              ? ["draft_id", "event"]
              : null;
        if (key && list.some((r) => key.every((k) => r[k] === row[k]))) {
          if (!ignore) throw new Error("duplicate");
          return [];
        }
        list.push({ ...row });
        return [row];
      },
      executeTakeFirst: async () => {
        const out = await q.execute();
        return { ...(out[0] ?? {}), numInsertedOrUpdatedRows: BigInt(out.length) };
      },
    };
    return q;
  };
  return { selectFrom: select, insertInto: insert };
}

vi.mock("@/server/db", () => ({ getDb: () => fakeDb() }));
const switches = new Map<string, "on" | "off">();
vi.mock("@/server/killswitch", () => ({
  switchStates: async () => switches,
  isOn: (s: Map<string, string>, n: string) => s.get(n) === "on",
}));

const flags = await import("@/server/flags");
const { placeFrom, nextQuestion, waitingToBuild, FLAG_EVENTS } = await import("@/lib/flags");

const U1 = "0b9c2d1e-1111-4a2b-8c3d-000000000001";
const U2 = "0b9c2d1e-1111-4a2b-8c3d-000000000002";

function seed(state: "on" | "off" = "on", percent = 0) {
  for (const k of Object.keys(tables)) delete tables[k];
  tables.flags = ["s1", "s2", "s3"].map((key) => ({ key, state, alternative_percent: percent }));
  tables.flag_assignments = [];
  tables.flag_exposures = [];
  tables.flag_events = [];
}

beforeEach(() => {
  failing = false;
  seed();
  switches.clear();
  for (const n of ["capture.voice", "speech.hosted", "submissions"]) switches.set(n, "on");
});

describe("P-DECISIONS.experiments: variantFor (BLD-C170, BLD-C171)", () => {
  it("ships at 0 %: everyone gets the default and nothing is written", async () => {
    expect(await flags.variantFor(U1, "s1")).toBe("default");
    expect(tables.flag_assignments).toEqual([]);
  });

  it("a flag that is off gives the default, even over an explicit assignment, and logs no exposure", async () => {
    seed("off", 100);
    tables.flag_assignments!.push({ flag_key: "s1", user_id: U1, variant: "alternative" });
    expect(await flags.variantFor(U1, "s1")).toBe("default");
    expect(await flags.logExposure(U1, "s1", "S-04")).toBeNull();
    expect(tables.flag_exposures).toEqual([]);
  });

  it("an explicit flag_assignments row wins over the percentage", async () => {
    seed("on", 0);
    tables.flag_assignments!.push({
      flag_key: "s3",
      user_id: U1,
      variant: "alternative",
      assigned_by: "e2e",
    });
    expect(await flags.variantFor(U1, "s3")).toBe("alternative");
    expect(await flags.variantFor(U1, "s1")).toBe("default");
  });

  it("by the rule, a stable hash against alternative_percent, written once so it never flips", async () => {
    seed("on", 100);
    expect(await flags.variantFor(U1, "s2")).toBe("alternative");
    expect(tables.flag_assignments).toEqual([
      { flag_key: "s2", user_id: U1, variant: "alternative", assigned_by: "rule" },
    ]);
    tables.flags!.find((f) => f.key === "s2")!.alternative_percent = 0; // HR lowers it: the person keeps theirs
    expect(await flags.variantFor(U1, "s2")).toBe("alternative");
    expect(tables.flag_assignments).toHaveLength(1);
  });

  it("the bucket is stable, 0 to 99, and independent between flags", () => {
    expect(flags.bucketOf(U1, "s1")).toBe(flags.bucketOf(U1, "s1"));
    const buckets = Array.from({ length: 400 }, (_, i) =>
      flags.bucketOf(`0b9c2d1e-1111-4a2b-8c3d-${String(i).padStart(12, "0")}`, "s1"),
    );
    expect(Math.min(...buckets)).toBeGreaterThanOrEqual(0);
    expect(Math.max(...buckets)).toBeLessThan(100);
    const under20 = buckets.filter((b) => b < 20).length / buckets.length;
    expect(under20).toBeGreaterThan(0.12);
    expect(under20).toBeLessThan(0.28);
    const differ = Array.from(
      { length: 50 },
      (_, i) => `0b9c2d1e-1111-4a2b-8c3d-${String(i).padStart(12, "0")}`,
    ).some((u) => flags.bucketOf(u, "s1") !== flags.bucketOf(u, "s3"));
    expect(differ).toBe(true);
  });

  it("any database error gives the default: a flag never fails a page", async () => {
    failing = true;
    expect(await flags.variantFor(U1, "s1")).toBe("default");
    expect(await flags.logExposure(U1, "s1", "S-04")).toBeNull();
    expect(await flags.interviewPlace(U1, U2)).toEqual({ started: false, done: {}, ended: null });
    expect(await flags.composeFlags(U1)).toEqual({ interview: false, voiceFirst: null });
  });
});

describe("exposures and events (BLD-C173, BLD-C174)", () => {
  it("one exposure per call, with the variant the server decided, on a screen the flag changes only", async () => {
    tables.flag_assignments!.push({ flag_key: "s1", user_id: U1, variant: "alternative" });
    expect(await flags.logExposure(U1, "s1", "S-04B")).toBe("alternative");
    expect(await flags.logExposure(U2, "s1", "S-04")).toBe("default");
    expect(await flags.logExposure(U1, "s1", "S-05")).toBeNull();
    expect(tables.flag_exposures).toEqual([
      { flag_key: "s1", user_id: U1, variant: "alternative", screen: "S-04B" },
      { flag_key: "s1", user_id: U2, variant: "default", screen: "S-04" },
    ]);
  });

  it("S1's steps are kept once per draft: a retry writes nothing", async () => {
    const step = {
      userId: U1,
      key: "s1" as const,
      variant: "alternative" as const,
      screen: "S-04B",
      draftId: U2,
    };
    expect(await flags.logFlagEvent({ ...step, event: "s1.often", outcome: "answered" })).toBe(true);
    expect(await flags.logFlagEvent({ ...step, event: "s1.often", outcome: "answered" })).toBe(false);
    expect(tables.flag_events).toHaveLength(1);
  });

  it("the events route takes only listed codes; S1's are not open to it", () => {
    expect(FLAG_EVENTS.s1).toEqual({});
    expect(FLAG_EVENTS.s3["s3.note"]).toEqual(["as_heard", "corrected"]);
    expect(FLAG_EVENTS.s3["s3.listen"]).toContain("typed_instead");
  });
});

describe("S3: kill switches beat the flag (BLD-C175)", () => {
  it("voice first only while voice can run; otherwise the alternative starts with typing", async () => {
    tables.flag_assignments!.push({ flag_key: "s3", user_id: U1, variant: "alternative" });
    expect(await flags.composeFlags(U1)).toEqual({ interview: false, voiceFirst: "listen" });
    switches.set("speech.hosted", "off");
    expect(await flags.composeFlags(U1)).toEqual({ interview: false, voiceFirst: "voice_off" });
    switches.set("speech.hosted", "on");
    switches.set("capture.voice", "off");
    expect((await flags.composeFlags(U1)).voiceFirst).toBe("voice_off");
    expect((await flags.composeFlags(U2)).voiceFirst).toBeNull();
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
      { flag_key: "s1", user_id: U1, draft_id: U2, event: "s1.start", outcome: "started" },
      { flag_key: "s1", user_id: U1, draft_id: U2, event: "s1.often", outcome: "skipped" },
      { flag_key: "s1", user_id: U2, draft_id: U2, event: "s1.who", outcome: "answered" },
    );
    expect(await flags.interviewPlace(U1, U2)).toEqual({
      started: true,
      done: { often: "skipped" },
      ended: null,
    });
  });
});
