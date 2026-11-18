/**
 * POST /api/flags/events (P-DECISIONS.experiments, BLD-C173, BLD-C174): only listed codes on a screen the flag
 * changes; S2's events and S3's notes name a draft of the person's own (422 otherwise, and for a draft id that is not a
 * UUID); S3's phone S-04 and S2's close match log the exposure through lane A's reader for the screen they name; a
 * flood is kept once per draft and outcome (the store's job, so the route just writes). Synthetic ids only.
 */
import { NextResponse } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const ME = {
  id: "0b9c2d1e-1111-4a2b-8c3d-000000000001",
  contributorCode: "CTR-0a1b2c",
  roles: ["contributor"],
};
const MINE = "6f1c2a8e-3b4d-4e5f-8a9b-0c1d2e3f4a5b";
const THEIRS = "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d";

let logged: Array<Record<string, unknown>>;
let exposed: string[];

vi.mock("@/server/auth/authorize", () => ({ signedIn: async () => ME }));
vi.mock("@/server/flag-events", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/server/flag-events")>();
  return {
    ...real,
    ownDraft: async (_code: string | null, id: string) => id === MINE,
    variantOn: async (_me: unknown, key: string, screen: string) => {
      exposed.push(`${key}:${screen}`);
      return "default";
    },
    logFlagEvent: async (e: Record<string, unknown>) => {
      logged.push(e);
      return "written";
    },
  };
});

const { POST } = await import("@/app/api/flags/events/route");

async function send(body: Record<string, unknown>) {
  const res = (await POST(
    new Request("http://localhost/api/flags/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  )) as NextResponse;
  return { status: res.status, body: res.status === 204 ? null : await res.json() };
}

beforeEach(() => {
  logged = [];
  exposed = [];
});

describe("POST /api/flags/events: codes only, drafts of the person's own (BLD-C174)", () => {
  it("takes a listed event; S3's listening needs no draft", async () => {
    expect(
      (await send({ flag: "s3", event: "s3.listen", outcome: "no_permission", screen: "S-04" })).status,
    ).toBe(204);
    expect(logged).toEqual([
      {
        userId: ME.id,
        key: "s3",
        event: "s3.listen",
        outcome: "no_permission",
        screen: "S-04",
        draftId: null,
      },
    ]);
    expect(exposed).toEqual([]);
  });

  it("422 for anything not listed, on a screen the flag does not change, or for S1", async () => {
    for (const body of [
      { flag: "s3", event: "s3.listen", outcome: "said something", screen: "S-04" },
      { flag: "s3", event: "s3.listen", outcome: "started", screen: "S-05" },
      { flag: "s1", event: "s1.often", outcome: "answered", screen: "S-04B" },
      { flag: "s9", event: "s9.x", outcome: "y", screen: "S-04" },
    ]) {
      const r = await send(body);
      expect(r.status).toBe(422);
      expect(r.body.error.code).toBe("event_invalid");
    }
    expect(logged).toEqual([]);
  });

  it("S2 events and S3's notes need a draft of the person's own; a bad id is refused, not logged", async () => {
    const cases: Array<[Record<string, unknown>, string]> = [
      [{ flag: "s2", event: "s2.check", outcome: "opened", screen: "S-05" }, "draft_required"],
      [{ flag: "s3", event: "s3.note", outcome: "corrected", screen: "S-04" }, "draft_required"],
      [
        { flag: "s2", event: "s2.check", outcome: "opened", screen: "S-05", draft_id: "not-a-uuid" },
        "draft_invalid",
      ],
      [
        { flag: "s2", event: "s2.compare", outcome: "shown", screen: "S-05", draft_id: THEIRS },
        "draft_invalid",
      ],
      [{ flag: "s3", event: "s3.listen", outcome: "started", screen: "S-04", draft_id: 42 }, "draft_invalid"],
    ];
    for (const [body, code] of cases) {
      const r = await send(body);
      expect(r.status).toBe(422);
      expect(r.body.error.code).toBe(code);
    }
    expect(logged).toEqual([]);
    expect(
      (await send({ flag: "s3", event: "s3.note", outcome: "as_heard", screen: "S-04B", draft_id: MINE }))
        .status,
    ).toBe(204);
    expect(logged[0]).toMatchObject({ event: "s3.note", draftId: MINE });
  });
});

describe("the exposures only the browser can tell (BLD-C173)", () => {
  it("S3's phone S-04 logs the exposure through lane A's reader, and no event row", async () => {
    expect((await send({ flag: "s3", event: "s3.exposure", outcome: "shown", screen: "S-04" })).status).toBe(
      204,
    );
    expect(exposed).toEqual(["s3:S-04"]);
    expect(logged).toEqual([]);
    // Not from S-04B
    expect((await send({ flag: "s3", event: "s3.exposure", outcome: "shown", screen: "S-04B" })).status).toBe(
      422,
    );
    expect(exposed).toEqual(["s3:S-04"]);
  });

  it("S2's close match on a fresh Check it logs the exposure and the event; opening it alone does not expose", async () => {
    await send({ flag: "s2", event: "s2.check", outcome: "opened", screen: "S-05", draft_id: MINE });
    expect(exposed).toEqual([]);
    await send({ flag: "s2", event: "s2.check", outcome: "close_match", screen: "S-05", draft_id: MINE });
    expect(exposed).toEqual(["s2:S-05"]);
    expect(logged.map((e) => e.outcome)).toEqual(["opened", "close_match"]);
  });
});
