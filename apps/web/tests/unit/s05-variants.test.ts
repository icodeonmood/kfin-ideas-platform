// @vitest-environment jsdom
/**
 * Flag S2 "Check first" on S-05 (P-DECISIONS.experiments, L-SIMILAR "Flag S2"; Review.md and PhoneReview.md
 * `simulatorS2=Check first`; BLD-C176): with a close top match the similar ideas come first. Desktop: they are part 1
 * of the rail, Check it opens on them fresh, "Back to your words" and Next lead on to your words, sorting, then proof.
 * Phone: the comparison before the rest, with "Team up" and "Mine is different". With no close match, or without the
 * flag, the default; the exposure and the deciding events are codes only. Synthetic people only.
 */
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ConfigResponse, SendViewResponse, SimilarMatch, SortingResponse } from "@/lib/contracts";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, push: vi.fn(), refresh: vi.fn() }) }));

/** Lane F's real sheet, with what the grid gives it and what it hands back kept for the tests to drive. */
const sheetHook = vi.hoisted(() => ({
  options: null as null | Record<string, unknown>,
  handle: null as null | { open(id: string): void; close(): void },
}));
vi.mock("@/components/teamup/teamup-sheet", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/components/teamup/teamup-sheet")>();
  return {
    ...real,
    useTeamUpSheet: (options: Parameters<typeof real.useTeamUpSheet>[0]) => {
      sheetHook.options = options as Record<string, unknown>;
      const handle = real.useTeamUpSheet(options);
      sheetHook.handle = handle;
      return handle;
    },
  };
});
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
    createElement("a", { href, ...rest }, children as never),
}));

const { CheckIt } = await import("@/app/share/[id]/check/check-it");
const model = await import("@/app/share/[id]/check/model");

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// --- Fixtures (synthetic) ----------------------------------------------------------------------------------------

const DRAFT_ID = "0b6f7a52-3c1e-4d7a-9f00-1a2b3c4d5e6f";
const KAVYA = { id: "u-kavya", name: "Kavya Menon", first_name: "Kavya", initials: "KM" };
const RAVI = { id: "u-ravi", name: "Ravi Nair", first_name: "Ravi", initials: "RN" };

function draft(extra: Record<string, unknown> = {}) {
  return {
    id: DRAFT_ID,
    owner_id: KAVYA.id,
    channel: "web",
    messages: [],
    parts: {
      title: { state: "filled", value: "Investors call to ask why a redemption was rejected" },
      summary: {
        state: "filled",
        value: "The rejection SMS only gives a code, such as R07. Investors call the branch to ask.",
      },
      often: { state: "filled", value: "About 40 calls a day at one branch" },
      who: { state: "filled", value: [] },
      value: { state: "filled", value: [] },
      area: { state: "filled", value: "Investor service" },
      similar: { state: "filled", value: [] },
    },
    hidden: [{ id: "h1", kind: "folio", masked: "Folio ••••89", state: "hidden" }],
    sorting: {},
    files: [],
    step: "check:1",
    saved_at: "2026-11-17T08:08:00Z",
    saved_on: { device: "laptop", this_device: true },
    ready: true,
    min_chars: 30,
    char_count: 180,
    ...extra,
  };
}

function sorting(confirmed = false): SortingResponse {
  return {
    affects: {
      value: ["Investors", "KFin teams"],
      source: "suggested",
      why: null,
      why_line: "Suggested because you mentioned investors and the branch.",
    },
    kind: {
      value: "problem",
      source: "suggested",
      why: null,
      why_line: "Suggested because you described something that goes wrong today.",
    },
    area: {
      value: "Investor service",
      source: "suggested",
      why: null,
      why_line: "Suggested because it’s about investors and the SMS they get.",
    },
    brings: { value: ["saves_time", "saves_cost"], source: "suggested", why: null, why_line: null },
    confirmed,
    complete: true,
    confirmed_at: confirmed ? "2026-11-17T08:09:00Z" : null,
    rail: confirmed ? "Investor service, saves time, saves cost" : "Suggested, not confirmed yet",
    summary: confirmed
      ? "Investor service, affecting investors and KFin teams, saves time, saves cost"
      : "Not confirmed yet",
    note: confirmed ? null : "These are suggestions from your words. Not confirmed yet.",
    problem: null,
  };
}

const CONFIG: ConfigResponse = {
  promises: {},
  sorting: {
    affects: [
      "Investors",
      "KFin teams",
      "Distributors",
      "AMC clients",
      "Issuer and corporate clients",
      "Others",
    ],
    areas: ["Investor service", "Operations", "Distributor experience", "Technology"],
    brings: ["saves_time", "saves_cost", "earns_revenue", "less_outside_tools", "not_sure"],
    helpers: ["Someone at a branch", "Someone in operations", "Someone from tech"],
    controls: {
      affects: {
        shown: ["Investors", "KFin teams", "Distributors"],
        all: [
          "Investors",
          "KFin teams",
          "Distributors",
          "AMC clients",
          "Issuer and corporate clients",
          "Others",
        ],
        search_link: "Search all groups",
        search_label: "Someone else? Search all 6",
        rule: "Pick all that apply",
      },
      area: {
        shown: ["Investor service", "Operations", "Distributor experience"],
        all: ["Investor service", "Operations", "Distributor experience", "Technology"],
        search_link: "Search all areas",
        search_label: "Another area? Search all 12",
        rule: "Pick one",
      },
      kind: {
        options: [
          { value: "problem", label: "A problem to fix" },
          { value: "business_idea", label: "A new business idea" },
        ],
        rule: "Pick one",
      },
      brings: {
        options: [
          { value: "saves_time", label: "Saves time" },
          { value: "saves_cost", label: "Saves cost" },
          { value: "earns_revenue", label: "Earns revenue" },
          { value: "less_outside_tools", label: "Cuts reliance on outside tools" },
          { value: "not_sure", label: "Not sure yet" },
        ],
        exclusive: "not_sure",
        rule: "Pick all that apply",
      },
      helpers: ["Someone at a branch", "Someone in operations", "Someone from tech"],
    },
  },
  declaration: { version: "2026-11-17", submit: "By submitting, you confirm…", save: "" },
};

const MATCH_RAVI: SimilarMatch = {
  idea: {
    id: "IDEA-2026-001412",
    title: "Rejection SMS codes confuse investors",
    status: "with_review_desk",
    area: "Investor service",
    city: "Hyderabad",
    shared_at: "2026-11-09T10:00:00+05:30",
    lead: RAVI,
    crew_faces: [RAVI],
    crew_count: 4,
    in_their_words: "Investors get a code, not a reason, and then they call us.",
    hue: 1,
  },
  strength: "close",
  reason: "Close match: same SMS, same calls",
};

const MATCH_SUNITA: SimilarMatch = {
  idea: {
    ...MATCH_RAVI.idea,
    id: "IDEA-2026-001398",
    title: "No script for calls about rejections",
    status: "picked",
    area: "Operations",
    city: "Mumbai",
    lead: { id: "u-sunita", name: "Sunita Pillai", first_name: "Sunita", initials: "SP" },
    crew_count: 2,
  },
  strength: "related",
  reason: "Related: the calls you describe",
};

function sendView(extra: Partial<SendViewResponse> = {}): SendViewResponse {
  return {
    id: DRAFT_ID,
    rows: [
      {
        key: "title",
        label: "Title",
        value: "Investors call to ask why a redemption was rejected",
        ok: true,
        step: "check:1",
      },
      { key: "sorting", label: "Sorting", value: "Not confirmed yet", ok: false, step: "check:2" },
      { key: "similar", label: "Similar ideas", value: "2 similar ideas found", ok: true, step: "check:3" },
      { key: "proof", label: "Proof", value: "None added", ok: true, step: "check:4" },
      { key: "fix", label: "Your fix", value: "None added", ok: true, step: "check:5" },
      { key: "helpers", label: "Who would help", value: "Not said", ok: true, step: "check:6" },
    ],
    declaration: {
      version: "2026-11-17",
      text: "By submitting, you confirm there’s no customer personal data in it or its files, and it’s your own work or you’ve credited others.",
    },
    button: "Submit",
    ready: false,
    problems: [],
    ...extra,
  };
}

type Answer = { status?: number; body?: unknown; fail?: boolean };
type Route = (method: string, url: string, body: unknown) => Answer | undefined;

let calls: Array<{ method: string; url: string; body: unknown; headers: Record<string, string> }>;
let host: HTMLElement;
let root: Root;

function serve(routes: Route[]) {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const method = (init.method ?? "GET").toUpperCase();
      let body: unknown = init.body;
      if (typeof body === "string") body = JSON.parse(body);
      calls.push({ method, url, body, headers: (init.headers ?? {}) as Record<string, string> });
      for (const r of routes) {
        const a = r(method, url, body);
        if (!a) continue;
        if (a.fail) throw new TypeError("Failed to fetch");
        const status = a.status ?? 200;
        return { ok: status >= 200 && status < 300, status, json: async () => a.body };
      }
      return { ok: false, status: 404, json: async () => ({ error: { code: "not_found", message: "" } }) };
    }),
  );
}

/** The usual answers for a draft at Check it; routes given first win. */
function base(
  state: {
    sorting?: SortingResponse;
    draft?: unknown;
    similar?: unknown;
    merge?: unknown;
    send?: unknown;
  } = {},
): Route[] {
  return [
    (m, u) => (m === "GET" && u === `/api/drafts/${DRAFT_ID}` ? { body: state.draft ?? draft() } : undefined),
    (m, u) => (m === "PATCH" && u === `/api/drafts/${DRAFT_ID}` ? { body: {} } : undefined),
    (m, u) => (m === "GET" && u.endsWith("/sorting") ? { body: state.sorting ?? sorting() } : undefined),
    (m, u, b) =>
      m === "PATCH" && u.endsWith("/sorting")
        ? { body: (b as { confirm?: boolean }).confirm ? sorting(true) : sorting() }
        : undefined,
    (m, u) =>
      m === "GET" && u.endsWith("/similar")
        ? { body: state.similar ?? [MATCH_RAVI, MATCH_SUNITA] }
        : undefined,
    (m, u) => (u.endsWith("/similar/keep-separate") ? { body: { kept_separate: true } } : undefined),
    (m, u) =>
      m === "GET" && u.endsWith("/merge-request")
        ? { body: state.merge ?? { state: "none", after: null } }
        : undefined,
    (m, u) => (m === "GET" && u.endsWith("/send") ? { body: state.send ?? sendView() } : undefined),
  ];
}

async function mount(
  routes: Route[],
  config: ConfigResponse | null = CONFIG,
  props: { blackout?: boolean } = {},
) {
  serve(routes);
  await act(async () => root.render(createElement(CheckIt, { draftId: DRAFT_ID, config, ...props })));
  await settle();
}

async function settle() {
  for (let i = 0; i < 6; i++) await act(async () => undefined);
}

const text = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();
const h1 = () => text(document.querySelector("h1"));
/** The accessible name the way Playwright reads a button: aria-label, else its text. */
const nameOf = (b: Element) => {
  const label = b.getAttribute("aria-label");
  if (label) return label;
  const copy = b.cloneNode(true) as Element;
  copy.querySelectorAll('[aria-hidden="true"]').forEach((n) => n.remove());
  return text(copy);
};
const buttons = () => Array.from(document.querySelectorAll<HTMLButtonElement>("button"));
const button = (name: string | RegExp) =>
  buttons().find((b) => (typeof name === "string" ? nameOf(b) === name : name.test(nameOf(b))));

async function click(el: Element | undefined | null) {
  if (!el) throw new Error("nothing to click");
  await act(async () => (el as HTMLElement).click());
  await settle();
}

/** This browser's storage, in memory, fresh for each test (Node's own `localStorage` is not a browser's). */
function memoryStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() {
      return m.size;
    },
    clear: () => m.clear(),
    getItem: (k: string) => m.get(k) ?? null,
    key: (i: number) => [...m.keys()][i] ?? null,
    removeItem: (k: string) => void m.delete(k),
    setItem: (k: string, v: string) => void m.set(k, String(v)),
  };
}

beforeEach(() => {
  vi.stubGlobal("localStorage", memoryStorage());
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  replace.mockReset();
});

afterEach(async () => {
  await act(async () => root.unmount());
  document.body.innerHTML = "";
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const flagCalls = (): Array<Record<string, unknown> & { url: string; event?: string }> =>
  calls
    .filter((c) => c.url.startsWith("/api/flags/"))
    .map((c) => ({ url: c.url, ...(c.body as Record<string, unknown>) }));
const flagsRoute: Route = (m, u) => (u.startsWith("/api/flags/") ? { status: 204, body: null } : undefined);
const FRESH = draft({ step: "tell" });

async function mountFlagged(routes: Route[], checkFirst: boolean) {
  serve([flagsRoute, ...routes]);
  await act(async () =>
    root.render(createElement(CheckIt, { draftId: DRAFT_ID, config: CONFIG, flags: { checkFirst } })),
  );
  await settle();
}

function asPhone() {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((q: string) => ({
      matches: q.includes("max-width: 720px"),
      media: q,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}

const railNames = () =>
  Array.from(document.querySelectorAll(".ck-rail .ck-rb")).map((b) =>
    nameOf(b).split(" ").slice(0, 3).join(" "),
  );
const counter = () => text(document.querySelector(".ck-count"));

describe("S2 Check first on desktop (Review.md simulatorS2=Check first)", () => {
  it("S-05 a close top match: opens on similar ideas as part 1, then your words, sorting and proof", async () => {
    await mountFlagged(base({ draft: FRESH }), true);
    expect(h1()).toBe("Has someone raised this already?");
    expect(counter()).toBe("Check it, part 1 of 6");
    expect(railNames().slice(0, 4)).toEqual([
      "1 Similar ideas",
      "2 Your words",
      "3 Sorting Suggested,",
      "4 Proof Optional",
    ]);
    expect(document.body.textContent).toContain("Close match: same SMS, same calls");
    const back = Array.from(document.querySelectorAll("a")).find((a) => text(a) === "Back to your words");
    expect(back?.getAttribute("href")).toBe(`/share/${DRAFT_ID}`);

    await click(button("Next"));
    expect(h1()).toBe("Is this how you’d put it?");
    expect(counter()).toBe("Check it, part 2 of 6");
    await click(button("Back"));
    expect(h1()).toBe("Has someone raised this already?");
    await click(button("Next"));
    await click(button("Looks right"));
    expect(h1()).toBe("Is it sorted right?");
    expect(counter()).toBe("Check it, part 3 of 6");
    await click(button("Confirm sorting"));
    expect(h1()).toBe("Anything that shows it?");
    expect(counter()).toBe("Check it, part 4 of 6");

    expect(flagCalls()).toEqual([
      {
        url: "/api/flags/events",
        flag: "s2",
        event: "s2.check",
        outcome: "opened",
        screen: "S-05",
        draft_id: DRAFT_ID,
      },
      {
        url: "/api/flags/events",
        flag: "s2",
        event: "s2.check",
        outcome: "close_match",
        screen: "S-05",
        draft_id: DRAFT_ID,
      },
      {
        url: "/api/flags/events",
        flag: "s2",
        event: "s2.compare",
        outcome: "shown",
        screen: "S-05",
        draft_id: DRAFT_ID,
      },
      {
        url: "/api/flags/events",
        flag: "s2",
        event: "s2.compare",
        outcome: "moved_on",
        screen: "S-05",
        draft_id: DRAFT_ID,
      },
    ]);
    // The step saved is the part's own, whatever its place in the rail
    expect(calls.some((c) => c.method === "PATCH" && (c.body as { step?: string }).step === "check:1")).toBe(
      true,
    );
  });

  it("with no close match Check it runs exactly as the default does", async () => {
    await mountFlagged(base({ draft: FRESH, similar: [MATCH_SUNITA] }), true);
    expect(h1()).toBe("Is this how you’d put it?");
    expect(counter()).toBe("Check it, part 1 of 6");
    expect(railNames().slice(0, 3)).toEqual(["1 Your words", "2 Sorting Suggested,", "3 Similar ideas"]);
    expect(flagCalls().map((c) => c.event ?? c.url)).toEqual(["s2.check"]);
  });

  it("couldn't check for similar ideas: the default, and sharing is not blocked", async () => {
    await mountFlagged(
      [
        (m, u) => (m === "GET" && u.endsWith("/similar") ? { status: 503, body: {} } : undefined),
        ...base({ draft: FRESH }),
      ],
      true,
    );
    expect(h1()).toBe("Is this how you’d put it?");
    expect(railNames()[2]).toBe("3 Similar ideas");
  });

  it("a Check it already begun stays as drawn: its part, the default order, no exposure", async () => {
    await mountFlagged(base({ draft: draft({ step: "check:2" }) }), true);
    expect(h1()).toBe("Is it sorted right?");
    expect(counter()).toBe("Check it, part 2 of 6");
    expect(railNames()[0]).toBe("1 Your words");
    await click(button("Back"));
    expect(flagCalls().map((c) => `${c.event}:${c.outcome}`)).toEqual(["s2.check:opened"]);
  });

  it("the default variant: the parts as drawn; a close match on a fresh Check it is the exposure, nothing changes", async () => {
    await mountFlagged(base({ draft: FRESH }), false);
    expect(h1()).toBe("Is this how you’d put it?");
    expect(railNames()[0]).toBe("1 Your words");
    expect(flagCalls().map((c) => `${c.event}:${c.outcome}`)).toEqual([
      "s2.check:opened",
      "s2.check:close_match",
    ]);
  });

  it("the page never waits for the similar ideas: drawn order at once; a close match that comes before anything is touched reorders it", async () => {
    let answer: (v: unknown) => void = () => undefined;
    const late = new Promise((r) => (answer = r));
    serve([
      flagsRoute,
      ...base({ draft: FRESH }).map(
        (r): Route =>
          (m, u, b) =>
            m === "GET" && u.endsWith("/similar") ? undefined : r(m, u, b),
      ),
    ]);
    const realFetch = globalThis.fetch as unknown as (u: string, i?: RequestInit) => Promise<unknown>;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (u: string, i: RequestInit = {}) =>
        u.endsWith("/similar") && (i.method ?? "GET") === "GET"
          ? late.then(() => ({ ok: true, status: 200, json: async () => [MATCH_RAVI, MATCH_SUNITA] }))
          : realFetch(u, i),
      ),
    );
    await act(async () =>
      root.render(createElement(CheckIt, { draftId: DRAFT_ID, config: CONFIG, flags: { checkFirst: true } })),
    );
    await settle();
    expect(h1()).toBe("Is this how you’d put it?"); // not held up by the similar ideas
    expect(railNames()[0]).toBe("1 Your words");
    await act(async () => answer(null));
    await settle();
    expect(h1()).toBe("Has someone raised this already?");
    expect(railNames()[0]).toBe("1 Similar ideas");
  });

  it("a close match that comes after the person has moved does not reorder the page", async () => {
    let answer: (v: unknown) => void = () => undefined;
    const late = new Promise((r) => (answer = r));
    serve([flagsRoute, ...base({ draft: FRESH })]);
    const realFetch = globalThis.fetch as unknown as (u: string, i?: RequestInit) => Promise<unknown>;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (u: string, i: RequestInit = {}) =>
        u.endsWith("/similar") && (i.method ?? "GET") === "GET"
          ? late.then(() => ({ ok: true, status: 200, json: async () => [MATCH_RAVI] }))
          : realFetch(u, i),
      ),
    );
    await act(async () =>
      root.render(createElement(CheckIt, { draftId: DRAFT_ID, config: CONFIG, flags: { checkFirst: true } })),
    );
    await settle();
    await click(button("Looks right"));
    expect(h1()).toBe("Is it sorted right?");
    await act(async () => answer(null));
    await settle();
    expect(h1()).toBe("Is it sorted right?");
    expect(railNames()[0]).toMatch(/^(?:1 )?Your words/);
    expect(flagCalls().map((c) => `${c.event}:${c.outcome}`)).toEqual(["s2.check:opened"]);
  });

  it("without flags from the page: nothing is logged", async () => {
    await mount(base({ draft: FRESH }));
    expect(h1()).toBe("Is this how you’d put it?");
    expect(calls.filter((c) => c.url.startsWith("/api/flags/"))).toEqual([]);
  });
});

describe("the default arm: similar ideas and the merge request arrive together (S-05, C-SIMGRID)", () => {
  it("a merge answer that comes after the similar ideas never leaves Team up clickable in between", async () => {
    let answer: (v: unknown) => void = () => undefined;
    const late = new Promise((r) => (answer = r));
    serve(base({ draft: draft({ step: "check:3" }) }));
    const realFetch = globalThis.fetch as unknown as (u: string, i?: RequestInit) => Promise<unknown>;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (u: string, i: RequestInit = {}) =>
        u.endsWith("/merge-request") && (i.method ?? "GET") === "GET"
          ? late.then(() => ({
              ok: true,
              status: 200,
              json: async () => ({ state: "waiting", other_idea_id: MATCH_RAVI.idea.id, after: null }),
            }))
          : realFetch(u, i),
      ),
    );
    await act(async () => root.render(createElement(CheckIt, { draftId: DRAFT_ID, config: CONFIG })));
    await settle();
    expect(h1()).toBe("Has someone raised this already?");
    // The similar ideas have answered, the merge request has not: no tile offers Team up yet
    expect(button(`Team up on ${MATCH_RAVI.idea.title}`)).toBeUndefined();
    await act(async () => answer(null));
    await settle();
    expect(button(`Team up on ${MATCH_RAVI.idea.title}`)).toBeUndefined();
    expect(text(document.querySelector(".simgrid"))).toContain("Waiting for Ravi");
  });
});

describe("S2: a page the person has begun is never reordered under them (BLD-C176)", () => {
  it("typing or moving into the page before a late close match keeps the drawn order", async () => {
    let answer: (v: unknown) => void = () => undefined;
    const late = new Promise((r) => (answer = r));
    serve([flagsRoute, ...base({ draft: FRESH })]);
    const realFetch = globalThis.fetch as unknown as (u: string, i?: RequestInit) => Promise<unknown>;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (u: string, i: RequestInit = {}) =>
        u.endsWith("/similar") && (i.method ?? "GET") === "GET"
          ? late.then(() => ({ ok: true, status: 200, json: async () => [MATCH_RAVI] }))
          : realFetch(u, i),
      ),
    );
    await act(async () =>
      root.render(createElement(CheckIt, { draftId: DRAFT_ID, config: CONFIG, flags: { checkFirst: true } })),
    );
    await settle();
    expect(h1()).toBe("Is this how you’d put it?");
    // The person moves into the page (a change button), without saving or moving part
    await act(async () => {
      (document.querySelector(".ck-stage button") as HTMLButtonElement).focus();
    });
    await act(async () => answer(null));
    await settle();
    expect(h1()).toBe("Is this how you’d put it?");
    expect(railNames()[0]).toMatch(/^(?:1 )?Your words/);
    expect(flagCalls().map((c) => `${c.event}:${c.outcome}`)).toEqual(["s2.check:opened"]);
  });
});

describe("S2 Check first on a phone (PhoneReview.md simulatorS2=Check first)", () => {
  it("the comparison stands before the rest; Mine is different carries on to the page", async () => {
    asPhone();
    await mountFlagged(base({ draft: FRESH }), true);
    expect(h1()).toBe("Check it, then send it");
    expect(text(document.querySelector(".ck-first h2"))).toBe("Is it one of these?");
    const body = text(document.body);
    expect(body).toContain(
      "Something very close was shared on 9 November. Adding yours to it gets both decided together, and you’re credited.",
    );
    expect(body).toContain("Yours, not sent yet");
    expect(body).toContain("IDEA-2026-001412, shared 9 November");
    expect(body).toContain("Investors get a code, not a reason, and then they call us.");
    expect(body).toContain("Investor service, Hyderabad, 4 colleagues");
    expect(body).toContain(
      "Also related: No script for calls about rejections, Operations, Mumbai. You’ll see it on the next part.",
    );
    expect(document.querySelector("#pr-sort-h")).toBeNull(); // the rest waits
    expect(button("Team up")).toBeTruthy();

    await click(button("Mine is different"));
    await act(async () => {
      await new Promise((r) => requestAnimationFrame(() => r(null)));
    });
    expect(document.querySelector(".ck-first")).toBeNull();
    expect(document.querySelector("#pr-sort-h")).toBeTruthy();
    // Focus goes to the first part of the page it reveals (WCAG 2.4.3)
    expect(document.activeElement).toBe(document.querySelector(".ck-ph [data-part] .ck-h"));
    expect(flagCalls().at(-1)).toMatchObject({ event: "s2.compare", outcome: "mine_is_different" });
    // Nothing about the idea is recorded: no keep-separate
    expect(calls.some((c) => c.url.endsWith("/similar/keep-separate"))).toBe(false);
  });

  it("Team up opens lane F's sheet on the close idea, with this draft", async () => {
    asPhone();
    await mountFlagged(base({ draft: FRESH }), true);
    await click(button("Team up"));
    expect(sheetHook.options?.draftId).toBe(DRAFT_ID);
    // The sheet's send: the comparison is done and the outcome logged
    await act(async () => {
      (sheetHook.options!.onSent as (s: unknown) => void)({
        kind: "merge",
        id: "tu-1",
        ideaId: MATCH_RAVI.idea.id,
        note: "",
        brought: [],
        after: null,
      });
    });
    await settle();
    expect(document.querySelector(".ck-first")).toBeNull();
    expect(flagCalls().at(-1)).toMatchObject({ event: "s2.compare", outcome: "merge_asked" });
  });

  it("keep separate is logged, and the comparison closes, only once the server has recorded it", async () => {
    asPhone();
    await mountFlagged(
      [
        (m, u) => (u.endsWith("/similar/keep-separate") ? { status: 503, body: {} } : undefined),
        ...base({ draft: FRESH }),
      ],
      true,
    );
    await act(async () => {
      (sheetHook.options!.onSent as (s: unknown) => void)({
        kind: "teamup",
        id: "tu-2",
        ideaId: MATCH_RAVI.idea.id,
        note: "",
        brought: [],
        after: null,
      });
    });
    await settle();
    expect(document.querySelector(".ck-first")).toBeTruthy();
    expect(text(document.querySelector(".ck-first"))).toContain("Something went wrong. Try again.");
    expect(flagCalls().some((c) => c.outcome === "kept_separate")).toBe(false);
  });

  it("a Check it already begun on a phone keeps its page: no comparison before it", async () => {
    asPhone();
    await mountFlagged(base({ draft: draft({ step: "check:2" }) }), true);
    expect(document.querySelector(".ck-first")).toBeNull();
    expect(document.querySelector("#pr-sort-h")).toBeTruthy();
    expect(flagCalls().map((c) => `${c.event}:${c.outcome}`)).toEqual(["s2.check:opened"]);
  });

  it("no close match on a phone: the page as drawn", async () => {
    asPhone();
    await mountFlagged(base({ draft: FRESH, similar: [MATCH_SUNITA] }), true);
    expect(document.querySelector(".ck-first")).toBeNull();
    expect(document.querySelector("#pr-sort-h")).toBeTruthy();
  });
});

describe("S2 order rules (model.ts)", () => {
  it("strongMatch is the top match when close; next, previous and place follow the order", () => {
    expect(model.strongMatch({ state: "ok", matches: [MATCH_RAVI, MATCH_SUNITA] })).toBe(MATCH_RAVI);
    expect(model.strongMatch({ state: "ok", matches: [MATCH_SUNITA, MATCH_RAVI] })).toBeNull();
    expect(model.strongMatch({ state: "failed" })).toBeNull();
    expect(model.nextIn(model.CHECK_FIRST_ORDER, 3)).toBe(1);
    expect(model.nextIn(model.CHECK_FIRST_ORDER, 2)).toBe(4);
    expect(model.prevIn(model.CHECK_FIRST_ORDER, 3)).toBeNull();
    expect(model.prevIn(model.CHECK_FIRST_ORDER, 1)).toBe(3);
    expect(model.placeIn(model.CHECK_FIRST_ORDER, 2)).toBe(3);
    expect(model.nextIn(model.DEFAULT_ORDER, 3)).toBe(4);
    expect(model.prevIn(model.DEFAULT_ORDER, 1)).toBeNull();
  });
});
