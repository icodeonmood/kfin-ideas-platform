// @vitest-environment jsdom
/**
 * S-04 and S-04B, the Tell it screen, against a mocked A-API (BLD-C126). J-SHARE/2 to /6 and J-RESUME/1, /3, /4 and
 * J-RECOVER/5 as far as the browser goes: the calm prompt with focus in the box and the draft's slots beside it;
 * the words saved on the first pause (one Idempotency-Key per draft) and "Start my draft" opening the conversation;
 * "You have a draft from …" with Continue that draft and Start a new one; the conversation with the person's words,
 * the receipt and "Picked up where you left off."; a detail with its own client_id; offline, the detail kept with
 * its client_id and `at`, "Unsaved, you're offline", then sent again and "Saved at …". Synthetic words only.
 */
import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Draft } from "@/lib/contracts";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, replace: push, refresh: vi.fn() }) }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: unknown }) =>
    createElement("a", { href, ...rest }, children as never),
}));

const { Compose } = await import("@/app/share/compose");

const DRAFT = "6f1c2a8e-3b4d-4e5f-8a9b-0c1d2e3f4a5b";
const NEW_DRAFT = "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d";
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
      often: {
        state: "filled",
        value: "About 25 times a week at one branch",
        why: "From your words: “about 25 times a week”",
      },
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
    saved_on: { device: "phone", this_device: false },
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
    receipt: [
      "Drafted a title: “Bank mandate changes take a week to show”.",
      "Your draft is ready. Add a detail, or check it.",
    ],
    suggestions: ["Add what you already tried"],
    run: { id: "r-0", state: "done" },
    ...over,
  };
}

type Sent = { method: string; url: string; key: string | null; body: Record<string, unknown> };
let sent: Sent[];
let online: boolean;
let route: (s: Sent) => { status: number; body: unknown };

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: false });
  sent = [];
  online = true;
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
  Object.defineProperty(navigator, "onLine", { get: () => online, configurable: true });
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
  );
  vi.stubGlobal(
    "EventSource",
    class {
      addEventListener() {}
      close() {}
    },
  );
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
      if (!online) throw new TypeError("Failed to fetch");
      const r = route(s);
      return new Response(JSON.stringify(r.body), { status: r.status });
    }),
  );
  route = () => ({ status: 200, body: { items: [], total: 0 } });
});

let host: HTMLDivElement;
let root: Root;

afterEach(() => {
  act(() => root?.unmount());
  host?.remove();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

async function mount(props: { draftId: string | null; startNew?: boolean }) {
  host = document.createElement("div");
  document.body.appendChild(host);
  root = createRoot(host);
  await act(async () => {
    root.render(createElement(Compose, { firstName: "Kavya", ...props }));
  });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(0);
  });
}

const text = () => host.textContent ?? "";
const button = (name: string) =>
  [...host.querySelectorAll("button, a")].find(
    (b) => (b.getAttribute("aria-label") ?? b.textContent ?? "").trim() === name,
  ) as HTMLButtonElement | undefined;

function type(el: HTMLTextAreaElement, value: string) {
  act(() => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!.call(el, value);
    el.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

describe("S-04 Tell it, a new problem (J-SHARE/2, /3; BLD-C126)", () => {
  it("S-04.empty/1 the question with their name, focus in the box, three starters, the draft's slots waiting", async () => {
    await mount({ draftId: null });
    const h1 = [...host.querySelectorAll("h1")].find((h) => h.classList.contains("dk-only"))!;
    expect(h1.textContent).toBe("What keeps getting in your way, Kavya?");
    expect(document.activeElement).toBe(host.querySelector("textarea"));
    for (const s of [
      "A step customers keep calling about",
      "Something we redo by hand every month",
      "A screen that asks for the same thing twice",
    ])
      expect(button(s)).toBeTruthy();
    expect(text()).toContain("Say it in whichever language feels most natural to you.");
    expect(host.querySelector("h2")!.textContent).toBe("Your draft");
    expect(text()).toContain("Your title appears here");
    expect(host.querySelector(".tsteps")).toBeNull(); // S-04.empty/2: no steps before the first message
    expect(sent.map((s) => s.url)).toEqual(["/api/drafts?recent=1"]);
  });

  it("C-PROMPT.anatomy/3 a starter fills the box with an opener and does not send", async () => {
    await mount({ draftId: null });
    act(() => button("A step customers keep calling about")!.click());
    expect((host.querySelector("textarea") as HTMLTextAreaElement).value).toBe(
      "Customers keep calling us about ",
    );
    expect(sent.filter((s) => s.method === "POST")).toHaveLength(0);
  });

  it("J-SHARE/3 L-DRAFT.autosave/1 the draft is made on the first pause, then the box saves as its first message", async () => {
    route = (s) =>
      s.url === "/api/drafts" && s.method === "POST"
        ? {
            status: 201,
            body: { draft: draft({ saved_on: { device: "laptop", this_device: true } }), run_id: "r-1" },
          }
        : s.method === "PATCH"
          ? { status: 202, body: { run_id: "r-2", message: draft().messages[0], draft: draft() } }
          : { status: 200, body: { items: [], total: 0 } };
    await mount({ draftId: null });
    const box = host.querySelector("textarea") as HTMLTextAreaElement;
    type(box, WORDS);
    expect(text()).toContain("Enter starts your draft. Shift and Enter for a new line.");
    expect(button("Start my draft")).toBeTruthy();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });
    const made = sent.filter((s) => s.url === "/api/drafts" && s.method === "POST");
    expect(made).toHaveLength(1);
    expect(made[0]!.body).toEqual({ channel: "web", text: WORDS, via: "typed" });
    expect(made[0]!.key).toMatch(/^[0-9a-f-]{36}$/);
    expect(text()).toMatch(/Saved at \d{1,2}:\d{2} (am|pm)/);
    expect(text()).toContain("Bank mandate changes take a week to show"); // the parts form while typing
    type(box, `${WORDS} We raise a ticket.`);
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1500);
    });
    const edits = sent.filter((s) => s.method === "PATCH");
    expect(edits.map((s) => s.url)).toEqual([`/api/drafts/${DRAFT}/messages/m-1`]);
    expect(edits[0]!.body).toEqual({ text: `${WORDS} We raise a ticket.` });
  });

  it("J-SHARE/4 Start my draft opens the conversation on that draft (S-04 → S-04B)", async () => {
    route = (s) =>
      s.method === "POST"
        ? { status: 201, body: { draft: draft({ id: NEW_DRAFT }), run_id: "r-1" } }
        : { status: 200, body: { items: [], total: 0 } };
    await mount({ draftId: null });
    type(host.querySelector("textarea") as HTMLTextAreaElement, WORDS);
    await act(async () => {
      button("Start my draft")!.click();
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(push).toHaveBeenCalledWith(`/share/${NEW_DRAFT}`);
    expect(sent.filter((s) => s.method === "POST")).toHaveLength(1); // saved once, not twice
  });

  it("J-RESUME/4 an earlier draft is offered; Continue that draft opens it, Start a new one leaves the box empty", async () => {
    route = () => ({
      status: 200,
      body: {
        items: [
          {
            id: DRAFT,
            title: "Distributors can’t see why an SIP registration is stuck",
            saved_at: "2026-11-13T15:12:00.000Z",
            saved_on: { device: "phone", this_device: false },
            saved_labels: draft().saved_labels,
            step: "tell",
            char_count: 120,
            channel: "web",
            archived: false,
          },
        ],
        total: 1,
      },
    });
    await mount({ draftId: null });
    expect(text()).toContain(
      "You have a draft from Friday: Distributors can’t see why an SIP registration is stuck.",
    );
    expect(text()).toContain(
      "Last saved on your phone, 8:42 pm. Continue it here, or start a new one below.",
    );
    act(() => button("Continue that draft")!.click());
    expect(push).toHaveBeenCalledWith(`/share/${DRAFT}`);
    act(() => button("Start a new one")!.click());
    expect(text()).not.toContain("You have a draft from");
    expect((host.querySelector("textarea") as HTMLTextAreaElement).value).toBe("");
  });

  it("P-ROUTES 'Start a new one instead' (?new=1) does not offer the earlier draft", async () => {
    await mount({ draftId: null, startNew: true });
    expect(sent).toHaveLength(0);
  });
});

describe("S-04B Tell it, the conversation (J-SHARE/5, J-RESUME/3, J-RECOVER/5; BLD-C126)", () => {
  function conversationRoute(extra?: (s: Sent) => { status: number; body: unknown } | null) {
    route = (s) => {
      const r = extra?.(s);
      if (r) return r;
      if (s.url === `/api/drafts/${DRAFT}?open=1` || s.url === `/api/drafts/${DRAFT}`)
        return { status: 200, body: draft() };
      return { status: 404, body: { error: { code: "not_found", message: "We couldn't find that draft." } } };
    };
  }

  it("J-RESUME/3 picked up: the words as they were, who and when, the receipt, the steps, Move to Review", async () => {
    conversationRoute();
    await mount({ draftId: DRAFT });
    expect(sent[0]!.url).toBe(`/api/drafts/${DRAFT}?open=1`);
    for (const t of ["Tell it", "Check it", "Send it"]) expect(text()).toContain(t);
    expect(text()).toContain("Picked up where you left off.");
    expect(text()).toContain("Last saved on your phone, Friday 8:42 pm.");
    expect(button("Start a new one instead")).toBeTruthy();
    expect(text()).toContain(WORDS);
    expect(text()).toContain("Friday, 8:42 pm, on your phone");
    expect(text()).toContain("Your draft is ready. Add a detail, or check it.");
    expect(button("Add what you already tried")).toBeTruthy();
    expect(text()).toContain("Add a detail any time. It goes straight into the draft.");
    const box = host.querySelector("textarea") as HTMLTextAreaElement;
    expect(box.labels?.[0]?.textContent).toBe("Add a detail, like how often it happens or what you tried");
    const move = button("Move to Review") as unknown as HTMLAnchorElement;
    expect(move.getAttribute("href")).toBe(`/share/${DRAFT}/check`);
  });

  it("J-SHARE/5 a detail goes into the conversation with its own client_id, and the draft updates", async () => {
    const detail = "We raise a ticket for each one and wait two days for an answer.";
    conversationRoute((s) =>
      s.method === "POST" && s.url === `/api/drafts/${DRAFT}/messages`
        ? {
            status: 202,
            body: {
              run_id: "r-9",
              message: { id: "m-2", text: detail },
              draft: draft({
                messages: [
                  ...draft().messages,
                  { ...draft().messages[0]!, id: "m-2", text: detail, at_label: "Just now" },
                ],
              }),
            },
          }
        : null,
    );
    await mount({ draftId: DRAFT });
    type(host.querySelector("textarea") as HTMLTextAreaElement, detail);
    await act(async () => {
      button("Add to your draft")!.click();
      await vi.advanceTimersByTimeAsync(0);
    });
    const post = sent.find((s) => s.method === "POST")!;
    expect(post.body).toMatchObject({ text: detail, via: "typed" });
    expect(post.key).toMatch(/^[0-9a-f-]{36}$/);
    expect(post.body.client_id).toBe(post.key);
    expect(text()).toContain(detail);
    expect(text()).toContain("Just now");
    expect((host.querySelector("textarea") as HTMLTextAreaElement).value).toBe("");
  });

  it("J-RECOVER/5 offline: the detail waits with its client_id and `at`; back online it goes, and Saved at", async () => {
    const detail = "We started a spreadsheet last month but nobody keeps it up to date.";
    conversationRoute((s) =>
      s.method === "POST"
        ? { status: 202, body: { run_id: "r-9", message: { id: "m-2" }, draft: draft() } }
        : null,
    );
    await mount({ draftId: DRAFT });
    online = false;
    act(() => {
      window.dispatchEvent(new Event("offline"));
    });
    type(host.querySelector("textarea") as HTMLTextAreaElement, detail);
    await act(async () => {
      button("Add to your draft")!.click();
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(text()).toContain("Unsaved, you’re offline");
    expect(text()).toContain(detail); // nothing typed is lost
    expect(text()).toContain("Queued. Goes in once the one above is done.");
    const first = sent.filter((s) => s.method === "POST");
    expect(first).toHaveLength(1);
    const kept = JSON.parse(localStorage.getItem(`1pc.outbox.${DRAFT}`)!) as Array<{
      clientId: string;
      at: string;
    }>;
    expect(kept[0]!.clientId).toBe(first[0]!.key);
    expect(kept[0]!.at).toMatch(/^\d{4}-\d{2}-\d{2}T/);

    online = true;
    await act(async () => {
      window.dispatchEvent(new Event("online"));
      await vi.advanceTimersByTimeAsync(0);
    });
    const posts = sent.filter((s) => s.method === "POST");
    expect(posts).toHaveLength(2);
    expect(posts[1]!.key).toBe(first[0]!.key); // the same client_id on the replay
    expect(posts[1]!.body).toMatchObject({ client_id: first[0]!.key, at: kept[0]!.at, text: detail });
    expect(text()).toMatch(/Saved at \d{1,2}:\d{2} (am|pm)/);
    expect(localStorage.getItem(`1pc.outbox.${DRAFT}`)).toBeNull();
  });

  it("A-API.conventions/2 a draft that is not there says so in plain words", async () => {
    route = () => ({
      status: 404,
      body: { error: { code: "not_found", message: "We couldn't find that draft." } },
    });
    await mount({ draftId: DRAFT });
    expect(host.querySelector('[role="alert"]')!.textContent).toBe("We couldn't find that draft.");
  });
});
