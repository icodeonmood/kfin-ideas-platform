// @vitest-environment jsdom
/**
 * V-ACC.similar gap tests on S-05 "Check it, then send it" (lane C's screen, J-SIMILAR), from lane F's coverage map
 * of 18 Nov 10:00. Each test names its row; lane C's code is exercised as it is on main and not changed.
 * - /1 part 3: a grid three across, their idea first ("Yours, not sent yet"), then the matches, closest first, in the
 *   order the API sends them (the worker's order is `test_1pc_f_vacc_db.py`);
 * - /5 after the lead declines with a reason: the reason, and "Send mine on its own", which leads to the normal Submit
 *   and sends the draft (the worker side is `test_1pc_f_vacc_db.py`).
 * The screen is real; its A-API answers are synthetic, served by a mocked fetch. Synthetic people only.
 */
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ConfigResponse, SimilarMatch, SortingResponse } from "@/lib/contracts";

import { applied, cssRules } from "./helpers/css-rules";

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, push: vi.fn(), refresh: vi.fn() }) }));
vi.mock("next/link", async () => {
  const { createElement: h } = await import("react");
  return {
    default: ({ href, children, ...rest }: { href: string; children?: unknown }) =>
      h("a", { href, ...rest }, children as never),
  };
});
vi.mock("@/lib/motion/spark", () => ({ sparkBurst: vi.fn() }));

const { CheckIt } = await import("@/app/share/[id]/check/check-it");

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// --- Fixtures (synthetic) ----------------------------------------------------------------------------------------
const DRAFT_ID = "0b6f7a52-3c1e-4d7a-9f00-1a2b3c4d5e6f";
const KAVYA = { id: "u-kavya", name: "Kavya Menon", first_name: "Kavya", initials: "KM" };
const RAVI = { id: "u-ravi", name: "Ravi Nair", first_name: "Ravi", initials: "RN" };
const SUNITA = { id: "u-sunita", name: "Sunita Pillai", first_name: "Sunita", initials: "SP" };
const ARJUN = { id: "u-arjun", name: "Arjun Rao", first_name: "Arjun", initials: "AR" };
const MY_TITLE = "Investors call to ask why a redemption was rejected";
const REASON = "Mine is about the SMS wording, yours is about the calls it causes. Better as two.";

function match(
  id: string,
  title: string,
  lead: typeof RAVI,
  strength: "close" | "related",
  extra: Partial<SimilarMatch["idea"]> = {},
): SimilarMatch {
  return {
    idea: {
      id,
      title,
      status: "with_review_desk",
      area: "Investor service",
      city: "Hyderabad",
      shared_at: "2026-11-09T10:00:00+05:30",
      lead,
      crew_faces: [lead],
      crew_count: 2,
      in_their_words: "Investors get a code, not a reason, and then they call us.",
      hue: 1,
      ...extra,
    },
    strength,
    reason: strength === "close" ? "Close match: same SMS, same calls" : "Related: the calls you describe",
  } as SimilarMatch;
}

/** Closest first, as the API sends them. The close one is the oldest and has the smallest crew, so a grid that
 * re-sorted by date or by crew would put it last. */
const CLOSE = match("IDEA-2026-001412", "Rejection SMS codes confuse investors", RAVI, "close", {
  shared_at: "2026-11-02T10:00:00+05:30",
  crew_count: 1,
});
const RELATED_NEW = match("IDEA-2026-001498", "No script for calls about rejections", SUNITA, "related", {
  shared_at: "2026-11-16T10:00:00+05:30",
  crew_count: 6,
});
const RELATED_OLD = match("IDEA-2026-001455", "Branch staff cannot read the SMS codes", ARJUN, "related", {
  shared_at: "2026-11-10T10:00:00+05:30",
  crew_count: 3,
});

function draft() {
  return {
    id: DRAFT_ID,
    owner_id: KAVYA.id,
    channel: "web",
    messages: [],
    parts: {
      title: { state: "filled", value: MY_TITLE },
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
    hidden: [],
    sorting: {},
    files: [],
    step: "check:3",
    saved_at: "2026-11-18T08:08:00Z",
    saved_on: { device: "laptop", this_device: true },
    ready: true,
    min_chars: 30,
    char_count: 180,
  };
}

function sorting(): SortingResponse {
  const field = (value: unknown) => ({ value, source: "confirmed", why: null, why_line: null });
  return {
    affects: field(["Investors", "KFin teams"]),
    kind: field("problem"),
    area: field("Investor service"),
    brings: field(["saves_time"]),
    confirmed: true,
    complete: true,
    confirmed_at: "2026-11-18T08:09:00Z",
    rail: "Investor service, saves time",
    summary: "Investor service, affecting investors and KFin teams, saves time",
    note: null,
    problem: null,
  } as unknown as SortingResponse;
}

const CONFIG = {
  promises: {},
  sorting: {
    affects: ["Investors", "KFin teams", "Distributors"],
    areas: ["Investor service", "Operations"],
    brings: ["saves_time", "saves_cost", "earns_revenue", "less_outside_tools", "not_sure"],
    helpers: ["Someone at a branch", "Someone in operations", "Someone from tech"],
    controls: {
      affects: {
        shown: ["Investors", "KFin teams", "Distributors"],
        all: ["Investors", "KFin teams", "Distributors"],
        search_link: "Search all groups",
        search_label: "Someone else? Search all 3",
        rule: "Pick all that apply",
      },
      area: {
        shown: ["Investor service", "Operations"],
        all: ["Investor service", "Operations"],
        search_link: "Search all areas",
        search_label: "Another area? Search all 2",
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
          { value: "not_sure", label: "Not sure yet" },
        ],
        exclusive: "not_sure",
        rule: "Pick all that apply",
      },
      helpers: ["Someone at a branch", "Someone in operations", "Someone from tech"],
    },
  },
  declaration: { version: "2026-11-17", submit: "By submitting, you confirm…", save: "" },
} as unknown as ConfigResponse;

function sendView() {
  return {
    id: DRAFT_ID,
    rows: [
      { key: "title", label: "Title", value: MY_TITLE, ok: true, step: "check:1" },
      { key: "sorting", label: "Sorting", value: "Investor service, saves time", ok: true, step: "check:2" },
      { key: "similar", label: "Similar ideas", value: "Ravi kept it separate", ok: true, step: "check:3" },
      { key: "proof", label: "Proof", value: "None added", ok: true, step: "check:4" },
      { key: "fix", label: "Your fix", value: "None added", ok: true, step: "check:5" },
      { key: "helpers", label: "Who would help", value: "Not said", ok: true, step: "check:6" },
    ],
    declaration: {
      version: "2026-11-17",
      text: "By submitting, you confirm there’s no customer personal data in it or its files, and it’s your own work or you’ve credited others.",
    },
    button: "Submit",
    ready: true,
    problems: [],
  };
}

/** What lane F's worker sends Check it once Ravi declined with a reason (`teamup/rules.py draft_after`). */
const DECLINED = {
  id: "m1",
  other_idea_id: CLOSE.idea.id,
  state: "declined",
  lead: RAVI,
  lead_reason: REASON,
  after: {
    state: "declined",
    label: "Ravi kept it separate",
    line: `Ravi kept that idea separate: “${REASON}” Send yours on its own.`,
    action: { label: "Send mine on its own", op: "submit" },
    can_submit: true,
  },
};

// --- A fetch that answers by method and path ---------------------------------------------------------------------
type Answer = { status?: number; body?: unknown };
type Route = (method: string, url: string, body: unknown) => Answer | undefined;
let calls: Array<{ method: string; url: string; body: unknown; headers: Record<string, string> }>;

function serve(routes: Route[]) {
  calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const method = (init.method ?? "GET").toUpperCase();
      const body: unknown = typeof init.body === "string" ? JSON.parse(init.body) : init.body;
      calls.push({ method, url, body, headers: (init.headers ?? {}) as Record<string, string> });
      for (const r of routes) {
        const a = r(method, url, body);
        if (!a) continue;
        const status = a.status ?? 200;
        return { ok: status >= 200 && status < 300, status, json: async () => a.body };
      }
      return { ok: false, status: 404, json: async () => ({ error: { code: "not_found", message: "" } }) };
    }),
  );
}

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

let host: HTMLElement;
let root: Root;

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
});

async function settle() {
  for (let i = 0; i < 6; i++) await act(async () => undefined);
}
const text = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();
const h1 = () => text(document.querySelector("h1"));
const nameOf = (b: Element) => {
  const label = b.getAttribute("aria-label");
  if (label) return label;
  const copy = b.cloneNode(true) as Element;
  copy.querySelectorAll('[aria-hidden="true"]').forEach((n) => n.remove());
  return text(copy);
};
const buttons = () => Array.from(document.querySelectorAll<HTMLButtonElement>("button"));
const button = (name: string) => buttons().find((b) => nameOf(b) === name);
async function click(el: Element | undefined | null) {
  if (!el) throw new Error("nothing to click");
  await act(async () => (el as HTMLElement).click());
  await settle();
}

// =================================================================================================================
// V-ACC.similar/1
// =================================================================================================================
describe("V-ACC.similar/1: Check it part 3, a grid three across: theirs first, then the matches, closest first", () => {
  /** S-05 opened on part 3 (the draft's saved step), with the matches in the API's order. */
  async function part3(matches: SimilarMatch[]) {
    serve([
      (m, u) => (m === "GET" && u === `/api/drafts/${DRAFT_ID}` ? { body: draft() } : undefined),
      (m, u) => (m === "PATCH" && u === `/api/drafts/${DRAFT_ID}` ? { body: {} } : undefined),
      (m, u) => (m === "GET" && u.endsWith("/sorting") ? { body: sorting() } : undefined),
      (m, u) => (m === "GET" && u.endsWith("/similar") ? { body: matches } : undefined),
      (m, u) =>
        m === "GET" && u.endsWith("/merge-request") ? { body: { state: "none", after: null } } : undefined,
      (m, u) => (m === "GET" && u.endsWith("/send") ? { body: sendView() } : undefined),
    ]);
    await act(async () => root.render(createElement(CheckIt, { draftId: DRAFT_ID, config: CONFIG })));
    await settle();
    expect(h1()).toBe("Has someone raised this already?");
    const list = Array.from(document.querySelectorAll("ul")).find((ul) =>
      text(ul).includes("Yours, not sent yet"),
    );
    expect(list, "the grid of ideas").toBeDefined();
    return list!;
  }

  it("V-ACC.similar/1: their idea is the first tile, Yours, not sent yet, with no actions; then the matches, closest first, as the API orders them", async () => {
    const tiles = Array.from((await part3([CLOSE, RELATED_NEW, RELATED_OLD])).children);
    expect(tiles).toHaveLength(4);
    expect(text(tiles[0])).toContain("Yours, not sent yet");
    expect(text(tiles[0])).toContain(MY_TITLE);
    expect(tiles[0]!.querySelectorAll("button, a")).toHaveLength(0);
    const order = [CLOSE, RELATED_NEW, RELATED_OLD].map((m) => m.idea.title);
    expect(tiles.slice(1).map((t) => order.find((title) => text(t).includes(title)))).toEqual(order);
    // The close one leads although it is the oldest with the smallest crew: the grid never re-sorts
    expect(text(tiles[1])).toContain("Close match: same SMS, same calls");
    expect(text(tiles[2])).toContain("Related: the calls you describe");
  });

  it("V-ACC.similar/1 C-SIMGRID.grid: on a laptop the grid is three across", async () => {
    const list = await part3([CLOSE, RELATED_NEW]);
    // The page's stylesheet as written, as it applies to the rendered grid at desktop width
    const sheet = cssRules("app/share/[id]/check/check.css");
    expect(applied(sheet, list, "display", 1440)).toBe("grid");
    const columns = applied(sheet, list, "grid-template-columns", 1440) ?? "";
    const repeat = columns.match(/^repeat\(\s*(\d+)\s*,/);
    const count = repeat ? Number(repeat[1]) : columns.split(/\s+(?![^(]*\))/).filter(Boolean).length;
    expect(count, columns).toBe(3);
  });
});

// =================================================================================================================
// V-ACC.similar/5
// =================================================================================================================
describe("V-ACC.similar/5: Ravi declined with a reason; Send mine on its own submits Kavya's idea normally", () => {
  it("V-ACC.similar/5: the reason shows with Send mine on its own; it leads to Send it, where Submit sends the draft and hands over to S-06", async () => {
    serve([
      (m, u) =>
        m === "POST" && u === `/api/drafts/${DRAFT_ID}/submit`
          ? {
              status: 201,
              body: {
                idea_id: "IDEA-2026-001520",
                ref: "IDEA-2026-001520",
                next: { to: "/ideas/IDEA-2026-001520", replace: true, state: "just_shared" },
              },
            }
          : undefined,
      (m, u) => (m === "GET" && u === `/api/drafts/${DRAFT_ID}` ? { body: draft() } : undefined),
      (m, u) => (m === "PATCH" && u === `/api/drafts/${DRAFT_ID}` ? { body: {} } : undefined),
      (m, u) => (m === "GET" && u.endsWith("/sorting") ? { body: sorting() } : undefined),
      (m, u) => (m === "GET" && u.endsWith("/similar") ? { body: [CLOSE] } : undefined),
      (m, u) => (m === "GET" && u.endsWith("/merge-request") ? { body: DECLINED } : undefined),
      (m, u) => (m === "GET" && u.endsWith("/send") ? { body: sendView() } : undefined),
    ]);
    await act(async () => root.render(createElement(CheckIt, { draftId: DRAFT_ID, config: CONFIG })));
    await settle();

    expect(text(document.body)).toContain(`Ravi kept that idea separate: “${REASON}” Send yours on its own.`);
    expect(button("Withdraw the request")).toBeUndefined();
    const sendAlone = button("Send mine on its own");
    expect(sendAlone).toBeDefined();
    expect(calls.some((c) => c.url.endsWith("/submit"))).toBe(false);

    await click(sendAlone);
    expect(h1()).toBe("Ready to send?");
    const submit = button("Submit")!;
    expect(submit.getAttribute("aria-disabled")).toBeNull();
    await click(submit);

    const sent = calls.filter((c) => c.method === "POST" && c.url === `/api/drafts/${DRAFT_ID}/submit`);
    expect(sent).toHaveLength(1);
    expect(sent[0]!.body).toEqual({ declaration_version: "2026-11-17" });
    expect(sent[0]!.headers["Idempotency-Key"]).toMatch(/^s05:/);
    // Nothing about the merge goes with it: no merge request is asked or withdrawn on the way
    expect(calls.filter((c) => c.method !== "GET" && c.url.endsWith("/merge-request"))).toEqual([]);
    expect(replace).toHaveBeenCalledWith("/ideas/IDEA-2026-001520");
  });
});
