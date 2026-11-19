// @vitest-environment jsdom
/**
 * DEC-118 (BLD-C195): "Move to Review" turns on once the words reach the minimum to check and no run is still building;
 * title, summary and area are no longer waited for, and a run that failed, or that the page gave up on, counts as
 * finished. V-ACC for S-04 and S-04B readiness and the C-DRAFT-PANEL states, on a desktop (the panel's footer and its
 * line, S-04.rules/2) and on a phone (the dock's button), against a mocked A-API. "All 6 parts are in" stays the
 * loader's line for all six (BLD-C157). Synthetic words only.
 */
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Draft, DraftPartKey, DraftStreamEvent } from "@/lib/contracts";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, replace: push, refresh: vi.fn() }) }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
    createElement("a", { href, ...rest }, children as never),
}));

const { Compose } = await import("@/app/share/compose");
const { DraftPanel, READINESS, readinessOf } = await import("@/components/compose/draft-panel");
const { applyEvent, fromDraft } = await import("@/lib/compose/live");
const { LOADER_ALL_IN } = await import("@/lib/compose/loader");

const DRAFT = "7a1c2a8e-3b4d-4e5f-8a9b-0c1d2e3f4a18";
const WORDS = "Visitors wait at reception because no meeting room shows as free.";
const SHORT = "Rooms show busy.";
const CHECK = `/share/${DRAFT}/check`;

type Parts = Draft["parts"];
const FILLED: Parts = {
  title: { state: "filled", value: "Visitors wait at reception because no meeting room shows as free" },
  summary: { state: "filled", value: WORDS },
  often: { state: "filled", value: "Every morning" },
  who: { state: "filled", value: ["KFin teams"] },
  value: { state: "filled", value: ["saves_time"] },
  area: { state: "filled", value: "Operations" },
  similar: { state: "filled", value: [] },
};
const EMPTY: Parts = {
  title: { state: "failed", value: "" },
  summary: { state: "failed", value: "" },
  often: { state: "waiting", value: null },
  who: { state: "waiting", value: [] },
  value: { state: "filled", value: ["not_sure"] },
  area: { state: "waiting", value: "" },
  similar: { state: "failed", value: [] },
};
const BUILDING: Parts = Object.fromEntries(
  Object.entries(FILLED).map(([k, p]) => [k, { ...p, state: "updating" }]),
) as Parts;

function draft(over: Partial<Draft> = {}): Draft {
  const text = over.char_count !== undefined && over.char_count < 30 ? SHORT : WORDS;
  return {
    id: DRAFT,
    owner_id: "u-1",
    channel: "web",
    messages: [
      {
        id: "m-1",
        text,
        at: "2026-11-19T06:00:00.000Z",
        at_label: "Today, 11:30 am",
        device: "laptop",
        via: "typed",
        files: [],
        spans: [],
      },
    ],
    parts: FILLED,
    hidden: [],
    sorting: {} as Draft["sorting"],
    files: [],
    step: "tell",
    saved_at: "2026-11-19T06:00:00.000Z",
    saved_on: { device: "laptop", this_device: true },
    saved_labels: {
      sidebar: "Today, on your laptop",
      resume: "Last saved on your laptop, today 11:30 am.",
      prompt_day: "Today",
      prompt_line: "Last saved on your laptop, 11:30 am.",
      status: "Saved at 11:30 am",
      my_ideas: "Saved 11:30 am today, on your laptop",
    },
    // The worker's own `ready` is left false throughout: the page's rule is the minimum and nothing building.
    ready: false,
    min_chars: 30,
    char_count: WORDS.length,
    receipt: [],
    suggestions: [],
    run: { id: "r-1", state: "done" },
    ...over,
  };
}

/** The draft stream, driven by the test: `emit` sends one named event the way the server's SSE does. */
class FakeStream {
  static last: FakeStream | null = null;
  readyState = 1;
  listeners: Record<string, Array<(e: MessageEvent<string>) => void>> = {};
  constructor(readonly url: string) {
    FakeStream.last = this;
  }
  addEventListener(name: string, fn: (e: MessageEvent<string>) => void) {
    (this.listeners[name] ??= []).push(fn);
  }
  close() {
    this.readyState = 2;
  }
}

let phone: boolean;
let reads: Draft[];

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: false });
  push.mockClear();
  phone = false;
  reads = [];
  FakeStream.last = null;
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
      const url = String(input);
      if ((init.method ?? "GET") === "GET" && url.startsWith(`/api/drafts/${DRAFT}`)) {
        // Each read gives the next shape, the last one again once they run out.
        const d = reads.length > 1 ? reads.shift()! : reads[0]!;
        return new Response(JSON.stringify(d), { status: 200 });
      }
      return new Response(JSON.stringify({ items: [], total: 0 }), { status: 200 });
    }),
  );
});

let host: HTMLDivElement;
let root: Root;

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function mount(...shapes: Draft[]) {
  reads = shapes;
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root.render(createElement(Compose, { firstName: "Kavya", draftId: DRAFT }));
  });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
}

const moves = () =>
  [...host.querySelectorAll("button, a")].filter((b) => b.textContent?.trim() === "Move to Review");
/** The one "Move to Review" of the layout: the panel's footer on a desktop, the dock on a phone. */
function move(): HTMLElement {
  const all = moves();
  expect(all).toHaveLength(1);
  return all[0] as HTMLElement;
}
const footLine = () => host.querySelector(".cvfn")?.textContent ?? null;

function expectOff(line: string) {
  expect(move().tagName).toBe("BUTTON");
  expect(move().getAttribute("aria-disabled")).toBe("true");
  // The line under the button is the desktop panel's; the phone's dock has the button alone (S-04.phone).
  expect(footLine()).toBe(phone ? null : line);
}

function expectOn() {
  expect(move().tagName).toBe("A");
  expect(move().getAttribute("href")).toBe(CHECK);
  expect(move().getAttribute("aria-disabled")).toBeNull();
  expect(footLine()).toBe(phone ? null : READINESS.ready);
}

describe.each([
  ["desktop", false],
  ["phone", true],
])("V-ACC S-04 readiness, DEC-118, on a %s (BLD-C195)", (_layout, isPhone) => {
  beforeEach(() => {
    phone = isPhone;
  });

  it("S-04.rules/2 below the minimum: off, 'Your draft needs a little more first.'", async () => {
    await mount(draft({ char_count: SHORT.length, parts: EMPTY }));
    expectOff(READINESS.more);
    expect(READINESS.more).toBe("Your draft needs a little more first.");
  });

  it("S-04.rules/2 at the minimum with a run building: off, 'Still working through your words.'", async () => {
    await mount(draft({ parts: BUILDING, run: { id: "r-1", state: "running" } }));
    expectOff(READINESS.working);
    expect(READINESS.working).toBe("Still working through your words.");
  });

  it("C-DRAFT-LOADER.failure at the minimum with a run that failed: on", async () => {
    await mount(draft({ parts: EMPTY, run: { id: "r-1", state: "failed" } }));
    expectOn();
  });

  it("C-DRAFT-LOADER.failure at the minimum with a run the page gave up on (timed out): on", async () => {
    // The server still says it is building; the stream never sends its run, so the page counts it as lost.
    const building = draft({ parts: BUILDING, run: { id: "r-1", state: "running" } });
    await mount(building, building);
    expectOff(READINESS.working);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(21_000);
    });
    expect(host.textContent).not.toContain("Updating your draft");
    expectOn();
  });

  it("L-DRAFT.parts/7 overridden: title, summary and area all empty at the minimum: on, the Area waiting", async () => {
    await mount(draft({ parts: EMPTY }));
    expectOn();
    const area = [...host.querySelectorAll(".row")].find(
      (r) => r.querySelector("dt")?.textContent === "Area",
    );
    expect(area?.querySelector("dd")?.textContent).toContain("Waiting for your words");
  });

  it("all six parts in: on, with the ready line on a desktop", async () => {
    await mount(draft());
    expectOn();
  });
});

// ---- C-DRAFT-PANEL with the loader: "All 6 parts are in" still means all six (BLD-C157) ---------------------------

const MEANS = (["similar", "title", "value", "who", "often", "area"] as DraftPartKey[]).map((key) => ({
  key,
  mean_ms: 600,
}));
const VALUES: Record<DraftPartKey, unknown> = {
  title: { title: FILLED.title.value, summary: WORDS },
  often: "Every morning",
  who: ["KFin teams"],
  value: ["saves_time"],
  area: "Operations",
  similar: [],
};

function streamed(values: Partial<Record<DraftPartKey, unknown>> = {}) {
  let live = applyEvent(fromDraft(null), { event: "run", data: { run_id: "r-1", parts: MEANS } }, 0);
  let t = 100;
  for (const { key } of MEANS) {
    const e: DraftStreamEvent = {
      event: "part",
      data: { key, state: "filled", value: key in values ? values[key] : VALUES[key], took_ms: 300 },
    };
    live = applyEvent(live, e, (t += 100));
  }
  return applyEvent(live, { event: "done", data: { ready: false } }, (t += 100));
}

function panel(live: ReturnType<typeof streamed>, isPhone: boolean) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  const readiness = readinessOf({
    chars: WORDS.length,
    minChars: 30,
    sending: false,
    running: live.running,
    saved: true,
  });
  act(() =>
    root.render(
      createElement(DraftPanel, { live, readiness, moveHref: CHECK, hidden: null, phone: isPhone }),
    ),
  );
}

describe("V-ACC C-DRAFT-PANEL, DEC-118: the panel's states", () => {
  it("desktop: all six in: 'All 6 parts are in', the ready line, Move to Review on", () => {
    panel(streamed(), false);
    expect(host.textContent).toContain(LOADER_ALL_IN);
    expect(LOADER_ALL_IN).toBe("All 6 parts are in");
    expect(footLine()).toBe("Looks right? Check the sorting and send it.");
    expect(move().tagName).toBe("A");
  });

  it("desktop: the area waiting: no all-in line, and Move to Review on all the same", () => {
    panel(streamed({ area: null }), false);
    expect(host.textContent).not.toContain(LOADER_ALL_IN);
    expect(footLine()).toBe(READINESS.ready);
    expect(move().tagName).toBe("A");
  });

  it("phone: the tube fills for all six only; the sheet holds no button of its own", () => {
    phone = true;
    const tube = () => host.querySelector(".dload") as HTMLElement;
    panel(streamed(), true);
    expect(tube().classList.contains("ph")).toBe(true);
    expect(tube().classList.contains("all")).toBe(true);
    expect(moves()).toHaveLength(0); // the dock holds it (S-04.phone), as checked above
    act(() => root.unmount());
    host.remove();
    panel(streamed({ area: null }), true);
    expect(tube().classList.contains("all")).toBe(false);
    expect(host.textContent).not.toContain(LOADER_ALL_IN);
  });
});
