// @vitest-environment jsdom
/**
 * S-04 and S-04B, the second review round (BLD-C120 to BLD-C129, BLD-C150), against a mocked A-API, a stream the
 * test drives and a voice hook the test sets. J-SHARE/3–6 (the "By voice" variation of 3), J-RESUME/3 and the draft
 * side of J-RECOVER: the stream's failure path; open on another device; typed words and a voice note as two
 * messages; a failed note's line per reason; "Change the title"; the phone's hero, count, peek and one loader;
 * a failed similar check; refusals on the hidden list. Synthetic words only.
 */
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Draft, HiddenDetail } from "@/lib/contracts";
import type { VoiceCaptureState } from "@/lib/voice-capture";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const voice = vi.hoisted(() => ({
  state: { status: "idle", notice: null } as unknown,
}));
vi.mock("@/lib/use-voice-capture", () => ({
  useVoiceCapture: () => ({
    state: voice.state,
    start: vi.fn(async () => undefined),
    stop: vi.fn(),
    reset: vi.fn(() => {
      voice.state = { status: "idle", notice: null };
    }),
    noticeShown: vi.fn(),
  }),
}));
const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, replace: push, refresh: vi.fn() }) }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
    createElement("a", { href, ...rest }, children as never),
}));

const { Compose, countLine, voiceFailedLine } = await import("@/app/share/compose");
const { HiddenDetails } = await import("@/components/compose/hidden");
const { DraftError } = await import("@/lib/compose/client");

const DRAFT = "6f1c2a8e-3b4d-4e5f-8a9b-0c1d2e3f4a5b";
const STREAM = "0a1b2c3d-4e5f-4a6b-8c7d-9e0f1a2b3c4d";
const WORDS =
  "Investors who change their bank mandate at the branch wait a week before the new mandate shows. It happens about 25 times a week.";

function draft(over: Partial<Draft> = {}): Draft {
  return {
    id: DRAFT,
    owner_id: "u-1",
    channel: "web",
    messages: [
      {
        id: "m-1",
        text: WORDS,
        at: "2026-11-13T15:12:00.000Z",
        at_label: "Friday, 8:42 pm, on your phone",
        device: "phone",
        via: "typed",
        files: [],
        spans: [],
      },
    ],
    parts: {
      title: { state: "filled", value: "Bank mandate changes take a week to show" },
      summary: { state: "filled", value: "A new mandate takes a week to show." },
      often: { state: "filled", value: "About 25 times a week at one branch" },
      who: { state: "filled", value: ["Investors"] },
      value: { state: "filled", value: ["saves_time"] },
      area: { state: "filled", value: "Investor service" },
      similar: { state: "filled", value: [] },
    },
    hidden: [],
    sorting: {} as Draft["sorting"],
    files: [],
    step: "tell",
    saved_at: "2026-11-13T15:12:00.000Z",
    saved_on: { device: "phone", this_device: true },
    saved_labels: {
      sidebar: "Friday, on your phone",
      resume: "Last saved on your phone, Friday 8:42 pm.",
      prompt_day: "Friday",
      prompt_line: "Last saved on your phone, 8:42 pm.",
      status: "Saved at 8:42 pm",
      my_ideas: "Saved 8:42 pm Friday, on your phone",
    },
    ready: true,
    min_chars: 30,
    char_count: WORDS.length,
    receipt: ["Drafted a title: “Bank mandate changes take a week to show”."],
    suggestions: ["Add what you already tried", "Change the title"],
    run: { id: "r-0", state: "done" },
    ...over,
  };
}

const RUNNING: Partial<Draft> = {
  ready: false,
  run: { id: "r-1", state: "running" },
  parts: {
    ...draft().parts,
    title: { state: "updating", value: "" },
    summary: { state: "updating", value: "" },
    area: { state: "updating", value: "" },
  },
};

// ── a stream the test drives ────────────────────────────────────────────────────────────────────────────────

class FakeStream {
  static all: FakeStream[] = [];
  readyState = 0;
  closed = false;
  private on = new Map<string, ((e: Event) => void)[]>();
  constructor(readonly url: string) {
    FakeStream.all.push(this);
  }
  addEventListener(type: string, fn: (e: Event) => void) {
    this.on.set(type, [...(this.on.get(type) ?? []), fn]);
  }
  close() {
    this.closed = true;
    this.readyState = 2;
  }
  emit(type: string, data?: unknown) {
    const e = data === undefined ? new Event(type) : new MessageEvent(type, { data: JSON.stringify(data) });
    for (const fn of this.on.get(type) ?? []) fn(e);
  }
}

type Sent = { method: string; url: string; key: string | null; body: Record<string, unknown> };
let sent: Sent[];
let route: (s: Sent) => { status: number; body: unknown };
let phone: boolean;

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: false });
  sent = [];
  phone = false;
  voice.state = { status: "idle", notice: null };
  FakeStream.all = [];
  push.mockClear();
  const mem = new Map<string, string>();
  const store = {
    getItem: (k: string) => mem.get(k) ?? null,
    setItem: (k: string, v: string) => void mem.set(k, String(v)),
    removeItem: (k: string) => void mem.delete(k),
    clear: () => mem.clear(),
  };
  vi.stubGlobal("localStorage", store);
  Object.defineProperty(window, "localStorage", { value: store, configurable: true });
  Object.defineProperty(navigator, "onLine", { get: () => true, configurable: true });
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({ matches: phone, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
  );
  vi.stubGlobal("EventSource", FakeStream);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const s: Sent = {
        method: init.method ?? "GET",
        url: String(input),
        key: new Headers(init.headers).get("Idempotency-Key"),
        body: typeof init.body === "string" ? JSON.parse(init.body) : {},
      };
      sent.push(s);
      const r = route(s);
      return new Response(JSON.stringify(r.body), { status: r.status });
    }),
  );
  route = () => ({ status: 200, body: draft() });
});

let host: HTMLDivElement;
let root: Root;

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function mount(draftId: string | null) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root.render(createElement(Compose, { firstName: "Kavya", draftId }));
  });
  await tick();
}

const tick = (ms = 0) =>
  act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
const text = () => host.textContent ?? "";
const button = (name: string) =>
  [...host.querySelectorAll("button, a")].find(
    (b) => (b.getAttribute("aria-label") ?? b.textContent ?? "").trim() === name,
  ) as HTMLButtonElement | undefined;
const box = () => host.querySelector("textarea") as HTMLTextAreaElement;

function type(el: HTMLTextAreaElement, value: string) {
  act(() => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

const FAILED = "Couldn't work this out. Add it yourself.";
const failedSlots = () => [...host.querySelectorAll(".wait")].filter((w) => w.textContent === FAILED).length;
const RUN_EVENT = {
  run_id: "r-1",
  parts: [
    { key: "title", mean_ms: 1800 },
    { key: "area", mean_ms: 700 },
  ],
};

describe("C-DRAFT-LOADER.failure on S-04B: the stream's failure path (J-RECOVER; BLD-C123)", () => {
  it("C-DRAFT-LOADER.failure/1 the server's error: each part still out fails with Change, and the draft is read again", async () => {
    route = () => ({ status: 200, body: draft(RUNNING) });
    await mount(DRAFT);
    const es = FakeStream.all.at(-1)!;
    expect(es.url).toBe(`/api/drafts/${DRAFT}/stream?run=r-1`);
    await act(async () => es.emit("run", RUN_EVENT));
    expect(text()).not.toContain(FAILED);
    const reads = sent.filter((s) => s.method === "GET").length;
    await act(async () => es.emit("error", { error: "stream_unavailable" }));
    await tick();
    expect(es.closed).toBe(true);
    expect(failedSlots()).toBe(2); // the title and Area
    expect(button("Change the title")).toBeTruthy();
    expect(button("Change Area")).toBeTruthy();
    expect(text()).not.toContain("Still working through your words.");
    expect(sent.filter((s) => s.method === "GET").length).toBe(reads + 1);
    await tick(3000); // the server is still building: read again a few seconds later
    expect(sent.filter((s) => s.method === "GET").length).toBe(reads + 2);
    expect(failedSlots()).toBe(2); // no skeleton no stream will fill
  });

  it("C-DRAFT-LOADER.failure/1 a part past 10 x its mean gives up on its own, with no event at all", async () => {
    route = () => ({ status: 200, body: draft(RUNNING) });
    await mount(DRAFT);
    const es = FakeStream.all.at(-1)!;
    await act(async () => es.emit("run", RUN_EVENT));
    await tick(8_100); // Area's mean is 700 ms; checked once a second
    expect(failedSlots()).toBe(1);
    await tick(11_000); // the title's is 1.8 s
    expect(failedSlots()).toBe(2);
    expect(es.closed).toBe(true);
  });

  it("A-API.draft-stream dropped connections: the browser's own retries are allowed, then the stream is lost", async () => {
    route = () => ({ status: 200, body: draft(RUNNING) });
    await mount(DRAFT);
    const es = FakeStream.all.at(-1)!;
    await act(async () => es.emit("run", RUN_EVENT));
    await act(async () => es.emit("error"));
    await act(async () => es.emit("error"));
    expect(es.closed).toBe(false);
    await act(async () => es.emit("error"));
    expect(es.closed).toBe(true);
    expect(text()).toContain(FAILED);
  });
});

describe("L-DRAFT.autosave/5 open on another device (BLD-C126)", () => {
  it("L-DRAFT.autosave/5 the banner shows and the task bar stops saying Saving…", async () => {
    route = (s) =>
      s.method === "POST"
        ? {
            status: 409,
            body: {
              error: {
                code: "open_elsewhere",
                message: "This draft is open on your phone. Carry on here?",
                device: "phone",
              },
            },
          }
        : { status: 200, body: draft() };
    await mount(DRAFT);
    type(box(), "We raise a ticket for each one and wait two days.");
    await act(async () => {
      button("Add to your draft")!.click();
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(text()).toContain("This draft is open on your phone. Carry on here?");
    expect(text()).not.toContain("Saving…");
    expect(text()).toContain("Unsaved changes");
    expect(box().value).toContain("We raise a ticket"); // the words come back to the box
  });
});

describe("BLD-C150 typed words, then a voice note (J-SHARE/3 by voice)", () => {
  const NOTE = {
    streamId: STREAM,
    text: "Branch mein roz das log aate hain",
    spans: [],
    textEn: "Ten people come to the branch every day",
    enLabel: "Typed up in English",
    seconds: 6,
    endedBy: "person",
    hiddenCount: 0,
    translated: true,
    translationFailure: null,
    lang: "hi-IN",
    language: "Hindi",
    summary: "Voice message, 6 seconds, in Hindi",
  };

  it("C-PROMPT.voice S-04B: the typed words go first as typed, then the note as voice with its stream, each its own client_id", async () => {
    route = (s) =>
      s.method === "POST"
        ? { status: 202, body: { run_id: "r-9", message: { id: `m-${sent.length}` }, draft: draft() } }
        : { status: 200, body: draft() };
    await mount(DRAFT);
    const typed = "The mandate screen asks for the IFSC twice.";
    type(box(), typed);
    voice.state = { status: "done", note: NOTE } as VoiceCaptureState;
    type(box(), `${typed} `); // any render lets the screen take the finished note
    await tick();
    expect(box().value).toBe(`${typed} ${NOTE.text}`); // the transcript stays in the box, editable
    expect(text()).toContain(NOTE.textEn); // with its English copy
    await act(async () => {
      button("Add to your draft")!.click();
      await vi.advanceTimersByTimeAsync(0);
    });
    const posts = sent.filter((s) => s.method === "POST");
    expect(posts.map((p) => [p.body.via, p.body.text, p.body.stream_id])).toEqual([
      ["typed", typed, undefined],
      ["voice", NOTE.text, STREAM],
    ]);
    expect(posts[0]!.key).not.toBe(posts[1]!.key);
    expect(posts.map((p) => p.body.client_id)).toEqual(posts.map((p) => p.key));
  });
});

describe("C-PROMPT.voice a failed note's line, by reason (BLD-C127)", () => {
  it("C-PROMPT.voice signed out → the sign-in line; paused or unavailable → the paused line; the rest → nothing invented", () => {
    expect(voiceFailedLine("signed_out")).toBe("sign_in");
    for (const r of ["paused", "unavailable", "voice_paused", "voice_unavailable"])
      expect(voiceFailedLine(r)).toBe("paused");
    for (const r of [
      "no_microphone",
      "not_supported",
      "audio_suspended",
      "too_many_this_hour",
      "stream_lost",
    ])
      expect(voiceFailedLine(r)).toBeNull();
  });

  it("C-PROMPT.voice the screen: an alert region that was there before the line arrives", async () => {
    route = () => ({ status: 200, body: draft() });
    await mount(DRAFT);
    const alerts = () => [...host.querySelectorAll('.cbox [role="alert"]')];
    expect(alerts().length).toBeGreaterThan(0);
    expect(alerts().every((a) => a.textContent === "")).toBe(true);
    const region = alerts()[0]!;
    voice.state = { status: "failed", reason: "signed_out", text: "", spans: [] } as VoiceCaptureState;
    type(box(), "x");
    expect(region.isConnected).toBe(true);
    const link = [...region.querySelectorAll("a")][0]!;
    expect(link.textContent).toBe("Sign in again to carry on");
    expect(link.getAttribute("href")).toBe(`/sign-in?next=${encodeURIComponent(`/share/${DRAFT}`)}`);
    voice.state = { status: "failed", reason: "too_many_this_hour", text: "", spans: [] } as VoiceCaptureState;
    type(box(), "xy");
    expect(region.textContent).toBe("");
    voice.state = { status: "failed", reason: "unavailable", text: "", spans: [] } as VoiceCaptureState;
    type(box(), "xyz");
    expect(region.textContent).toBe("Voice notes are paused just now. Please type it instead.");
  });
});

describe("S-04B suggestions, the phone and the panel (C-DRAFT-PANEL; BLD-C125, C126)", () => {
  it("C-DRAFT-PANEL.behaviour/5 'Change the title' opens the title; Escape closes it and focus is back on Change", async () => {
    route = () => ({ status: 200, body: draft() });
    await mount(DRAFT);
    const change = () => host.querySelector(".tslot .tb") as HTMLButtonElement;
    expect(change().getAttribute("aria-expanded")).toBe("false");
    const chip = [...host.querySelectorAll("button.chip")].find((b) => b.textContent === "Change the title")!;
    act(() => (chip as HTMLButtonElement).click());
    const field = host.querySelector(".tslot input") as HTMLInputElement;
    expect(field).toBeTruthy();
    expect(change().getAttribute("aria-expanded")).toBe("true");
    act(() => {
      field.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    });
    expect(host.querySelector(".tslot input")).toBeNull();
    expect(document.activeElement).toBe(change());
    expect(change().getAttribute("aria-expanded")).toBe("false");
  });

  it("C-DRAFT-PANEL.states a failed similar check says so (L-SIMILAR.failure)", async () => {
    route = () => ({
      status: 200,
      body: draft({ parts: { ...draft().parts, similar: { state: "failed", value: [] } } }),
    });
    await mount(DRAFT);
    expect(text()).toContain("Couldn’t check for similar ideas. The review desk will.");
  });

  it("S-04B.rules/6 phone: the board's heading, help, count and privacy line; the peek builds; one loader; Escape closes", async () => {
    phone = true;
    route = () => ({ status: 200, body: draft(RUNNING) });
    await mount(DRAFT);
    expect(host.querySelector("h1")!.textContent).toBe("What’s getting in your way?");
    expect(text()).toContain(
      "What happens, who it affects, how often. Any language. At least 30 characters, and no fix needed.",
    );
    expect(text()).toContain("Enough to work with");
    expect(text()).toContain(
      "Nothing is shared until you send it. Saved as you go, here and on your computer.",
    );
    await act(async () => FakeStream.all.at(-1)!.emit("run", RUN_EVENT));
    const peek = host.querySelector(".dpeek") as HTMLButtonElement;
    expect(peek.textContent).toMatch(/^Building your draft0 of 2 ready, about \d+ seconds? left$/);
    expect(host.querySelectorAll('[role="progressbar"]')).toHaveLength(1);
    act(() => peek.click());
    expect(peek.getAttribute("aria-expanded")).toBe("true");
    act(() => {
      host
        .querySelector(".dsheet-b button")!
        .dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    });
    expect(peek.getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(peek);
  });

  it("C-PROMPT.states the phone's live count in the pack's words", () => {
    expect(countLine(0)).toBe("30 more characters");
    expect(countLine(29)).toBe("1 more character");
    expect(countLine(30)).toBe("Enough to work with");
  });

  it("C-DRAFT-PANEL.behaviour/2 each landed part is said once, politely", async () => {
    route = () => ({ status: 200, body: draft(RUNNING) });
    await mount(DRAFT);
    const es = FakeStream.all.at(-1)!;
    await act(async () => es.emit("run", RUN_EVENT));
    await act(async () =>
      es.emit("part", { key: "area", state: "filled", value: "Operations", took_ms: 500 }),
    );
    const polite = [...host.querySelectorAll('.canvas [aria-live="polite"]')];
    expect(polite.map((p) => p.textContent)).toContain("Area: Operations");
  });
});

describe("C-HIDDEN.list refusals (L-HIDE.rules/6; BLD-C121)", () => {
  const shown: HiddenDetail = {
    id: "h-1",
    kind: "folio",
    masked: "Folio ••••89",
    state: "shown",
    reason: "internal_reference",
  };

  async function render(err: unknown) {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
    await act(async () => {
      root.render(
        createElement(HiddenDetails, {
          details: [shown],
          actions: { show: vi.fn(), hide: vi.fn(async () => Promise.reject(err)) },
        }),
      );
    });
    act(() => (host.querySelector(".hidb") as HTMLButtonElement).click());
    await act(async () => {
      button("Hide it")!.click();
      await vi.advanceTimersByTimeAsync(0);
    });
  }

  it("C-HIDDEN.list/3 a refused 'Hide it' shows the server's words in an alert", async () => {
    await render(new DraftError(503, "paused", "Sharing is paused for a short while."));
    const alert = host.querySelector('li [role="alert"]')!;
    expect(alert.textContent).toBe("Sharing is paused for a short while.");
  });

  it("C-HIDDEN.list/3 with no words from the server, nothing is invented", async () => {
    await render(new DraftError(401, "sign_in_required", null));
    expect(host.querySelector('li [role="alert"]')!.textContent).toBe("");
  });
});
