// @vitest-environment jsdom
/**
 * S-06B "Edit after sharing" (BLD-C160 to BLD-C164): the rules in edit/model.ts, then the screen against mocked A-API
 * answers: load, edit in place with nothing sent until Save, Save that makes a version or says nothing has changed,
 * `edit_window_closed` with the changes kept, Cancel's in-place confirm, the hidden-detail rules (Show it, and a detail
 * the review desk hid), the sorting held until Save, the fix kept on the page until Save, files on the shared idea,
 * a closed window at load, and the phone. Synthetic people only: the pack's fictional cast.
 */
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ConfigResponse, EditPageResponse, SortingResponse } from "@/lib/contracts";

const nav = vi.hoisted(() => ({ push: (() => undefined) as (to: string) => void }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: () => undefined,
    push: (to: string) => nav.push(to),
    refresh: () => undefined,
  }),
}));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
    createElement("a", { href, ...rest }, children as never),
}));

const { EditIdea } = await import("@/app/ideas/[id]/edit/edit-idea");
const model = await import("@/app/ideas/[id]/edit/model");
const { EDIT_COPY } = await import("@/app/ideas/[id]/edit/copy");
const { api } = await import("@/app/share/[id]/check/client");
const { EMPTY_FIX } = await import("@/app/share/[id]/check/model");

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// --- Fixtures (synthetic) ----------------------------------------------------------------------------------------

const REF = "IDEA-2026-001481";
const UUID = "7c1d2e3f-4a5b-4c6d-8e9f-0a1b2c3d4e5f";
const URL_EDIT = `/api/ideas/${REF}/edit`;
const TITLE = "Investors call to ask why a redemption was rejected";
const SAVED = "Saved. The review desk will see the latest version.";
const CLOSED =
  "The review desk has just opened it, so it can’t be changed now. Your changes are kept below. Send them as a message instead.";
const DECL =
  "By saving, you confirm there’s no customer personal data in it or its files, and it’s your own work or you’ve credited others.";

function sorting(): SortingResponse {
  return {
    affects: {
      value: ["Investors", "KFin teams"],
      source: "confirmed",
      why: null,
      why_line: "Suggested because you mentioned investors and the branch.",
    },
    kind: {
      value: "problem",
      source: "confirmed",
      why: null,
      why_line: "Suggested because you described something that goes wrong today.",
    },
    area: {
      value: "Investor service",
      source: "confirmed",
      why: null,
      why_line: "Suggested because it’s about investors and the SMS they get.",
    },
    brings: { value: ["saves_time", "saves_cost"], source: "confirmed", why: null, why_line: null },
    confirmed: true,
    complete: true,
    confirmed_at: "2026-11-14T10:00:00+05:30",
    rail: "Investor service, saves time, saves cost",
    summary: "Investor service, affecting investors and KFin teams, saves time, saves cost",
    note: "Confirmed when you shared it. You can still change any of these.",
    problem: null,
  };
}

function page(extra: Partial<EditPageResponse> = {}): EditPageResponse {
  return {
    screen: "S-06B",
    id: UUID,
    ref: REF,
    status: "with_review_desk",
    kind: "problem",
    bar: {
      title: `Edit ${REF}`,
      line: "Shared Saturday 14 November. You can edit until the review desk opens it, at the latest Tuesday 17 November.",
      back: { label: "Back to your idea", to: `/ideas/${REF}` },
    },
    window: {
      open: true,
      closes_at: "2026-11-17T10:00:00+05:30",
      countdown: { label: "3 days left", variant: "neutral", until: "2026-11-17T10:00:00+05:30" },
    },
    fields: {
      title: TITLE,
      summary:
        "The rejection SMS only gives a code, such as R07. Investors don’t know what it means, so they call the branch.",
      often: "About 40 calls a day at one branch",
    },
    hidden: [
      { id: "a1b2c3d4-0000-4000-8000-000000000001", kind: "folio", masked: "Folio ••••89", state: "hidden" },
    ],
    sorting: sorting(),
    fix: null,
    helpers: { picks: [], text: null, line: "Not said", part: { rail: "Optional" } },
    files: [],
    prompts: {},
    side: [
      {
        when: "Straight away",
        line: "The review desk sees the latest version. Earlier versions are kept on the timeline.",
      },
      {
        when: "At the latest Tuesday 17 November",
        line: "Editing closes when the review desk opens it. After that, you can add a note for them instead.",
      },
      { when: "By Friday 20 November", line: "The review desk decides, and tells you why." },
    ],
    declaration: { version: "1pc-2026-11", text: DECL },
    versions: { count: 1, summary: "1 version. Sorting confirmed." },
    ...extra,
  };
}

const FIX = {
  how: "Send the reason in plain words with the code, in the SMS itself.",
  solved_already: "partly",
  ready_count: 2,
  included: true,
  ready_of: 5,
  readiness: "2 of 5 ready for the review desk",
  next: { key: "worth", line: "Most useful next: a rough size. A range is fine." },
  part: {
    rail: "Added",
    line: "Included, 2 of 5 ready",
    fix_line: "Send the reason in plain words with the code, in the SMS itself.",
  },
} as unknown as EditPageResponse["fix"];

const CONFIG: ConfigResponse = {
  promises: {},
  sorting: {
    affects: ["Investors", "KFin teams", "Distributors", "AMC clients", "Others"],
    areas: ["Investor service", "Operations", "Distributor experience", "Technology"],
    brings: ["saves_time", "saves_cost", "earns_revenue", "less_outside_tools", "not_sure"],
    helpers: [],
    controls: {
      affects: {
        shown: ["Investors", "KFin teams", "Distributors"],
        all: ["Investors", "KFin teams", "Distributors", "AMC clients", "Others"],
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
      helpers: [],
    },
  },
  declaration: { version: "1pc-2026-11", submit: "", save: DECL },
};

type Answer = { status?: number; body?: unknown; fail?: boolean };
type Route = (method: string, url: string, body: unknown) => Answer | undefined;

let calls: Array<{ method: string; url: string; body: unknown }>;
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
      calls.push({ method, url, body });
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

function base(p: () => EditPageResponse = () => page()): Route[] {
  return [
    (m, u) => (m === "GET" && u === URL_EDIT ? { body: p() } : undefined),
    (m, u) => (m === "GET" && u === "/api/config/uploads" ? { status: 404, body: {} } : undefined),
  ];
}

async function mount(routes: Route[]) {
  serve(routes);
  await act(async () => root.render(createElement(EditIdea, { ideaId: REF, config: CONFIG })));
  await settle();
}

async function settle() {
  for (let i = 0; i < 6; i++) await act(async () => undefined);
}

const text = (el: Element | null | undefined) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();
const nameOf = (b: Element) => {
  const label = b.getAttribute("aria-label");
  if (label) return label;
  const copy = b.cloneNode(true) as Element;
  copy.querySelectorAll('[aria-hidden="true"]').forEach((n) => n.remove());
  return text(copy);
};
const all = (sel: string) => Array.from(document.querySelectorAll<HTMLElement>(sel));
const button = (name: string | RegExp) =>
  all("button").find((b) => (typeof name === "string" ? nameOf(b) === name : name.test(nameOf(b))));
const link = (name: string) => all("a").find((a) => nameOf(a) === name);
const status = () => text(document.querySelector(".tbar .saved"));
const saves = () => calls.filter((c) => c.method === "PATCH" && c.url === URL_EDIT);

async function click(el: Element | undefined | null) {
  if (!el) throw new Error("nothing to click");
  await act(async () => (el as HTMLElement).click());
  await settle();
}

async function type(el: Element | null | undefined, value: string) {
  if (!el) throw new Error("nothing to type in");
  const input = el as HTMLInputElement | HTMLTextAreaElement;
  const proto =
    input instanceof HTMLTextAreaElement ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
  await act(async () => {
    Object.getOwnPropertyDescriptor(proto, "value")!.set!.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

/** Change the title in place: the pen, the new words, Enter. */
async function retitle(value: string) {
  await click(button("Change the title"));
  const input = document.querySelector<HTMLInputElement>('input[aria-label="Title"]');
  await type(input, value);
  await act(async () => {
    input!.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
  });
  await settle();
}

/** Whether the page let a click on a link go on (not prevented). Navigation itself is stopped here. */
async function follows(a: Element | undefined): Promise<boolean> {
  if (!a) throw new Error("no link");
  let prevented = true;
  const record = (e: Event) => {
    prevented = e.defaultPrevented;
    e.preventDefault();
  };
  document.addEventListener("click", record);
  await act(async () => {
    a.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }));
  });
  document.removeEventListener("click", record);
  await settle();
  return !prevented;
}

beforeEach(() => {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(async () => {
  await act(async () => root.unmount());
  document.body.innerHTML = "";
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  window.sessionStorage.clear();
  nav.push = () => undefined;
});

// --- Rules -------------------------------------------------------------------------------------------------------

describe("S-06B rules (edit/model.ts, BLD-C160)", () => {
  const fresh = () => model.initialState(page(), EMPTY_FIX, EMPTY_FIX);

  it("L-SUBMIT.edit/2: Save sends only what changed; nothing changed is an empty body", () => {
    const p = page();
    expect(model.editPatch(p, fresh())).toEqual({});
    expect(model.isDirty(p, fresh())).toBe(false);
    const s = { ...fresh(), title: "Investors call to ask why a redemption was not processed", often: "" };
    expect(model.editPatch(p, s)).toEqual({
      title: "Investors call to ask why a redemption was not processed",
      often: null,
    });
    expect(model.isDirty(p, s)).toBe(true);
  });

  it("L-SORT S-06B.rules/3: a sorting change is sent only when it differs; emptying a required field unconfirms it", () => {
    const p = page();
    const same = { ...fresh(), sorting: { affects: ["KFin teams", "Investors"], area: "Investor service" } };
    expect(model.editPatch(p, same)).toEqual({});
    const moved = { ...fresh(), sorting: { area: "Operations" } };
    expect(model.editPatch(p, moved)).toEqual({ sorting: { area: "Operations" } });
    const v = model.sortingView(p.sorting, moved.sorting);
    expect(v.area.value).toBe("Operations");
    expect(v.area.why_line).toBeNull();
    expect(v.affects.why_line).toBe("Suggested because you mentioned investors and the branch.");
    expect(v.confirmed).toBe(true);
    const emptied = model.sortingView(p.sorting, { affects: [] });
    expect(emptied.complete).toBe(false);
    expect(emptied.confirmed).toBe(false);
  });

  it("S-05.fix on S-06B: an added fix is sent without included; Remove sends null; a started one stays here", () => {
    const p = page({ fix: FIX });
    const form = { ...EMPTY_FIX, how: "Send the reason in plain words with the code.", solved: "partly" };
    const added = {
      ...fresh(),
      fix: { part: { kind: "added" as const, line: "", fixLine: "" }, form, touched: true },
    };
    expect(model.editPatch(p, added).fix).toEqual({
      how: "Send the reason in plain words with the code.",
      solved_already: "partly",
    });
    const removed = { ...fresh(), fix: { part: { kind: "none" as const }, form: EMPTY_FIX, touched: true } };
    expect(model.editPatch(p, removed)).toEqual({ fix: null });
    const started = { ...fresh(), fix: { part: { kind: "started" as const }, form, touched: false } };
    expect(model.editPatch(page(), started)).toEqual({});
  });

  it("A-API.conventions/2: a refusal's field puts its words under the part it is about", () => {
    expect(model.placeOf("title")).toBe("words");
    expect(model.placeOf("sorting")).toBe("sorting");
    expect(model.placeOf("fix.worth.hours_month")).toBe("fix");
    expect(model.placeOf(undefined)).toBe("save");
    expect(model.placeOf("declaration")).toBe("save");
  });
});

// --- The screen ----------------------------------------------------------------------------------------------------

describe("S-06B screen: load (BLD-C160)", () => {
  it("S-06B.layout J-SHARE S-06→S-06B: the bar, the heading, your problem with the hidden detail, the sorting confirmed, the side panel and Save", async () => {
    await mount(base());
    expect(text(document.querySelector("h1"))).toBe("Edit your problem");
    expect(text(document.querySelector(".tbar"))).toContain(`Edit ${REF}`);
    expect(text(document.querySelector(".tbar"))).toContain(
      "Shared Saturday 14 November. You can edit until the review desk opens it, at the latest Tuesday 17 November.",
    );
    expect(link("Back to your idea")?.getAttribute("href")).toBe(`/ideas/${REF}`);
    expect(document.body.textContent).toContain(
      "Change anything that isn’t right. Nothing changes for anyone else until you save.",
    );
    const h2s = all("h2").map(text);
    expect(h2s).toEqual(
      expect.arrayContaining([
        "Your problem",
        "Is this sorted right?",
        "Anything that shows it? Optional",
        "Your fix Optional",
        "What happens when you save",
      ]),
    );
    expect(text(document.querySelector("h3"))).toBe(TITLE);
    expect(button("Change the title")).toBeTruthy();
    expect(button("Change what happens")).toBeTruthy();
    expect(button("Change how often")).toBeTruthy();
    expect(document.body.textContent).toContain("Hidden from everyone");
    expect(document.body.textContent).toContain("Folio ••••89");
    const note = all('[role="status"]').find(
      (n) => text(n) === "Confirmed when you shared it. You can still change any of these.",
    );
    expect(note).toBeTruthy();
    expect(document.body.textContent).toContain("Got an idea how to solve it?");
    expect(button("Add your fix")).toBeTruthy();
    expect(document.body.textContent).toContain("At the latest Tuesday 17 November");
    expect(document.body.textContent).toContain(DECL);
    expect(link("Cancel")?.getAttribute("href")).toBe(`/ideas/${REF}`);
    expect(button("Save changes")).toBeTruthy();
    expect(status()).toBe("Saved");
    expect(calls.filter((c) => c.method !== "GET")).toEqual([]);
  });

  it("C-FILE.uploader S-06B: the drop area is open, with the edit board's link field and Add link", async () => {
    await mount(base());
    expect(document.body.textContent).toContain("Drop files here, or");
    expect(button("browse")).toBeTruthy();
    const input = document.querySelector<HTMLInputElement>('input[type="url"]');
    expect(input?.placeholder).toBe("Or paste a link to a report, dashboard or ticket");
    expect(button("Add link")).toBeTruthy();
    expect(button("Attach files")).toBeUndefined();
    expect(document.body.textContent).toContain("What helps most");
  });

  it("A-API.ideas: an idea that is not theirs reads as missing, with Try again", async () => {
    await mount([
      (m, u) =>
        m === "GET" && u === URL_EDIT
          ? { status: 404, body: { error: { code: "not_found", message: "We can’t find that idea." } } }
          : undefined,
    ]);
    expect(document.body.textContent).toContain("We can’t find that idea.");
    expect(button("Try again")).toBeTruthy();
  });

  it("L-SUBMIT.edit/5: a window already closed shows the server's line and Open the conversation, and no Save", async () => {
    const line =
      "The review desk opened it on Monday 16 November, so the idea itself can’t be changed now. Write to them in the conversation.";
    await mount(
      base(() => page({ window: { open: false, opened_by_desk_at: "2026-11-16T10:00:00+05:30", line } })),
    );
    expect(document.body.textContent).toContain(line);
    expect(link("Open the conversation")?.getAttribute("href")).toBe(`/ideas/${REF}/conversation`);
    expect(button("Save changes")).toBeUndefined();
  });
});

describe("S-06B screen: edit and Save (BLD-C160, L-SUBMIT.edit)", () => {
  it("J-RECOVER/15 S-06B L-SUBMIT.edit/2,/4: a change waits for Save; Save sends it with the declaration's version and reads Saved", async () => {
    let n = 0;
    await mount([
      (m, u) =>
        m === "PATCH" && u === URL_EDIT
          ? {
              body: {
                version: { n: 2, changed_fields: ["title"], at: "2026-11-15T08:09:00Z" },
                changed_fields: ["title"],
                saved_label: "Saved at 1:39 pm",
                message: SAVED,
                next: { to: `/ideas/${REF}`, replace: true },
              },
            }
          : undefined,
      (m, u) =>
        m === "GET" && u === URL_EDIT
          ? {
              body:
                n++ === 0
                  ? page()
                  : page({
                      fields: { ...page().fields, title: "Investors call about a redemption not processed" },
                    }),
            }
          : undefined,
      ...base(),
    ]);
    await retitle("Investors call about a redemption not processed");
    expect(status()).toBe("Unsaved changes");
    expect(saves()).toEqual([]);
    await click(button("Save changes"));
    expect(saves()).toHaveLength(1);
    expect(saves()[0]!.body).toEqual({
      title: "Investors call about a redemption not processed",
      declaration_version: "1pc-2026-11",
    });
    expect(status()).toBe("Saved at 1:39 pm");
    const said = all('[role="status"]').find((s) => text(s) === SAVED);
    expect(said).toBeTruthy();
    expect(link("Cancel")).toBeUndefined();
    expect(link("Back to your idea")?.getAttribute("href")).toBe(`/ideas/${REF}`);
    expect(text(document.querySelector("h3"))).toBe("Investors call about a redemption not processed");
  });

  it("L-SUBMIT.edit/4: Save with nothing changed makes no version and says so in the server's words", async () => {
    await mount([
      (m, u) =>
        m === "PATCH" && u === URL_EDIT
          ? {
              body: {
                version: null,
                changed_fields: [],
                message: "Nothing has changed.",
                next: { to: `/ideas/${REF}`, replace: true },
              },
            }
          : undefined,
      ...base(),
    ]);
    await click(button("Save changes"));
    expect(saves()[0]!.body).toEqual({ declaration_version: "1pc-2026-11" });
    expect(all('[role="status"]').some((s) => text(s) === "Nothing has changed.")).toBe(true);
    expect(status()).toBe("Saved");
  });

  it("S-06B.rules/2 V-FIELDS.checkit/15: the desk opened it meanwhile: Save is refused, the changes stay, Open the conversation", async () => {
    await mount([
      (m, u) =>
        m === "PATCH" && u === URL_EDIT
          ? {
              status: 409,
              body: {
                error: {
                  code: "edit_window_closed",
                  message: CLOSED,
                  opened_by_desk_at: "2026-11-16T10:00:00+05:30",
                  to: `/ideas/${REF}/conversation`,
                },
              },
            }
          : undefined,
      ...base(),
    ]);
    await retitle("Investors call about a redemption not processed");
    await click(button("Save changes"));
    const alert = all('[role="alert"]').find((a) => text(a).startsWith(CLOSED));
    expect(alert).toBeTruthy();
    expect(link("Open the conversation")?.getAttribute("href")).toBe(`/ideas/${REF}/conversation`);
    expect(text(document.querySelector("h3"))).toBe("Investors call about a redemption not processed");
    expect(status()).toBe("Unsaved changes");
    expect(button("Save changes")?.getAttribute("aria-disabled")).toBe("true");
    await click(button("Save changes"));
    expect(saves()).toHaveLength(1);
  });

  it("A-API.conventions/2: a field refusal goes under its part; a failure says try again under Save, nothing lost", async () => {
    let fail = false;
    await mount([
      (m, u) =>
        m === "PATCH" && u === URL_EDIT
          ? fail
            ? { fail: true }
            : {
                status: 422,
                body: {
                  error: { code: "field_needed", message: "Give it a title of a few words.", field: "title" },
                },
              }
          : undefined,
      ...base(),
    ]);
    await retitle("Investors call about a redemption not processed");
    await click(button("Save changes"));
    expect(text(document.querySelector(".ed-words .field-msg"))).toBe("Give it a title of a few words.");
    fail = true;
    await click(button("Save changes"));
    expect(all('[role="alert"]').some((a) => text(a) === "Something went wrong. Try again.")).toBe(true);
    expect(text(document.querySelector("h3"))).toBe("Investors call about a redemption not processed");
  });

  it("S-06B.layout/7: Cancel leaves at once with nothing changed; with changes it confirms in place, then leaves", async () => {
    await mount(base());
    expect(await follows(link("Cancel"))).toBe(true);
    await retitle("Investors call about a redemption not processed");
    expect(await follows(link("Cancel"))).toBe(false);
    const confirm = document.querySelector(".ed-confirm");
    expect(text(confirm)).toBe("Unsaved changes. Nothing changes for anyone else until you save.");
    expect(confirm?.getAttribute("role")).toBe("alert");
    expect(await follows(link("Cancel"))).toBe(true);
    expect(saves()).toEqual([]);
  });
});

describe("S-06B screen: hidden details (C-HIDDEN, L-HIDE.rules/6)", () => {
  const HID = "a1b2c3d4-0000-4000-8000-000000000001";
  const SHOW = `/api/drafts/${REF}/hidden/${HID}/show`;

  async function showWith(answer: Answer) {
    await mount([(m, u) => (m === "POST" && u === SHOW ? answer : undefined), ...base()]);
    await click(button("Show it"));
    await click(all('[role="radio"]').find((r) => /made up for the example/.test(text(r))));
    const confirm = all("button").filter((b) => nameOf(b) === "Show it");
    await click(confirm[confirm.length - 1]);
  }

  it("J-RECOVER/11 S-06B: Show it asks for a reason and acts at once on the shared idea, by its reference", async () => {
    await showWith({
      body: { id: HID, kind: "folio", masked: "Folio ••••89", state: "shown", reason: "made_up_example" },
    });
    const post = calls.find((c) => c.method === "POST" && c.url === SHOW);
    expect(post?.body).toEqual({ reason: "made_up_example" });
    expect(document.body.textContent).toContain("Shown, because it’s made up for the example.");
    expect(saves()).toEqual([]);
  });

  it("L-HIDE.rules/7: a detail the review desk hid stays hidden, in the server's words (403)", async () => {
    await showWith({
      status: 403,
      body: { error: { code: "forbidden", message: "The review desk hid this, so it stays hidden." } },
    });
    expect(
      all('[role="alert"]').some((a) => text(a) === "The review desk hid this, so it stays hidden."),
    ).toBe(true);
    expect(document.body.textContent).not.toContain("Shown, because");
  });
});

describe("S-06B screen: sorting and the fix wait for Save (L-SORT, S-05.fix)", () => {
  it("J-RECOVER/10 S-06B: one choice changes the area; nothing is sent until Save, which sends the sorting", async () => {
    await mount([
      (m, u) =>
        m === "PATCH" && u === URL_EDIT
          ? {
              body: {
                version: { n: 2, changed_fields: ["sorting"], at: "2026-11-15T08:09:00Z" },
                changed_fields: ["sorting"],
                message: SAVED,
                next: { to: `/ideas/${REF}`, replace: true },
              },
            }
          : undefined,
      ...base(),
    ]);
    await click(all('[role="radio"]').find((r) => text(r) === "Operations"));
    expect(
      all('[role="radio"]')
        .find((r) => text(r) === "Operations")
        ?.getAttribute("aria-checked"),
    ).toBe("true");
    expect(calls.some((c) => c.url.includes("/sorting"))).toBe(false);
    expect(status()).toBe("Unsaved changes");
    await click(button("Save changes"));
    expect(saves()[0]!.body).toEqual({ sorting: { area: "Operations" }, declaration_version: "1pc-2026-11" });
  });

  it("S-06B.rules/3 V-FIELDS.checkit/3: a required field emptied says what to do under the card, and Save sends nothing", async () => {
    await mount(base());
    for (const name of ["Investors", "KFin teams"]) {
      await click(all("button[aria-pressed]").find((r) => nameOf(r) === name));
    }
    const msg = document.querySelector(".ck-sort .field-msg");
    expect(text(msg)).toBe("Confirm these, or change any of them, before you send.");
    await click(button("Save changes"));
    expect(saves()).toEqual([]);
    expect(document.activeElement?.getAttribute("data-part")).toBe("sorting");
  });

  it("S-05.fix on S-06B: Add my fix keeps the fix on the page (no PUT); Save sends it", async () => {
    await mount([
      (m, u) =>
        m === "PATCH" && u === URL_EDIT
          ? {
              body: {
                version: { n: 2, changed_fields: ["fix"], at: "2026-11-15T08:09:00Z" },
                changed_fields: ["fix"],
                message: SAVED,
                next: { to: `/ideas/${REF}`, replace: true },
              },
            }
          : undefined,
      ...base(),
    ]);
    await click(button("Add your fix"));
    const how = document.querySelector<HTMLTextAreaElement>(".ck-sheet textarea");
    await type(how, "Too short");
    await click(button("Add my fix"));
    expect(text(document.querySelector(".ck-sheet .field-msg"))).toBe(
      "Say how you’d solve it, or close this to send without a fix.",
    );
    await type(how, "Send the reason in plain words with the code, in the SMS itself.");
    await click(button("Add my fix"));
    expect(document.querySelector(".ck-sheet")).toBeNull();
    expect(calls.some((c) => c.url.includes("/fix"))).toBe(false);
    expect(document.body.textContent).toContain(
      "Send the reason in plain words with the code, in the SMS itself.",
    );
    await click(button("Save changes"));
    expect(saves()[0]!.body).toEqual({
      fix: { how: "Send the reason in plain words with the code, in the SMS itself." },
      declaration_version: "1pc-2026-11",
    });
  });

  it("S-05.parts/5 on S-06B: Remove takes an added fix off the page; Save sends fix: null", async () => {
    await mount([
      (m, u) =>
        m === "PATCH" && u === URL_EDIT
          ? { body: { version: null, changed_fields: [], message: "" } }
          : undefined,
      ...base(() => page({ fix: FIX })),
    ]);
    expect(document.body.textContent).toContain("Included, 2 of 5 ready");
    await click(button("Remove your fix"));
    expect(button("Add your fix")).toBeTruthy();
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
    await click(button("Save changes"));
    expect(saves()[0]!.body).toEqual({ fix: null, declaration_version: "1pc-2026-11" });
  });
});

describe("S-06B screen: files on the shared idea (A-API.files, C-FILE)", () => {
  it("A-API.files: an upload and a link name the idea (idea_id), not a draft", async () => {
    serve([
      (m, u) => (m === "POST" && (u === "/api/files" || u === "/api/links") ? { body: {} } : undefined),
    ]);
    const fetchMock = globalThis.fetch as unknown as ReturnType<typeof vi.fn>;
    await api.upload(
      { idea_id: UUID },
      new File(["x"], "rejection-sms-screenshot.png", { type: "image/png" }),
    );
    const form = (fetchMock.mock.calls[0]![1] as RequestInit).body as FormData;
    expect(form.get("idea_id")).toBe(UUID);
    expect(form.get("draft_id")).toBeNull();
    await api.link({ idea_id: UUID }, "https://intranet.kfintech.example/codes");
    expect(calls[1]!.body).toEqual({ url: "https://intranet.kfintech.example/codes", idea_id: UUID });
    await api.link("0b6f7a52-3c1e-4d7a-9f00-1a2b3c4d5e6f", "https://intranet.kfintech.example/codes");
    expect(calls[2]!.body).toEqual({
      url: "https://intranet.kfintech.example/codes",
      draft_id: "0b6f7a52-3c1e-4d7a-9f00-1a2b3c4d5e6f",
    });
  });

  it("J-RECOVER/7 S-06B: a failed upload says so with Try again and Remove; the other rows and the edits are unaffected", async () => {
    await mount([(m, u) => (m === "POST" && u === "/api/files" ? { fail: true } : undefined), ...base()]);
    const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;
    const file = new File(["x"], "rejection-sms-screenshot.png", { type: "image/png" });
    await act(async () => {
      Object.defineProperty(input, "files", { value: [file], configurable: true });
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await settle();
    expect(all('[role="alert"]').some((a) => text(a) === "Didn’t upload. Your other files are fine.")).toBe(
      true,
    );
    expect(button("Try again")).toBeTruthy();
    expect(button("Remove rejection-sms-screenshot.png")).toBeTruthy();
    expect(status()).toBe("Saved");
  });
});

describe("S-06B phone (PhoneEdit, S-06B.rules/5)", () => {
  it("PhoneEdit: Change buttons, Not personal? Show it, the picker button, the phone declaration and Save changes in the dock", async () => {
    vi.stubGlobal("matchMedia", (q: string) => ({
      matches: q.includes("max-width"),
      media: q,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
    }));
    await mount(base());
    expect(button("Change title")).toBeTruthy();
    expect(button("Change what happens")).toBeTruthy();
    expect(button("Not personal? Show it")).toBeTruthy();
    // The picker's name has a space between its two lines (minor of the c/s06b review).
    expect(
      button(
        "Add a photo or file A screenshot of the SMS, a call log, or a report with the time or money it costs",
      ),
    ).toBeTruthy();
    expect(document.querySelector<HTMLInputElement>('input[type="url"]')?.placeholder).toBe(
      "Or paste a link",
    );
    expect(button("Add")).toBeTruthy();
    const dock = document.querySelector(".dock");
    expect(text(dock)).toContain(
      "Saving confirms there’s no customer personal data in it or its files, and it’s your own work or credited.",
    );
    expect(dock?.querySelector("button") && nameOf(dock.querySelector("button")!)).toBe("Save changes");
    expect(document.body.textContent).toContain(
      "Editing closes when the review desk opens it. After that, you can add a note for them.",
    );
    expect(document.body.textContent).not.toContain("By Friday 20 November");
  });
});

// --- Review round on c/s06b (BLD-C161, C163, C165) ------------------------------------------------------------------

const LINK = {
  id: "ATT-2026-000501",
  kind: "link",
  name: "intranet.kfintech.example/codes",
  type: "link",
  state: "checked",
  link_scope: "internal",
};
const SHOWN = {
  id: "ATT-2026-000400",
  kind: "file",
  name: "rejection-sms-screenshot.png",
  type: "image/png",
  size: 84_000,
  state: "checked",
};
const CONFIRM = "Unsaved changes. Nothing changes for anyone else until you save.";

/** sessionStorage that cannot be used (blocked site data): reading it throws. Returns the way back. */
function blockStorage(): () => void {
  const real = Object.getOwnPropertyDescriptor(window, "sessionStorage");
  Object.defineProperty(window, "sessionStorage", {
    configurable: true,
    get() {
      throw new Error("blocked");
    },
  });
  return () => {
    if (real) Object.defineProperty(window, "sessionStorage", real);
    else delete (window as unknown as Record<string, unknown>).sessionStorage;
  };
}

function phoneScreen() {
  vi.stubGlobal("matchMedia", (q: string) => ({
    matches: q.includes("max-width"),
    media: q,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }));
}

async function addLink(url: string) {
  await type(document.querySelector('input[type="url"]'), url);
  await click(button("Add link"));
}

describe("S-06B review: files count as changes (BLD-C161 as amended)", () => {
  it("BLD-C161: the rows added or removed since loading are the files delta; Cancel takes the added ones away", () => {
    const row = (id: string | null, extra: object = {}) =>
      ({ key: id ?? "local-1", item: id ? { id } : null, name: "x", ...extra }) as never;
    const d = model.filesDelta(
      ["ATT-2026-000400", "ATT-2026-000401"],
      [row("ATT-2026-000401"), row("ATT-2026-000501")],
    );
    expect(d).toEqual({ added: ["ATT-2026-000501"], removed: ["ATT-2026-000400"], moving: false });
    const p = page();
    const s = model.initialState(p, EMPTY_FIX, EMPTY_FIX);
    expect(model.isDirty(p, s, d)).toBe(true);
    expect(model.editPatch(p, s, d)).toEqual({
      files: { added: ["ATT-2026-000501"], removed: ["ATT-2026-000400"] },
    });
    const up = model.filesDelta([], [row(null, { localState: "uploading" })]);
    expect(up.moving).toBe(true);
    expect(model.editPatch(p, s, up)).toEqual({});
    expect(model.isDirty(p, s, up)).toBe(true);
    expect(model.isDirty(p, s, model.filesDelta([], [row(null, { localState: "upload_failed" })]))).toBe(
      false,
    );
    expect(
      model
        .addedRows(["ATT-2026-000401"], [row("ATT-2026-000401"), row("ATT-2026-000501"), row(null)])
        .map((r) => (r as { key: string }).key),
    ).toEqual(["ATT-2026-000501", "local-1"]);
    expect(model.baseAfter(["ATT-2026-000400", "ATT-2026-000401"], d)).toEqual([
      "ATT-2026-000401",
      "ATT-2026-000501",
    ]);
  });

  it("BLD-C161 S-06B.layout/7: a link added here is an unsaved change; Cancel confirms, takes it away again, then leaves", async () => {
    const pushed: string[] = [];
    nav.push = (to) => pushed.push(to);
    await mount([
      (m, u) => (m === "POST" && u === "/api/links" ? { body: LINK } : undefined),
      (m, u) => (m === "DELETE" && u === `/api/files/${LINK.id}` ? { status: 204 } : undefined),
      ...base(),
    ]);
    await addLink("https://intranet.kfintech.example/codes");
    expect(document.body.textContent).toContain(LINK.name);
    expect(status()).toBe("Unsaved changes");
    expect(await follows(link("Cancel"))).toBe(false);
    expect(text(document.querySelector(".ed-confirm"))).toBe(CONFIRM);
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
    // The second Cancel takes the link away first, then goes back to the idea.
    expect(await follows(link("Cancel"))).toBe(false);
    expect(calls.filter((c) => c.method === "DELETE").map((c) => c.url)).toEqual([`/api/files/${LINK.id}`]);
    expect(pushed).toEqual([`/ideas/${REF}`]);
    expect(saves()).toEqual([]);
  });

  it("BLD-C161 L-SUBMIT.edit/4: Save records the files added and removed here, so a file-only save is a version", async () => {
    await mount([
      (m, u) => (m === "POST" && u === "/api/links" ? { body: LINK } : undefined),
      (m, u) => (m === "DELETE" && u === `/api/files/${SHOWN.id}` ? { status: 204 } : undefined),
      (m, u) =>
        m === "PATCH" && u === URL_EDIT
          ? {
              body: {
                version: { n: 2, changed_fields: ["files"], at: "2026-11-15T08:09:00Z" },
                changed_fields: ["files"],
                message: SAVED,
                next: { to: `/ideas/${REF}`, replace: true },
              },
            }
          : undefined,
      ...base(() => page({ files: [SHOWN] as unknown as EditPageResponse["files"] })),
    ]);
    expect(status()).toBe("Saved");
    await click(button(`Remove ${SHOWN.name}`));
    expect(status()).toBe("Unsaved changes");
    await addLink("https://intranet.kfintech.example/codes");
    await click(button("Save changes"));
    expect(saves()[0]!.body).toEqual({
      files: { added: [LINK.id], removed: [SHOWN.id] },
      declaration_version: "1pc-2026-11",
    });
    expect(all('[role="status"]').some((s) => text(s) === SAVED)).toBe(true);
    expect(status()).toBe("Saved at 1:39 pm");
    expect(link("Cancel")).toBeUndefined();
  });
});

describe("S-06B review: leaving with unsaved changes (BLD-C163, item 1)", () => {
  it("S-06B.layout/7: any other link on the page (the side bar, the bar's Back to your idea) confirms first, then leaves", async () => {
    await mount(base());
    const side = document.createElement("a");
    side.href = "/home";
    side.textContent = "Home";
    document.body.prepend(side);
    expect(await follows(side)).toBe(true);
    await retitle("Investors call about a redemption not processed");
    expect(await follows(side)).toBe(false);
    expect(text(document.querySelector(".ed-confirm"))).toBe(CONFIRM);
    expect(document.querySelector(".ed-confirm")?.getAttribute("role")).toBe("alert");
    expect(await follows(document.querySelector(".tbar a") ?? undefined)).toBe(true);
  });

  it("S-06B.layout/7: a change made after the confirm asks again; the bar's close is guarded too", async () => {
    await mount(base());
    await retitle("Investors call about a redemption not processed");
    expect(await follows(document.querySelector(".tbar a") ?? undefined)).toBe(false);
    expect(text(document.querySelector(".ed-confirm"))).toBe(CONFIRM);
    await retitle("Investors call about a redemption not yet processed");
    expect(document.querySelector(".ed-confirm")).toBeNull();
    expect(await follows(link("Cancel"))).toBe(false);
  });

  it("S-06B: closing or reloading the tab with unsaved changes asks the browser's question; with none it does not", async () => {
    await mount(base());
    const leave = () => {
      const e = new Event("beforeunload", { cancelable: true });
      window.dispatchEvent(e);
      return e.defaultPrevented;
    };
    expect(leave()).toBe(false);
    await retitle("Investors call about a redemption not processed");
    expect(leave()).toBe(true);
  });
});

describe("S-06B review: the words go on to the conversation (S-06B.rules/2, BLD-C165)", () => {
  it("S-06B.rules/2: Open the conversation keeps the changed words for the message box in sessionStorage, never in the URL", async () => {
    await mount([
      (m, u) =>
        m === "PATCH" && u === URL_EDIT
          ? {
              status: 409,
              body: {
                error: { code: "edit_window_closed", message: CLOSED, to: `/ideas/${REF}/conversation` },
              },
            }
          : undefined,
      ...base(),
    ]);
    await retitle("Investors call about a redemption not processed");
    await click(button("Change how often"));
    const often = document.querySelector<HTMLInputElement>('input[aria-label="How often"]');
    await type(often, "About 50 calls a day at one branch");
    await act(async () => {
      often!.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    });
    await settle();
    await click(button("Save changes"));
    const open = link("Open the conversation")!;
    expect(open.getAttribute("href")).toBe(`/ideas/${REF}/conversation`);
    expect(window.sessionStorage.getItem(`1pc.conversation.prefill.${REF}`)).toBeNull();
    // It goes as it is: no confirm, and the words wait for the conversation's box.
    expect(await follows(open)).toBe(true);
    expect(document.querySelector(".ed-confirm")).toBeNull();
    expect(window.sessionStorage.getItem(`1pc.conversation.prefill.${REF}`)).toBe(
      "Title: Investors call about a redemption not processed\n\nHow often: About 50 calls a day at one branch",
    );
  });

  it("S-06B.rules/2: words only: a sorting change carries nothing, and storage that cannot be used never stops the way on", async () => {
    const p = page();
    const s = model.initialState(p, EMPTY_FIX, EMPTY_FIX);
    const labels = {
      title: "Title",
      summary: "What happens",
      often: "How often",
      how: "How would you solve it?",
    };
    expect(model.prefillText(p, { ...s, sorting: { area: "Operations" } }, labels)).toBe("");
    const form = { ...EMPTY_FIX, how: "Send the reason in plain words with the code." };
    const withFix = {
      ...s,
      fix: { part: { kind: "added" as const, line: "", fixLine: "" }, form, touched: true },
    };
    expect(model.prefillText(p, withFix, labels)).toBe(
      "How would you solve it? Send the reason in plain words with the code.",
    );
    const { putPrefill } = await import("@/components/convo/prefill");
    const restore = blockStorage();
    try {
      expect(putPrefill(REF, "Title: x")).toBe(false);
    } finally {
      restore();
    }
  });
});

describe("S-06B review: the closed page, the phone and the saved line (items 4, 5, minors)", () => {
  it("L-SUBMIT.edit/5: a closed window without a line shows no empty status", async () => {
    await mount(base(() => page({ window: { open: false } })));
    expect(document.querySelector('.ed-closed [role="status"]')).toBeNull();
    expect(link("Open the conversation")).toBeTruthy();
  });

  it("PhoneEdit S-06B item 5: the phone's bar reads Cancel before saving and Back to your idea once saved, once", async () => {
    phoneScreen();
    await mount([
      (m, u) =>
        m === "PATCH" && u === URL_EDIT
          ? {
              body: {
                version: { n: 2, changed_fields: ["title"], at: "2026-11-15T08:09:00Z" },
                changed_fields: ["title"],
                message: SAVED,
                next: { to: `/ideas/${REF}`, replace: true },
              },
            }
          : undefined,
      ...base(),
    ]);
    expect(text(document.querySelector(".tbar a"))).toBe("Cancel");
    await click(button("Change title"));
    const input = document.querySelector<HTMLInputElement>('input[aria-label="Title"]');
    await type(input, "Investors call about a redemption not processed");
    await act(async () => {
      input!.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    });
    await settle();
    // The bar's Cancel goes through the same confirm as the dock's.
    expect(await follows(document.querySelector(".tbar a") ?? undefined)).toBe(false);
    expect(text(document.querySelector(".ed-confirm"))).toBe(CONFIRM);
    await click(button("Save changes"));
    expect(text(document.querySelector(".tbar a"))).toBe("Back to your idea");
    expect(all("a").filter((a) => text(a) === "Back to your idea")).toHaveLength(1);
  });

  it("PhoneEdit declaration_changed: the dock shows the server's new declaration, and the next Save sends its version", async () => {
    phoneScreen();
    const NEW =
      "By saving, you confirm there’s no customer personal data in it or its files, and that it’s your own work.";
    let first = true;
    await mount([
      (m, u) => {
        if (m !== "PATCH" || u !== URL_EDIT) return undefined;
        if (first) {
          first = false;
          return {
            status: 409,
            body: {
              error: {
                code: "declaration_changed",
                message: "The declaration beside Save has changed. Read it again, then save.",
                field: "declaration",
                version: "1pc-2026-12",
                text: NEW,
              },
            },
          };
        }
        return { body: { version: null, changed_fields: [], message: "Nothing has changed." } };
      },
      ...base(),
    ]);
    await click(button("Save changes"));
    const dock = document.querySelector(".dock");
    expect(text(dock)).toContain(NEW);
    expect(text(dock)).not.toContain("Saving confirms there’s no customer personal data");
    await click(button("Save changes"));
    expect(saves()[1]!.body).toEqual({ declaration_version: "1pc-2026-12" });
  });

  it("WCAG 4.1.3: the saved line's status region is on the page, empty, before Save puts its words in it", async () => {
    await mount([
      (m, u) =>
        m === "PATCH" && u === URL_EDIT
          ? { body: { version: null, changed_fields: [], message: "Nothing has changed." } }
          : undefined,
      ...base(),
    ]);
    const live = document.querySelector(".ed-live");
    expect(live?.getAttribute("role")).toBe("status");
    expect(text(live)).toBe("");
    await click(button("Save changes"));
    expect(document.querySelector(".ed-live")).toBe(live);
    expect(text(live)).toBe("Nothing has changed.");
  });

  it("S-06B: a change made while Save is on its way is kept, not overwritten by the page read after it", async () => {
    let answer: (v: unknown) => void = () => undefined;
    vi.spyOn(api, "saveEdit").mockImplementation(
      () =>
        new Promise((resolve) => {
          answer = resolve as (v: unknown) => void;
        }) as never,
    );
    let reads = 0;
    await mount([
      (m, u) =>
        m === "GET" && u === URL_EDIT
          ? {
              body:
                reads++ === 0
                  ? page()
                  : page({
                      fields: { ...page().fields, title: "Investors call about a redemption not processed" },
                    }),
            }
          : undefined,
      ...base(),
    ]);
    await retitle("Investors call about a redemption not processed");
    await click(button("Save changes"));
    await click(button("Change how often"));
    const often = document.querySelector<HTMLInputElement>('input[aria-label="How often"]');
    await type(often, "About 50 calls a day at one branch");
    await act(async () => {
      often!.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    });
    await settle();
    await act(async () =>
      answer({
        ok: true,
        status: 200,
        body: {
          version: { n: 2, changed_fields: ["title"], at: "2026-11-15T08:09:00Z" },
          changed_fields: ["title"],
          message: SAVED,
        },
      }),
    );
    await settle();
    expect(text(document.querySelector("h3"))).toBe("Investors call about a redemption not processed");
    expect(document.body.textContent).toContain("About 50 calls a day at one branch");
    expect(status()).toBe("Unsaved changes");
  });
});

describe("S-06B words (F-COPY)", () => {
  it("never says duplicate, rejected, already solved, appeal, invalid or Garage to the sharer", () => {
    const words = JSON.stringify(EDIT_COPY);
    for (const w of [/duplicate/i, /\brejected\b/i, /already solved/i, /appeal/i, /invalid/i, /garage/i]) {
      expect(words).not.toMatch(w);
    }
  });
});
