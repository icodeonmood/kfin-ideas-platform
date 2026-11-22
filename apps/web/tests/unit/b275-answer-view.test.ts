// @vitest-environment jsdom
/**
 * S-R3, C-FILE.row, L-QUESTIONS.answer, BLD-B275: the "+" on an answer in the screen, with a fake `fetch` and fake
 * timers. One save per question before any upload (also when an autosave is on its way), a save the worker refuses
 * uploads nothing, asking again stops at Checked and when the screen goes, a found file never blocks Send, and a file
 * removed while it uploads leaves no row. Synthetic people, words and files only.
 */
import { act, createElement, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { AnswerFile, SharerQuestionSetResponse } from "@/lib/contracts";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) =>
    createElement("a", { href, ...rest }, children),
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: () => undefined, push: () => undefined }),
}));

const { AnswerView } = await import("@/app/ideas/[id]/answer/answer-view");
type SharerSet = NonNullable<SharerQuestionSetResponse>;

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const IDEA = "IDEA-2026-000931";
const NAME = "branch-call-log.md";
const CLOSED = "The review desk has decided, so these questions are closed.";
const FOUND_LINE = "Only you, the review desk and the Ones Committee can open it.";

function answerFile(state: string, over: Partial<AnswerFile> = {}): AnswerFile {
  return {
    id: "f-seeded",
    kind: "file",
    name: "sms-screenshot.png",
    type: "image/png",
    size: 2048,
    pages: null,
    state,
    hidden_note: null,
    customer_detail: state === "personal_data_found",
    ...over,
  };
}

function set(files: AnswerFile[] | null = null): SharerSet {
  return {
    id: "6b1d2c3e-4f5a-4b6c-8d7e-9f0a1b2c3d4e",
    idea_id: IDEA,
    idea: { id: IDEA, title: "Investors call to ask why a redemption was held" },
    by: null,
    state: "seen",
    time_to_answer: "3d",
    sent_at: new Date(Date.now() - 3_600_000).toISOString(),
    seen_at: new Date().toISOString(),
    due_at: new Date(Date.now() + 3 * 86_400_000).toISOString(),
    answered_at: null,
    extended_times: 0,
    reminded_at: null,
    count: 1,
    answered: 0,
    overdue: false,
    questions: [
      {
        id: "q-1",
        seq: 1,
        part: "evidence",
        part_name: "Attached",
        text: "Can you add the call log for the whole of November?",
        suggested: false,
        answer: files
          ? {
              id: "a-seeded",
              question_id: "q-1",
              text: "",
              files,
              by: {
                id: "u-kavya",
                name: "Kavya Menon",
                first_name: "Kavya",
                initials: "KM",
                city: null,
                area: null,
              },
              at: null,
              added_to: "evidence",
              added_to_name: "Attached",
              saved_at: new Date().toISOString(),
              sent_at: null,
              sent: false,
            }
          : null,
      },
    ],
    countdown: { label: "3 days left to answer", variant: "normal" },
    deadline: "Answer by Thursday 19 November, 6 pm",
    progress: "0 of 1 answered",
    send_label: "Answer at least one question",
  } as SharerSet;
}

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });

function fileItem(id: string, state: string) {
  return {
    id,
    kind: "file",
    name: NAME,
    type: "text/markdown",
    size: 25,
    state,
    added_by: { id: "u-kavya", name: "Kavya Menon" },
    added_at: new Date().toISOString(),
  };
}

type Seen = { method: string; url: string; answerId: string | null; hasFor: boolean };
type Handler = (url: string) => Promise<Response> | Response;

/** The screen's calls, answered by `on` where given, else as the worker would answer them. */
function server(on: { put?: Handler; post?: Handler; get?: Handler } = {}): Seen[] {
  const seen: Seen[] = [];
  let posted = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: RequestInfo | URL, init: RequestInit = {}) => {
      const url = String(input);
      const method = (init.method ?? "GET").toUpperCase();
      const form = init.body instanceof FormData ? init.body : null;
      seen.push({
        method,
        url,
        answerId: form ? String(form.get("answer_id")) : null,
        hasFor: form ? form.has("for") : false,
      });
      if (method === "PUT")
        return on.put ? on.put(url) : json({ id: "a-1", text: "", files: [], sent: false });
      if (method === "POST" && url === "/api/files") {
        posted += 1;
        return on.post ? on.post(url) : json(fileItem(`f-${posted}`, "checking"), 201);
      }
      if (method === "GET" && url.startsWith("/api/files/"))
        return on.get ? on.get(url) : json(fileItem(url.split("/").pop() ?? "", "checked"));
      if (method === "DELETE") return new Response(null, { status: 204 });
      if (url.startsWith("/api/config/uploads")) return json({ limit_mb: 25, types: ["md"], help_text: "" });
      return json({}, 404);
    }),
  );
  return seen;
}

function deferred(): { promise: Promise<Response>; resolve(r: Response): void } {
  let resolve!: (r: Response) => void;
  const promise = new Promise<Response>((r) => (resolve = r));
  return { promise, resolve };
}

describe("S-R3, C-FILE.row, L-QUESTIONS.answer, BLD-B275: files on an answer", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });
  afterEach(() => {
    act(() => root.unmount());
    host.remove();
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  const render = (initial: SharerSet) =>
    act(async () => root.render(createElement(AnswerView, { ideaId: IDEA, initial })));

  /** Moves the clock on, then lets every reply on its way land (a few rounds: a save, then an upload). */
  async function flush(ms = 0) {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(ms);
    });
    for (let i = 0; i < 4; i++) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0);
      });
    }
  }

  /** Picks files in the system's file chooser behind the "+". */
  async function pick(...names: string[]) {
    const input = host.querySelector<HTMLInputElement>('input[type="file"]')!;
    const chosen = names.map((n) => new File(["The call log for week 47."], n, { type: "text/markdown" }));
    Object.defineProperty(input, "files", { value: chosen, configurable: true });
    await act(async () => {
      input.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }

  async function type(words: string) {
    const box = host.querySelector("textarea")!;
    const setValue = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!;
    await act(async () => {
      setValue.call(box, words);
      box.dispatchEvent(new Event("input", { bubbles: true }));
    });
  }

  const buttons = () => [...host.querySelectorAll("button")];
  const button = (name: string) =>
    buttons().find((b) => (b.getAttribute("aria-label") ?? b.textContent) === name);

  it('S-R3, BLD-B275: the "+" has the Answer board\'s name and tooltip', async () => {
    server();
    await render(set());
    const plus = host.querySelector(".attach-btn")!;
    expect(plus.getAttribute("aria-label")).toBe("Attach files to this answer");
    expect(plus.getAttribute("title")).toBe("Attach files");
  });

  it("L-QUESTIONS.answer, BLD-B275: two quick picks make one save, then both uploads carry its answer_id and never `for`", async () => {
    const seen = server();
    await render(set());
    await pick(NAME, "second-log.md");
    await pick("third-log.md");
    await flush();
    const puts = seen.filter((c) => c.method === "PUT");
    const posts = seen.filter((c) => c.method === "POST" && c.url === "/api/files");
    expect(puts).toHaveLength(1);
    expect(posts).toHaveLength(3);
    expect(posts.map((c) => c.answerId)).toEqual(["a-1", "a-1", "a-1"]);
    expect(posts.some((c) => c.hasFor)).toBe(false);
    expect(seen.findIndex((c) => c.method === "PUT")).toBeLessThan(
      seen.findIndex((c) => c.method === "POST" && c.url === "/api/files"),
    );
  });

  it("L-QUESTIONS.answer, BLD-B275: a pick while the autosave is on its way waits for it and makes no second save", async () => {
    const put = deferred();
    const seen = server({ put: () => put.promise });
    await render(set());
    await type("The log is attached.");
    await flush(700); // the autosave goes
    expect(seen.filter((c) => c.method === "PUT")).toHaveLength(1);
    await pick(NAME);
    expect(seen.filter((c) => c.method === "POST")).toHaveLength(0); // waiting for the save
    put.resolve(json({ id: "a-7", text: "The log is attached.", files: [], sent: false }));
    await flush();
    expect(seen.filter((c) => c.method === "PUT")).toHaveLength(1);
    const posts = seen.filter((c) => c.method === "POST" && c.url === "/api/files");
    expect(posts.map((c) => c.answerId)).toEqual(["a-7"]);
  });

  it("C-FILE.row, BLD-B275: a save the worker refuses (409 set_closed) uploads nothing and offers no Try again", async () => {
    const seen = server({ put: () => json({ error: { code: "set_closed", message: CLOSED } }, 409) });
    await render(set());
    await pick(NAME);
    await flush();
    expect(seen.filter((c) => c.method === "POST")).toHaveLength(0);
    const row = host.querySelector(".frow")!;
    expect(row.textContent).toContain(CLOSED);
    expect(button("Try again")).toBeUndefined();
    expect(host.textContent!.split(CLOSED)).toHaveLength(2); // said once, under the row, not again under the box
  });

  it("C-FILE.row, BLD-B275: asking again stops once the row is Checked", async () => {
    const seen = server();
    await render(set([answerFile("checking", { id: "f-9", name: NAME, type: "text/markdown" })]));
    await flush(2000);
    expect(seen.filter((c) => c.method === "GET" && c.url === "/api/files/f-9")).toHaveLength(1);
    expect(host.querySelector(".frow")!.textContent).toContain("Checked");
    await flush(30_000);
    expect(seen.filter((c) => c.method === "GET" && c.url.startsWith("/api/files/"))).toHaveLength(1);
  });

  it("C-FILE.row, BLD-B275: asking again stops when the screen goes", async () => {
    const seen = server({ get: (url) => json(fileItem(url.split("/").pop() ?? "", "checking")) });
    await render(set([answerFile("checking", { id: "f-9", name: NAME, type: "text/markdown" })]));
    await flush(2000);
    const asked = seen.filter((c) => c.method === "GET" && c.url.startsWith("/api/files/")).length;
    expect(asked).toBe(1);
    act(() => root.unmount());
    root = createRoot(host); // afterEach unmounts again
    await flush(30_000);
    expect(seen.filter((c) => c.method === "GET" && c.url.startsWith("/api/files/"))).toHaveLength(asked);
  });

  it("C-FILE.row, DEC-107, BLD-B275: a seeded file with a customer detail shows as found and never blocks Send", async () => {
    server();
    await render(set([answerFile("personal_data_found")]));
    expect(host.querySelector(".frow")!.textContent).toContain(FOUND_LINE);
    expect(button("Question 1, answered")).toBeDefined();
    const check = buttons().find((b) => b.textContent === "Check your answers and send")!;
    await act(async () => check.click());
    expect(host.textContent).toContain("One screenshot attached.");
    const send = buttons().find((b) => b.textContent?.startsWith("Send 1 answer to the review desk"));
    expect(send).toBeDefined();
    expect(send!.getAttribute("aria-disabled")).not.toBe("true");
  });

  it("DEC-132, L-QUESTIONS.answer, BLD-B275: a file-only answer counts once its check ends, never while checking", async () => {
    let open!: () => void;
    const gate = new Promise<void>((r) => (open = r));
    server({
      get: async () => {
        await gate; // the check runs until the test lets it end
        return json(fileItem("f-9", "checked"));
      },
    });
    await render(set([answerFile("checking", { id: "f-9", name: NAME, type: "text/markdown" })]));
    expect(button("Question 1, not answered yet")).toBeDefined();
    expect(button("Skip for now")).toBeDefined();
    await flush(2000);
    expect(button("Question 1, not answered yet")).toBeDefined(); // still checking
    open();
    await flush(2000);
    expect(host.querySelector(".frow")!.textContent).toContain("Checked");
    expect(button("Question 1, answered")).toBeDefined();
    expect(button("Next")).toBeDefined();
  });

  it("DEC-132, BLD-B275: an answer whose only file is infected is not answered, attaches nothing and can't be sent", async () => {
    server();
    await render(set([answerFile("infected", { id: "f-9", name: NAME, type: "text/markdown" })]));
    expect(button("Question 1, not answered yet")).toBeDefined();
    const check = buttons().find((b) => b.textContent === "Check your answers and send")!;
    await act(async () => check.click());
    expect(host.textContent).not.toContain("attached.");
    const send = buttons().find((b) => b.textContent === "Answer at least one question");
    expect(send).toBeDefined();
    expect(send!.disabled || send!.getAttribute("aria-disabled") === "true").toBe(true);
  });

  it("C-FILE.row, BLD-B275: a file removed while it uploads leaves no row, and what reached the server goes too", async () => {
    const post = deferred();
    const seen = server({ post: () => post.promise });
    await render(set());
    await pick(NAME);
    await flush();
    expect(host.querySelectorAll(".frow")).toHaveLength(1);
    await act(async () => button(`Remove ${NAME}`)!.click());
    expect(host.querySelectorAll(".frow")).toHaveLength(0);
    post.resolve(json(fileItem("f-late", "checking"), 201));
    await flush(5000);
    expect(host.querySelectorAll(".frow")).toHaveLength(0);
    expect(seen.some((c) => c.method === "DELETE" && c.url === "/api/files/f-late")).toBe(true);
    expect(seen.filter((c) => c.method === "GET" && c.url.startsWith("/api/files/"))).toHaveLength(0);
  });
});
