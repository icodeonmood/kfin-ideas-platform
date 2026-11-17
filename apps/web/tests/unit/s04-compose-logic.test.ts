/**
 * S-04, S-04B: the logic under Tell it (BLD-C120 to BLD-C123). C-DRAFT-LOADER.maths (the bar never pauses, never
 * moves back, stays under 97% until all six are in; the estimate and the slow line), C-HIDDEN (the kinds line, the
 * reasons, the underline cut), the draft client (every message's client_id on every retry and every replay; the
 * offline outbox keeps each message's client_id and `at`), and the stream reducer (L-DRAFT.parts/4: only the part
 * that changed moves). Synthetic words only.
 */
import { describe, expect, it, vi } from "vitest";

import type { Draft, DraftStreamEvent } from "@/lib/contracts";
import {
  clearOutboxes,
  DraftClient,
  DraftError,
  messagesFor,
  type HeldNote,
  type Outgoing,
} from "@/lib/compose/client";
import { kindsLine, quoteRange, segments, SHOW_REASONS, shownLine } from "@/lib/compose/hidden";
import {
  applyEvent,
  fromDraft,
  giveUp,
  hasValue,
  loseStream,
  withDraft,
  withDraftAfterLoss,
} from "@/lib/compose/live";
import {
  barValue,
  LOADER_ALL_IN,
  loaderLine,
  partProgress,
  readyCount,
  type LoaderRun,
} from "@/lib/compose/loader";

const DRAFT = "6f1c2a8e-3b4d-4e5f-8a9b-0c1d2e3f4a5b";

const MEANS = [
  { key: "similar" as const, mean_ms: 2600 },
  { key: "title" as const, mean_ms: 1800 },
  { key: "value" as const, mean_ms: 1500 },
  { key: "who" as const, mean_ms: 1200 },
  { key: "often" as const, mean_ms: 900 },
  { key: "area" as const, mean_ms: 700 },
];

const run = (answered: LoaderRun["answered"] = {}): LoaderRun => ({ parts: MEANS, startedAt: 0, answered });

describe("C-DRAFT-LOADER.maths (S-04, S-04B; BLD-C120)", () => {
  it("C-DRAFT-LOADER.maths/2 a pending part rises as 0.9 × (1 − e^(−t ÷ mean)) and is never full on its own", () => {
    expect(partProgress(0, 1000)).toBe(0);
    expect(partProgress(1000, 1000)).toBeCloseTo(0.9 * (1 - Math.exp(-1)), 6);
    expect(partProgress(1e9, 1000)).toBeLessThanOrEqual(0.9);
  });

  it("V-ACC.share/5 the bar moves forward continuously, never back, and stays under 97% until all six are in", () => {
    let last = -1;
    for (let t = 0; t <= 20_000; t += 50) {
      const answered = t > 800 ? { area: 800 } : {};
      const v = barValue(run(answered), t);
      expect(v).toBeGreaterThanOrEqual(last);
      expect(v).toBeLessThanOrEqual(0.97);
      last = v;
    }
    const all = Object.fromEntries(MEANS.map((p) => [p.key, 100]));
    expect(barValue(run(all), 3000)).toBe(1);
  });

  it("C-DRAFT-LOADER.maths/5 the line counts ready parts and gives the largest time left, then 'almost there'", () => {
    expect(loaderLine(run({ area: 600 }), 600)).toBe("1 of 6 ready, about 2 seconds left");
    expect(loaderLine(run({ area: 600, often: 800, who: 900, value: 1000 }), 1400)).toBe(
      "4 of 6 ready, about 1 second left",
    );
    expect(loaderLine(run({ area: 1, often: 1, who: 1, value: 1, title: 1 }), 2000)).toBe(
      "5 of 6 ready, almost there",
    );
  });

  it("V-ACC.share/6 a part past 1.5 × its mean names itself: 'still looking for similar ideas'", () => {
    const answered = { area: 1, often: 1, who: 1, value: 1, title: 1 };
    expect(loaderLine(run(answered), 2600 * 1.5 + 1)).toBe("5 of 6 ready, still looking for similar ideas");
  });

  it("C-DRAFT-LOADER.failure/1 a part past 10 × its mean stops counting as pending", () => {
    expect(readyCount(run(), 7001)).toBe(1); // area: 10 × 700
    const all = Object.fromEntries(MEANS.map((p) => [p.key, 1]));
    expect(loaderLine(run(all), 10)).toBe(LOADER_ALL_IN);
  });
});

describe("C-HIDDEN helpers (S-04, S-04B; BLD-C121)", () => {
  it("C-HIDDEN.where the folded bar names the kinds once each, in order: 'Folio number, PAN and phone number'", () => {
    expect(
      kindsLine([{ kind: "folio" }, { kind: "pan" }, { kind: "phone" }, { kind: "folio" }] as never),
    ).toBe("Folio number, PAN and phone number");
    expect(kindsLine([{ kind: "pan" }] as never)).toBe("PAN");
  });

  it("C-HIDDEN.list/1 three reasons in the module's order; /3 the shown line", () => {
    expect(SHOW_REASONS.map((r) => r.label)).toEqual([
      "it's a scheme or product code",
      "it's an internal reference",
      "it's made up for the example",
    ]);
    expect(shownLine("scheme_or_product_code")).toBe("Shown, because it's a scheme or product code.");
  });

  it("L-HIDE.rules/2 the person's text is cut at each span and joins back unchanged, whatever the spans", () => {
    const text = "One investor, folio 1234567/89, called three times.";
    const segs = segments(text, [
      { start: 20, end: 30, kind: "folio" },
      { start: 25, end: 28, kind: "pan" }, // overlaps: clipped
      { start: 90, end: 99, kind: "phone" }, // past the end: dropped
    ]);
    expect(segs.map((s) => s.text).join("")).toBe(text);
    expect(segs.find((s) => s.kind === "folio")?.text).toBe("1234567/89");
    expect(segments("", [])).toEqual([{ text: "", at: 0 }]);
  });
});

// ── the draft client ─────────────────────────────────────────────────────────────────────────────────────────

function memoryStore() {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => m.get(k) ?? null,
    setItem: (k: string, v: string) => void m.set(k, v),
    removeItem: (k: string) => void m.delete(k),
    m,
  };
}

type Sent = {
  url: string;
  method: string;
  key: string | null;
  device: string | null;
  body: Record<string, unknown>;
};

function server(replies: Array<"network" | { status: number; body?: unknown }>) {
  const sent: Sent[] = [];
  const fetch = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const headers = new Headers(init.headers);
    sent.push({
      url: String(input),
      method: init.method ?? "GET",
      key: headers.get("Idempotency-Key"),
      device: headers.get("X-Device-Id"),
      body: typeof init.body === "string" ? (JSON.parse(init.body) as Record<string, unknown>) : {},
    });
    const reply = replies.shift() ?? { status: 202, body: { run_id: null, message: null, draft: {} } };
    if (reply === "network") throw new TypeError("Failed to fetch");
    return new Response(JSON.stringify(reply.body ?? {}), { status: reply.status });
  });
  return { fetch: fetch as unknown as typeof globalThis.fetch, sent };
}

const ok = (mid: string) => ({
  status: 202,
  body: { run_id: "r-1", message: { id: mid }, draft: { id: DRAFT, messages: [] } },
});

describe("C-DRAFT-PANEL.behaviour/3 the source phrase's underline (BLD-C121)", () => {
  it("C-DRAFT-PANEL.behaviour/3 ignores case without moving the offsets after an 'İ'", () => {
    const text = "İstanbul desk: About 40 calls a day reach the branch"; // synthetic
    const r = quoteRange(text, "about 40 calls a day");
    expect(r).not.toBeNull();
    expect(text.slice(r!.start, r!.end)).toBe("About 40 calls a day");
    expect(quoteRange(text, "nothing like this")).toBeNull();
    expect(quoteRange(text, "a (day")).toBeNull(); // a phrase with pattern characters is matched as text
  });

  it("C-DRAFT-PANEL.behaviour/3 after an emoji the exact phrase is found where the browser counts it", () => {
    const text = "🙂🙂 about 40 calls a day";
    const r = quoteRange(text, "about 40 calls a day")!;
    expect(text.slice(r.start, r.end)).toBe("about 40 calls a day");
  });
});

describe("the draft client: client_id on every message (S-04B, A-API.drafts; BLD-C122)", () => {
  it("A-API.drafts a retried message after a lost answer carries the same client_id, and the voice note its stream", async () => {
    const { fetch, sent } = server([
      "network",
      { status: 503, body: { error: { code: "save_failed" } } },
      ok("m-1"),
    ]);
    const client = new DraftClient({ fetch, store: memoryStore(), retryDelaysMs: [0, 0, 0] });
    const m: Outgoing = {
      clientId: "c-voice-1",
      text: "Folio wale customers ko code milta hai",
      via: "voice",
      streamId: "s-1",
    };
    const out = await client.addMessage(DRAFT, m);
    expect(out.message.id).toBe("m-1");
    expect(sent).toHaveLength(3);
    for (const s of sent) {
      expect(s.url).toBe(`/api/drafts/${DRAFT}/messages`);
      expect(s.key).toBe("c-voice-1"); // the route turns the Idempotency-Key into client_id
      expect(s.body).toMatchObject({ client_id: "c-voice-1", via: "voice", stream_id: "s-1" });
      expect(s.body).not.toHaveProperty("at"); // a first try carries no `at`
    }
    expect(new Set(sent.map((s) => s.device)).size).toBe(1); // one device id, kept for this browser
  });

  it("A-API.drafts two messages get two client_ids; a refusal is not retried and says why", async () => {
    const { fetch, sent } = server([
      ok("m-1"),
      {
        status: 422,
        body: { error: { code: "too_long", message: "That's too long. Please make it shorter." } },
      },
    ]);
    const client = new DraftClient({ fetch, store: memoryStore(), retryDelaysMs: [0] });
    await client.addMessage(DRAFT, { clientId: "c-a", text: "First detail", via: "typed" });
    const err = await client
      .addMessage(DRAFT, { clientId: "c-b", text: "Second", via: "typed" })
      .catch((e) => e);
    expect(err).toBeInstanceOf(DraftError);
    expect(err.code).toBe("too_long");
    expect(err.text).toBe("That's too long. Please make it shorter.");
    expect(sent.map((s) => s.key)).toEqual(["c-a", "c-b"]);
  });

  it("L-DRAFT.autosave/7 the outbox keeps each message's client_id and `at`, and replays them in order with both", async () => {
    const store = memoryStore();
    const { fetch, sent } = server([ok("m-1"), ok("m-2")]);
    const client = new DraftClient({ fetch, store, retryDelaysMs: [0] });
    const a = client.queue(DRAFT, {
      clientId: "c-1",
      text: "We tried a branch FAQ sheet",
      via: "typed",
      at: "2026-11-17T10:00:00.000Z",
    });
    const b = client.queue(DRAFT, {
      clientId: "c-2",
      text: "It also happens with SIP",
      via: "voice",
      streamId: "s-9",
    });
    expect(a.at).toBe("2026-11-17T10:00:00.000Z");
    expect(typeof b.at).toBe("string");
    // survives a reload: a new client on the same storage reads it back
    const again = new DraftClient({ fetch, store, retryDelaysMs: [0] });
    expect(again.outbox(DRAFT).map((m) => [m.clientId, m.at])).toEqual([
      ["c-1", a.at],
      ["c-2", b.at],
    ]);
    const { sent: done, refused } = await again.flush(DRAFT);
    expect(done).toHaveLength(2);
    expect(refused).toEqual([]);
    expect(sent.map((s) => [s.key, s.body.client_id, s.body.at, s.body.stream_id])).toEqual([
      ["c-1", "c-1", a.at, undefined],
      ["c-2", "c-2", b.at, "s-9"],
    ]);
    expect(again.outbox(DRAFT)).toEqual([]);
  });

  it("L-DRAFT.autosave/7 still offline: the replay stops at the first that cannot go and keeps it and the rest", async () => {
    const store = memoryStore();
    const { fetch } = server([ok("m-1"), "network", "network"]);
    const client = new DraftClient({ fetch, store, retryDelaysMs: [0] });
    client.queue(DRAFT, { clientId: "c-1", text: "one", via: "typed" });
    client.queue(DRAFT, { clientId: "c-2", text: "two", via: "typed" });
    client.queue(DRAFT, { clientId: "c-3", text: "three", via: "typed" });
    const { sent } = await client.flush(DRAFT);
    expect(sent).toHaveLength(1);
    expect(client.outbox(DRAFT).map((m) => m.clientId)).toEqual(["c-2", "c-3"]);
  });

  it("L-DRAFT.autosave/7 a message refused for good leaves the queue and comes back, so its words are not lost", async () => {
    const { fetch } = server([
      { status: 409, body: { error: { code: "archived", message: "This draft is archived." } } },
    ]);
    const client = new DraftClient({ fetch, store: memoryStore(), retryDelaysMs: [0] });
    client.queue(DRAFT, { clientId: "c-1", text: "Kept words", via: "typed" });
    const { refused } = await client.flush(DRAFT);
    expect(refused.map((r) => [r.message.text, r.error.code])).toEqual([["Kept words", "archived"]]);
    expect(client.outbox(DRAFT)).toEqual([]);
  });

  it("A-API.drafts creating the draft sends one Idempotency-Key per draft on every try", async () => {
    const { fetch, sent } = server([
      "network",
      { status: 201, body: { draft: { id: DRAFT }, run_id: null } },
    ]);
    const client = new DraftClient({ fetch, store: memoryStore(), retryDelaysMs: [0] });
    await client.create("k-draft-1", "Investors call the branch about R07");
    expect(sent.map((s) => s.key)).toEqual(["k-draft-1", "k-draft-1"]);
    expect(sent[0]!.body).toEqual({
      channel: "web",
      text: "Investors call the branch about R07",
      via: "typed",
    });
  });

  it("C-HIDDEN Show it and Hide it call A-API lines 60-61 with the reason", async () => {
    const detail = {
      id: "h-1",
      kind: "pan",
      masked: "PAN ••••4F",
      state: "shown",
      reason: "made_up_example",
    };
    const { fetch, sent } = server([
      { status: 200, body: detail },
      { status: 200, body: { ...detail, state: "hidden" } },
    ]);
    const client = new DraftClient({ fetch, store: memoryStore() });
    expect((await client.showHidden(DRAFT, "h-1", "made_up_example")).state).toBe("shown");
    expect((await client.hideHidden(DRAFT, "h-1")).state).toBe("hidden");
    expect(sent.map((s) => [s.method, s.url, s.body])).toEqual([
      ["POST", `/api/drafts/${DRAFT}/hidden/h-1/show`, { reason: "made_up_example" }],
      ["POST", `/api/drafts/${DRAFT}/hidden/h-1/hide`, {}],
    ]);
  });
});

// ── the stream reducer ───────────────────────────────────────────────────────────────────────────────────────

function draft(over: Partial<Draft> = {}): Draft {
  return {
    id: DRAFT,
    owner_id: "u-1",
    channel: "web",
    messages: [],
    parts: {
      title: {
        state: "filled",
        value: "Investors call to ask why a redemption was rejected",
        why: "From your first sentence.",
      },
      summary: { state: "filled", value: "The rejection SMS only gives a code." },
      often: { state: "pinned", value: "About 40 calls a day at one branch" },
      who: {
        state: "filled",
        value: ["Investors", "KFin teams"],
        why: "Suggested because you mentioned investors and the branch.",
      },
      value: { state: "waiting", value: [] },
      area: { state: "filled", value: "Investor service" },
      similar: { state: "waiting", value: [] },
    },
    hidden: [],
    sorting: {} as Draft["sorting"],
    files: [],
    step: "tell",
    saved_at: "2026-11-17T08:08:00.000Z",
    saved_on: { device: "laptop", this_device: true },
    ready: true,
    min_chars: 30,
    char_count: 120,
    receipt: ["Your draft is ready. Add a detail, or check it."],
    suggestions: ["Add what you already tried"],
    run: { id: "r-0", state: "done" },
    ...over,
  };
}

describe("the draft as the stream builds it (C-DRAFT-PANEL, A-API.draft-stream; BLD-C123)", () => {
  it("C-DRAFT-PANEL.behaviour/1 a run marks only its parts updating; a part event fills only its own slot", () => {
    let live = fromDraft(draft());
    const ev = (e: DraftStreamEvent, t = 0) => (live = applyEvent(live, e, t));
    ev({
      event: "run",
      data: {
        run_id: "r-1",
        parts: [
          { key: "value", mean_ms: 1500 },
          { key: "who", mean_ms: 1200 },
        ],
      },
    });
    expect(live.running).toBe(true);
    expect(live.updating).toEqual(["value", "who"]);
    expect(live.parts.title.state).toBe("filled"); // not in the run: untouched
    expect(live.parts.often.state).toBe("pinned"); // the person's own value: never rewritten (L-DRAFT.pins)
    ev({
      event: "hidden",
      data: {
        spans: [{ start: 0, end: 4, kind: "pan" }],
        details: [{ id: "h-1", kind: "pan", masked: "PAN ••••4F", state: "hidden" }],
      },
    });
    expect(live.hidden[0]!.masked).toBe("PAN ••••4F");
    ev(
      {
        event: "part",
        data: {
          key: "value",
          state: "filled",
          value: ["saves_time", "saves_cost"],
          why: "From your words: “about 40 calls a day”",
          took_ms: 900,
        },
      },
      900,
    );
    expect(live.updating).toEqual(["who"]);
    expect(live.parts.value.value).toEqual(["saves_time", "saves_cost"]);
    expect(live.loader?.answered.value).toBe(900);
    ev({ event: "part", data: { key: "who", state: "failed", value: null, took_ms: 0 } });
    expect(live.parts.who.state).toBe("failed");
    ev({ event: "receipt", data: { lines: ["Marked it as saves time and saves cost."], suggestions: [] } });
    ev({ event: "done", data: { ready: true } });
    expect(live.running).toBe(false);
    expect(live.ready).toBe(true);
    expect(live.receipt).toEqual(["Marked it as saves time and saves cost."]);
  });

  it("A-API.draft-stream the title event carries its summary", () => {
    const live = applyEvent(
      fromDraft(draft()),
      {
        event: "part",
        data: {
          key: "title",
          state: "filled",
          value: { title: "Plain words for R07", summary: "Two lines." },
          took_ms: 1,
        },
      },
      0,
    );
    expect(live.parts.title.value).toBe("Plain words for R07");
    expect(live.parts.summary.value).toBe("Two lines.");
  });

  it("A-API.drafts a fresh read wins, except a run still being followed on the stream", () => {
    let live = applyEvent(
      fromDraft(draft()),
      { event: "run", data: { run_id: "r-2", parts: [{ key: "area", mean_ms: 700 }] } },
      0,
    );
    live = withDraft(live, draft({ run: { id: "r-2", state: "running" } }));
    expect(live.loader?.parts[0]!.key).toBe("area");
    live = withDraft(live, draft({ run: { id: "r-2", state: "done" } }));
    expect(live.loader?.parts[0]!.key).toBe("area"); // kept, so the strip fills and folds (maths/7)
    expect(live.running).toBe(false);
    live = withDraft(live, draft({ run: { id: "r-3", state: "done" } }));
    expect(live.loader).toBeNull();
  });

  it("C-DRAFT-PANEL.states a value shows when filled or changed by the person, and not when empty", () => {
    expect(hasValue({ state: "filled", value: "x" })).toBe(true);
    expect(hasValue({ state: "pinned", value: ["a"] })).toBe(true);
    expect(hasValue({ state: "filled", value: [] })).toBe(false);
    expect(hasValue({ state: "updating", value: "x" })).toBe(false);
  });
});

describe("S-04B review fixes: the stream's failure path and replays (BLD-C123)", () => {
  const RUN = {
    event: "run" as const,
    data: {
      run_id: "r-9",
      parts: [
        { key: "title" as const, mean_ms: 1800 },
        { key: "value" as const, mean_ms: 1500 },
        { key: "area" as const, mean_ms: 700 },
      ],
    },
  };

  it("C-DRAFT-LOADER.maths/4 the browser's reconnect replays the run: the clock, the answers and filled parts stay", () => {
    let live = applyEvent(fromDraft(draft()), RUN, 1000);
    live = applyEvent(
      live,
      { event: "part", data: { key: "area", state: "filled", value: "Operations", took_ms: 600 } },
      1600,
    );
    const replayed = applyEvent(live, RUN, 9000); // the native reconnect, `?run=` from its start
    expect(replayed).toBe(live);
    expect(replayed.loader!.startedAt).toBe(1000);
    expect(replayed.parts.area).toMatchObject({ state: "filled", value: "Operations" });
    const again = applyEvent(
      replayed,
      { event: "part", data: { key: "area", state: "filled", value: "Operations", took_ms: 600 } },
      9100,
    );
    expect(again.loader!.answered.area).toBe(1600); // the first answer's time is kept
    // A page that loaded mid-run knows the run's id but has no loader yet: its first `run` still starts the bar.
    const loaded = fromDraft(draft({ run: { id: "r-9", state: "running" } }));
    expect(applyEvent(loaded, RUN, 5000).loader!.startedAt).toBe(5000);
  });

  it("C-DRAFT-LOADER.failure/1 a part past 10 x its mean fails, counts as answered, and the rest keep building", () => {
    let live = applyEvent(fromDraft(draft()), RUN, 0);
    live = giveUp(live, 7_001); // area's mean is 700 ms
    expect(live.parts.area.state).toBe("failed");
    expect(live.updating).toEqual(["title", "value"]);
    expect(live.loader!.answered.area).toBe(7_001);
    expect(live.running).toBe(true);
    live = giveUp(live, 18_001); // title and value too
    expect(live.parts.title.state).toBe("failed");
    expect(live.parts.summary.state).toBe("failed");
    expect(live.running).toBe(false); // nothing left to wait for: no skeleton, no "Still working"
    const late = applyEvent(
      live,
      { event: "part", data: { key: "value", state: "filled", value: ["saves_time"], took_ms: 19_000 } },
      19_000,
    );
    expect(late.parts.value).toMatchObject({ state: "filled", value: ["saves_time"] }); // a late part still lands
  });

  it("L-DRAFT.errors a lost stream fails every part still out; a fresh read keeps them failed while the server builds", () => {
    let live = applyEvent(fromDraft(draft()), RUN, 0);
    live = applyEvent(
      live,
      { event: "part", data: { key: "area", state: "filled", value: "Operations", took_ms: 600 } },
      600,
    );
    live = loseStream(live, 2_000);
    expect(live.running).toBe(false);
    expect(live.updating).toEqual([]);
    expect([live.parts.title.state, live.parts.value.state]).toEqual(["failed", "failed"]);
    const still = draft({
      run: { id: "r-9", state: "running" },
      parts: {
        ...draft().parts,
        title: { state: "updating", value: "" },
        summary: { state: "updating", value: "" },
        value: { state: "filled", value: ["saves_cost"] },
        area: { state: "filled", value: "Operations" },
      },
    });
    const read = withDraftAfterLoss(live, still);
    expect(read.running).toBe(false);
    expect(read.updating).toEqual([]);
    expect(read.parts.title.state).toBe("failed"); // not back to a skeleton no stream will fill
    expect(read.parts.value).toMatchObject({ state: "filled", value: ["saves_cost"] }); // what landed shows
    const done = withDraftAfterLoss(read, draft({ run: { id: "r-9", state: "done" } }));
    expect(done.parts.title.state).toBe("filled"); // the finished run wins
  });
});

describe("BLD-C150 a voice note after typed words goes as its own message", () => {
  const note = (prefix: string | null): HeldNote => ({
    streamId: "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d",
    text: "Branch mein roz das log aate hain",
    textEn: "Ten people come to the branch every day",
    prefix,
  });

  it("C-PROMPT.voice typed first (typed), then the note (voice, with its stream), each with its own client_id", () => {
    const typed = "The mandate screen asks for the IFSC twice.";
    const out = messagesFor(`${typed} ${note(typed).text}`, note(typed));
    expect(out.map((m) => [m.via, m.text, m.streamId])).toEqual([
      ["typed", typed, undefined],
      ["voice", note(typed).text, note(typed).streamId],
    ]);
    expect(new Set(out.map((m) => m.clientId)).size).toBe(2);
  });

  it("C-PROMPT.voice the note edited in the box still goes as the voice message; typed words edited still split", () => {
    const typed = "The mandate screen asks twice.";
    const n = note(typed);
    const edited = messagesFor(`${typed} Branch mein roz bees log aate hain`, n);
    expect(edited.map((m) => m.via)).toEqual(["typed", "voice"]);
    expect(edited[1]!.text).toBe("Branch mein roz bees log aate hain");
    const retyped = messagesFor(`The mandate screen asks for it twice. ${n.text}`, n);
    expect(retyped.map((m) => [m.via, m.text])).toEqual([
      ["typed", "The mandate screen asks for it twice."],
      ["voice", n.text],
    ]);
  });

  it("C-PROMPT.voice a note into an empty box is one voice message; no note is one typed message", () => {
    expect(messagesFor(note("").text, note("")).map((m) => m.via)).toEqual(["voice"]);
    expect(messagesFor("Only typed words here.", null).map((m) => m.via)).toEqual(["typed"]);
    expect(messagesFor("   ", note("x"))).toEqual([]);
  });
});

describe("S-04.rules/4 sign-out leaves no waiting words on the device", () => {
  it("L-DRAFT.autosave/7 every draft's outbox is cleared; other keys stay", () => {
    const m = new Map<string, string>([
      ["1pc.outbox.d-1", "[]"],
      ["1pc.outbox.d-2", "[]"],
      ["1pc.device-id", "abcdef123456"],
    ]);
    const store = {
      get length() {
        return m.size;
      },
      key: (i: number) => [...m.keys()][i] ?? null,
      getItem: (k: string) => m.get(k) ?? null,
      setItem: (k: string, v: string) => void m.set(k, v),
      removeItem: (k: string) => void m.delete(k),
    };
    clearOutboxes(store as unknown as Storage);
    expect([...m.keys()]).toEqual(["1pc.device-id"]);
  });
});
