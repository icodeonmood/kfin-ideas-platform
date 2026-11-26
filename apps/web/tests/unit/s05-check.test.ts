// @vitest-environment jsdom
/**
 * S-05 "Check it, then send it" (BLD-C130 to BLD-C135): the rules in model.ts, then the screen against mocked A-API
 * answers: the rail and its statuses, part 1 with the hidden details, sorting and its confirmation, the similar
 * ideas grid (yours first, the tiles, waiting, folding after "Keep mine separate", couldn't check), proof rows in every
 * state, the fix sheet, who would help, and Send: not confirmed, send failed, offline, a merge request waiting, and
 * the hand-over to S-06. Synthetic people only: the pack's fictional cast.
 */
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  ConfigResponse,
  FileItem,
  SendViewResponse,
  SimilarMatch,
  SortingResponse,
} from "@/lib/contracts";
import { CLOSED_STATUSES } from "@/lib/contracts";

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
const { withExclusive } = await import("@/app/share/[id]/check/parts");
const { CHECK_COPY } = await import("@/app/share/[id]/check/copy");

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

type Answer = { status?: number; body?: unknown; fail?: boolean; hold?: Promise<void> };
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
        if (a.hold) await a.hold; // a reply still on its way
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

async function railTo(label: string) {
  await click(button(new RegExp(`^(?:\\d )?${label}\\b`)));
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

// --- Rules -------------------------------------------------------------------------------------------------------

describe("S-05 rules (model.ts, BLD-C130)", () => {
  it("S-05.layout: a saved step opens its part; check:1 to check:6, send is part 7, anything else part 1", () => {
    expect(model.partFromStep("check:4")).toBe(4);
    expect(model.partFromStep("send")).toBe(7);
    expect(model.partFromStep("tell")).toBe(1);
    expect(model.partFromStep(undefined)).toBe(1);
    expect(model.stepOf(7)).toBe("send");
    expect(model.stepOf(3)).toBe("check:3");
  });

  it("S-05.layout C-SIMGRID: the part 3 rail reads the count, none, couldn't check, or the merge outcome", () => {
    expect(model.similarRail({ state: "ok", matches: [MATCH_RAVI, MATCH_SUNITA] }, null)).toBe(
      "2 close ideas found",
    );
    expect(model.similarRail({ state: "ok", matches: Array(8).fill(MATCH_RAVI) }, null)).toBe(
      "8 similar ideas found",
    );
    expect(model.similarRail({ state: "ok", matches: [] }, null)).toBe("Nobody has raised this yet.");
    // L-SIMILAR.failure: never "none found".
    expect(model.similarRail({ state: "failed" }, null)).toBe(
      "Couldn’t check for similar ideas. The review desk will.",
    );
    const waiting = model.mergeView({ state: "waiting", other_idea_id: MATCH_RAVI.idea.id, after: null }, [
      MATCH_RAVI,
    ]);
    expect(model.similarRail({ state: "ok", matches: [MATCH_RAVI] }, waiting)).toBe(
      "Waiting on Ravi to merge",
    );
  });

  it("L-MERGE.request/4: lane F's words win; without them the drawn lines are made from the lead's first name", () => {
    const fromF = model.mergeView(
      {
        state: "accepted",
        other_idea_id: "IDEA-2026-001412",
        after: {
          state: "accepted",
          label: "Merged into IDEA-2026-001412",
          line: "Ravi accepted. Yours is now part of IDEA-2026-001412, with credit to you. Nothing else to send.",
          can_submit: false,
        },
      },
      [],
    )!;
    expect(fromF.rail).toBe("Merged into IDEA-2026-001412");
    expect(fromF.canSubmit).toBe(false);
    const drawn = model.mergeView({ state: "waiting", other_idea_id: MATCH_RAVI.idea.id, after: null }, [
      MATCH_RAVI,
    ])!;
    expect(drawn.line).toBe(
      "Waiting for Ravi to accept the merge. If Ravi declines, you can send yours on its own.",
    );
    expect(drawn.action?.label).toBe("Withdraw the request");
    expect(model.mergeView({ state: "none", after: null }, [])).toBeNull();
  });

  it("C-SIMGRID.tile: Team up, then Waiting for Ravi with Withdraw, then On the crew", () => {
    expect(model.tileAction(MATCH_RAVI, null)).toEqual({ kind: "team-up" });
    const sent = {
      ...MATCH_RAVI,
      my_request: {
        id: "r1",
        idea_id: MATCH_RAVI.idea.id,
        from: KAVYA,
        note: "",
        brought: [],
        state: "sent" as const,
        sent_at: "",
      },
    };
    expect(model.tileAction(sent, null)).toEqual({
      kind: "waiting",
      label: "Waiting for Ravi",
      withdraw: { requestId: "r1" },
    });
    const on = { ...sent, my_request: { ...sent.my_request, state: "approved_team_only" as const } };
    expect(model.tileAction(on, null)).toEqual({ kind: "on-crew" });
    const merge = model.mergeView({ state: "waiting", other_idea_id: MATCH_RAVI.idea.id, after: null }, [
      MATCH_RAVI,
    ]);
    expect(model.tileAction(MATCH_RAVI, merge)).toEqual({
      kind: "waiting",
      label: "Waiting for Ravi",
      withdraw: { merge: true },
    });
  });

  it("C-FILE.row: every state reads as the board draws it; links never say they could not be opened (BLD-E001)", () => {
    const item = (state: FileItem["state"], extra: Partial<FileItem> = {}): FileItem => ({
      id: "f1",
      kind: "file",
      name: "branch-call-log-nov.pdf",
      type: "application/pdf",
      size: 140 * 1024,
      state,
      added_by: KAVYA,
      added_at: "",
      ...extra,
    });
    const v = (state: FileItem["state"], extra: Partial<FileItem> = {}) =>
      model.rowView({ key: "k", item: item(state, extra), name: "branch-call-log-nov.pdf" }, 25);
    expect(v("checking")).toMatchObject({
      status: "checking",
      statusText: "Checking for personal details",
      size: "140 KB",
    });
    expect(v("checked")).toMatchObject({ status: "checked", statusText: "Checked", actions: ["remove"] });
    expect(v("upload_failed")).toMatchObject({
      message: { kind: "error", text: "Didn’t upload. Your other files are fine." },
      actions: ["retry", "remove"],
    });
    expect(
      v("personal_data_found", {
        problem:
          "Found a phone number on page 2. Only you, the review desk and the Ones Committee can open it.",
      }),
    ).toMatchObject({
      status: "found",
      message: {
        kind: "warn",
        text: "Found a phone number on page 2. Only you, the review desk and the Ones Committee can open it.",
      },
      actions: ["hide", "remove"],
    });
    expect(v("hidden_checked", { hidden_note: "Folio hidden" })).toMatchObject({
      status: "hidden",
      statusText: "Folio hidden",
    });
    expect(v("too_big")).toMatchObject({ message: { text: "Too big. Files can be up to 25 MB." } });
    const link = v("unreachable", {
      kind: "link",
      name: "https://intranet.kfintech.example/codes",
      link_scope: "internal",
    });
    expect(link).toMatchObject({
      status: "checked",
      statusText: "Internal link",
      kind: "link",
      size: "intranet.kfintech.example",
    });
    expect(JSON.stringify(link)).not.toMatch(/couldn/);
  });

  it("BLD-C225 L-HIDE.files: a check waiting for the gatekeeper reads the worker's waiting line, still checking with Remove", () => {
    const waiting = "Waiting for the personal details check. It runs when the assistant is back.";
    const row = model.rowView(
      {
        key: "k",
        name: "branch-call-log-nov.pdf",
        item: {
          id: "f1",
          kind: "file",
          name: "branch-call-log-nov.pdf",
          type: "application/pdf",
          size: 140 * 1024,
          state: "checking",
          added_by: KAVYA,
          added_at: "",
          problem: waiting,
        },
      },
      25,
    );
    expect(row).toMatchObject({ status: "checking", statusText: waiting, actions: ["remove"] });
    expect(row.message).toBeUndefined();
    // C-FILE.row BLD-C237 (WCAG 2.2.2): the waiting row asks for no spinner; a check that runs still has one.
    expect(row.waiting).toBe(true);
    const running = model.rowView(
      {
        key: "k2",
        name: "branch-call-log-nov.pdf",
        item: {
          id: "f2",
          kind: "file",
          name: "branch-call-log-nov.pdf",
          type: "application/pdf",
          size: 140 * 1024,
          state: "checking",
          added_by: KAVYA,
          added_at: "",
        },
      },
      25,
    );
    expect(running.status).toBe("checking");
    expect(running.waiting).toBeUndefined();
  });

  it("C-FILE.row BLD-C139: infected and locked rows say the server's words when sent, else the drawn line, with Remove only", () => {
    const item = (state: FileItem["state"], problem?: string) => ({
      key: "k",
      name: "scan.pdf",
      item: {
        id: "f",
        kind: "file" as const,
        name: "scan.pdf",
        type: "application/pdf",
        size: 1,
        state,
        added_by: KAVYA,
        added_at: "",
        problem,
      },
    });
    expect(model.rowView(item("infected"), 25).message?.text).toBe(
      "Didn’t upload. Your other files are fine.",
    );
    expect(model.rowView(item("locked", "This file has a password."), 25).message?.text).toBe(
      "This file has a password.",
    );
    expect(model.rowView(item("locked"), 25).actions).toEqual(["remove"]);
    expect(model.rowView({ ...item("checking"), stalled: true }, 25).actions).toEqual(["retry", "remove"]);
    expect(
      model.rowView({ ...item("checked"), note: "Something went wrong. Try again." }, 25).message,
    ).toEqual({
      kind: "error",
      text: "Something went wrong. Try again.",
    });
  });

  it("C-FILE.uploader/3: links one at a time or with commas; anything else is not a link", () => {
    expect(model.splitLinks("intranet.kfintech.example/page, https://teams.example/x")).toEqual({
      links: ["https://intranet.kfintech.example/page", "https://teams.example/x"],
      typed: ["intranet.kfintech.example/page", "https://teams.example/x"],
      bad: false,
    });
    expect(model.splitLinks("the codes list").bad).toBe(true);
    expect(model.splitLinks("").bad).toBe(true);
  });

  it("S-05.fix: readiness counts five answers, names the most useful next one, and sends the figures as typed", () => {
    const f = { ...model.EMPTY_FIX, how: "Send the reason in plain words.", solved: "partly" };
    expect(model.fixReady(f)).toBe(2);
    expect(model.fixNext(f)).toBe("worth");
    expect(CHECK_COPY.sheet.next[model.fixNext(f)!]).toBe("Most useful next: a rough size. A range is fine.");
    const full = {
      ...f,
      measures: ["hours", "cost"] as const,
      hours: "70 to 150",
      cost: "25k",
      basis: "conversation",
      needs: "SMS template change",
    };
    expect(model.fixReady({ ...full, measures: [...full.measures] })).toBe(5);
    expect(model.fixRequest({ ...full, measures: [...full.measures] }, true)).toEqual({
      included: true,
      how: "Send the reason in plain words.",
      needs: "SMS template change",
      solved_already: "partly",
      basis: "conversation",
      worth: { hours_month: "70 to 150", cost_month: "25k" },
    });
  });

  it("V-FIELDS.checkit/3: Not sure yet clears the others, and any other choice clears it", () => {
    expect(withExclusive(["saves_time"], ["saves_time", "not_sure"], "not_sure")).toEqual(["not_sure"]);
    expect(withExclusive(["not_sure"], ["not_sure", "saves_cost"], "not_sure")).toEqual(["saves_cost"]);
    expect(withExclusive(["saves_time", "saves_cost"], ["saves_time"], "not_sure")).toEqual(["saves_time"]);
  });
});

// --- The screen ---------------------------------------------------------------------------------------------------

describe("S-05 screen: rail and part 1 (BLD-C131)", () => {
  it("S-05.layout J-SHARE/7: seven rail buttons named number, part and status; part 1 with the title as h3 and the hidden detail", async () => {
    await mount(base());
    const rail = Array.from(document.querySelectorAll(".ck-rail button")).map(nameOf);
    expect(rail).toEqual([
      "1 Your words Title, what happens, how often",
      "2 Sorting Suggested, not confirmed yet",
      "3 Similar ideas 2 close ideas found",
      "4 Proof Optional",
      "5 Your fix Optional",
      "6 Who would help Optional",
      // Its line describes it, so "Submit" names one button (BLD-C130).
      "7 Send it",
    ]);
    const send = document.querySelectorAll(".ck-rail button")[6]!;
    expect(text(document.getElementById(send.getAttribute("aria-describedby")!))).toBe(
      "One last look, then submit",
    );
    expect(buttons().filter((b) => /submit/i.test(nameOf(b)))).toHaveLength(0);
    expect(text(document.querySelector(".ck-count"))).toBe("Check it, part 1 of 6");
    expect(h1()).toBe("Is this how you’d put it?");
    expect(document.body.textContent).toContain(CHECK_COPY.words.line);
    expect(text(document.querySelector("h3"))).toBe("Investors call to ask why a redemption was rejected");
    expect(document.body.textContent).toContain("Hidden from everyone");
    expect(document.body.textContent).toContain("Folio ••••89");
    const back = Array.from(document.querySelectorAll("a")).find((a) => text(a) === "Back to your words")!;
    expect(back.getAttribute("href")).toBe(`/share/${DRAFT_ID}`);
    for (const n of ["Change the title", "Change what happens", "Change how often"])
      expect(button(n)).toBeTruthy();
    // Saved at …, in the task bar's live region (C-TASKBAR.save).
    expect(text(document.querySelector('.tbar [role="status"]'))).toMatch(/^Saved at \d{1,2}:\d{2} (am|pm)$/);
  });

  it("C-HIDDEN.list J-RECOVER/11: Show it asks for one of three reasons, stays disabled until one is picked, then reads Shown, because …", async () => {
    await mount([
      (m, u, b) =>
        m === "POST" && u.endsWith("/hidden/h1/show")
          ? {
              body: {
                id: "h1",
                kind: "folio",
                masked: "Folio ••••89",
                state: "shown",
                reason: (b as { reason: string }).reason,
              },
            }
          : undefined,
      ...base(),
    ]);
    await click(button("Show it"));
    expect(document.body.textContent).toContain(
      "Only show it if it isn’t about a real customer. What is it?",
    );
    expect(document.body.textContent).toContain("We note your reason with the idea.");
    const radios = Array.from(document.querySelectorAll('[role="radio"]')).map(text);
    expect(radios).toEqual([
      "it’s a scheme or product code",
      "it’s an internal reference",
      "it’s made up for the example",
    ]);
    const confirm = buttons()
      .filter((b) => nameOf(b) === "Show it")
      .pop()!;
    expect(confirm.getAttribute("aria-disabled")).toBe("true");
    await click(Array.from(document.querySelectorAll('[role="radio"]'))[2]);
    await click(
      buttons()
        .filter((b) => nameOf(b) === "Show it")
        .pop(),
    );
    expect(calls.find((c) => c.url.endsWith("/show"))?.body).toEqual({ reason: "made_up_example" });
    expect(document.body.textContent).toContain("Shown, because it’s made up for the example.");
    expect(button("Hide it")).toBeTruthy();
  });

  it("V-FIELDS.checkit/1: a title changed in place is saved as a part; an empty one says what to do", async () => {
    await mount([
      (m, u) => (m === "PATCH" && u.endsWith("/parts/title") ? { body: { run_id: null } } : undefined),
      ...base(),
    ]);
    await click(button("Change the title"));
    const input = document.querySelector<HTMLInputElement>('input[aria-label="Title"]')!;
    const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    await act(async () => {
      setValue.call(input, "");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await act(async () => input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })));
    expect(document.body.textContent).toContain("Give it a title of a few words.");
    await act(async () => {
      setValue.call(input, "R07 rejections confuse investors");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await act(async () => input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })));
    await settle();
    expect(calls.find((c) => c.url.endsWith("/parts/title"))?.body).toEqual({
      value: "R07 rejections confuse investors",
    });
    expect(text(document.querySelector("h3"))).toBe("R07 rejections confuse investors");
  });
});

describe("S-05 screen: sorting (BLD-C131, L-SORT)", () => {
  it("J-SHARE/8: suggestions with their reasons until confirmed; Confirm sorting moves on and the rail stops saying suggested", async () => {
    await mount(base());
    await click(button("Looks right"));
    expect(text(document.querySelector(".ck-count"))).toBe("Check it, part 2 of 6");
    expect(h1()).toBe("Is it sorted right?");
    expect(document.body.textContent).toContain("These are suggestions from your words. Not confirmed yet.");
    expect(document.body.textContent).toContain("Suggested because you mentioned investors and the branch.");
    const problem = Array.from(document.querySelectorAll('[role="radio"]')).find(
      (r) => text(r) === "A problem to fix",
    )!;
    expect(problem.getAttribute("aria-checked")).toBe("true");
    expect(
      document.querySelector('input[role="combobox"][aria-label="Someone else? Search all 6"]'),
    ).toBeTruthy();
    expect(
      document.querySelector('input[role="combobox"][aria-label="Another area? Search all 12"]'),
    ).toBeTruthy();
    await click(button("Confirm sorting"));
    expect(
      calls.some(
        (c) =>
          c.method === "PATCH" && c.url.endsWith("/sorting") && (c.body as { confirm?: boolean }).confirm,
      ),
    ).toBe(true);
    expect(text(document.querySelector(".ck-count"))).toBe("Check it, part 3 of 6");
    expect(buttons().some((b) => /Sorting Suggested, not confirmed yet/.test(nameOf(b)))).toBe(false);
    expect(button(/^Sorting, done Investor service, saves time, saves cost$/)).toBeTruthy();
  });

  it("BLD-C233, L-SORT, BLD-C176: a late Confirm sorting reply never moves someone who has opened another part", async () => {
    let release!: () => void;
    const held = new Promise<void>((r) => (release = r));
    const slowConfirm: Route = (m, u, b) =>
      m === "PATCH" && u.endsWith("/sorting") && (b as { confirm?: boolean }).confirm
        ? { body: sorting(true), hold: held }
        : undefined;
    await mount([slowConfirm, ...base()]);
    await click(button("Looks right"));
    expect(h1()).toBe("Is it sorted right?");
    await click(button("Confirm sorting")); // its reply is held
    await railTo("Send it"); // the person moves on before the reply comes
    const here = h1();
    expect(here).not.toBe("Is it sorted right?");
    release();
    await settle();
    expect(h1()).toBe(here); // still where the person is
    expect(button(/^Sorting, done /)).toBeTruthy(); // and the sorting reads as done
  });

  it("J-RECOVER/10: one choice changes the area and is saved at once", async () => {
    await mount(base());
    await railTo("Sorting");
    await click(
      Array.from(document.querySelectorAll('[role="radio"]')).find((r) => text(r) === "Operations"),
    );
    expect(calls.find((c) => c.method === "PATCH" && c.url.endsWith("/sorting"))?.body).toEqual({
      area: "Operations",
    });
  });
});

describe("S-05 screen: similar ideas (BLD-C132, C-SIMGRID, L-SIMILAR)", () => {
  it("C-SIMGRID.grid J-SIMILAR/2: yours first with no actions, then the matches with Preview and Team up; Preview opens C-PREVIEW", async () => {
    await mount(base());
    await railTo("Similar ideas");
    expect(h1()).toBe("Has someone raised this already?");
    expect(document.body.textContent).toContain(
      "Two colleagues shared something close while you were writing. Team up with them, and bring yours along if you like, or keep yours separate.",
    );
    const tiles = Array.from(document.querySelectorAll(".simgrid > li"));
    expect(tiles).toHaveLength(3);
    expect(text(tiles[0])).toContain("Yours, not sent yet");
    expect(tiles[0]!.querySelectorAll("button")).toHaveLength(0);
    expect(text(tiles[1])).toContain("IDEA-2026-001412, Investor service, Hyderabad");
    expect(text(tiles[1])).toContain("Close match: same SMS, same calls");
    expect(text(tiles[1])).toContain("4 colleagues on it");
    expect(button("Team up on Rejection SMS codes confuse investors")).toBeTruthy();
    expect(document.body.textContent).toContain(
      "None of these the same? Just carry on. Yours goes on its own.",
    );
    await click(button("Preview Rejection SMS codes confuse investors"));
    const dialog = document.querySelector('[role="dialog"]')!;
    expect(text(dialog)).toContain("Teaming up adds you to their crew. Your draft stays yours.");
    expect(text(dialog)).toContain("Close match: same SMS, same calls");
  });

  it("J-SHARE/9 C-SIMGRID.grid/4 (BLD-C131 amended): Next only moves on and records nothing; the grid is still there on the way back", async () => {
    await mount(base());
    await railTo("Similar ideas");
    await click(button("Next"));
    expect(calls.some((c) => c.url.endsWith("/similar/keep-separate"))).toBe(false);
    expect(text(document.querySelector(".ck-count"))).toBe("Check it, part 4 of 6");
    await railTo("Similar ideas");
    expect(document.body.textContent).not.toContain("Kept separate.");
    expect(document.querySelector(".simgrid")).toBeTruthy();
  });

  it("C-SIMGRID.grid/4 V-ACC.share/7 J-SIMILAR/3: Keep mine separate in lane F's sheet records it and folds the grid; on close focus goes to Show them again", async () => {
    await mount(base());
    await railTo("Similar ideas");
    const teamUp = button("Team up on Rejection SMS codes confuse investors")!;
    // C-SIMGRID.tile: Team up is marked for the sheet to give focus back to (BLD-F074).
    expect(teamUp.getAttribute("data-teamup-opener")).toBe("IDEA-2026-001412");
    expect(typeof sheetHook.options?.returnFocus).toBe("function");
    expect(sheetHook.options?.draftId).toBe(DRAFT_ID);
    teamUp.focus();
    await click(teamUp);
    expect(document.querySelector('[role="dialog"]')).toBeTruthy();
    const sent = {
      kind: "teamup",
      id: "tu-1",
      ideaId: MATCH_RAVI.idea.id,
      note: "I take these calls at the Hyderabad branch too.",
      brought: [],
      after: null,
    };
    await act(async () => (sheetHook.options!.onSent as (s: unknown) => void)(sent));
    await settle();
    expect(calls.find((c) => c.url.endsWith("/similar/keep-separate"))?.body).toEqual({ on: true });
    expect(document.body.textContent).toContain(
      "Kept separate. The review desk still sees the similar ideas next to yours.",
    );
    // The sheet stays open over the fold until the person closes it.
    expect(document.querySelector('[role="dialog"]')).toBeTruthy();
    await act(async () => sheetHook.handle!.close());
    await settle();
    expect(document.activeElement).toBe(button("Show them again"));
  });

  it("L-MERGE.request/1 C-SIMGRID.grid/4: Ask Ravi to merge mine in does not fold the grid; it reloads the merge request", async () => {
    await mount(base());
    await railTo("Similar ideas");
    const before = calls.filter((c) => c.url.endsWith("/merge-request")).length;
    await act(async () =>
      (sheetHook.options!.onSent as (s: unknown) => void)({
        kind: "merge",
        id: "m-1",
        ideaId: MATCH_RAVI.idea.id,
        note: "Please take mine into yours.",
        brought: [],
        after: null,
      }),
    );
    await settle();
    expect(calls.some((c) => c.url.endsWith("/similar/keep-separate"))).toBe(false);
    expect(calls.filter((c) => c.url.endsWith("/merge-request")).length).toBeGreaterThan(before);
    expect(document.querySelector(".simgrid")).toBeTruthy();
  });

  it("C-SIMGRID.grid/4 BLD-C131: the fold follows the draft's kept_separate after a reload; Show them again opens the grid", async () => {
    await mount(base({ draft: draft({ kept_separate: true }) }));
    await railTo("Similar ideas");
    expect(document.body.textContent).toContain(
      "Kept separate. The review desk still sees the similar ideas next to yours.",
    );
    expect(document.querySelector(".simgrid")).toBeNull();
    await click(button("Show them again"));
    expect(calls.filter((c) => c.url.endsWith("/similar/keep-separate")).pop()?.body).toEqual({ on: false });
    expect(document.querySelector(".simgrid")).toBeTruthy();
  });

  it("L-SIMILAR.failure: a failed check says couldn't check, never none found; none found says nobody has raised it", async () => {
    await mount([
      (m, u) => (u.endsWith("/similar") && m === "GET" ? { status: 502, body: {} } : undefined),
      ...base(),
    ]);
    await railTo("Similar ideas");
    expect(document.body.textContent).toContain("Couldn’t check for similar ideas. The review desk will.");
    expect(document.body.textContent).not.toContain("Nobody has raised this yet.");
    expect(document.body.textContent).toContain("Yours, not sent yet");
    await act(async () => root.unmount());
    root = createRoot(host);
    await mount(base({ similar: [] }));
    await railTo("Similar ideas");
    expect(document.body.textContent).toContain("Nobody has raised this yet.");
  });

  it("L-MERGE.request/4 J-SIMILAR/4b J-RECOVER/16: a waiting merge request: the bar, Waiting for Ravi on the tile, Withdraw the request, Submit unavailable", async () => {
    const waiting = {
      id: "m1",
      other_idea_id: MATCH_RAVI.idea.id,
      state: "waiting",
      lead: RAVI,
      after: {
        state: "waiting",
        label: "Waiting on Ravi to merge",
        line: "Waiting for Ravi to accept the merge. If Ravi declines, you can send yours on its own.",
        action: { label: "Withdraw the request", op: "withdraw" },
        can_submit: false,
      },
    };
    await mount([
      (m, u) =>
        m === "DELETE" && u.endsWith("/merge-request")
          ? { body: { state: "withdrawn", after: null } }
          : undefined,
      ...base({ merge: waiting }),
    ]);
    await railTo("Similar ideas");
    expect(button(/Similar ideas Waiting on Ravi to merge$/)).toBeTruthy();
    const line = "Waiting for Ravi to accept the merge. If Ravi declines, you can send yours on its own.";
    expect(Array.from(document.querySelectorAll("p")).filter((p) => text(p) === line)).toHaveLength(1);
    expect(Array.from(document.querySelectorAll(".tuwait")).map(text)).toEqual(["Waiting for Ravi"]);
    // Where "Team up" was, marked for lane F's sheet to give focus back to (teamUpOpener, WCAG 2.4.3).
    expect(document.querySelector('[data-teamup-opener="IDEA-2026-001412"]')?.textContent).toBe("Withdraw");
    expect(button("Withdraw the request")).toBeTruthy();
    await railTo("Send it");
    expect(h1()).toBe("Ready to send?");
    expect(button("Submit")!.getAttribute("aria-disabled")).toBe("true");
    await click(button("Withdraw the request"));
    expect(calls.some((c) => c.method === "DELETE" && c.url.endsWith("/merge-request"))).toBe(true);
  });

  it("L-MERGE.request/4 WCAG 4.1.3: the bar's live region is on the page before its words; a failed Withdraw on the bar says so on the bar", async () => {
    await mount(base());
    const live = document.querySelector('.ck-mlive[role="status"]');
    expect(live).toBeTruthy();
    expect(text(live)).toBe("");
    await act(async () => root.unmount());
    root = createRoot(host);
    const waiting = {
      id: "m1",
      other_idea_id: MATCH_RAVI.idea.id,
      state: "waiting",
      lead: RAVI,
      after: {
        state: "waiting",
        label: "Waiting on Ravi to merge",
        line: "Waiting for Ravi to accept the merge. If Ravi declines, you can send yours on its own.",
        action: { label: "Withdraw the request", op: "withdraw" },
        can_submit: false,
      },
    };
    await mount([
      (m, u) => (m === "DELETE" && u.endsWith("/merge-request") ? { status: 502, body: {} } : undefined),
      ...base({ merge: waiting }),
    ]);
    await railTo("Proof");
    await click(button("Withdraw the request"));
    const bar = document.querySelector('.ck-mlive[role="status"]')!;
    expect(text(bar)).toContain("Something went wrong. Try again.");
    expect(h1()).toBe("Anything that shows it?");
  });
});

describe("S-05 screen: proof (BLD-C133, C-FILE)", () => {
  function chooseFile(name: string, type: string, bytes = 1024) {
    const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;
    const file = new File([new Uint8Array(bytes)], name, { type });
    Object.defineProperty(input, "files", { value: [file], configurable: true });
    return act(async () => input.dispatchEvent(new Event("change", { bubbles: true })));
  }

  it("J-SHARE/10: empty proof shows what helps most and Skip for now; parts 4 to 6 skip on to Send it", async () => {
    await mount(base());
    await railTo("Proof");
    expect(h1()).toBe("Anything that shows it?");
    expect(document.body.textContent).toContain("What helps most");
    await click(button("Skip for now"));
    expect(h1()).toBe("Got an idea how to solve it?");
    await click(button("Skip for now"));
    expect(h1()).toBe("Who would help?");
    await click(button("Skip for now"));
    expect(h1()).toBe("Ready to send?");
    expect(text(document.querySelector(".ck-count"))).toBe("Step 3 of 3");
  });

  it("J-RECOVER/7 C-FILE.row: a failed upload says so with Try again and Remove; Remove takes it away", async () => {
    await mount([(m, u) => (m === "POST" && u === "/api/files" ? { fail: true } : undefined), ...base()]);
    await railTo("Proof");
    await click(button("Attach files"));
    expect(button("browse")).toBeTruthy();
    await chooseFile("courier-register-photo.png", "image/png");
    await settle();
    expect(document.body.textContent).toContain("Didn’t upload. Your other files are fine.");
    expect(button("Try again")).toBeTruthy();
    expect(button(/Proof 1 file$/)).toBeTruthy();
    await click(button("Remove courier-register-photo.png"));
    expect(document.body.textContent).not.toContain("courier-register-photo.png");
  });

  it("J-RECOVER/8 L-HIDE.files: a file with personal data: the found line, Hide it for me (files.blackout on) and Remove; checking until it settles", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const uploaded: FileItem = {
      id: "f9",
      kind: "file",
      name: "courier-call-log.pdf",
      type: "application/pdf",
      size: 2048,
      state: "checking",
      added_by: KAVYA,
      added_at: "",
    };
    await mount(
      [
        (m, u) => (m === "POST" && u === "/api/files" ? { status: 201, body: uploaded } : undefined),
        (m, u) =>
          m === "GET" && u === "/api/files/f9"
            ? {
                body: {
                  ...uploaded,
                  state: "personal_data_found",
                  problem:
                    "Found a phone number on page 1. Only you, the review desk and the Ones Committee can open it.",
                },
              }
            : undefined,
        (m, u) =>
          m === "POST" && u === "/api/files/f9/hide"
            ? { body: { ...uploaded, state: "hidden_checked", hidden_note: "Phone hidden" } }
            : undefined,
        ...base(),
      ],
      CONFIG,
      { blackout: true },
    );
    await railTo("Proof");
    await click(button("Attach files"));
    await chooseFile("courier-call-log.pdf", "application/pdf");
    await settle();
    expect(document.body.textContent).toContain("Checking for personal details");
    await act(async () => vi.advanceTimersByTime(2100));
    await settle();
    expect(document.body.textContent).toContain(
      "Found a phone number on page 1. Only you, the review desk and the Ones Committee can open it.",
    );
    await click(button("Hide it for me"));
    expect(document.body.textContent).toContain("Phone hidden");
  });

  it("A-API.files C-FILE.uploader/1: the configured limit and help line; a refusal says the server's words with Remove only", async () => {
    await mount([
      (m, u) =>
        m === "GET" && u === "/api/config/uploads"
          ? {
              body: {
                limit_mb: 15,
                types: [".pdf", ".png"],
                help_text: "PDFs or screenshots, up to 15 MB each.",
              },
            }
          : undefined,
      (m, u) =>
        m === "POST" && u === "/api/files"
          ? {
              status: 415,
              body: { error: { code: "type_not_allowed", message: "This kind of file can’t be added." } },
            }
          : undefined,
      ...base(),
    ]);
    await railTo("Proof");
    await click(button("Attach files"));
    expect(document.body.textContent).toContain("PDFs or screenshots, up to 15 MB each.");
    expect(document.querySelector<HTMLInputElement>('input[type="file"]')!.accept).toBe(".pdf,.png");
    await chooseFile("branch-notes.exe", "application/octet-stream");
    await settle();
    expect(document.body.textContent).toContain("This kind of file can’t be added.");
    expect(button("Try again")).toBeUndefined();
    expect(button("Remove branch-notes.exe")).toBeTruthy();
    await chooseFile("huge-scan.pdf", "application/pdf", 16 * 1024 * 1024);
    await settle();
    expect(document.body.textContent).toContain("Too big. Files can be up to 15 MB.");
    expect(calls.filter((c) => c.method === "POST" && c.url === "/api/files")).toHaveLength(1);
  });

  it("C-FILE.row: a checked file the person may open has View, to GET /api/files/:id/view", async () => {
    const f: FileItem = {
      id: "f3",
      kind: "file",
      name: "rejection-sms-screenshot.png",
      type: "image/png",
      size: 86016,
      state: "checked",
      added_by: KAVYA,
      added_at: "",
      view_url: "/api/files/f3/view",
    };
    await mount(base({ draft: draft({ files: [f] }) }));
    await railTo("Proof");
    const view = Array.from(document.querySelectorAll("a")).find(
      (a) => a.getAttribute("aria-label") === "View rejection-sms-screenshot.png",
    )!;
    expect(view.getAttribute("href")).toBe("/api/files/f3/view");
    expect(text(view)).toBe("View");
    expect(button(/Proof 1 file$/)).toBeTruthy();
  });

  it("C-PROMPT.attach (DEC-124, BLD-C214): a file added in the prompt box is listed again on Check it under Proof", async () => {
    // As the draft read sends a file added in the box (draft/store.py `_files`): on the draft, with no message_id.
    const f = {
      id: "ATT-2026-000101",
      kind: "file",
      name: "Rejection codes reference.pdf",
      type: "application/pdf",
      size: 880640,
      state: "checked",
      added_by: { id: KAVYA.id },
      added_at: "2026-11-20T10:00:00.000Z",
    } as unknown as FileItem;
    await mount(base({ draft: draft({ files: [f] }) }));
    await railTo("Proof");
    expect(h1()).toBe("Anything that shows it?");
    expect(text(document.querySelector(".ck-proof .flist"))).toContain("Rejection codes reference.pdf");
    expect(button("Remove Rejection codes reference.pdf")).toBeTruthy();
    expect(button(/Proof 1 file$/)).toBeTruthy();
  });

  it("J-RECOVER/9 BLD-E001: a link is kept as typed, never opened, with Remove; not a link says what a link looks like", async () => {
    await mount([
      (m, u, b) =>
        m === "POST" && u === "/api/links"
          ? {
              status: 201,
              body: {
                id: "l1",
                kind: "link",
                name: (b as { url: string }).url,
                type: "link",
                state: "ok",
                link_scope: "internal",
                added_by: KAVYA,
                added_at: "",
              },
            }
          : undefined,
      ...base(),
    ]);
    await railTo("Proof");
    const input = document.querySelector<HTMLInputElement>('input[inputmode="url"]')!;
    const labelled = (input.getAttribute("aria-labelledby") ?? "")
      .split(" ")
      .map((id) => text(document.getElementById(id)))
      .join(" ");
    expect(labelled).toContain("Paste a link, or attach files. Add several links at once with commas.");
    const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    await act(async () => {
      setValue.call(input, "the codes list");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await click(button("Add a link"));
    expect(document.body.textContent).toContain(
      "That doesn’t look like a link. A link looks like intranet.kfintech.com/page.",
    );
    await act(async () => {
      setValue.call(input, "https://intranet.kfintech.example/courier-returns");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await click(button("Add a link"));
    expect(button("Remove https://intranet.kfintech.example/courier-returns")).toBeTruthy();
    expect(document.body.textContent).toContain("Internal link");
    expect(document.body.textContent).not.toMatch(/couldn.t open this link/);
  });

  const checking = (id: string, name: string, state: FileItem["state"] = "checking"): FileItem => ({
    id,
    kind: "file",
    name,
    type: "application/pdf",
    size: 2048,
    state,
    added_by: KAVYA,
    added_at: "",
  });

  it("DEC-107 BLD-C064: while files.blackout is off, a file with a detail found offers Remove but not Hide it for me", async () => {
    const found = {
      ...checking("f4", "branch-call-log.pdf", "personal_data_found"),
      problem:
        "Found a phone number on page 1. Only you, the review desk and the Ones Committee can open it.",
    };
    await mount(base({ draft: draft({ files: [found] }) }));
    await railTo("Proof");
    expect(document.body.textContent).toContain("Found a phone number on page 1.");
    expect(button("Hide it for me")).toBeUndefined();
    expect(button("Remove branch-call-log.pdf")).toBeTruthy();
  });

  it("L-HIDE.files/3 S-05.rules/5: a Hide it for me that fails says the server's words under its row", async () => {
    const found = {
      ...checking("f4", "branch-call-log.pdf", "personal_data_found"),
      problem: "Found a phone number.",
    };
    const paused =
      "Hiding details inside a file is coming soon. The review desk will look at the file with you.";
    await mount(
      [
        (m, u) =>
          m === "POST" && u === "/api/files/f4/hide"
            ? { status: 503, body: { error: { code: "not_available", message: paused } } }
            : undefined,
        ...base({ draft: draft({ files: [found] }) }),
      ],
      CONFIG,
      { blackout: true },
    );
    await railTo("Proof");
    await click(button("Hide it for me"));
    const row = document.querySelector(".frow")!;
    expect(text(row)).toContain(paused);
    expect(text(row)).toContain("branch-call-log.pdf");
  });

  it("C-FILE.row S-05.rules/5: a Remove that fails keeps the row where it was and says so under it", async () => {
    const a = checking("f1", "first-screenshot.pdf", "checked");
    const b = checking("f2", "second-report.pdf", "checked");
    await mount([
      (m, u) => (m === "DELETE" && u === "/api/files/f1" ? { status: 502, body: {} } : undefined),
      (m, u) => (m === "DELETE" && u === "/api/files/f2" ? { status: 204 } : undefined),
      ...base({ draft: draft({ files: [a, b] }) }),
    ]);
    await railTo("Proof");
    await click(button("Remove first-screenshot.pdf"));
    const rows = Array.from(document.querySelectorAll(".frow"));
    expect(rows.map((r) => text(r.querySelector(".frow-n")))).toEqual([
      "first-screenshot.pdf",
      "second-report.pdf",
    ]);
    expect(text(rows[0])).toContain("Something went wrong. Try again.");
    await click(button("Remove second-report.pdf"));
    expect(
      Array.from(document.querySelectorAll(".frow")).map((r) => text(r.querySelector(".frow-n"))),
    ).toEqual(["first-screenshot.pdf"]);
  });

  it("A-API.files: Remove while the upload is on its way deletes the file once the upload answers, and never brings the row back", async () => {
    let answer: (v: unknown) => void = () => undefined;
    const answered = new Promise((r) => (answer = r));
    await mount([
      (m, u) =>
        m === "POST" && u === "/api/files"
          ? { status: 201, body: checking("f7", "courier-log.pdf") }
          : undefined,
      (m, u) => (m === "DELETE" && u === "/api/files/f7" ? { status: 204 } : undefined),
      ...base(),
    ]);
    const real = globalThis.fetch as unknown as (u: string, i?: RequestInit) => Promise<unknown>;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (u: string, i?: RequestInit) => {
        if (u === "/api/files" && i?.method === "POST") await answered;
        return real(u, i);
      }),
    );
    await railTo("Proof");
    await click(button("Attach files"));
    await chooseFile("courier-log.pdf", "application/pdf");
    await click(button("Remove courier-log.pdf"));
    expect(document.body.textContent).not.toContain("courier-log.pdf");
    await act(async () => answer(null));
    await settle();
    expect(calls.some((c) => c.method === "DELETE" && c.url === "/api/files/f7")).toBe(true);
    expect(document.body.textContent).not.toContain("courier-log.pdf");
  });

  it("C-FILE.row BLD-C139: a failed ask for a file's state waits longer and asks again; it settles when an ask answers", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let asks = 0;
    await mount([
      (m, u) => {
        if (m !== "GET" || u !== "/api/files/f9") return undefined;
        asks += 1;
        return asks <= 2 ? { fail: true } : { body: checking("f9", "courier-call-log.pdf", "checked") };
      },
      ...base({ draft: draft({ files: [checking("f9", "courier-call-log.pdf")] }) }),
    ]);
    await railTo("Proof");
    await act(async () => vi.advanceTimersByTime(2100));
    await settle();
    expect(asks).toBe(1);
    await act(async () => vi.advanceTimersByTime(2100));
    await settle();
    expect(asks).toBe(1); // after one failure the next ask waits 4 s
    await act(async () => vi.advanceTimersByTime(2000));
    await settle();
    expect(asks).toBe(2);
    await act(async () => vi.advanceTimersByTime(8100));
    await settle();
    expect(asks).toBe(3);
    expect(text(document.querySelector(".frow"))).toContain("Checked");
  });

  it("C-FILE.row BLD-C139: after five failed asks in a row (a 4xx while a switch is off) the row offers Try again, which asks again", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let refuse = true;
    await mount([
      (m, u) =>
        m === "GET" && u === "/api/files/f9"
          ? refuse
            ? { status: 403, body: { error: { code: "forbidden", message: "" } } }
            : { body: checking("f9", "courier-call-log.pdf", "checked") }
          : undefined,
      ...base({ draft: draft({ files: [checking("f9", "courier-call-log.pdf")] }) }),
    ]);
    await railTo("Proof");
    expect(button("Try again")).toBeUndefined();
    for (const wait of [2000, 4000, 8000, 16000, 30000]) {
      await act(async () => vi.advanceTimersByTime(wait + 50));
      await settle();
    }
    expect(calls.filter((c) => c.url === "/api/files/f9")).toHaveLength(5);
    expect(text(document.querySelector(".frow"))).toContain("Checking for personal details");
    expect(button("Try again")).toBeTruthy();
    await act(async () => vi.advanceTimersByTime(60_000));
    await settle();
    expect(calls.filter((c) => c.url === "/api/files/f9")).toHaveLength(5);
    refuse = false;
    await click(button("Try again"));
    await act(async () => vi.advanceTimersByTime(2100));
    await settle();
    expect(text(document.querySelector(".frow"))).toContain("Checked");
    expect(button("Try again")).toBeUndefined();
  });

  it("C-FILE.uploader/3: several links go in one by one; one that fails stays in the box, and trying again never adds one twice", async () => {
    let failB = true;
    await mount([
      (m, u, b) => {
        if (m !== "POST" || u !== "/api/links") return undefined;
        const url = (b as { url: string }).url;
        if (url.endsWith("/b") && failB) {
          failB = false;
          return { status: 502, body: {} };
        }
        return {
          status: 201,
          body: {
            id: url.endsWith("/a") ? "la" : "lb",
            kind: "link",
            name: url,
            url,
            type: "link",
            state: "ok",
            link_scope: "internal",
            added_by: KAVYA,
            added_at: "",
          },
        };
      },
      ...base(),
    ]);
    await railTo("Proof");
    const input = document.querySelector<HTMLInputElement>('input[inputmode="url"]')!;
    const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    await act(async () => {
      setValue.call(input, "intranet.kfintech.example/a, intranet.kfintech.example/b");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await click(button("Add a link"));
    expect(button("Remove https://intranet.kfintech.example/a")).toBeTruthy();
    expect(input.value).toBe("intranet.kfintech.example/b");
    expect(document.body.textContent).toContain("Something went wrong. Try again.");
    await click(button("Add a link"));
    expect(input.value).toBe("");
    const posted = calls.filter((c) => c.url === "/api/links").map((c) => (c.body as { url: string }).url);
    expect(posted).toEqual([
      "https://intranet.kfintech.example/a",
      "https://intranet.kfintech.example/b",
      "https://intranet.kfintech.example/b",
    ]);
    expect(document.querySelectorAll(".frow")).toHaveLength(2);
  });
});

describe("S-05 screen: the fix and who would help (BLD-C134, S-05.fix)", () => {
  it("S-05.fix V-FIELDS.checkit/8: the sheet counts what is ready, asks for how, and Add my fix shows the part as the server words it", async () => {
    await mount([
      (m, u) =>
        m === "PUT" && u.endsWith("/fix")
          ? {
              body: {
                ready_count: 5,
                included: true,
                ready_of: 5,
                readiness: "5 of 5 ready for the review desk",
                next: null,
                part: {
                  rail: "Added",
                  line: "Included, 5 of 5 ready",
                  fix_line: "Send the reason in plain words in the SMS, with a link to what to do next.",
                  size_line: "70 to 150 hours a month, about ₹25,000 a month saved, solved elsewhere: partly",
                },
              },
            }
          : undefined,
      ...base(),
    ]);
    await railTo("Your fix");
    await click(button("Add your fix"));
    const dialog = document.querySelector('[role="dialog"]')!;
    expect(text(dialog.querySelector("h2"))).toBe("Your fix");
    expect(text(dialog)).toContain("0 of 5 ready for the review desk");
    expect(text(dialog)).toContain("Most useful next: how you’d solve it.");
    await click(button("Add my fix"));
    expect(text(dialog)).toContain("Say how you’d solve it, or close this to send without a fix.");
    const how = dialog.querySelector("textarea")!;
    const setValue = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!;
    await act(async () => {
      setValue.call(how, "Send the reason in plain words in the SMS, with a link to what to do next.");
      how.dispatchEvent(new Event("input", { bubbles: true }));
    });
    expect(text(dialog)).toContain("1 of 5 ready for the review desk");
    expect(text(dialog)).toContain("Most useful next: a rough size. A range is fine.");
    await click(button("Add my fix"));
    expect(calls.find((c) => c.method === "PUT")?.body).toMatchObject({ included: true });
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.body.textContent).toContain("Included, 5 of 5 ready");
    expect(document.body.textContent).toContain(
      "70 to 150 hours a month, about ₹25,000 a month saved, solved elsewhere: partly",
    );
    expect(button("Change your fix")).toBeTruthy();
    expect(button("Remove your fix")).toBeTruthy();
    expect(button(/Your fix Added$/)).toBeTruthy();
    expect(button("Next")).toBeTruthy();
  });

  it("S-05.fix: the cross keeps a started fix (included false); the part offers Carry on with your fix", async () => {
    await mount([
      (m, u) =>
        m === "PUT" && u.endsWith("/fix")
          ? { body: { part: { rail: "Optional", line: "", action: "" } } }
          : undefined,
      ...base(),
    ]);
    await railTo("Your fix");
    await click(button("Add your fix"));
    const how = document.querySelector<HTMLTextAreaElement>('[role="dialog"] textarea')!;
    const setValue = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!;
    await act(async () => {
      setValue.call(how, "Plain words in the SMS.");
      how.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await click(button("Close, and keep what you wrote"));
    expect(calls.find((c) => c.method === "PUT")?.body).toMatchObject({
      included: false,
      how: "Plain words in the SMS.",
    });
    expect(document.body.textContent).toContain("You started a fix. It isn’t included yet.");
    expect(button("Carry on with your fix")).toBeTruthy();
    expect(button("Skip for now")).toBeTruthy();
  });

  it("S-05.parts/6: picks are saved at once and the rail reads Added", async () => {
    await mount([
      (m, u) =>
        m === "PUT" && u.endsWith("/helpers")
          ? { body: { picks: [], text: null, line: "", part: { rail: "Added" } } }
          : undefined,
      ...base(),
    ]);
    await railTo("Who would help");
    expect(document.body.textContent).toContain(
      "Optional. It shows on Find your crew as “They’re looking for”, so the right colleagues can team up with you.",
    );
    await click(button("Someone at a branch"));
    expect(calls.find((c) => c.url.endsWith("/helpers"))?.body).toEqual({ picks: ["Someone at a branch"] });
    expect(button(/Who would help Added$/)).toBeTruthy();
    expect(button("Next")).toBeTruthy();
  });
});

describe("S-05 screen: who would help, saved in order (BLD-C135)", () => {
  it("S-05.parts/6 V-FIELDS.checkit/10: own words wait for a pause, and a pick in the meantime is never undone by them", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    await mount([
      (m, u) =>
        m === "PUT" && u.endsWith("/helpers")
          ? { body: { picks: [], text: null, line: "", part: { rail: "Added" } } }
          : undefined,
      ...base(),
    ]);
    await railTo("Who would help");
    const input = document.querySelector<HTMLInputElement>(".ck-helpers input.fld")!;
    const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    await act(async () => {
      setValue.call(input, "someone who takes these calls");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    expect(text(document.querySelector(".ck-helpers .help"))).toBe("29 of 140");
    await click(button("Someone at a branch"));
    await act(async () => vi.advanceTimersByTime(800));
    await settle();
    const puts = calls.filter((c) => c.url.endsWith("/helpers")).map((c) => c.body);
    expect(puts).toEqual([{ picks: ["Someone at a branch"], text: "someone who takes these calls" }]);
  });
});

describe("S-05 screen: send it (BLD-C135, L-SUBMIT)", () => {
  it("J-RECOVER/12 V-FIELDS.checkit/3–4: Submit before confirming: the message with Go to the sorting, nothing sent; the sorting card says what to do", async () => {
    await mount(base());
    await railTo("Send it");
    expect(h1()).toBe("Ready to send?");
    expect(document.body.textContent).toContain(
      "One last look. You can still change it until the review desk opens it.",
    );
    expect(document.body.textContent).toContain(sendView().declaration.text);
    for (const n of [
      "Change title",
      "Change sorting",
      "Change similar ideas",
      "Change proof",
      "Change your fix",
      "Change who would help",
    ]) {
      expect(button(n)).toBeTruthy();
    }
    await click(button("Submit"));
    expect(document.body.textContent).toContain("Confirm the sorting first, or change any of it.");
    expect(calls.some((c) => c.url.endsWith("/submit"))).toBe(false);
    await click(button("Go to the sorting"));
    expect(h1()).toBe("Is it sorted right?");
    expect(document.body.textContent).toContain("Confirm these, or change any of them, before you send.");
  });

  it("J-SHARE/11 L-SUBMIT.send: Submit sends the declaration's version with an idempotency key and hands over to S-06", async () => {
    await mount([
      (m, u) =>
        m === "POST" && u.endsWith("/submit")
          ? {
              status: 201,
              body: {
                idea_id: "IDEA-2026-001481",
                ref: "IDEA-2026-001481",
                next: { to: "/ideas/IDEA-2026-001481?from=share", replace: true, state: "just_shared" },
              },
            }
          : undefined,
      ...base({ sorting: sorting(true) }),
    ]);
    await railTo("Send it");
    // J-SHARE/11 finds Submit by name, as a substring: exactly one button may match it.
    expect(buttons().filter((b) => /submit/i.test(nameOf(b)))).toHaveLength(1);
    await click(button("Submit"));
    const sent = calls.find((c) => c.url.endsWith("/submit"))!;
    expect(sent.body).toEqual({ declaration_version: "2026-11-17" });
    expect(sent.headers["Idempotency-Key"]).toMatch(/^s05:/);
    expect(replace).toHaveBeenCalledWith("/ideas/IDEA-2026-001481?from=share");
  });

  it("S-06.rules/6 BLD-C084 J-SHARE/11: after a send, Check it replaces to the server's first-arrival link, or builds the same one when the answer has none", async () => {
    await mount([
      (m, u) =>
        m === "POST" && u.endsWith("/submit")
          ? { status: 201, body: { idea_id: "IDEA-2026-001484", ref: "IDEA-2026-001484" } }
          : undefined,
      ...base({ sorting: sorting(true) }),
    ]);
    await railTo("Send it");
    await click(button("Submit"));
    expect(replace).toHaveBeenCalledTimes(1);
    expect(replace).toHaveBeenCalledWith("/ideas/IDEA-2026-001484?from=share");
  });

  it("J-RECOVER/13 V-FIELDS.checkit/13: a failed send says the draft is safe, with Try again, and the retry reuses the key", async () => {
    await mount([
      (m, u) =>
        m === "POST" && u.endsWith("/submit")
          ? {
              status: 502,
              body: { error: { code: "unavailable", message: "Something went wrong. Try again." } },
            }
          : undefined,
      ...base({ sorting: sorting(true) }),
    ]);
    await railTo("Send it");
    await click(button("Submit"));
    expect(document.body.textContent).toContain(
      "Couldn’t send. Your draft is safe. Check your connection, then try again.",
    );
    await click(button("Try again"));
    const keys = calls.filter((c) => c.url.endsWith("/submit")).map((c) => c.headers["Idempotency-Key"]);
    expect(keys).toHaveLength(2);
    expect(keys[0]).toBe(keys[1]);
    expect(replace).not.toHaveBeenCalled();
  });

  it("J-RECOVER/14 V-FIELDS.checkit/14: offline, it says it will send when back online; Submit waits, then sends", async () => {
    await mount([
      (m, u) =>
        m === "POST" && u.endsWith("/submit")
          ? {
              status: 201,
              body: {
                idea_id: "IDEA-2026-001482",
                ref: "IDEA-2026-001482",
                next: { to: "/ideas/IDEA-2026-001482?from=share" },
              },
            }
          : undefined,
      ...base({ sorting: sorting(true) }),
    ]);
    await railTo("Send it");
    const online = vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
    await act(async () => window.dispatchEvent(new Event("offline")));
    expect(document.body.textContent).toContain(
      "You’re offline. Your draft is saved on this device. Submit now and it sends when you’re back online.",
    );
    expect(text(document.querySelector('.tbar [role="status"]'))).toBe("Unsaved, you’re offline");
    await click(button("Submit"));
    expect(calls.some((c) => c.url.endsWith("/submit"))).toBe(false);
    online.mockReturnValue(true);
    await act(async () => window.dispatchEvent(new Event("online")));
    await settle();
    expect(calls.some((c) => c.url.endsWith("/submit"))).toBe(true);
    expect(replace).toHaveBeenCalledWith("/ideas/IDEA-2026-001482?from=share");
  });

  it("L-SUBMIT.pre: a refusal from the server says its own words under Submit (file_blocked)", async () => {
    await mount([
      (m, u) =>
        m === "POST" && u.endsWith("/submit")
          ? {
              status: 409,
              body: {
                error: { code: "file_blocked", message: "A file still needs its personal details hidden." },
              },
            }
          : undefined,
      ...base({ sorting: sorting(true) }),
    ]);
    await railTo("Send it");
    await click(button("Submit"));
    expect(document.body.textContent).toContain("A file still needs its personal details hidden.");
    expect(replace).not.toHaveBeenCalled();
  });
});

// --- Review round on 4ec8201d (BLD-C138, C139) ---------------------------------------------------------------

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

describe("S-05 review fixes: the rail and the phone (S-05.layout, S-05.phone)", () => {
  it("S-05.layout WCAG 1.1.1: a done part's tick says , done to a screen reader; a part that needs attention keeps its number", async () => {
    await mount(base());
    await click(button("Looks right"));
    const words = button(/^Your words, done Title, what happens, how often$/)!;
    expect(words).toBeTruthy();
    expect(words.querySelector('.ck-rn[aria-hidden="true"] svg')).toBeTruthy();
    await railTo("Send it");
    await click(button("Submit"));
    await click(button("Go to the sorting"));
    await railTo("Proof");
    const sortingButton = button(/^2 Sorting Suggested, not confirmed yet$/)!;
    expect(sortingButton).toBeTruthy();
    expect(text(sortingButton.querySelector('.ck-rn[aria-hidden="true"]'))).toBe("!");
  });

  it("S-05.phone PhoneReview.md: the three counts link to their parts: 1 detail hidden, 4 sortings, 2 similar ideas", async () => {
    asPhone();
    await mount(base());
    const links = Array.from(document.querySelectorAll<HTMLAnchorElement>(".ck-stats a"));
    expect(links.map((a) => [text(a), a.getAttribute("href")])).toEqual([
      ["1 detail hidden", "#pr-hidden"],
      ["4 sortings", "#pr-sort-h"],
      ["2 similar ideas", "#pr-sim-h"],
    ]);
    expect(document.getElementById("pr-hidden")?.textContent).toContain("Folio ••••89");
    expect(text(document.getElementById("pr-sort-h"))).toBe("Is this sorted right?");
    expect(text(document.getElementById("pr-sim-h"))).toBe("Already raised?");
  });

  it("S-05.phone: a count of none is left out, so no link points at an empty part", async () => {
    asPhone();
    await mount(base({ draft: draft({ hidden: [] }), similar: [] }));
    expect(Array.from(document.querySelectorAll(".ck-stats a")).map(text)).toEqual(["4 sortings"]);
  });

  it("L-SORT.rules/4 J-RECOVER/12 on a phone: Change on a Send row and Go to the sorting take focus to that part's heading", async () => {
    asPhone();
    await mount(base());
    await click(button("Change sorting"));
    expect(document.activeElement).toBe(document.getElementById("pr-sort-h"));
    await click(button("Change similar ideas"));
    expect(document.activeElement).toBe(document.getElementById("pr-sim-h"));
    await click(button("Submit"));
    expect(document.body.textContent).toContain("Confirm the sorting first, or change any of it.");
    (document.activeElement as HTMLElement).blur();
    await click(button("Go to the sorting"));
    expect(document.activeElement).toBe(document.getElementById("pr-sort-h"));
    expect(document.body.textContent).toContain("Confirm these, or change any of them, before you send.");
  });
});

describe("S-05 review fixes: hidden details (C-HIDDEN.list)", () => {
  function shownDetail(id: string, masked: string) {
    return { id, kind: "phone", masked, state: "shown", reason: "made_up_example" };
  }

  it("C-HIDDEN.list/3 WCAG 2.4.3: after Show it confirms, focus is on the row's Hide it; after Hide it, on its Show it", async () => {
    await mount([
      (m, u) =>
        m === "POST" && u.endsWith("/hidden/h1/show")
          ? {
              body: {
                id: "h1",
                kind: "folio",
                masked: "Folio ••••89",
                state: "shown",
                reason: "internal_reference",
              },
            }
          : undefined,
      (m, u) =>
        m === "POST" && u.endsWith("/hidden/h1/hide")
          ? { body: { id: "h1", kind: "folio", masked: "Folio ••••89", state: "hidden" } }
          : undefined,
      ...base(),
    ]);
    await click(button("Show it"));
    await click(Array.from(document.querySelectorAll('[role="radio"]'))[1]);
    await click(
      buttons()
        .filter((b) => nameOf(b) === "Show it")
        .pop(),
    );
    expect(nameOf(document.activeElement!)).toBe("Hide it");
    await click(button("Hide it"));
    expect(calls.some((c) => c.url.endsWith("/hidden/h1/hide"))).toBe(true);
    expect(nameOf(document.activeElement!)).toBe("Show it");
  });

  it("C-HIDDEN.list: while one detail is being shown, Hide it on another waits too", async () => {
    let release: (v: unknown) => void = () => undefined;
    const pending = new Promise((r) => (release = r));
    const routes = [
      (m: string, u: string) =>
        m === "POST" && u.endsWith("/hidden/h1/show")
          ? {
              body: {
                id: "h1",
                kind: "folio",
                masked: "Folio ••••89",
                state: "shown",
                reason: "internal_reference",
              },
            }
          : undefined,
      ...base({
        draft: draft({
          hidden: [
            { id: "h1", kind: "folio", masked: "Folio ••••89", state: "hidden" },
            shownDetail("h2", "Phone ••••12"),
          ],
        }),
      }),
    ];
    await mount(routes);
    const real = globalThis.fetch as unknown as (u: string, i?: RequestInit) => Promise<unknown>;
    vi.stubGlobal(
      "fetch",
      vi.fn(async (u: string, i?: RequestInit) => {
        if (u.endsWith("/hidden/h1/show")) await pending;
        return real(u, i);
      }),
    );
    await click(button("Show it"));
    await click(Array.from(document.querySelectorAll('[role="radio"]'))[1]);
    const confirm = buttons()
      .filter((b) => nameOf(b) === "Show it")
      .pop()!;
    await act(async () => confirm.click());
    expect(button("Hide it")!.getAttribute("aria-disabled")).toBe("true");
    await act(async () => release(null));
    await settle();
    expect(button("Hide it")!.getAttribute("aria-disabled")).toBeNull();
  });
});

describe("S-05 review fixes: send it (L-SUBMIT.send, V-FIELDS.checkit)", () => {
  const submitted = {
    status: 201,
    body: {
      idea_id: "IDEA-2026-001483",
      ref: "IDEA-2026-001483",
      next: { to: "/ideas/IDEA-2026-001483?from=share" },
    },
  };
  const refuse =
    (status: number, error: Record<string, string>): Route =>
    (m, u) =>
      m === "POST" && u.endsWith("/submit") ? { status, body: { error } } : undefined;

  it("V-FIELDS.checkit/14 J-RECOVER/14: a Submit pressed offline is kept on this device (id and key, no words) and sent on the next visit, then cleared", async () => {
    await mount([
      (m, u) => (m === "POST" && u.endsWith("/submit") ? submitted : undefined),
      ...base({ sorting: sorting(true) }),
    ]);
    await railTo("Send it");
    const online = vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
    await act(async () => window.dispatchEvent(new Event("offline")));
    await click(button("Submit"));
    const kept = JSON.parse(localStorage.getItem(`1pc.s05.queued.${DRAFT_ID}`)!);
    expect(Object.keys(kept).sort()).toEqual(["draftId", "key"]);
    expect(kept.draftId).toBe(DRAFT_ID);
    expect(kept.key).toMatch(/^s05:/);
    expect(calls.some((c) => c.url.endsWith("/submit"))).toBe(false);
    // The tab closes; later, online again, Check it opens for the same draft.
    await act(async () => root.unmount());
    root = createRoot(host);
    online.mockReturnValue(true);
    await mount([
      (m, u) => (m === "POST" && u.endsWith("/submit") ? submitted : undefined),
      ...base({ sorting: sorting(true) }),
    ]);
    await settle();
    const sent = calls.filter((c) => c.url.endsWith("/submit"));
    expect(sent).toHaveLength(1);
    expect(sent[0]!.headers["Idempotency-Key"]).toBe(kept.key);
    expect(replace).toHaveBeenCalledWith("/ideas/IDEA-2026-001483?from=share");
    expect(localStorage.getItem(`1pc.s05.queued.${DRAFT_ID}`)).toBeNull();
    online.mockRestore();
  });

  it("V-FIELDS.checkit/14: storage that cannot be used never breaks Submit offline", async () => {
    vi.stubGlobal("localStorage", {
      ...memoryStorage(),
      setItem: () => {
        throw new Error("QuotaExceededError");
      },
    });
    await mount(base({ sorting: sorting(true) }));
    await railTo("Send it");
    const online = vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
    await act(async () => window.dispatchEvent(new Event("offline")));
    await click(button("Submit"));
    expect(document.body.textContent).toContain(
      "You’re offline. Your draft is saved on this device. Submit now and it sends when you’re back online.",
    );
    online.mockRestore();
  });

  it("J-RECOVER/13 WCAG 2.4.3: a failed send keeps the one button, now Try again, with focus on it and the message announced", async () => {
    await mount([refuse(502, { code: "unavailable", message: "" }), ...base({ sorting: sorting(true) })]);
    await railTo("Send it");
    const submitButton = button("Submit")!;
    submitButton.focus();
    await click(submitButton);
    expect(submitButton.isConnected).toBe(true);
    expect(nameOf(submitButton)).toBe("Try again");
    expect(document.activeElement).toBe(submitButton);
    expect(text(document.querySelector('.ck-send [role="alert"]'))).toBe(
      "Couldn’t send. Your draft is safe. Check your connection, then try again.",
    );
  });

  it("S-05.rules/5 L-SUBMIT.pre: file_blocked shows under that file's row and takes the person to Proof", async () => {
    const f: FileItem = {
      id: "f3",
      kind: "file",
      name: "branch-call-log.pdf",
      type: "application/pdf",
      size: 2048,
      state: "checking",
      added_by: KAVYA,
      added_at: "",
    };
    const line = "This file is still being checked. Wait a moment, or remove it.";
    await mount([
      refuse(422, { code: "file_blocked", message: line, field: "f3" }),
      (m, u) => (m === "GET" && u === "/api/files/f3" ? { body: f } : undefined),
      ...base({ draft: draft({ files: [f] }), sorting: sorting(true) }),
    ]);
    await railTo("Send it");
    await click(button("Submit"));
    expect(h1()).toBe("Anything that shows it?");
    expect(text(document.querySelector(".frow"))).toContain(line);
  });

  it("S-05.rules/5 V-FIELDS.checkit/2: not_ready for what happens goes to Your words and says it under that line", async () => {
    await mount([
      refuse(422, {
        code: "not_ready",
        message: "Say what happens, in a sentence or two.",
        field: "summary",
      }),
      ...base({ sorting: sorting(true) }),
    ]);
    await railTo("Send it");
    await click(button("Submit"));
    expect(h1()).toBe("Is this how you’d put it?");
    const lines = Array.from(document.querySelectorAll(".ck-w"));
    expect(text(lines[1])).toContain("Say what happens, in a sentence or two.");
    expect(text(lines[0])).not.toContain("Say what happens");
  });

  it("A-API not_a_draft: an idea already sent gets its own line and Submit stays unavailable, with no Try again", async () => {
    await mount([
      refuse(409, { code: "not_a_draft", message: "This idea has been sent." }),
      ...base({ sorting: sorting(true) }),
    ]);
    await railTo("Send it");
    await click(button("Submit"));
    expect(text(document.querySelector('.ck-send [role="alert"]'))).toBe("This idea has been sent.");
    expect(document.body.textContent).not.toContain("Check your connection");
    expect(button("Try again")).toBeUndefined();
    expect(button("Submit")!.getAttribute("aria-disabled")).toBe("true");
  });

  it("L-SORT.rules/2: sorting_unconfirmed shows the server's own line (confirmed, but a field left empty)", async () => {
    const line = "Confirm these, or change any of them, before you send.";
    await mount([
      refuse(422, { code: "sorting_unconfirmed", message: line, field: "sorting" }),
      ...base({ sorting: sorting(true) }),
    ]);
    await railTo("Send it");
    await click(button("Submit"));
    expect(text(document.querySelector('.ck-send [role="alert"]'))).toContain(line);
    expect(button("Go to the sorting")).toBeTruthy();
  });

  it("S-05.parts/6: words typed for Who would help that wait for a pause are saved before Submit sends", async () => {
    await mount([
      (m, u) => (m === "POST" && u.endsWith("/submit") ? submitted : undefined),
      (m, u) =>
        m === "PUT" && u.endsWith("/helpers")
          ? { body: { picks: [], text: "x", line: "", part: { rail: "Added" } } }
          : undefined,
      ...base({ sorting: sorting(true) }),
    ]);
    await railTo("Who would help");
    const input = document.querySelector<HTMLInputElement>(".ck-helpers input.fld")!;
    const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    await act(async () => {
      setValue.call(input, "someone who takes these calls");
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await railTo("Send it");
    await click(button("Submit"));
    const order = calls.map((c) => `${c.method} ${c.url.split("/").pop()}`);
    const put = order.indexOf("PUT helpers");
    expect(put).toBeGreaterThan(-1);
    expect(put).toBeLessThan(order.indexOf("POST submit"));
    expect(calls.find((c) => c.url.endsWith("/helpers"))?.body).toEqual({
      picks: [],
      text: "someone who takes these calls",
    });
  });
});

describe("S-05 review fixes: the fix sheet (S-05.fix)", () => {
  async function typeHow(value: string) {
    const how = document.querySelector<HTMLTextAreaElement>('[role="dialog"] textarea')!;
    const setValue = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!;
    await act(async () => {
      setValue.call(how, value);
      how.dispatchEvent(new Event("input", { bubbles: true }));
    });
  }

  it("S-05.fix V-FIELDS.checkit/9: the cross saves before closing; a figure it cannot read keeps the sheet open with the line under the figure", async () => {
    let unclear = true;
    await mount([
      (m, u) => {
        if (m !== "PUT" || !u.endsWith("/fix")) return undefined;
        if (unclear) {
          unclear = false;
          return {
            status: 422,
            body: {
              error: {
                code: "worth_unclear",
                message: "Write a rough figure or a range, like 70 to 150.",
                field: "worth",
              },
            },
          };
        }
        return { body: { part: { rail: "Optional", line: "", action: "" } } };
      },
      ...base(),
    ]);
    await railTo("Your fix");
    await click(button("Add your fix"));
    await typeHow("Plain words in the SMS.");
    await click(button("Time saved"));
    const hours = document.querySelector<HTMLInputElement>('[role="dialog"] input[inputmode="decimal"]')!;
    const setValue = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
    await act(async () => {
      setValue.call(hours, "lots");
      hours.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await click(button("Close, and keep what you wrote"));
    const dialog = document.querySelector('[role="dialog"]');
    expect(dialog).toBeTruthy();
    expect(text(dialog)).toContain("Write a rough figure or a range, like 70 to 150.");
    expect(hours.getAttribute("aria-invalid")).toBe("true");
    await click(button("Close, and keep what you wrote"));
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(document.body.textContent).toContain("You started a fix. It isn’t included yet.");
  });

  it("S-05.fix: Escape is Cancel and never saves; the page behind the open sheet is inert", async () => {
    await mount(base());
    await railTo("Your fix");
    await click(button("Add your fix"));
    expect(host.hasAttribute("inert")).toBe(true);
    await typeHow("Plain words in the SMS.");
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]')!;
    await act(async () =>
      dialog.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })),
    );
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(calls.some((c) => c.method === "PUT" && c.url.endsWith("/fix"))).toBe(false);
    expect(host.hasAttribute("inert")).toBe(false);
    expect(button("Add your fix")).toBeTruthy();
  });
});

describe("S-05 verification should-fixes (BLD-C131, C134)", () => {
  it("C-SIMGRID.grid/4 BLD-C131: Keep mine separate that the server does not record leaves the grid unfolded with the drawn line under it", async () => {
    await mount([
      (m, u) =>
        m === "POST" && u.endsWith("/similar/keep-separate")
          ? { status: 503, body: { error: { code: "not_available", message: "Paused for now." } } }
          : undefined,
      ...base(),
    ]);
    await railTo("Similar ideas");
    await act(async () =>
      (sheetHook.options!.onSent as (s: unknown) => void)({
        kind: "teamup",
        id: "tu-1",
        ideaId: MATCH_RAVI.idea.id,
        note: "I take these calls at the Hyderabad branch too.",
        brought: [],
        after: null,
      }),
    );
    await settle();
    expect(calls.find((c) => c.url.endsWith("/similar/keep-separate"))?.body).toEqual({ on: true });
    expect(document.querySelector(".simgrid")).toBeTruthy();
    expect(document.body.textContent).not.toContain("Kept separate.");
    expect(document.body.textContent).toContain(CHECK_COPY.failed);
  });

  it("S-05.rules/5 BLD-C134: not_ready for how often shows the server's words under Submit, with no Try again", async () => {
    const line = "Say roughly how often it happens.";
    await mount([
      (m, u) =>
        m === "POST" && u.endsWith("/submit")
          ? { status: 422, body: { error: { code: "not_ready", message: line, field: "often" } } }
          : undefined,
      ...base({ sorting: sorting(true) }),
    ]);
    await railTo("Send it");
    await click(button("Submit"));
    expect(text(document.querySelector('.ck-send [role="alert"]'))).toBe(line);
    expect(button("Try again")).toBeUndefined();
    expect(button("Submit")).toBeTruthy();
  });
});

// --- J-SIMILAR/6a: a draft merged into another idea (BLD-C155); ticks after a reload (BLD-C156) ------------------

const REF = "IDEA-2026-001412";
const ACCEPTED_LINE = `Ravi accepted. Yours is now part of ${REF}, with credit to you. Nothing else to send.`;
const ACCEPTED = {
  id: "m1",
  other_idea_id: REF,
  state: "accepted",
  lead: RAVI,
  after: {
    state: "accepted",
    label: `Merged into ${REF}`,
    line: ACCEPTED_LINE,
    action: { label: "See the merged idea", to: `/ideas/${REF}` },
    can_submit: false,
  },
};

function mergedSend(): SendViewResponse {
  const v = sendView();
  return {
    ...v,
    rows: v.rows.map((r) =>
      r.key === "sorting"
        ? {
            ...r,
            value: "Investor service, affecting investors and KFin teams, saves time, saves cost",
            ok: true,
          }
        : r.key === "similar"
          ? { ...r, value: `Merged into ${REF}` }
          : r,
    ),
  };
}

const writes = () => calls.filter((c) => c.method !== "GET");

describe("S-05 J-SIMILAR/6a L-MERGE.request/5: a merged draft stays on Check it, read-only (BLD-C155)", () => {
  it("desktop: the rail reads Merged into IDEA-…, the bar the accepted line with See the merged idea; nothing to send or change", async () => {
    await mount(
      base({ draft: draft({ merged_into: REF, ready: false }), merge: ACCEPTED, send: mergedSend() }),
    );
    const rail = Array.from(document.querySelectorAll(".ck-rail button")).map(nameOf);
    expect(rail).toEqual([
      "1 Your words Title, what happens, how often",
      "2 Sorting Suggested, not confirmed yet",
      `Similar ideas, done Merged into ${REF}`,
      "4 Proof Optional",
      "5 Your fix Optional",
      "6 Who would help Optional",
    ]); // no Send it: nothing to send
    expect(
      Array.from(document.querySelectorAll(".ck-rs")).filter((e) => text(e) === `Merged into ${REF}`),
    ).toHaveLength(1);
    // Review.md, merge=Ravi accepted: announced as status, with the line; the action is the link.
    const bar = document.querySelector('.ck-mlive[role="status"]')!;
    expect(text(bar.querySelector("p"))).toBe(ACCEPTED_LINE);
    const see = Array.from(bar.querySelectorAll("a")).find((a) => text(a) === "See the merged idea")!;
    expect(see.getAttribute("href")).toBe(`/ideas/${REF}`);
    // Part 1 as it was, with nothing to change.
    expect(h1()).toBe("Is this how you’d put it?");
    expect(text(document.querySelector("h3"))).toBe("Investors call to ask why a redemption was rejected");
    expect(document.body.textContent).toContain("Folio ••••89");
    for (const gone of [
      "Looks right",
      "Change the title",
      "Change what happens",
      "Change how often",
      "Show it",
    ])
      expect(button(gone)).toBeUndefined();
    expect(Array.from(document.querySelectorAll("a")).some((a) => text(a) === "Back to your words")).toBe(
      false,
    );
    expect(buttons().filter((b) => /submit/i.test(nameOf(b)))).toHaveLength(0);

    // The other parts read, and moving between them writes nothing.
    await click(button("Next"));
    expect(h1()).toBe("Is it sorted right?");
    expect(document.body.textContent).toContain(
      "Investor service, affecting investors and KFin teams, saves time, saves cost",
    );
    expect(document.querySelectorAll(".ck-stage .chip")).toHaveLength(0);
    expect(button("Confirm sorting")).toBeUndefined();
    await railTo("Similar ideas");
    expect(h1()).toBe("Has someone raised this already?");
    expect(buttons().filter((b) => nameOf(b) === "Team up" || /^Team up on /.test(nameOf(b)))).toHaveLength(
      0,
    );
    expect(button(`Preview ${MATCH_RAVI.idea.title}`)).toBeTruthy();
    expect(Array.from(document.querySelectorAll(".ck-crew")).map(text)).toEqual(["On the crew"]);
    expect(document.body.textContent).not.toContain(CHECK_COPY.similar.carryOn);
    await railTo("Your fix");
    expect(text(document.querySelector(".ck-stage .ck-v"))).toBe("None added");
    expect(button("Add my fix")).toBeUndefined();
    await railTo("Who would help");
    expect(text(document.querySelector(".ck-stage .ck-v"))).toBe("Not said");
    expect(document.querySelectorAll(".ck-stage .chip")).toHaveLength(0);
    expect(writes()).toEqual([]);
  });

  it("kept separate before the merge: the grid shows as it is, with no Show them again and nothing that writes; Tell it is not a link", async () => {
    await mount(
      base({
        draft: draft({ merged_into: REF, kept_separate: true, step: "check:3" }),
        merge: ACCEPTED,
        send: mergedSend(),
      }),
    );
    expect(h1()).toBe("Has someone raised this already?");
    expect(button("Show them again")).toBeUndefined();
    expect(document.body.textContent).not.toContain(CHECK_COPY.similar.kept);
    expect(document.querySelectorAll(".simgrid .sgt")).toHaveLength(3); // yours, then the two matches
    const controls = buttons().map(nameOf);
    expect(controls.filter((n) => /^(Team up|Withdraw|Show them again)/.test(n))).toEqual([]);
    // The task bar: "Tell it, done" in words only, since Tell it would bring the person straight back here.
    const tell = Array.from(document.querySelectorAll(".tbar li")).find((li) => /Tell it/.test(text(li)))!;
    expect(text(tell)).toBe("Tell it, done");
    expect(tell.querySelector("a")).toBeNull();
    expect(writes()).toEqual([]);
  });

  it("a saved Send it opens part 1, and a send kept on this device is dropped, never sent", async () => {
    localStorage.setItem(`1pc.s05.queued.${DRAFT_ID}`, JSON.stringify({ draftId: DRAFT_ID, key: "s05:k" }));
    await mount(
      base({ draft: draft({ merged_into: REF, step: "send" }), merge: ACCEPTED, send: mergedSend() }),
    );
    expect(h1()).toBe("Is this how you’d put it?");
    expect(localStorage.getItem(`1pc.s05.queued.${DRAFT_ID}`)).toBeNull();
    expect(writes()).toEqual([]);
  });

  it("when the merge request cannot be read, the draft's own merged_into gives the drawn rail and See the merged idea", async () => {
    await mount([
      (m, u) => (m === "GET" && u.endsWith("/merge-request") ? { status: 502, body: {} } : undefined),
      ...base({ draft: draft({ merged_into: REF }), send: mergedSend() }),
    ]);
    expect(button(new RegExp(`Similar ideas, done Merged into ${REF}$`))).toBeTruthy();
    const bar = document.querySelector('.ck-mlive[role="status"]')!;
    expect(bar.querySelector("p")).toBeNull(); // no lead's name to make the line from: only the link
    expect(Array.from(bar.querySelectorAll("a")).map((a) => [text(a), a.getAttribute("href")])).toEqual([
      ["See the merged idea", `/ideas/${REF}`],
    ]);
    expect(button("Submit")).toBeUndefined();
  });

  it("model: an accepted request without lane F's words reads as drawn, from the lead's first name", () => {
    const v = model.mergeView({ state: "accepted", other_idea_id: REF, lead: RAVI, after: null }, [])!;
    expect(v).toMatchObject({
      state: "accepted",
      rail: `Merged into ${REF}`,
      line: ACCEPTED_LINE,
      action: { label: "See the merged idea", to: `/ideas/${REF}` },
      canSubmit: false,
    });
    expect(model.mergedView(null, null)).toBeNull();
  });

  it("phone: the same parts to read, the bar with See the merged idea, and no declaration or Submit", async () => {
    asPhone();
    await mount(base({ draft: draft({ merged_into: REF }), merge: ACCEPTED, send: mergedSend() }));
    const bar = document.querySelector('.ck-mlive[role="status"]')!;
    expect(text(bar.querySelector("p"))).toBe(ACCEPTED_LINE);
    expect(Array.from(bar.querySelectorAll("a")).map(text)).toEqual(["See the merged idea"]);
    expect(document.querySelectorAll(".ck-part")).toHaveLength(6);
    expect(button("Submit")).toBeUndefined();
    expect(document.querySelector(".decl")).toBeNull();
    expect(button("Confirm sorting")).toBeUndefined();
    expect(Array.from(document.querySelectorAll("a")).some((a) => text(a) === "Back to your words")).toBe(
      false,
    );
    expect(writes()).toEqual([]);
  });
});

describe("S-05.layout J-SHARE/8–11: the rail's ticks come from what the server keeps (BLD-C156)", () => {
  it("after a reload at part 4, part 1 (Looks right) and part 3 (Similar ideas) are ticked; sorting only once confirmed", async () => {
    await mount(base({ draft: draft({ step: "check:4" }) }));
    expect(h1()).toBe("Anything that shows it?");
    const rail = Array.from(document.querySelectorAll(".ck-rail button")).map(nameOf);
    expect(rail.slice(0, 4)).toEqual([
      "Your words, done Title, what happens, how often",
      "2 Sorting Suggested, not confirmed yet",
      "Similar ideas, done 2 close ideas found",
      "4 Proof Optional",
    ]);
    expect(button(/^Your words, done/)!.querySelector('.ck-rn[aria-hidden="true"] svg')).toBeTruthy();
    expect(button(/^Similar ideas, done/)!.querySelector('.ck-rn[aria-hidden="true"] svg')).toBeTruthy();
  });

  it("Keep mine separate kept on the server ticks part 3 after a reload, wherever the person is", async () => {
    await mount(base({ draft: draft({ step: "check:2", kept_separate: true }), sorting: sorting(true) }));
    expect(h1()).toBe("Is it sorted right?");
    expect(button(/^Your words, done/)).toBeTruthy();
    expect(button(/^Similar ideas, done/)).toBeTruthy();
    expect(button(/^4 Proof/)).toBeTruthy();
  });

  it("a draft still at Tell it or part 1 shows no ticks", async () => {
    await mount(base({ draft: draft({ step: "tell" }) }));
    expect(Array.from(document.querySelectorAll(".ck-rail .ck-rb.done"))).toHaveLength(0);
  });
});

describe("S-05 words (F-COPY)", () => {
  it("never says duplicate, rejected, already solved, appeal, invalid or Garage to the sharer", () => {
    const all = JSON.stringify(CHECK_COPY, (_k, v) => (typeof v === "function" ? v("2", "Ravi") : v));
    expect(all).not.toMatch(/\b(duplicate|rejected|already solved|appeal|invalid|Garage)\b/i);
  });
});

describe("S-05.similar C-SIMGRID.tile L-TEAMUP.rules/1 J-SHARE/8: no Team up on an idea L-TEAMUP refuses (BLD-C187)", () => {
  const open: SimilarMatch = { ...MATCH_RAVI, can_team_up: true, team_up_why_not: null };
  const notNow: SimilarMatch = {
    ...MATCH_SUNITA,
    idea: { ...MATCH_SUNITA.idea, status: "not_now", title: "Branch calls about rejection codes" },
    can_team_up: false,
    team_up_why_not: "idea_closed",
  };

  it("model: an open idea offers Team up; not_now and every other closed state offer nothing; on the crew reads On the crew", () => {
    expect(model.tileAction(open, null)).toEqual({ kind: "team-up" });
    expect(CLOSED_STATUSES).toEqual(expect.arrayContaining(["not_now", "not_picked", "withdrawn", "merged"]));
    for (const status of CLOSED_STATUSES) {
      const closed: SimilarMatch = {
        ...MATCH_RAVI,
        idea: { ...MATCH_RAVI.idea, status },
        can_team_up: false,
        team_up_why_not: "idea_closed",
      };
      expect(model.tileAction(closed, null), status).toEqual({ kind: "none" });
    }
    expect(
      model.tileAction({ ...open, can_team_up: false, team_up_why_not: "already_on_crew" }, null),
    ).toEqual({
      kind: "on-crew",
    });
    // An older worker that sends no can_team_up: offered as before.
    expect(model.tileAction(MATCH_RAVI, null)).toEqual({ kind: "team-up" });
  });

  it("screen: the Not now tile keeps Preview and has no Team up, on the tile or in the preview; the open one keeps Team up", async () => {
    await mount(base({ similar: [open, notNow] }));
    await railTo("Similar ideas");
    const tiles = Array.from(document.querySelectorAll(".simgrid > li"));
    expect(tiles).toHaveLength(3);
    expect(button(`Team up on ${open.idea.title}`)).toBeTruthy();
    expect(button(`Team up on ${notNow.idea.title}`)).toBeUndefined();
    expect(Array.from(tiles[2]!.querySelectorAll("button")).map(nameOf)).toEqual([
      `Preview ${notNow.idea.title}`,
    ]);
    expect(text(tiles[2])).toContain("Not now");
    expect(text(tiles[2])).not.toContain("On the crew");
    await click(button(`Preview ${notNow.idea.title}`));
    const dialog = document.querySelector('[role="dialog"]')!;
    expect(dialog).toBeTruthy();
    expect(Array.from(dialog.querySelectorAll("button")).map(nameOf)).not.toContain(
      `Team up on ${notNow.idea.title}`,
    );
    expect(text(dialog)).not.toMatch(/Team up\b/);
  });
});

describe("S-05.parts/1 J-RECOVER/7-11: a line of your words left empty reads Not given. beside its pen (BLD-C188)", () => {
  const parts = draft().parts;

  it("an empty How often reads Not given. under its label and keeps Change how often", async () => {
    await mount(base({ draft: draft({ parts: { ...parts, often: { state: "empty", value: "" } } }) }));
    const line = Array.from(document.querySelectorAll(".ck-w")).find(
      (w) => text(w.querySelector(".lbl")) === "How often",
    )!;
    expect(text(line.querySelector(".ck-v"))).toBe("Not given.");
    expect(line.querySelector(".ck-v")!.classList.contains("ck-empty")).toBe(true);
    expect(button("Change how often")).toBeTruthy();
    expect(text(document.querySelector("h3"))).toBe("Investors call to ask why a redemption was rejected");
  });

  it("every line that can be empty reads the same: the title, What happens (or only spaces) and How often", async () => {
    await mount(
      base({
        draft: draft({
          parts: {
            ...parts,
            title: { state: "empty", value: "" },
            summary: { state: "filled", value: "   " },
            often: { state: "empty", value: null },
          },
        }),
      }),
    );
    const empty = Array.from(document.querySelectorAll(".ck-words .ck-empty")).map(text);
    expect(empty).toEqual(["Not given.", "Not given.", "Not given."]);
    expect(document.querySelector(".ck-words h3")).toBeNull();
    for (const n of ["Change the title", "Change what happens", "Change how often"])
      expect(button(n)).toBeTruthy();
  });

  it("the phone reads the same line with its Change button", async () => {
    asPhone();
    await mount(base({ draft: draft({ parts: { ...parts, often: { state: "empty", value: "" } } }) }));
    const line = Array.from(document.querySelectorAll(".ck-w")).find(
      (w) => text(w.querySelector(".lbl")) === "How often",
    )!;
    expect(text(line.querySelector(".ck-v"))).toBe("Not given.");
    expect(button("Change how often")).toBeTruthy();
  });
});

describe("S-05.layout J-RECOVER/9-13: the rail's Proof step counts links as links, as Send it does (BLD-C190)", () => {
  const at = "2026-11-17T08:00:00Z";
  const file = (id: string, name: string): FileItem => ({
    id,
    kind: "file",
    name,
    type: "image/png",
    size: 84_000,
    state: "checked",
    added_by: KAVYA,
    added_at: at,
  });
  const link = (id: string, url: string): FileItem => ({
    id,
    kind: "link",
    name: url,
    type: "link",
    state: "checked",
    link_scope: "internal",
    url: `https://${url}`,
    added_by: KAVYA,
    added_at: at,
  });
  const SMS = file("f1", "rejection-sms-screenshot.png");
  const LOG = file("f2", "branch-call-log-nov.png");
  const CODES = link("l1", "intranet.kfintech.example/codes");
  const proofRail = () => nameOf(button(/^4 Proof/)!);

  it("the words: 1 file and 2 files as Review.md draws them; 1 link, 2 links and 1 file and 1 link as Send it words them", () => {
    expect(CHECK_COPY.proof.count(1, 0)).toBe("1 file");
    expect(CHECK_COPY.proof.count(2, 0)).toBe("2 files");
    expect(CHECK_COPY.proof.count(0, 1)).toBe("1 link");
    expect(CHECK_COPY.proof.count(0, 2)).toBe("2 links");
    expect(CHECK_COPY.proof.count(1, 1)).toBe("1 file and 1 link");
    expect(CHECK_COPY.proof.count(2, 3)).toBe("2 files and 3 links");
  });

  for (const [what, files, drawn] of [
    ["1 link", [CODES], "4 Proof 1 link"],
    ["1 file", [SMS], "4 Proof 1 file"],
    ["2 files", [SMS, LOG], "4 Proof 2 files"],
    ["1 file and 1 link", [SMS, CODES], "4 Proof 1 file and 1 link"],
  ] as const) {
    it(`the rail reads ${what}`, async () => {
      await mount(base({ draft: draft({ files }) }));
      expect(proofRail()).toBe(drawn);
    });
  }

  it("a link added on part 4 counts as a link on the rail", async () => {
    await mount([(m, u) => (m === "POST" && u === "/api/links" ? { body: CODES } : undefined), ...base()]);
    await railTo("Proof");
    expect(proofRail()).toBe("4 Proof Optional");
    const field = document.querySelector<HTMLInputElement>('input[inputmode="url"]')!;
    await act(async () => {
      const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
      set.call(field, "intranet.kfintech.example/codes");
      field.dispatchEvent(new Event("input", { bubbles: true }));
    });
    await click(button("Add a link"));
    expect(proofRail()).toBe("4 Proof 1 link");
  });
});

// --- Lane G's 09:30 walk: the task bar's saved line on an earlier day (BLD-C192) --------------------------------

describe("S-05 C-TASKBAR.save BLD-C192: saved on an earlier day, the top bar says the day (J-RECOVER/3, /6, /16, J-SIMILAR/6b, /6c)", () => {
  const status = () => text(document.querySelector('.tbar [role="status"]'));
  const labels = (s: string) => ({
    sidebar: "Monday, on your phone",
    resume: "Last saved on your phone, Monday 10:59 pm.",
    prompt_day: "Monday",
    prompt_line: "Last saved on your phone, 10:59 pm.",
    status: s,
    my_ideas: "Saved 10:59 pm Monday, on your phone",
  });

  it("saved on an earlier day it reads the server's day and time; a save made here reads as now again", async () => {
    const monday = draft({
      saved_at: "2026-11-16T17:29:00Z",
      saved_on: { device: "phone", this_device: false },
      saved_labels: labels("Saved Monday, 10:59 pm"),
    });
    await mount(base({ draft: monday }));
    expect(status()).toBe("Saved Monday, 10:59 pm");
    await railTo("Sorting");
    await click(button("Confirm sorting"));
    expect(status()).toMatch(/^Saved at \d{1,2}:\d{2} (am|pm)$/);
    expect(status()).not.toContain("Monday");
  });

  it("saved today it reads as now, exactly as before", async () => {
    const today = draft({
      saved_labels: { ...labels("Saved at 1:38 pm"), sidebar: "Today, on this laptop" },
    });
    await mount(base({ draft: today }));
    expect(status()).toBe("Saved at 1:38 pm");
  });

  it("offline is unchanged", async () => {
    const monday = draft({ saved_labels: labels("Saved Monday, 10:59 pm") });
    await mount(base({ draft: monday }));
    const online = vi.spyOn(navigator, "onLine", "get").mockReturnValue(false);
    await act(async () => window.dispatchEvent(new Event("offline")));
    expect(status()).toBe("Unsaved, you’re offline");
    online.mockRestore();
  });
});

// --- Lane G's 09:30 walk: a masked detail's label said once in a quote (BLD-C193) -------------------------------

describe("S-05 C-HIDDEN L-HIDE BLD-C193: the sorting's quote says a masked detail's label once (J-RECOVER/10)", () => {
  const quoting = (why: string): SortingResponse => {
    const s = sorting();
    return { ...s, brings: { ...s.brings, why: "from_words", why_line: why } };
  };
  const whys = () => Array.from(document.querySelectorAll(".ck-why")).map((p) => text(p));

  it("'folio Folio ••••17' reads 'Folio ••••17' once; the value stays masked", async () => {
    await mount(
      base({ sorting: quoting("Suggested because you mentioned “one investor with folio Folio ••••17”.") }),
    );
    await railTo("Sorting");
    expect(whys()).toContain("Suggested because you mentioned “one investor with Folio ••••17”.");
    expect(document.body.textContent).not.toMatch(/folio Folio/i);
    expect(document.body.innerHTML).not.toContain("88001234");
  });

  it("a different word before the masked form keeps the label", async () => {
    await mount(
      base({ sorting: quoting("Suggested because you mentioned “the investor at Folio ••••17”.") }),
    );
    await railTo("Sorting");
    expect(whys()).toContain("Suggested because you mentioned “the investor at Folio ••••17”.");
  });
});

// --- Lane G's 09:30 walk: the sorting reasons in the drawn form (BLD-C194) -------------------------------------

describe("S-05 part 2 L-SORT BLD-C194: each sorting reason reads as Review.md draws it (J-RECOVER/10)", () => {
  const DRAWN =
    "Suggested because you said “about 40 calls a day” and “5 to 10 minutes each”. Add revenue or outside tools if it does those too.";

  it("the four reasons read 'Suggested because …', the worth one with its quotes; no 'Suggested: from your words'", async () => {
    const s = sorting();
    await mount(base({ sorting: { ...s, brings: { ...s.brings, why: "from_words", why_line: DRAWN } } }));
    await railTo("Sorting");
    expect(Array.from(document.querySelectorAll(".ck-why")).map((p) => text(p))).toEqual([
      "Suggested because you mentioned investors and the branch.",
      "Suggested because you described something that goes wrong today.",
      "Suggested because it’s about investors and the SMS they get.",
      DRAWN,
    ]);
    expect(document.body.textContent).not.toContain("Suggested: from your words");
  });
});

// --- DEC-118: Check it with an empty title, summary and area (BLD-C195) -----------------------------------------------

describe("V-ACC S-05 DEC-118: a draft that reaches Check it with no title, summary or area (BLD-C195)", () => {
  const EMPTY_PARTS = {
    title: { state: "failed", value: "" },
    summary: { state: "failed", value: "" },
    often: { state: "waiting", value: null },
    who: { state: "waiting", value: [] },
    value: { state: "filled", value: ["not_sure"] },
    area: { state: "waiting", value: "" },
    similar: { state: "failed", value: [] },
  };
  const emptyDraft = () => draft({ parts: EMPTY_PARTS, hidden: [], ready: true });
  const emptySorting = (): SortingResponse => ({
    affects: { value: [], source: "suggested", why: null, why_line: null },
    kind: {
      value: "problem",
      source: "suggested",
      why: "because you described something that goes wrong today.",
      why_line: "Suggested because you described something that goes wrong today.",
    },
    area: { value: null, source: "suggested", why: null, why_line: null },
    brings: { value: [], source: "suggested", why: null, why_line: null },
    confirmed: false,
    complete: false,
    confirmed_at: null,
    rail: "Suggested, not confirmed yet",
    summary: "Not confirmed yet",
    note: "These are suggestions from your words. Not confirmed yet.",
    problem: {
      code: "sorting_incomplete",
      message: "Confirm these, or change any of them, before you send.",
      field: "sorting",
    },
  });
  const emptySend = () =>
    sendView({
      rows: [
        { key: "title", label: "Title", value: null, ok: false, step: "check:1" },
        ...sendView().rows.filter((r) => r.key !== "title"),
      ],
      problems: [{ code: "not_ready", message: "Give it a title of a few words.", field: "title" }],
    });
  const refuseConfirm: Route = (m, u, b) =>
    m === "PATCH" && u.endsWith("/sorting") && (b as { confirm?: boolean }).confirm
      ? {
          status: 422,
          body: {
            error: {
              code: "sorting_incomplete",
              message: "Confirm these, or change any of them, before you send.",
              field: "sorting",
            },
          },
        }
      : undefined;
  const emptyBase = () =>
    base({ draft: emptyDraft(), sorting: emptySorting(), send: emptySend(), similar: [] });

  it("S-05 part 1: no crash; the empty title, what happens and how often read Not given. with their pens; part 1 is not ticked", async () => {
    await mount(emptyBase());
    expect(h1()).toBe("Is this how you’d put it?");
    expect(Array.from(document.querySelectorAll(".ck-v.ck-empty")).map(text)).toEqual([
      "Not given.",
      "Not given.",
      "Not given.",
    ]);
    expect(button("Change the title")).toBeTruthy();
    expect(button("Change what happens")).toBeTruthy();
    await click(button("Looks right"));
    expect(h1()).toBe("Is it sorted right?");
    expect(buttons().some((b) => /^Your words, done/.test(nameOf(b)))).toBe(false);
  });

  it("S-05 part 2 L-SORT: the area unpicked with no reason line; who and worth too; Confirm sorting says what to do", async () => {
    await mount([refuseConfirm, ...emptyBase()]);
    await railTo("Sorting");
    const group = document.querySelector('[role="radiogroup"][aria-label="Area"]')!;
    expect(group).toBeTruthy();
    const radios = Array.from(group.querySelectorAll('[role="radio"]'));
    expect(radios.map(text)).toEqual(["Investor service", "Operations", "Distributor experience"]);
    expect(radios.every((r) => r.getAttribute("aria-checked") === "false")).toBe(true);
    // Only the kind, which always has a suggestion, says why; the empty fields say nothing.
    expect(Array.from(document.querySelectorAll(".ck-why")).map(text)).toEqual([
      "Suggested because you described something that goes wrong today.",
    ]);
    expect(document.body.textContent).toContain("These are suggestions from your words. Not confirmed yet.");
    await click(button("Confirm sorting"));
    expect(h1()).toBe("Is it sorted right?"); // nothing moves on
    expect(document.body.textContent).toContain("Confirm these, or change any of them, before you send.");
    await click(radios.find((r) => text(r) === "Operations"));
    expect(calls.filter((c) => c.method === "PATCH" && c.url.endsWith("/sorting")).pop()?.body).toEqual({
      area: "Operations",
    });
  });

  it("S-05 part 7 V-FIELDS.checkit: the title row reads Not given.; Submit stays blocked: the sorting first, then the title", async () => {
    await mount([
      (m, u) =>
        m === "POST" && u.endsWith("/submit")
          ? {
              status: 422,
              body: {
                error: { code: "not_ready", message: "Give it a title of a few words.", field: "title" },
              },
            }
          : undefined,
      ...emptyBase(),
    ]);
    await railTo("Send it");
    const titleRow = Array.from(document.querySelectorAll(".ck-row")).find(
      (r) => text(r.querySelector("dt")) === "!Title",
    )!;
    expect(text(titleRow.querySelector("dd .ck-v"))).toBe("Not given.");
    const submit = button("Submit")!;
    expect(submit.getAttribute("aria-disabled")).toBeNull();
    await click(submit);
    expect(document.body.textContent).toContain("Confirm the sorting first, or change any of it.");
    expect(calls.some((c) => c.url.endsWith("/submit"))).toBe(false);
  });

  it("S-05 part 1 V-FIELDS.checkit/1: with the sorting confirmed, Submit's refusal asks for the title under it", async () => {
    await mount([
      (m, u) =>
        m === "POST" && u.endsWith("/submit")
          ? {
              status: 422,
              body: {
                error: { code: "not_ready", message: "Give it a title of a few words.", field: "title" },
              },
            }
          : undefined,
      ...base({ draft: emptyDraft(), sorting: sorting(true), send: emptySend(), similar: [] }),
    ]);
    await railTo("Send it");
    await click(button("Submit"));
    expect(h1()).toBe("Is this how you’d put it?");
    expect(document.body.textContent).toContain("Give it a title of a few words.");
    expect(button("Change the title")?.getAttribute("aria-describedby")).toBeTruthy();
  });
});

// --- A new business idea picked by hand (lane C, BLD-C204, L-SORT) -------------------------------------------------

const BUSINESS_LINE = "Suggested because you described something new KFintech could offer.";
const PROBLEM_LINE = "Suggested because you described something that goes wrong today.";

/** The usual config with New business among the areas, as `draft/config.py` lists it. */
const BIZ_CONFIG: ConfigResponse = {
  ...CONFIG,
  sorting: {
    ...CONFIG.sorting,
    areas: [...CONFIG.sorting.areas, "New business"],
    controls: {
      ...CONFIG.sorting.controls,
      area: {
        ...CONFIG.sorting.controls.area,
        shown: [...CONFIG.sorting.controls.area.shown, "New business"],
        all: [...CONFIG.sorting.controls.area.all, "New business"],
      },
    },
  },
};

/** The worker's answer to an area picked by hand (BLD-C204, `submit/sorting.py`): New business suggests a new
 * business idea with its line; any other area takes the kind back to a problem. The kind stays a suggestion. */
const areaByHand: Route = (m, u, b) => {
  const area = (b as { area?: string } | undefined)?.area;
  if (m !== "PATCH" || !u.endsWith("/sorting") || !area) return undefined;
  const business = area === "New business";
  return {
    body: {
      ...sorting(),
      area: { value: area, source: "changed", why: null, why_line: null },
      kind: {
        value: business ? "business_idea" : "problem",
        source: "suggested",
        why: null,
        why_line: business ? BUSINESS_LINE : PROBLEM_LINE,
      },
    } satisfies SortingResponse,
  };
};

describe("S-05 screen: New business picked by hand (BLD-C204, L-SORT, DEC-118)", () => {
  const radio = (label: string) =>
    Array.from(document.querySelectorAll('[role="radio"]')).find((r) => text(r) === label);
  const lastSortingPatch = () =>
    calls.filter((c) => c.method === "PATCH" && c.url.endsWith("/sorting")).at(-1)?.body;

  for (const where of ["desktop", "phone"] as const) {
    it(`on a ${where}: New business picked by hand shows a new business idea with its line; another area takes it back`, async () => {
      if (where === "phone") asPhone();
      await mount([areaByHand, ...base()], BIZ_CONFIG);
      if (where === "desktop") await railTo("Sorting");
      expect(radio("A problem to fix")?.getAttribute("aria-checked")).toBe("true");
      expect(document.body.textContent).toContain(PROBLEM_LINE);

      await click(radio("New business"));
      expect(lastSortingPatch()).toEqual({ area: "New business" }); // only the area: the kind is never sent
      expect(radio("New business")?.getAttribute("aria-checked")).toBe("true");
      expect(radio("A new business idea")?.getAttribute("aria-checked")).toBe("true");
      expect(radio("A problem to fix")?.getAttribute("aria-checked")).toBe("false");
      expect(document.body.textContent).toContain(BUSINESS_LINE);
      expect(document.body.textContent).toContain(
        "These are suggestions from your words. Not confirmed yet.",
      );

      await click(radio("Operations"));
      expect(lastSortingPatch()).toEqual({ area: "Operations" });
      expect(radio("A problem to fix")?.getAttribute("aria-checked")).toBe("true");
      expect(document.body.textContent).toContain(PROBLEM_LINE);
      expect(document.body.textContent).not.toContain(BUSINESS_LINE);
    });
  }
});
