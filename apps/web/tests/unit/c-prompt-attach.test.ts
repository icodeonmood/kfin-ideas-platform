// @vitest-environment jsdom
/**
 * V-ACC for the walk's WF-01 and WF-04 (DEC-124, DEC-125; BLD-C212 to BLD-C215), against a mocked A-API.
 * C-PROMPT.attach: the "+" ("Add files, a folder or a link") first in the box's tool row on Home (S-03), Share a
 * problem (S-04) and the draft page (S-04B), on a desk and on a phone; the picker as the Home board draws it; a file
 * added shows as a row in the box with "Remove {name}"; on Home and an empty S-04 the first file makes the draft once
 * (POST /api/drafts, the same call as the first send), a second file does not make another, and Home's send continues
 * into THAT draft; the draft page puts the draft's files back in the box.
 * S-04B in Capture first (`ai.all` off): no draft panel and no "Forms as you write", the full width, and the tool row
 * "+", Move to Review, its readiness line (tied with aria-describedby); the hint chips stay. Full mode keeps today's
 * design plus "+". The phone is unchanged except "+". axe on each state. Synthetic words and files only.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Draft, FileItem } from "@/lib/contracts";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, replace: push, refresh: vi.fn() }) }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
    createElement("a", { href, ...rest }, children as never),
}));

const { HomeScreen } = await import("@/app/home/home");
const { Compose } = await import("@/app/share/compose");
const { ATTACH_NAME: ATTACH_LABEL } = await import("@/components/ui/attach-button");
const { PANEL_COPY, READINESS } = await import("@/components/compose/draft-panel");
const { boxFilesOf } = await import("@/app/share/box-files");

const DRAFT = "6f1c2a8e-3b4d-4e5f-8a9b-0c1d2e3f4a5b";
const KAVYA = { id: "u-1", name: "Kavya Menon", first_name: "Kavya", initials: "KM" };
const WORDS =
  "Investors who change their bank mandate at the branch wait a week before the new mandate shows. It happens about 25 times a week.";
const CONFIG = {
  limit_mb: 25,
  types: ["pdf", "png", "xlsx"],
  help_text: "PDF, Excel or images or a whole folder, up to 25 MB each.",
};

function fileItem(id: string, name: string, over: Partial<FileItem> = {}): FileItem {
  return {
    id,
    kind: "file",
    name,
    type: "application/pdf",
    size: 880_640,
    state: "checked",
    added_by: KAVYA,
    added_at: "2026-11-20T10:00:00.000Z",
    ...over,
  };
}

function draft(over: Partial<Draft> = {}): Draft {
  return {
    id: DRAFT,
    owner_id: "u-1",
    channel: "web",
    messages: [
      {
        id: "m-1",
        text: WORDS,
        at: "2026-11-20T10:00:00.000Z",
        at_label: "Just now",
        device: "laptop",
        via: "typed",
        files: [],
        spans: [],
      },
    ],
    parts: {
      title: { state: "failed", value: null },
      summary: { state: "failed", value: null },
      often: { state: "failed", value: null },
      who: { state: "failed", value: null },
      value: { state: "failed", value: null },
      area: { state: "failed", value: null },
      similar: { state: "failed", value: [] },
    } as unknown as Draft["parts"],
    hidden: [],
    sorting: {} as Draft["sorting"],
    files: [],
    step: "tell",
    saved_at: new Date().toISOString(),
    saved_on: { device: "laptop", this_device: true },
    saved_labels: {
      sidebar: "Today, on this laptop",
      resume: "Last saved on this laptop, 3:30 pm.",
      prompt_day: "Today",
      prompt_line: "Last saved on this laptop, 3:30 pm.",
      status: "Saved at 3:30 pm",
      my_ideas: "Saved 3:30 pm today, on this laptop",
    },
    ready: true,
    min_chars: 30,
    char_count: WORDS.length,
    receipt: ["Your draft is saved. Add a detail, or check it."],
    suggestions: ["Say how often it happens", "Say who feels it most"],
    run: { id: "r-0", state: "failed" },
    ...over,
  } as Draft;
}

// --- a mocked A-API --------------------------------------------------------------------------------------------

type Call = { method: string; url: string; json: Record<string, unknown> | null; form: FormData | null };
type Answer = { status: number; body?: unknown };
let calls: Call[];
let routes: Array<(c: Call) => Answer | undefined>;
let uploads: number;

function respond(c: Call): Answer {
  for (const r of routes) {
    const a = r(c);
    if (a) return a;
  }
  if (c.method === "GET" && c.url === "/api/config/uploads") return { status: 200, body: CONFIG };
  if (c.method === "POST" && c.url === "/api/files") {
    uploads += 1;
    const file = c.form?.get("file") as File | null;
    return {
      status: 201,
      body: fileItem(`ATT-2026-00010${uploads}`, file?.name ?? "file", { state: "checked" }),
    };
  }
  if (c.method === "DELETE" && c.url.startsWith("/api/files/")) return { status: 204 };
  if (c.method === "GET" && c.url === "/api/drafts?recent=1")
    return { status: 200, body: { items: [], total: 0 } };
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

let phone = false;
let host: HTMLDivElement;
let root: Root;

beforeEach(() => {
  calls = [];
  routes = [];
  uploads = 0;
  phone = false;
  push.mockReset();
  const mem = new Map<string, string>();
  const store = {
    getItem: (k: string) => mem.get(k) ?? null,
    setItem: (k: string, v: string) => void mem.set(k, String(v)),
    removeItem: (k: string) => void mem.delete(k),
    clear: () => mem.clear(),
  };
  vi.stubGlobal("localStorage", store);
  Object.defineProperty(window, "localStorage", { value: store, configurable: true });
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({ matches: phone, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
  );
  vi.stubGlobal(
    "EventSource",
    class {
      addEventListener() {}
      close() {}
    },
  );
  vi.stubGlobal("fetch", fakeFetch);
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

async function flush() {
  for (let i = 0; i < 8; i++) await act(async () => await Promise.resolve());
}

const text = () => (host.textContent ?? "").replace(/\s+/g, " ");
const named = (name: string) =>
  [...host.querySelectorAll<HTMLElement>("button, a")].find(
    (b) => (b.getAttribute("aria-label") ?? b.textContent ?? "").trim() === name,
  );
const plus = () => named(ATTACH_LABEL) as HTMLButtonElement | undefined;
/** The tool row's children, by what they are. */
function toolRow(): string[] {
  const foot = host.querySelector(".prompt .cfoot")!;
  return [...foot.children].map((el) => {
    const c = el.className;
    if (c.includes("attach-w")) return "+";
    if (c.includes("cmove")) return "move";
    if (c.includes("mic2")) return "mic";
    if (c.includes("sendw")) return "send";
    if (c.includes("cnt")) return "hint";
    return "status";
  });
}

async function openPicker() {
  await act(async () => plus()!.click());
  await flush();
}

async function choose(files: File[]) {
  const input = host.querySelector<HTMLInputElement>(".cpick input[type=file]:not([webkitdirectory])")!;
  Object.defineProperty(input, "files", { value: files, configurable: true });
  await act(async () => {
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await flush();
}

const pdf = (name: string) =>
  new File([new Uint8Array([37, 80, 68, 70, 45])], name, { type: "application/pdf" });

async function axeSerious(): Promise<string[]> {
  const axe = (await import("axe-core")).default;
  const result = await axe.run(host, {
    rules: { "color-contrast": { enabled: false } },
    resultTypes: ["violations"],
  });
  return result.violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(" ")).join(", ")}`);
}

function typeInto(ta: HTMLTextAreaElement, value: string) {
  act(() => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(ta, value);
    ta.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

// --- Home ------------------------------------------------------------------------------------------------------

async function showHome() {
  routes.push((c) =>
    c.url.startsWith("/api/me/ideas")
      ? { status: 200, body: { items: [], total: 0, counts: {} } }
      : undefined,
  );
  routes.push((c) =>
    c.url.startsWith("/api/crew") ? { status: 200, body: { items: [], total: 0 } } : undefined,
  );
  routes.push((c) => (c.url.startsWith("/api/ones/posts") ? { status: 200, body: [] } : undefined));
  await act(async () => {
    root.render(createElement(HomeScreen, { firstName: "Kavya", fetchImpl: fakeFetch as typeof fetch }));
  });
  await flush();
}

describe("C-PROMPT.attach on Home (S-03; DEC-124, BLD-C213, C214)", () => {
  for (const device of ["desk", "phone"] as const) {
    it(`V-ACC S-03 C-PROMPT.anatomy/2 (${device}): "+" is first in the box's tool row, named and titled "Add files, a folder or a link"`, async () => {
      phone = device === "phone";
      await showHome();
      const b = plus()!;
      expect(b).toBeTruthy();
      expect(b.getAttribute("title")).toBe(ATTACH_LABEL);
      expect(b.getAttribute("aria-expanded")).toBe("false");
      expect(b.closest(".prompt")).toBe(host.querySelector("textarea")!.closest(".prompt"));
      expect(toolRow()[0]).toBe("+");
      expect(calls.some((c) => c.url === "/api/config/uploads")).toBe(false); // read only when the picker opens
      expect(await axeSerious()).toEqual([]);
    });
  }

  it("V-ACC S-03.hero/5, C-FILE.uploader: the picker as the Home board draws it, its help line from the one configured limit", async () => {
    await showHome();
    await openPicker();
    const b = plus()!;
    expect(b.getAttribute("aria-expanded")).toBe("true");
    const picker = document.getElementById(b.getAttribute("aria-controls")!)!;
    expect(picker.classList.contains("cpick")).toBe(true);
    // BLD-C243: the prompt says the picker is open, so Home hides its hint without :has().
    expect(host.querySelector(".hm-prompt")!.classList.contains("picking")).toBe(true);
    expect(picker.textContent).toContain("Drop files or a folder here, or browse");
    expect(picker.textContent).toContain(`${CONFIG.help_text} Tap the folder to add a whole folder.`);
    expect(picker.textContent).toContain(
      "SharePoint, Teams and 1% Club links are marked internal. Anything else is marked external.",
    );
    expect(named("Choose a folder")).toBeTruthy();
    expect(named("browse")).toBeTruthy();
    expect(named("Add link")).toBeTruthy();
    const link = picker.querySelector<HTMLInputElement>("input[type=url]")!;
    expect(document.querySelector(`label[for="${link.id}"]`)?.textContent).toBe(
      "Or paste a link to a page, file or idea",
    );
    expect(link.getAttribute("inputmode")).toBe("url");
    expect(picker.querySelector("input[webkitdirectory]")).toBeTruthy();
    expect(await axeSerious()).toEqual([]);
    // Escape closes it and gives the focus back to "+".
    await act(async () => {
      picker.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    });
    await act(async () => await new Promise<void>((r) => requestAnimationFrame(() => r())));
    expect(host.querySelector(".cpick")).toBeNull();
    expect(host.querySelector(".hm-prompt")!.classList.contains("picking")).toBe(false);
    expect(document.activeElement).toBe(plus());
  });

  it('V-ACC C-PROMPT.attach, WCAG 2.4.3 (BLD-C224): the picker opens with the focus on its first control, and Escape with the focus on "+" closes it and keeps the focus on "+"', async () => {
    await showHome();
    await openPicker();
    expect(document.activeElement).toBe(named("Choose a folder"));
    const b = plus()!;
    act(() => b.focus());
    expect(document.activeElement).toBe(b);
    await act(async () => {
      b.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    });
    await act(async () => await new Promise<void>((r) => requestAnimationFrame(() => r())));
    expect(host.querySelector(".cpick")).toBeNull();
    expect(plus()!.getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(plus());
  });

  it('BLD-C224: a pick of only names starting with "." adds nothing, and the picker says so', async () => {
    await showHome();
    await openPicker();
    await choose([pdf(".DS_Store")]);
    // No file, and no draft made for it.
    expect(calls.some((c) => c.method === "POST" && /^\/api\/(files|drafts)$/.test(c.url))).toBe(false);
    expect(host.querySelector(".cpick")?.textContent).toContain(
      "Nothing was added. Files whose names start with a dot are left out.",
    );
  });

  it("BLD-C224: a folder dropped on the drop area adds its files through the directory entries; without them it says to use Choose a folder", async () => {
    routes.push((c) =>
      c.method === "POST" && c.url === "/api/drafts"
        ? { status: 201, body: { draft: { id: DRAFT, messages: [] }, run_id: null } }
        : undefined,
    );
    type Entry = Record<string, unknown>;
    const fileEntry = (f: File): Entry => ({
      isFile: true,
      isDirectory: false,
      file: (ok: (f: File) => void) => ok(f),
    });
    const dirEntry = (children: Entry[]): Entry => ({
      isFile: false,
      isDirectory: true,
      createReader: () => {
        let read = false;
        return {
          readEntries: (ok: (es: Entry[]) => void) => {
            ok(read ? [] : children);
            read = true;
          },
        };
      },
    });
    const drop = async (items: unknown[]) => {
      await act(async () => {
        const ev = new Event("drop", { bubbles: true, cancelable: true });
        Object.defineProperty(ev, "dataTransfer", { value: { items, files: [] } });
        host.querySelector(".cpick")!.dispatchEvent(ev);
      });
      for (let i = 0; i < 4; i++) await flush(); // the folder is read entry by entry, then the draft, then each file
    };
    await showHome();
    await openPicker();
    const folder = dirEntry([
      fileEntry(pdf("Week 47 call log.pdf")),
      fileEntry(pdf(".DS_Store")),
      dirEntry([fileEntry(pdf("Week 48 call log.pdf"))]),
    ]);
    await drop([
      { kind: "file", getAsFile: () => new File([], "Branch notes"), webkitGetAsEntry: () => folder },
    ]);
    const sent = calls.filter((c) => c.method === "POST" && c.url === "/api/files");
    expect(sent.map((c) => (c.form!.get("file") as File).name)).toEqual([
      "Week 47 call log.pdf",
      "Week 48 call log.pdf",
    ]);
    expect(host.querySelector(".cpick")).toBeNull(); // the files are in: the picker closes

    // A browser with no directory entries hands a folder over as an empty file with no type: never uploaded.
    await openPicker();
    await drop([{ kind: "file", getAsFile: () => new File([], "Branch notes") }]);
    expect(calls.filter((c) => c.method === "POST" && c.url === "/api/files")).toHaveLength(2);
    expect(host.querySelector(".cpick")?.textContent).toContain("Use Choose a folder to add a folder.");
    expect(text()).not.toContain("Didn’t upload");
  });

  it("V-ACC J-SHARE C-PROMPT.attach: the first file makes the draft once, a second file does not, and sending continues into THAT draft", async () => {
    const created: Call[] = [];
    routes.push((c) => {
      if (c.method === "POST" && c.url === "/api/drafts") {
        created.push(c);
        return { status: 201, body: { draft: { id: DRAFT, messages: [] }, run_id: null } };
      }
      return undefined;
    });
    routes.push((c) =>
      c.method === "POST" && c.url === `/api/drafts/${DRAFT}/messages`
        ? { status: 201, body: { message: { id: "m-1" }, draft: { id: DRAFT }, run_id: "r-1" } }
        : undefined,
    );
    await showHome();
    await openPicker();
    await choose([pdf("Rejection codes reference.pdf")]);
    expect(created).toHaveLength(1);
    expect(created[0]!.json).toEqual({ channel: "web" }); // no words yet: the same call as the first send, empty
    const first = calls.filter((c) => c.method === "POST" && c.url === "/api/files");
    expect(first).toHaveLength(1);
    expect(first[0]!.form!.get("draft_id")).toBe(DRAFT);
    expect(first[0]!.form!.get("for")).toBeNull();
    // The row, inside the box, with its remove named for the file (Home.md, attachments=One file).
    const box = host.querySelector(".prompt")!;
    expect(box.querySelector(".cfiles")?.textContent).toContain("Rejection codes reference.pdf");
    expect(named("Remove Rejection codes reference.pdf")?.closest(".prompt")).toBe(box);
    // BLD-C224: the list is no live region; the status line, outside the list, says what changed.
    expect(box.querySelector(".cfiles ul")?.hasAttribute("aria-live")).toBe(false);
    expect(box.querySelector(".cfiles ul")?.getAttribute("aria-label")).toBe("Your files and links");
    const status = host.querySelector<HTMLElement>(".attach-w [role=status]")!;
    expect(box.querySelector(".cfiles")?.contains(status)).toBe(false);
    expect(status.textContent).toMatch(/^Rejection codes reference\.pdf(?: added|: Checked)$/);
    expect(host.querySelector(".cpick")).toBeNull(); // the picker closes once the files are in

    await openPicker();
    await choose([pdf("R07 call log, October.pdf")]);
    expect(created).toHaveLength(1); // the same draft
    const both = calls.filter((c) => c.method === "POST" && c.url === "/api/files");
    expect(both.map((c) => c.form!.get("draft_id"))).toEqual([DRAFT, DRAFT]);
    expect(box.querySelectorAll(".cfiles li")).toHaveLength(2);
    expect(await axeSerious()).toEqual([]);

    typeInto(host.querySelector("textarea")!, WORDS);
    await act(async () => named("Continue to Share a problem")!.click());
    await flush();
    expect(created).toHaveLength(1); // never a new draft
    const msg = calls.find((c) => c.method === "POST" && c.url === `/api/drafts/${DRAFT}/messages`)!;
    expect(msg.json).toMatchObject({ text: WORDS, via: "typed" });
    expect(push).toHaveBeenCalledWith(`/share/${DRAFT}`);
  });

  it("C-FILE.row on Home: Remove deletes the file through DELETE /api/files/:id and the row goes; the draft stays", async () => {
    routes.push((c) =>
      c.method === "POST" && c.url === "/api/drafts"
        ? { status: 201, body: { draft: { id: DRAFT, messages: [] }, run_id: null } }
        : undefined,
    );
    await showHome();
    await openPicker();
    await choose([pdf("Branch notes.pdf")]);
    await act(async () => named("Remove Branch notes.pdf")!.click());
    await flush();
    expect(calls.some((c) => c.method === "DELETE" && c.url === "/api/files/ATT-2026-000101")).toBe(true);
    expect(host.querySelector(".cfiles")).toBeNull();
    expect(calls.some((c) => c.method === "DELETE" && c.url.startsWith("/api/drafts"))).toBe(false);
  });

  it("Home with no file sends as before: one POST /api/drafts with the words", async () => {
    const created: Call[] = [];
    routes.push((c) => {
      if (c.method !== "POST" || c.url !== "/api/drafts") return undefined;
      created.push(c);
      return { status: 201, body: { draft: { id: DRAFT, messages: [] }, run_id: null } };
    });
    await showHome();
    typeInto(host.querySelector("textarea")!, WORDS);
    await act(async () => named("Continue to Share a problem")!.click());
    await flush();
    expect(created).toHaveLength(1);
    expect(created[0]!.json).toMatchObject({ text: WORDS });
    expect(calls.some((c) => c.url.endsWith("/messages"))).toBe(false);
  });
});

// --- Share a problem and the draft page ------------------------------------------------------------------------

async function showCompose(props: { draftId: string | null; captureFirst?: boolean }, d: Draft = draft()) {
  routes.push((c) =>
    c.method === "GET" && c.url.startsWith(`/api/drafts/${DRAFT}`) ? { status: 200, body: d } : undefined,
  );
  await act(async () => {
    root.render(createElement(Compose, { firstName: "Kavya", ...props }));
  });
  await flush();
}

describe("C-PROMPT.attach on Share a problem and the draft page (S-04, S-04B; DEC-124, BLD-C213, C214)", () => {
  it('V-ACC S-04B C-PROMPT.anatomy/2, full mode: today\'s design plus "+" first in the tool row', async () => {
    await showCompose({ draftId: DRAFT });
    expect(toolRow()).toEqual(["+", "hint", "status", "mic", "send"]);
    expect(host.querySelector(".cz.capture")).toBeNull();
    expect(host.querySelector(".canvas")).toBeTruthy(); // the draft panel
    expect(host.querySelector(".cmove")).toBeNull();
    expect(await axeSerious()).toEqual([]);
  });

  it("V-ACC S-04 C-PROMPT.attach: on an empty Share a problem the first file makes the draft once; a second file does not", async () => {
    const created: Call[] = [];
    routes.push((c) => {
      if (c.method !== "POST" || c.url !== "/api/drafts") return undefined;
      created.push(c);
      return { status: 201, body: { draft: draft({ messages: [], char_count: 0 }), run_id: null } };
    });
    await showCompose({ draftId: null });
    expect(toolRow()[0]).toBe("+");
    await openPicker();
    await choose([pdf("Mandate form.pdf")]);
    await openPicker();
    await choose([pdf("Branch notes.pdf")]);
    expect(created).toHaveLength(1);
    expect(created[0]!.json).toEqual({ channel: "web" });
    const ups = calls.filter((c) => c.method === "POST" && c.url === "/api/files");
    expect(ups.map((c) => c.form!.get("draft_id"))).toEqual([DRAFT, DRAFT]);
    expect(host.querySelectorAll(".prompt .cfiles li")).toHaveLength(2);
    expect(await axeSerious()).toEqual([]);
  });

  it("V-ACC S-04B C-PROMPT.attach: the draft page puts the draft's files back in the box; a file sent with a message stays with it", async () => {
    await showCompose(
      { draftId: DRAFT },
      draft({
        files: [
          fileItem("ATT-2026-000201", "Rejection codes reference.pdf"),
          { ...fileItem("ATT-2026-000202", "From the email.pdf"), message_id: "m-1" } as FileItem,
        ],
      }),
    );
    const rows = host.querySelector(".prompt .cfiles")!;
    expect(rows.textContent).toContain("Rejection codes reference.pdf");
    expect(rows.textContent).toContain("Checked");
    expect(rows.textContent).not.toContain("From the email.pdf");
    expect(named("Remove Rejection codes reference.pdf")).toBeTruthy();
    expect(boxFilesOf(undefined)).toEqual([]);
    // BLD-C224: files put back in the box are not news: the status line is empty on page load.
    expect(host.querySelector(".attach-w [role=status]")?.textContent).toBe("");
  });
});

describe("S-04B in Capture first (DEC-125, BLD-C212)", () => {
  it('V-ACC S-04B Capture first: no draft panel and no Forms as you write, full width, "+" then Move to Review and its readiness line', async () => {
    await showCompose({ draftId: DRAFT, captureFirst: true });
    expect(host.querySelector(".cz.capture")).toBeTruthy();
    expect(host.querySelector(".canvas")).toBeNull();
    expect(text()).not.toContain(PANEL_COPY.forms);
    expect(text()).not.toContain(PANEL_COPY.failed); // no "Couldn't work this out" parts
    expect([...host.querySelectorAll("h2")].map((h) => h.textContent)).not.toContain(PANEL_COPY.heading);
    expect(toolRow()).toEqual(["+", "move", "hint", "status", "mic", "send"]);
    const move = host.querySelector(".cmove")!;
    const go = move.querySelector("a")!;
    expect(go.textContent).toBe(PANEL_COPY.move);
    expect(go.getAttribute("href")).toBe(`/share/${DRAFT}/check`);
    const line = document.getElementById(go.getAttribute("aria-describedby")!)!;
    expect(line.textContent).toBe(READINESS.ready);
    expect(line.classList.contains("cmove-l")).toBe(true);
    // The rule-based hint chips stay (lib/canvas rules on the worker; no model call).
    expect(named("Say how often it happens")).toBeTruthy();
    expect(named("Say who feels it most")).toBeTruthy();
    // Only one Move to Review on the desk.
    expect(
      [...host.querySelectorAll("a, button")].filter((b) => b.textContent === PANEL_COPY.move),
    ).toHaveLength(1);
    expect(await axeSerious()).toEqual([]);
  });

  it("V-ACC S-04B Capture first: below the minimum, Move to Review waits, aria-disabled, with Your draft needs a little more first.", async () => {
    await showCompose(
      { draftId: DRAFT, captureFirst: true },
      draft({ char_count: 12, messages: [{ ...draft().messages[0]!, text: "Calls double." }] }),
    );
    const btn = host.querySelector<HTMLButtonElement>(".cmove button")!;
    expect(btn.textContent).toBe(PANEL_COPY.move);
    expect(btn.getAttribute("aria-disabled")).toBe("true");
    expect(document.getElementById(btn.getAttribute("aria-describedby")!)?.textContent).toBe(READINESS.more);
    await act(async () => btn.click());
    expect(document.activeElement).toBe(host.querySelector("textarea")); // C-BUTTON.states/4: to what blocks it
    expect(await axeSerious()).toEqual([]);
  });

  it('V-ACC S-04B Capture first, the phone: unchanged except "+" (the sheet and the dock\'s Move to Review stay)', async () => {
    phone = true;
    await showCompose({ draftId: DRAFT, captureFirst: true });
    expect(host.querySelector(".cz.capture")).toBeNull();
    expect(toolRow()).toEqual(["+", "hint", "status", "mic", "send"]);
    expect(host.querySelector(".dsheet")).toBeTruthy(); // the draft sheet, as today
    expect(host.querySelector(".cmove")).toBeNull();
    expect([...host.querySelectorAll("a, button")].some((b) => b.textContent === PANEL_COPY.move)).toBe(true);
    expect(await axeSerious()).toEqual([]);
  });

  it('V-ACC S-04B full mode on the phone: unchanged except "+"', async () => {
    phone = true;
    await showCompose({ draftId: DRAFT });
    expect(toolRow()).toEqual(["+", "hint", "status", "mic", "send"]);
    expect(host.querySelector(".dsheet")).toBeTruthy();
    expect(await axeSerious()).toEqual([]);
  });
});

describe('The "+" and the Capture first layout in CSS (WCAG 2.1 AA; BLD-C212, C213)', () => {
  const css = readFileSync(resolve(__dirname, "../../src/app/share/compose.css"), "utf8").replace(
    /\/\*[\s\S]*?\*\//g,
    "",
  );
  const rule = (selector: string) => {
    const at = css.indexOf(`${selector} {`);
    expect(at, selector).toBeGreaterThanOrEqual(0);
    return css.slice(at, css.indexOf("}", at));
  };

  it("WCAG 2.5.8: the \"+\" is lane D's shared 44 × 44 button with a visible focus ring (BLD-D019, BLD-D025); a file's remove is 32 × 32, padded to 44 on touch", () => {
    const shared = readFileSync(resolve(__dirname, "../../src/app/components.css"), "utf8");
    expect(shared).toMatch(/\n\.attach-btn \{[^}]*width: var\(--target\);[^}]*height: var\(--target\);/);
    expect(shared).toMatch(/\n\.attach-btn:focus-visible \{[^}]*outline: 2px solid var\(--blue\);/);
    expect(css).not.toMatch(/\.attach-btn/);
    expect(rule(".cz .cfile-x")).toMatch(/width: 32px;[\s\S]*height: 32px;/);
  });

  it("DEC-125/2, DEC-130, BLD-D032: Capture first on a desk is one column up to 960px, centred; the conversation and the box fill it", () => {
    expect(rule(".cz.capture .cmain")).toContain("grid-template-columns: minmax(0, 960px);");
    expect(rule(".cz.capture .cmain")).toContain("justify-content: center;");
    expect(rule(".cz.capture.has .tin,\n.cz.capture.has .cdock > *")).toContain("max-width: none;");
    expect(rule(".cz .cmove-l")).toContain("color: var(--mute);");
  });
});
