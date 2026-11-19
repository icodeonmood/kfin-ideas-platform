/**
 * S1 "Interview", the route (P-DECISIONS.experiments, L-DRAFT.parts/10; BLD-C172): POST /api/drafts/:id/interview.
 * An answer goes through the worker's own messages path, kept without building; the last question (or moving on)
 * builds the draft once, and only if something was answered; each step is kept once per draft; a retry writes
 * nothing twice; only the person's own draft, and only in the alternative. Synthetic words only.
 */
import { NextRequest, NextResponse } from "next/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

const DRAFT = "6f1c2a8e-3b4d-4e5f-8a9b-0c1d2e3f4a5b";
const ME = {
  id: "0b9c2d1e-1111-4a2b-8c3d-000000000001",
  contributorCode: "CTR-0a1b2c",
  roles: ["contributor"],
};

type Ev = { event: string; outcome: string };
let events: Ev[];
let variant: "default" | "alternative";
let own: boolean;
let worker: { method: string; path: string; body: Record<string, unknown> }[];
let assistantOff: boolean;
let eventsDown: boolean;
let endDownOnce: boolean;

vi.mock("@/server/auth/authorize", () => ({ authorize: async () => ME }));
vi.mock("@/server/worker", () => ({
  workerFetch: vi.fn(async (path: string, init: RequestInit = {}) => {
    const body = typeof init.body === "string" ? (JSON.parse(init.body) as Record<string, unknown>) : {};
    worker.push({ method: init.method ?? "GET", path: path.split("?")[0]!, body });
    if (path.includes("/runs")) {
      if (assistantOff) return Response.json({ error: "assistant_off" }, { status: 409 });
      return Response.json({ run_id: "r-build" }, { status: 202 });
    }
    if (path.includes("/messages"))
      return Response.json(
        {
          run_id: null,
          message: { id: "m-2", text: body.text, spans: [] },
          draft: { id: DRAFT, messages: [] },
        },
        { status: 202 },
      );
    return Response.json({ id: DRAFT, messages: [], run: { id: "r-build", state: "running" } });
  }),
}));
vi.mock("@/server/flag-events", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/server/flag-events")>();
  const { placeFrom } = await import("@/lib/flags");
  return {
    ...real,
    ownDraft: async () => own,
    // A build is a /runs call the worker took: once one has been made since the last answer, it is not made again.
    builtSinceAnswers: async () => worker.some((w) => w.path.endsWith("/runs")) && !assistantOff,
    inAlternative: async () => variant === "alternative",
    interviewPlace: async () => placeFrom(events),
    logFlagEvent: async (e: { event: string; outcome: string }) => {
      if (events.some((x) => x.event === e.event)) return "exists";
      if (eventsDown || (endDownOnce && e.event === "s1.end")) {
        endDownOnce = false;
        return "failed";
      }
      events.push({ event: e.event, outcome: e.outcome });
      return "written";
    },
  };
});

const { POST } = await import("@/app/api/drafts/[id]/interview/route");

function call(body: Record<string, unknown>, key?: string) {
  const req = new NextRequest(`http://localhost/api/drafts/${DRAFT}/interview`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(key ? { "Idempotency-Key": key } : {}) },
    body: JSON.stringify(body),
  });
  return POST(req, { params: Promise.resolve({ id: DRAFT }) }) as Promise<NextResponse>;
}

beforeEach(() => {
  events = [];
  variant = "alternative";
  own = true;
  worker = [];
  assistantOff = false;
  eventsDown = false;
  endDownOnce = false;
});

describe("L-DRAFT.parts/10 S-04B: the interview's steps", () => {
  it("starts once; an answer goes in as the person's words, kept without building", async () => {
    expect((await (await call({ action: "start" })).json()).interview).toEqual({
      started: true,
      done: {},
      ended: null,
    });
    await call({ action: "start" });
    expect(events).toEqual([{ event: "s1.start", outcome: "started" }]);

    const res = await call(
      { action: "answer", question: "often", text: "About 20 times a week" },
      "key-often-001",
    );
    const out = await res.json();
    expect(res.status).toBe(200);
    expect(worker).toEqual([
      {
        method: "POST",
        path: `/internal/drafts/${DRAFT}/messages`,
        body: expect.objectContaining({
          text: "About 20 times a week",
          via: "typed",
          defer_run: true,
          client_id: "key-often-001",
        }),
      },
    ]);
    expect(out.interview.done).toEqual({ often: "answered" });
    expect(out.run_id).toBeNull();
    expect(out.message.id).toBe("m-2");
  });

  it("the last one builds the draft once, with what was answered, and ends the interview", async () => {
    events = [
      { event: "s1.start", outcome: "started" },
      { event: "s1.often", outcome: "answered" },
      { event: "s1.who", outcome: "skipped" },
    ];
    const out = await (await call({ action: "skip", question: "size" })).json();
    expect(worker.map((w) => `${w.method} ${w.path}`)).toEqual([
      `POST /internal/drafts/${DRAFT}/runs`,
      `GET /internal/drafts/${DRAFT}`,
    ]);
    expect(out.run_id).toBe("r-build");
    expect(out.interview.ended).toBe("finished");
    expect(out.draft.run.state).toBe("running");
    expect(events.at(-1)).toEqual({ event: "s1.end", outcome: "finished" });
  });

  it("all three skipped: nothing to build, the draft is as the first telling left it", async () => {
    events = [
      { event: "s1.start", outcome: "started" },
      { event: "s1.often", outcome: "skipped" },
      { event: "s1.who", outcome: "skipped" },
    ];
    const out = await (await call({ action: "skip", question: "size" })).json();
    expect(worker.some((w) => w.path.endsWith("/runs"))).toBe(false);
    expect(out.run_id).toBeNull();
    expect(out.interview.ended).toBe("finished");
  });

  it("moving on before the last question builds what was answered and is logged as left", async () => {
    events = [
      { event: "s1.start", outcome: "started" },
      { event: "s1.often", outcome: "answered" },
    ];
    const out = await (await call({ action: "finish" })).json();
    expect(out.run_id).toBe("r-build");
    expect(out.interview.ended).toBe("left");
    expect(events.at(-1)).toEqual({ event: "s1.end", outcome: "left" });
  });

  it("with the assistant paused the interview still ends; the parts are filled by hand (DEC-105)", async () => {
    assistantOff = true;
    events = [
      { event: "s1.start", outcome: "started" },
      { event: "s1.often", outcome: "answered" },
      { event: "s1.who", outcome: "answered" },
    ];
    const res = await call(
      { action: "answer", question: "size", text: "About 100 hours a month" },
      "key-size-0001",
    );
    expect(res.status).toBe(200);
    expect((await res.json()).interview.ended).toBe("finished");
  });

  it("a retry of a question already kept writes nothing twice", async () => {
    events = [
      { event: "s1.start", outcome: "started" },
      { event: "s1.often", outcome: "answered" },
    ];
    const out = await (
      await call({ action: "answer", question: "often", text: "Again" }, "key-often-001")
    ).json();
    expect(worker).toEqual([]);
    expect(out.interview.done).toEqual({ often: "answered" });
  });

  it("only the person's own draft, only in the alternative; finish works whatever the flag says now", async () => {
    own = false;
    expect((await call({ action: "start" })).status).toBe(404);
    own = true;
    variant = "default";
    const refused = await call({ action: "answer", question: "often", text: "x" });
    expect(refused.status).toBe(409);
    expect((await refused.json()).error.code).toBe("not_in_interview");
    events = [
      { event: "s1.start", outcome: "started" },
      { event: "s1.often", outcome: "answered" },
    ];
    expect((await (await call({ action: "finish" })).json()).run_id).toBe("r-build");
  });

  it("a step that cannot be kept answers 503; the retry with the same key keeps the answer once", async () => {
    events = [{ event: "s1.start", outcome: "started" }];
    eventsDown = true;
    const first = await call(
      { action: "answer", question: "often", text: "About 20 times a week" },
      "key-often-009",
    );
    expect(first.status).toBe(503);
    expect((await first.json()).error.code).toBe("save_failed");
    expect(events).toEqual([{ event: "s1.start", outcome: "started" }]);
    eventsDown = false;
    const again = await call(
      { action: "answer", question: "often", text: "About 20 times a week" },
      "key-often-009",
    );
    expect(again.status).toBe(200);
    // The worker took the same client_id both times: it keeps the message once (L-DRAFT.autosave/7)
    const writes = worker.filter((w) => w.path.endsWith("/messages"));
    expect(writes.map((w) => w.body.client_id)).toEqual(["key-often-009", "key-often-009"]);
    expect(events.at(-1)).toEqual({ event: "s1.often", outcome: "answered" });
  });

  it("the end that cannot be logged answers 503; the retry logs it and does not build the draft again", async () => {
    events = [
      { event: "s1.start", outcome: "started" },
      { event: "s1.often", outcome: "answered" },
      { event: "s1.who", outcome: "skipped" },
    ];
    endDownOnce = true;
    const first = await call({ action: "skip", question: "size" });
    expect(first.status).toBe(503);
    expect(worker.filter((w) => w.path.endsWith("/runs"))).toHaveLength(1);
    const again = await call({ action: "skip", question: "size" });
    expect(again.status).toBe(200);
    expect((await again.json()).interview.ended).toBe("finished");
    expect(worker.filter((w) => w.path.endsWith("/runs"))).toHaveLength(1); // built exactly once
    expect(events.at(-1)).toEqual({ event: "s1.end", outcome: "finished" });
  });

  it("refuses an unknown action or question", async () => {
    events = [{ event: "s1.start", outcome: "started" }];
    expect((await call({ action: "shout" })).status).toBe(400);
    expect((await call({ action: "skip", question: "why" })).status).toBe(400);
  });
});
