// @vitest-environment jsdom
/**
 * S-08's "+" (DEC-124, walk item WF-01; lane F, BLD-F095), against a mocked A-API: S-08.layout/3 ("the box with
 * attach"), C-PROMPT.attach and C-FILE.row in the conversation's box. The "+" only for the readers who may attach
 * (`composer.can_attach`), first in the box's tool row; the picker with the Home board's words and no link line;
 * each file through `POST /api/files` with the idea's reference and `for: "conversation"`; its row with "Checked" and
 * "Remove {name}" (DELETE); a file with a customer detail says it can't be sent in the conversation, never Check it's
 * line about who opens it; Send carries the files' ids and the worker's refusal shows under the box; a typed link goes
 * into the words; a sent file's View opens where the server says. Synthetic people, words and files only.
 */
import { act, createElement, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) =>
    createElement("a", { href, ...rest }, children),
}));

const { Conversation } = await import("@/components/convo/conversation");
const { S08_COPY, putLink } = await import("@/components/convo/compose");
const { convoRowView, sendable } = await import("@/components/convo/attach");
const { ATTACH_NAME } = await import("@/components/ui/attach-button");
const { BOX_FILES_COPY } = await import("@/app/share/box-files");
type View = import("@/lib/contracts").ConversationView;
type Entry = View["entries"][number];
type FileItem = import("@/lib/contracts").FileItem;

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// --- Fixtures (synthetic: the pack's fictional cast) -------------------------------------------------------------
const IDEA = "IDEA-2026-001481";
const KAVYA = { id: "u-kavya", name: "Kavya Menon", first_name: "Kavya", initials: "KM" };
const DESK = { id: "", name: "The review desk", first_name: "The review desk", initials: "" };
const CONFIG = {
  limit_mb: 25,
  types: ["pdf", "md", "png", "xlsx"],
  help_text: "PDF, Markdown, images or Excel or a whole folder, up to 25 MB each.",
};
/** Check it's line for a found file (DEC-107, BLD-C199): about who opens it, so never on S-08. */
const CHECK_IT_FOUND = "Only you, the review desk and the Ones Committee can open it.";
/** The worker's words (services/worker/convo/messages.py), as the route passes them on. */
const FILE_HAS_DETAIL =
  "This file has a customer detail in it, so it can’t be sent in the conversation. Remove it first.";
const FILE_NOT_CHECKED = "This file is still being checked. Send it once it shows as checked.";

function fileItem(id: string, name: string, over: Partial<FileItem> = {}): FileItem {
  return {
    id,
    kind: "file",
    name,
    type: "text/markdown",
    size: 2048,
    state: "checked",
    added_by: KAVYA,
    added_at: "2026-11-21T10:00:00+05:30",
    ...over,
  };
}

function message(id: string, text: string, files: FileItem[]): Entry {
  return {
    type: "message",
    id,
    from: KAVYA,
    from_label: "You",
    you: true,
    text,
    files,
    at: "2026-11-21T10:12:00+05:30",
    at_label: "Today, 10:12 am",
    mentions: [],
    mentions_you: false,
    removed: false,
  } as Entry;
}

/** Kavya's own idea with the review desk: she may attach (BLD-F063). */
function sharerView(over: Partial<View> = {}): View {
  return {
    idea: {
      id: IDEA,
      title: "Investors call to ask why a redemption was rejected",
      status: "with_review_desk",
    },
    audience: "you_and_desk",
    header: { whose: "Your idea", line: "Your idea, shared Saturday 14 November" },
    participants: [
      { person: DESK, label: "The review desk", doing: "Reviewing it", you: false },
      { person: KAVYA, label: "You", doing: "Shared the idea", you: true },
    ],
    entries: [
      {
        type: "event",
        id: "e-open",
        code: "desk.opened",
        text: "The review desk opened it. Monday 16 November, 9:50 am",
        at: "2026-11-16T09:50:00+05:30",
      } as Entry,
    ],
    composer: {
      placeholder: "Message the review desk",
      visibility: "Only you and the review desk see this conversation.",
      can_attach: true,
    },
    teams_on: false,
    ...over,
  } as View;
}

/** The same idea as a crew member reads it: no files to add (BLD-F063). */
function crewView(): View {
  const v = sharerView();
  return {
    ...v,
    audience: "crew_and_desk",
    composer: {
      placeholder: "Message the crew",
      visibility: "The crew and the review desk see this conversation.",
      can_attach: false,
    },
  } as View;
}

// --- A mocked A-API ----------------------------------------------------------------------------------------------
type Call = { method: string; url: string; json: Record<string, unknown> | null; form: FormData | null };
type Answer = { status: number; body?: unknown };
let calls: Call[];
let routes: Array<(c: Call) => Answer | undefined>;
let uploaded: number;
/** What `POST /api/files` answers for the next file: its state, and a problem line as lane C's route sends one. */
let nextFile: Partial<FileItem>;

function respond(c: Call): Answer {
  for (const r of routes) {
    const a = r(c);
    if (a) return a;
  }
  if (c.url.includes("/question-set"))
    return { status: 404, body: { error: { code: "not_found", message: "" } } };
  if (c.method === "GET" && c.url === "/api/config/uploads") return { status: 200, body: CONFIG };
  if (c.method === "POST" && c.url === "/api/files") {
    uploaded += 1;
    const file = c.form?.get("file") as File | null;
    return {
      status: 201,
      body: fileItem(`ATT-2026-00070${uploaded}`, file?.name ?? "file", { state: "checked", ...nextFile }),
    };
  }
  if (c.method === "DELETE" && c.url.startsWith("/api/files/")) return { status: 204 };
  return { status: 404, body: { error: { code: "not_found", message: "" } } };
}

const fakeFetch = vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
  const body = init.body;
  const c: Call = {
    method: (init.method ?? "GET").toUpperCase(),
    url: String(input),
    json: typeof body === "string" ? (JSON.parse(body) as Record<string, unknown>) : null,
    form: body instanceof FormData ? body : null,
  };
  calls.push(c);
  const a = respond(c);
  return new Response(a.body === undefined ? null : JSON.stringify(a.body), {
    status: a.status,
    headers: { "Content-Type": "application/json" },
  });
});

let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  calls = [];
  routes = [];
  uploaded = 0;
  nextFile = {};
  vi.stubGlobal("fetch", fakeFetch);
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

/** Lets the mocked calls answer and React settle. */
async function flush(rounds = 12) {
  for (let i = 0; i < rounds; i++) await act(async () => await Promise.resolve());
}

async function frame() {
  await act(async () => await new Promise<void>((r) => requestAnimationFrame(() => r())));
}

/** The width S-08 lays out for: jsdom has no `matchMedia`, which is the phone's layout (as the server draws it). */
function wide() {
  vi.stubGlobal(
    "matchMedia",
    vi.fn((q: string) => ({
      matches: false,
      media: q,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  );
}

async function show(view: View) {
  await act(async () => {
    root.render(createElement(Conversation, { initial: view, ideaId: view.idea.id, now: () => Date.now() }));
  });
}

/** The name a screen reader hears: aria-label, else the words less anything aria-hidden. */
function nameOf(el: Element): string {
  const label = el.getAttribute("aria-label");
  if (label) return label;
  const copy = el.cloneNode(true) as Element;
  copy.querySelectorAll('[aria-hidden="true"]').forEach((x) => x.remove());
  return (copy.textContent ?? "").trim();
}

function named(name: string): HTMLButtonElement | HTMLAnchorElement | undefined {
  return [...host.querySelectorAll<HTMLButtonElement | HTMLAnchorElement>("button, a")].find(
    (b) => nameOf(b) === name,
  );
}

const plus = () => named(ATTACH_NAME) as HTMLButtonElement | undefined;
const textbox = () => host.querySelector("textarea")!;
const rows = () => host.querySelector<HTMLUListElement>(`ul[aria-label="${S08_COPY.files}"]`);
const posts = (url: string) => calls.filter((c) => c.method === "POST" && c.url === url);

async function openPicker(): Promise<HTMLElement> {
  await act(async () => plus()!.click());
  await flush();
  return document.getElementById(plus()!.getAttribute("aria-controls")!)!;
}

async function choose(files: File[]) {
  const input = host.querySelector<HTMLInputElement>(".cv-pick input[type=file]:not([webkitdirectory])")!;
  Object.defineProperty(input, "files", { value: files, configurable: true });
  await act(async () => {
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
}

const md = (name: string, words = "Calls about R07, week 47: about 40 a day.") =>
  new File([words], name, { type: "text/markdown" });

async function type(value: string, caret = value.length) {
  const box = textbox();
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(box, value);
    box.setSelectionRange(caret, caret);
    box.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

async function typeLink(input: HTMLInputElement, value: string) {
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!.call(input, value);
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

async function send() {
  await act(async () => named(S08_COPY.send)!.click());
  await flush();
}

function alerts(): string[] {
  return [...host.querySelectorAll('[role="alert"]')].map((a) => (a.textContent ?? "").trim());
}

/** axe on the box (the "+", the picker, the rows), where this work is. */
async function axeSerious(): Promise<string[]> {
  const axe = (await import("axe-core")).default;
  const result = await axe.run(host.querySelector<HTMLElement>("form.cv-box")!, {
    rules: { "color-contrast": { enabled: false } },
    resultTypes: ["violations"],
  });
  return result.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
}

// --- The "+" ----------------------------------------------------------------------------------------------------
describe('S-08.layout/3, C-PROMPT.attach: the "+" only for those who may attach (DEC-124, BLD-F063, BLD-F095)', () => {
  for (const width of ["phone", "wide"] as const) {
    it(`S-08.layout/3 (${width}): the sharer's box has the "+", first in its tool row, named and titled "${ATTACH_NAME}"`, async () => {
      if (width === "wide") wide();
      await show(sharerView());
      const b = plus()!;
      expect(b).toBeTruthy();
      expect(b.getAttribute("title")).toBe(ATTACH_NAME);
      expect(b.getAttribute("type")).toBe("button");
      expect(b.getAttribute("aria-expanded")).toBe("false");
      expect(b.hasAttribute("aria-controls")).toBe(false); // named only while the picker is there
      const row = host.querySelector("form.cv-box .cv-row.cfoot")!;
      expect(row.classList.contains("with-attach")).toBe(true);
      expect(row.querySelector("button, a")).toBe(b); // first in the tool row (lane G's `.cfoot`)
      // On a phone it comes before the words, as PhoneMessages draws it; wider, after them (Messages.jpg)
      const field = row.querySelector(".cv-field")!;
      const before = Boolean(b.compareDocumentPosition(field) & Node.DOCUMENT_POSITION_FOLLOWING);
      expect(before).toBe(width === "phone");
      expect(calls).toEqual([]); // the upload config is read only when the picker opens
      expect(await axeSerious()).toEqual([]);
    });
  }

  it('BLD-F063: the crew\'s box has no "+", no picker and no file input; the row keeps its shape', async () => {
    await show(crewView());
    expect(plus()).toBeUndefined();
    expect(host.querySelector('input[type="file"]')).toBeNull();
    const row = host.querySelector("form.cv-box .cv-row")!;
    expect(row.classList.contains("with-attach")).toBe(false);
    expect(row.querySelectorAll("button")).toHaveLength(1); // Send only
    expect(textbox().getAttribute("aria-label")).toBe("Message the crew");
  });

  it('L-MERGE.effects/6: a closed conversation has no box, so no "+" either', async () => {
    await show(
      sharerView({
        composer: {
          ...sharerView().composer,
          closed: "This idea is now part of IDEA-2026-001412. Write there.",
        },
      } as Partial<View>),
    );
    expect(host.querySelector("form.cv-box")).toBeNull();
    expect(plus()).toBeUndefined();
  });
});

// --- The picker ---------------------------------------------------------------------------------------------------
describe('C-FILE.uploader in S-08\'s box: the picker the "+" opens (BLD-F095)', () => {
  it('C-PROMPT.attach: the Home board\'s picker and words, no link line; Escape closes it and focus goes back to the "+"', async () => {
    wide();
    await show(sharerView());
    const picker = await openPicker();
    const b = plus()!;
    expect(b.getAttribute("aria-expanded")).toBe("true");
    expect(picker.classList.contains("cv-pick")).toBe(true);
    expect(calls.map((c) => `${c.method} ${c.url}`)).toEqual(["GET /api/config/uploads"]);
    expect(picker.textContent).toContain(`${BOX_FILES_COPY.dropTitle} ${BOX_FILES_COPY.browse}`);
    expect(picker.textContent).toContain(`${CONFIG.help_text} ${BOX_FILES_COPY.folderLine}`);
    expect(picker.textContent).not.toContain(BOX_FILES_COPY.linkLine); // a link is not marked here (BLD-F095)
    for (const name of ["browse", "Choose a folder", "Add link"]) expect(named(name), name).toBeTruthy();
    const link = picker.querySelector<HTMLInputElement>("input[type=url]")!;
    expect(document.querySelector(`label[for="${link.id}"]`)?.textContent).toBe(
      "Or paste a link to a page, file or idea",
    );
    expect(picker.querySelector("input[webkitdirectory]")).toBeTruthy();
    expect(await axeSerious()).toEqual([]);
    await act(async () => {
      link.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    });
    await frame();
    expect(host.querySelector(".cv-pick")).toBeNull();
    expect(plus()!.getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(plus());
  });

  it('the "+" closes the picker it opened, and Escape on the "+" does too', async () => {
    await show(sharerView());
    await openPicker();
    await act(async () => plus()!.click());
    expect(host.querySelector(".cv-pick")).toBeNull();
    await openPicker();
    await act(async () => {
      plus()!.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    });
    await frame();
    expect(host.querySelector(".cv-pick")).toBeNull();
    expect(document.activeElement).toBe(plus());
  });
});

// --- Files -------------------------------------------------------------------------------------------------------
describe("C-FILE.row in S-08's box: upload, Remove, a found file (DEC-107, BLD-F095)", () => {
  it('A-API.files: each file goes to POST /api/files with the idea\'s reference and for: "conversation"; its row reads Checked, with Remove {name}', async () => {
    wide();
    await show(sharerView());
    await openPicker();
    await choose([md("branch-call-log.md")]);
    await frame();
    const [post] = posts("/api/files");
    expect(post).toBeTruthy();
    expect(post!.form!.get("idea_id")).toBe(IDEA);
    expect(post!.form!.get("for")).toBe("conversation");
    expect((post!.form!.get("file") as File).name).toBe("branch-call-log.md");
    expect([...post!.form!.keys()].sort()).toEqual(["file", "for", "idea_id"]); // never a draft or an answer
    expect(host.querySelector(".cv-pick")).toBeNull(); // the picker closes once files are chosen
    expect(document.activeElement).toBe(plus());
    const list = rows()!;
    expect(list.getAttribute("role")).toBe("list");
    const [row] = [...list.querySelectorAll("li")];
    expect(row!.textContent).toContain("branch-call-log.md");
    expect(row!.textContent).toContain("Checked");
    expect(row!.querySelector(".fmsg")).toBeNull();
    const remove = named("Remove branch-call-log.md")!;
    expect(remove.getAttribute("title")).toBe("Remove branch-call-log.md");
    expect(row!.contains(remove)).toBe(true);
    expect(named("View branch-call-log.md")).toBeUndefined(); // the box offers no View, as on Home
    expect(await axeSerious()).toEqual([]);
  });

  it("Remove {name} deletes the file (DELETE /api/files/:id); its row goes and focus is back in the box", async () => {
    await show(sharerView());
    await openPicker();
    await choose([md("branch-call-log.md")]);
    await frame(); // focus is back on the "+" once the picker has closed
    await act(async () => named("Remove branch-call-log.md")!.click());
    await flush();
    expect(calls.filter((c) => c.method === "DELETE").map((c) => c.url)).toEqual([
      "/api/files/ATT-2026-000701",
    ]);
    expect(rows()).toBeNull();
    expect(document.activeElement).toBe(textbox());
  });

  it("DEC-107: a file with a customer detail says it can't be sent in the conversation, offers Remove, and never shows Check it's line", async () => {
    nextFile = {
      state: "personal_data_found",
      problem: `Found a phone number on page 1. ${CHECK_IT_FOUND}`,
      view_url: "/api/files/ATT-2026-000701/view",
    };
    await show(sharerView());
    await openPicker();
    await choose([md("calls-with-a-number.md")]);
    const [row] = [...rows()!.querySelectorAll("li")];
    expect(row!.querySelector(".fmsg.warn")?.textContent?.trim()).toBe(S08_COPY.fileHasDetail);
    expect(S08_COPY.fileHasDetail).toBe(
      "This file has a customer detail in it, so it can’t be sent in the conversation. Remove it to send your message.",
    );
    expect(host.textContent).not.toContain(CHECK_IT_FOUND);
    expect(host.textContent).not.toContain("Hide it for me");
    expect([...row!.querySelectorAll("button, a")].map(nameOf)).toEqual(["Remove calls-with-a-number.md"]);

    // Alone in the box, Send goes to the worker, which refuses it in its own words; nothing is sent and it stays
    routes.push((c) =>
      c.method === "POST" && c.url === `/api/ideas/${IDEA}/conversation/messages`
        ? {
            status: 422,
            body: { error: { code: "file_has_detail", message: FILE_HAS_DETAIL, field: "file_ids" } },
          }
        : undefined,
    );
    await send();
    const [msg] = posts(`/api/ideas/${IDEA}/conversation/messages`);
    expect(msg!.json).toEqual({ text: "", mentions: [], file_ids: ["ATT-2026-000701"] });
    expect(alerts()).toContain(FILE_HAS_DETAIL);
    expect(rows()!.textContent).toContain("calls-with-a-number.md");
    // Removed, the box is empty: S-08.rules/2's words, and nothing is sent
    await act(async () => named("Remove calls-with-a-number.md")!.click());
    await flush();
    await send();
    expect(posts(`/api/ideas/${IDEA}/conversation/messages`)).toHaveLength(1);
    expect(alerts()).toEqual(["Write a message or attach a file first."]);
  });

  it("L-CONVO/7: a file still being checked goes with the message's ids; the worker's line says to wait, and nothing is sent", async () => {
    nextFile = { state: "checking" };
    routes.push((c) =>
      c.method === "POST" && c.url === `/api/ideas/${IDEA}/conversation/messages`
        ? {
            status: 422,
            body: { error: { code: "file_not_checked", message: FILE_NOT_CHECKED, field: "file_ids" } },
          }
        : undefined,
    );
    await show(sharerView());
    await openPicker();
    await choose([md("still-checking.md")]);
    expect(rows()!.textContent).toContain("Checking for personal details");
    await type("The call log for week 47.");
    await send();
    const [msg] = posts(`/api/ideas/${IDEA}/conversation/messages`);
    expect(msg!.json!.file_ids).toEqual(["ATT-2026-000701"]);
    expect(alerts()).toContain(FILE_NOT_CHECKED);
    expect(textbox().value).toBe("The call log for week 47."); // the words stay
    expect(rows()!.textContent).toContain("still-checking.md");
  });

  it("C-FILE.row BLD-C237 (WCAG 2.2.2): a file whose check waits for the assistant shows the worker's line and no spinner; a running check keeps its spinner", async () => {
    const WAITING = "Waiting for the personal details check. It runs when the assistant is back.";
    nextFile = { state: "checking", problem: WAITING };
    await show(sharerView());
    await openPicker();
    await choose([md("week-47-calls.md")]);
    expect(rows()!.textContent).toContain(WAITING);
    expect(rows()!.querySelector(".spin")).toBeNull();
    nextFile = { state: "checking" };
    await openPicker();
    await choose([md("still-checking.md")]);
    const [waits, runs] = Array.from(rows()!.querySelectorAll("li"));
    expect(waits!.querySelector(".spin")).toBeNull();
    expect(runs!.textContent).toContain("Checking for personal details");
    expect(runs!.querySelector(".spin")).not.toBeNull();
  });
});

// --- Sending -----------------------------------------------------------------------------------------------------
describe("L-CONVO/5, L-CONVO/7: Send carries the files (BLD-F095)", () => {
  it("send carries file_ids with the words; once sent the rows leave the box and the message shows its file with View", async () => {
    wide();
    const sent = message("m-new", "The call log for week 47.", [
      fileItem("ATT-2026-000701", "branch-call-log.md", { view_url: "/api/files/ATT-2026-000701/view" }),
    ]);
    routes.push((c) => {
      if (c.method === "POST" && c.url === `/api/ideas/${IDEA}/conversation/messages`)
        return { status: 201, body: { entry: sent, hidden: 0 } };
      if (c.method === "GET" && c.url === `/api/ideas/${IDEA}/conversation`)
        return { status: 200, body: sharerView({ entries: [...sharerView().entries, sent] }) };
      return undefined;
    });
    await show(sharerView());
    await openPicker();
    await choose([md("branch-call-log.md")]);
    await type("The call log for week 47.");
    await send();
    const [msg] = posts(`/api/ideas/${IDEA}/conversation/messages`);
    expect(msg!.json).toEqual({
      text: "The call log for week 47.",
      mentions: [],
      file_ids: ["ATT-2026-000701"],
    });
    expect(rows()).toBeNull();
    expect(textbox().value).toBe("");
    const files = host.querySelector('ul[aria-label="Files in your message"]')!;
    expect(files.textContent).toContain("branch-call-log.md");
    const view = named("View branch-call-log.md") as HTMLAnchorElement;
    expect(view.getAttribute("href")).toBe("/api/files/ATT-2026-000701/view");
    expect(alerts()).toEqual([]);
  });

  it("words alone send as before, with no file_ids (L-CONVO/5)", async () => {
    routes.push((c) =>
      c.method === "POST" && c.url === `/api/ideas/${IDEA}/conversation/messages`
        ? { status: 201, body: { entry: message("m-new", "Hello.", []), hidden: 0 } }
        : undefined,
    );
    await show(sharerView());
    await type("Hello.");
    await send();
    expect(posts(`/api/ideas/${IDEA}/conversation/messages`)[0]!.json).toEqual({
      text: "Hello.",
      mentions: [],
    });
  });

  it("BLD-F095: View on a sent file goes where the server says: /api/files/:id/view, or /api/attachments/:id for a file from before the cut-over", async () => {
    await show(
      sharerView({
        entries: [
          message("m-two", "Both logs.", [
            fileItem("ATT-2026-000711", "branch-call-log.md", {
              view_url: "/api/files/ATT-2026-000711/view",
            }),
            fileItem("ATT-2026-000045", "old-call-log.xlsx", {
              view_url: "/api/attachments/ATT-2026-000045",
            }),
          ]),
        ],
      }),
    );
    expect(named("View branch-call-log.md")!.getAttribute("href")).toBe("/api/files/ATT-2026-000711/view");
    expect(named("View old-call-log.xlsx")!.getAttribute("href")).toBe("/api/attachments/ATT-2026-000045");
  });
});

// --- Links -------------------------------------------------------------------------------------------------------
describe("C-FILE.uploader/3 on S-08: a link goes into the words, never fetched (non-negotiable 8, BLD-F095)", () => {
  it("Add link puts the link into the box as typed, at the caret, and closes the picker; nothing is posted", async () => {
    await show(sharerView());
    await type("See for the R07 list.", 3);
    const picker = await openPicker();
    const link = picker.querySelector<HTMLInputElement>("input[type=url]")!;
    await typeLink(link, "  intranet.kfintech.com/ops/R07 ");
    await act(async () => named("Add link")!.click());
    await flush();
    expect(textbox().value).toBe("See intranet.kfintech.com/ops/R07 for the R07 list.");
    expect(host.querySelector(".cv-pick")).toBeNull();
    expect(calls.filter((c) => c.method !== "GET")).toEqual([]); // no /api/links, no upload
    expect(rows()).toBeNull(); // a link is never a row here
    expect(document.activeElement).toBe(textbox());
  });

  it("Enter in the link field adds it at the end of the words, never sends the message", async () => {
    await show(sharerView());
    await type("The list:");
    const picker = await openPicker();
    const link = picker.querySelector<HTMLInputElement>("input[type=url]")!;
    await typeLink(link, "https://kfintech.sharepoint.com/ops/R07");
    await act(async () => {
      link.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
    });
    await flush();
    expect(textbox().value).toBe("The list: https://kfintech.sharepoint.com/ops/R07 ");
    expect(posts(`/api/ideas/${IDEA}/conversation/messages`)).toHaveLength(0);
  });

  it("something that is not a link is said so, in Check it's words, and stays out of the box", async () => {
    await show(sharerView());
    const picker = await openPicker();
    const link = picker.querySelector<HTMLInputElement>("input[type=url]")!;
    await typeLink(link, "call me");
    await act(async () => named("Add link")!.click());
    expect(alerts()).toEqual([
      "That doesn’t look like a link. A link looks like intranet.kfintech.com/page.",
    ]);
    expect(link.getAttribute("aria-invalid")).toBe("true");
    expect(textbox().value).toBe("");
  });

  it("putLink: at the caret or the end, with a space either side, and the caret after it", () => {
    expect(putLink("", null, "a.com/x")).toEqual({ text: "a.com/x ", caret: 8 });
    expect(putLink("Hello", undefined, "a.com/x")).toEqual({ text: "Hello a.com/x ", caret: 14 });
    expect(putLink("Hello ", 6, "a.com/x")).toEqual({ text: "Hello a.com/x ", caret: 14 });
    expect(putLink("See the list", 3, "a.com/x")).toEqual({ text: "See a.com/x the list", caret: 11 });
    expect(putLink("See the list", 4, "a.com/x")).toEqual({ text: "See a.com/x the list", caret: 12 });
    expect(putLink("abc", 99, "a.com/x")).toEqual({ text: "abc a.com/x ", caret: 12 });
  });
});

// --- The rules on their own ---------------------------------------------------------------------------------------
describe("BLD-F095 helpers", () => {
  it("sendable: a file on the server that has not failed; never a link, a local row or a failed one", () => {
    const row = (over: Partial<FileItem> | null, extra: object = {}) => ({
      key: "k",
      name: "f.md",
      item: over === null ? null : fileItem("ATT-2026-000701", "f.md", over),
      ...extra,
    });
    expect(sendable(row({}))).toBe(true);
    expect(sendable(row({ state: "checking" }))).toBe(true); // the worker says to wait
    expect(sendable(row({ state: "personal_data_found" }))).toBe(true); // the worker refuses it in its words
    for (const state of ["upload_failed", "infected", "locked", "too_big"] as const)
      expect(sendable(row({ state })), state).toBe(false);
    expect(sendable(row({ kind: "link", state: "ok" }))).toBe(false);
    expect(sendable(row(null, { localState: "uploading" }))).toBe(false);
    expect(sendable(row({}, { localState: "refused" }))).toBe(false);
  });

  it("convoRowView: a found row's line is S-08's and its only action is Remove; a checked row keeps Remove only", () => {
    const found = convoRowView(
      {
        key: "k",
        name: "f.md",
        item: fileItem("ATT-2026-000701", "f.md", {
          state: "personal_data_found",
          problem: `Found a phone number on page 1. ${CHECK_IT_FOUND}`,
          view_url: "/api/files/ATT-2026-000701/view",
        }),
      },
      25,
    );
    expect(found.status).toBe("found");
    expect(found.message).toEqual({ kind: "warn", text: S08_COPY.fileHasDetail });
    expect(found.actions).toEqual(["remove"]);
    const checked = convoRowView(
      {
        key: "k",
        name: "f.md",
        item: fileItem("ATT-2026-000701", "f.md", { view_url: "/api/files/ATT-2026-000701/view" }),
      },
      25,
    );
    expect(checked.statusText).toBe("Checked");
    expect(checked.actions).toEqual(["remove"]);
  });
});
