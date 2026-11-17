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

const replace = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ replace, push: vi.fn(), refresh: vi.fn() }) }));
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

async function mount(routes: Route[], config: ConfigResponse | null = CONFIG) {
  serve(routes);
  await act(async () => root.render(createElement(CheckIt, { draftId: DRAFT_ID, config })));
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

beforeEach(() => {
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
        problem: "Found a phone number on page 2. Nobody can open it until it’s hidden.",
      }),
    ).toMatchObject({
      status: "found",
      message: {
        kind: "warn",
        text: "Found a phone number on page 2. Nobody can open it until it’s hidden.",
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

  it("C-FILE.uploader/3: links one at a time or with commas; anything else is not a link", () => {
    expect(model.splitLinks("intranet.kfintech.example/page, https://teams.example/x")).toEqual({
      links: ["https://intranet.kfintech.example/page", "https://teams.example/x"],
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
      "7 Send it One last look, then submit",
    ]);
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
    expect(button(/^Sorting Investor service, saves time, saves cost$/)).toBeTruthy();
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

  it("J-SHARE/9 C-SIMGRID.grid/4: Next keeps theirs separate; back on the part the grid folds, and Show them again opens it", async () => {
    await mount(base());
    await railTo("Similar ideas");
    await click(button("Next"));
    expect(calls.find((c) => c.url.endsWith("/similar/keep-separate"))?.body).toEqual({ on: true });
    expect(text(document.querySelector(".ck-count"))).toBe("Check it, part 4 of 6");
    await railTo("Similar ideas");
    expect(document.body.textContent).toContain(
      "Kept separate. The review desk still sees the similar ideas next to yours.",
    );
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
    expect(button("Withdraw the request")).toBeTruthy();
    await railTo("Send it");
    expect(h1()).toBe("Ready to send?");
    expect(button("Submit")!.getAttribute("aria-disabled")).toBe("true");
    await click(button("Withdraw the request"));
    expect(calls.some((c) => c.method === "DELETE" && c.url.endsWith("/merge-request"))).toBe(true);
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

  it("J-RECOVER/8 L-HIDE.files: a file with personal data: the found line, Hide it for me and Remove; checking until it settles", async () => {
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
    await mount([
      (m, u) => (m === "POST" && u === "/api/files" ? { status: 201, body: uploaded } : undefined),
      (m, u) =>
        m === "GET" && u === "/api/files/f9"
          ? {
              body: {
                ...uploaded,
                state: "personal_data_found",
                problem: "Found a phone number on page 1. Nobody can open it until it’s hidden.",
              },
            }
          : undefined,
      (m, u) =>
        m === "POST" && u === "/api/files/f9/hide"
          ? { body: { ...uploaded, state: "hidden_checked", hidden_note: "Phone hidden" } }
          : undefined,
      ...base(),
    ]);
    await railTo("Proof");
    await click(button("Attach files"));
    await chooseFile("courier-call-log.pdf", "application/pdf");
    await settle();
    expect(document.body.textContent).toContain("Checking for personal details");
    await act(async () => vi.advanceTimersByTime(2100));
    await settle();
    expect(document.body.textContent).toContain(
      "Found a phone number on page 1. Nobody can open it until it’s hidden.",
    );
    await click(button("Hide it for me"));
    expect(document.body.textContent).toContain("Phone hidden");
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
                next: { to: "/ideas/IDEA-2026-001481", replace: true, state: "just_shared" },
              },
            }
          : undefined,
      ...base({ sorting: sorting(true) }),
    ]);
    await railTo("Send it");
    await click(button("Submit"));
    const sent = calls.find((c) => c.url.endsWith("/submit"))!;
    expect(sent.body).toEqual({ declaration_version: "2026-11-17" });
    expect(sent.headers["Idempotency-Key"]).toMatch(/^s05:/);
    expect(replace).toHaveBeenCalledWith("/ideas/IDEA-2026-001481");
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
                next: { to: "/ideas/IDEA-2026-001482" },
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
    expect(replace).toHaveBeenCalledWith("/ideas/IDEA-2026-001482");
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

describe("S-05 words (F-COPY)", () => {
  it("never says duplicate, rejected, already solved, appeal, invalid or Garage to the sharer", () => {
    const all = JSON.stringify(CHECK_COPY, (_k, v) => (typeof v === "function" ? v("2", "Ravi") : v));
    expect(all).not.toMatch(/\b(duplicate|rejected|already solved|appeal|invalid|Garage)\b/i);
  });
});
