// @vitest-environment jsdom
/**
 * C-QCARD.places on S-H5 (J-TRACK/3): the desk's questions in the Inbox reader are lane B's card, fed from the
 * sharer's question set (`GET /api/ideas/:id/question-set`), with the reader's own header, Archive, Mark unread and
 * the phone h1 kept, and its forward action in the foot with the set's own words (C-QCARD.states, S-H5.rules/3).
 * After the answers send on S-R3 (J-TRACK/4), the shell hears every Inbox count again (L-INBOX.rules/1,
 * V-ACC.track/8). Mocked routes, synthetic people.
 */
import { act, createElement } from "react";
import { createRoot, hydrateRoot, type Root } from "react-dom/client";
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { COUNTS_EVENT, InboxReader, questionActions } from "@/app/inbox/inbox-reader";
import type { SharerQuestionSetResponse } from "@/lib/contracts";
import { tellInboxCounts } from "@/lib/desk/answers";
import type { Action, InboxCounts, InboxEntry, InboxList } from "@/server/inbox";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: () => undefined }),
  useSearchParams: () => new URLSearchParams(globalThis.location?.search ?? ""),
}));
vi.mock("next/link", async () => {
  const { createElement: h } = await import("react");
  return {
    default: (p: { href: string; className?: string; children?: unknown }) =>
      h("a", { href: p.href, className: p.className }, p.children as never),
  };
});

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const IDEA = "IDEA-2026-000912";
const TITLE = "Investors call to ask why a redemption was rejected";
const SET_ID = "8d2f4b6a-1c3e-4a5b-9d7f-2e6c8a0b4d13";
/** The reader names the item's own set, so the worker marks nothing seen for another (BLD-B248). */
const SET_URL = `/api/ideas/${IDEA}/question-set?set_id=${SET_ID}`;
const readsSet = (calls: string[]) => calls.some((c) => c.includes("/question-set"));
const DUE = new Date(Date.now() + 3 * 86_400_000).toISOString();
const MEERA = {
  id: "u-meera",
  name: "Meera Iyer",
  first_name: "Meera",
  initials: "MI",
  city: null,
  area: null,
};

const ACTIONS: Action[] = [
  { label: "Open the conversation", to: `/ideas/${IDEA}/conversation`, style: "line" },
  { label: "Answer the questions", to: `/ideas/${IDEA}/answer`, style: "primary" },
];

const ITEM: InboxEntry = {
  id: "77",
  kind: "questions",
  from: { id: "u-meera", name: "Meera Iyer", first_name: "Meera", initials: "MI" },
  idea: { id: IDEA, title: TITLE, status: "needs_you" },
  line: "asked you 3 questions",
  at: new Date().toISOString(),
  unread: false,
  needs_you: true,
  due: { at: DUE, label: "3 days left" },
  archived: false,
  body: {
    heading: "Questions from the review desk",
    note: "Answer by Thursday 19 November, 6 pm.",
    sender: "Meera from the review desk",
    count: 3,
    set_id: SET_ID,
  },
  actions: ACTIONS,
} as InboxEntry;

const QUESTIONS = [
  ["summary", "The problem", "Is it mostly R07, or all rejection codes?"],
  ["often", "How often", "Is the 40 calls a day at one branch, or across Hyderabad?"],
  ["evidence", "Attached", "Can you add a screenshot of the SMS, with the folio hidden?"],
] as const;

function questionSet(answered = 0): NonNullable<SharerQuestionSetResponse> {
  return {
    id: SET_ID,
    idea_id: IDEA,
    idea: { id: IDEA, title: TITLE },
    by: MEERA,
    state: answered ? "partly_answered" : "seen",
    time_to_answer: "3d",
    sent_at: new Date().toISOString(),
    seen_at: new Date().toISOString(),
    due_at: DUE,
    answered_at: null,
    extended_times: 0,
    reminded_at: null,
    count: 3,
    answered,
    overdue: false,
    questions: QUESTIONS.map(([part, part_name, text], i) => ({
      id: `q-${i + 1}`,
      seq: i + 1,
      part,
      part_name,
      text,
      suggested: false,
      answer:
        i < answered
          ? {
              id: `a-${i + 1}`,
              question_id: `q-${i + 1}`,
              text: "Our Hyderabad branch alone.",
              files: [],
              by: MEERA,
              at: null,
              added_to: part,
              added_to_name: part_name,
              saved_at: null,
              sent_at: new Date().toISOString(),
              sent: true,
            }
          : null,
    })),
    countdown: { label: "3 days left to answer", variant: "normal" },
    deadline: "Answer by Thursday 19 November, 6 pm",
    progress: `${answered} of 3 answered`,
    send_label: "Answer at least one question",
  } as NonNullable<SharerQuestionSetResponse>;
}

const COUNTS: InboxCounts = { all: 4, needs_you: 1, unread: 2, archived: 0 };

let host: HTMLElement;
let root: Root;
let calls: string[];
let served: NonNullable<SharerQuestionSetResponse>;

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const realMatchMedia = window.matchMedia;

function stubWidth(desktop: boolean) {
  window.matchMedia = ((q: string) => ({
    matches: desktop,
    media: q,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  })) as unknown as typeof window.matchMedia;
}

beforeEach(() => {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  calls = [];
  served = questionSet();
  stubWidth(true);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? "GET"} ${url}`);
      if (url.startsWith(`/api/ideas/${IDEA}/question-set`)) return json(200, served);
      if (url === "/api/inbox/counts") return json(200, COUNTS);
      return json(404, { error: { code: "not_found", message: "We couldn’t find that." } });
    }),
  );
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
  window.matchMedia = realMatchMedia;
});

async function settle() {
  for (let i = 0; i < 5; i++) await act(async () => await Promise.resolve());
}

async function open(item: InboxEntry = ITEM) {
  const initial: InboxList = { items: [item], total: 1, counts: COUNTS, unread: 2 };
  await act(async () => {
    root.render(createElement(InboxReader, { initial, initialTab: "all", initialItem: item.id }));
  });
  await settle();
}

const text = (sel: string) => Array.from(host.querySelectorAll(sel)).map((e) => e.textContent?.trim());
const footLinks = () =>
  Array.from(host.querySelectorAll<HTMLAnchorElement>(".ibx-read .ibx-bar a")).map((a) => [
    a.textContent?.trim(),
    a.getAttribute("href"),
  ]);

describe("C-QCARD.places S-H5: the desk's questions in the Inbox reader", () => {
  it("J-TRACK/3 Inbox.md: the card is the body, under the reader's own header, with one Answer the questions in the foot", async () => {
    await open();
    expect(calls.filter((c) => c.includes("/question-set"))).toEqual([`GET ${SET_URL}`]);
    // The reader's header stays: what it is, the idea as the item's title, who asked, when and the countdown
    expect(host.querySelector(".ibx-kind")?.textContent).toBe("Questions from the review desk");
    expect(host.querySelector("#ibx-title")?.textContent).toBe(TITLE);
    expect(host.querySelector(".ibx-from")?.textContent).toContain(
      "Meera from the review desk asked you 3 questions",
    );
    expect(host.querySelector(".ibx-from")?.textContent).toContain("3 days left");
    for (const name of ["Archive", "Mark unread"])
      expect(host.querySelector(`.ibx-tool button[aria-label="${name}"]`)).not.toBeNull();
    // The card: each question numbered, in the board's words, then the deadline once
    const card = host.querySelector(".ibx-msg .qcard-inbox");
    expect(card).not.toBeNull();
    expect(text(".qcard-inbox .qcard-qn")).toEqual(["Question 1", "Question 2", "Question 3"]);
    expect(text(".qcard-inbox .qcard-qt")).toEqual(QUESTIONS.map(([, , q]) => q));
    expect(card?.querySelector(".qcard-due")?.textContent).toBe("Answer by Thursday 19 November, 6 pm.");
    expect(host.textContent?.split("Answer by Thursday 19 November, 6 pm.").length).toBe(2); // the note is not repeated
    expect(host.querySelector(".ibx-foot")).toBeNull();
    // The two ways on, pinned to the reader's foot (S-H5.rules/3): never a second button in the card
    expect(footLinks()).toEqual([
      ["Open the conversation", `/ideas/${IDEA}/conversation`],
      ["Answer the questions", `/ideas/${IDEA}/answer`],
    ]);
    expect(card?.querySelector("a, button, textarea, input")).toBeNull();
  });

  it("C-QCARD.states partly answered: a tick on each answered question, and the foot reads Carry on answering", async () => {
    served = questionSet(1);
    await open();
    const rows = Array.from(host.querySelectorAll(".qcard-inbox li"));
    expect(rows.map((r) => r.querySelector("[role=img]")?.getAttribute("aria-label") ?? null)).toEqual([
      "Answered",
      null,
      null,
    ]);
    expect(footLinks()).toEqual([
      ["Open the conversation", `/ideas/${IDEA}/conversation`],
      ["Carry on answering", `/ideas/${IDEA}/answer`],
    ]);
  });

  it("S-H5.rules/6 WCAG 2.1 AA: on a phone the item's title is still the screen's h1, with the card under it", async () => {
    stubWidth(false);
    await open();
    expect(text("h1")).toEqual(["Inbox", TITLE]);
    expect(host.querySelector(".qcard-inbox")).not.toBeNull();
    expect(host.querySelector(".qcard-inbox h1, .qcard-inbox h2, .qcard-inbox h3")).toBeNull();
  });

  it("L-INBOX.kinds: an answer reminder shows the same set; another set, a refused read, an item naming no set or a done item keeps the item's note", async () => {
    await open({
      ...ITEM,
      id: "78",
      kind: "answer_reminder",
      line: "1 day left to answer Meera’s questions",
    });
    expect(text(".qcard-inbox .qcard-qn")).toHaveLength(3);
    act(() => root.unmount());

    for (const [name, item, set] of [
      ["another set", ITEM, { ...questionSet(), id: "1f0e2d3c-4b5a-4968-8776-655443322110" }],
      ["a refused read", ITEM, null],
      ["no set named", { ...ITEM, body: { ...ITEM.body, set_id: undefined } }, questionSet()],
      ["done", { ...ITEM, needs_you: false }, questionSet()],
    ] as const) {
      root = createRoot(host);
      calls = [];
      served = set as NonNullable<SharerQuestionSetResponse>;
      if (set === null)
        vi.stubGlobal(
          "fetch",
          vi.fn(async (url: string) => {
            calls.push(`GET ${url}`);
            return json(404, { error: { code: "not_found", message: "We couldn’t find that." } });
          }),
        );
      await open(item as InboxEntry);
      expect(host.querySelector(".qcard-inbox"), name).toBeNull();
      expect(host.querySelector(".ibx-foot")?.textContent, name).toBe(
        "Answer by Thursday 19 November, 6 pm.",
      );
      expect(
        footLinks().map(([l]) => l),
        name,
      ).toEqual(["Open the conversation", "Answer the questions"]);
      // A done item, or one that names no set, never reads one: the first read marks it seen for the desk
      // (L-QUESTIONS.clock/1)
      if (name === "done" || name === "no set named") expect(readsSet(calls), name).toBe(false);
      else expect(calls, name).toEqual([`GET ${SET_URL}`]);
      act(() => root.unmount());
    }
    root = createRoot(host);
  });

  it("L-QUESTIONS.clock/1 S-H5.rules/6: on a phone, hydrating the server's desktop render reads no set until the item is opened", async () => {
    stubWidth(false);
    const initial: InboxList = { items: [ITEM], total: 1, counts: COUNTS, unread: 2 };
    const el = createElement(InboxReader, { initial, initialTab: "all", initialItem: null });
    const server = document.createElement("div");
    server.innerHTML = renderToString(el); // the server's layout: a desktop with the first item open
    document.body.append(server);
    let hydrated: Root | undefined;
    await act(async () => {
      hydrated = hydrateRoot(server, el);
    });
    await settle();
    expect(readsSet(calls)).toBe(false);
    expect(server.querySelector(".qcard-inbox")).toBeNull();
    // Opening it is what reads the set, and only then is it seen
    const row = server.querySelector<HTMLButtonElement>(`#ibx-row-${ITEM.id}`);
    await act(async () => row!.click());
    await settle();
    expect(calls.filter((c) => c.includes("/question-set"))).toEqual([`GET ${SET_URL}`]);
    expect(server.querySelector(".qcard-inbox")).not.toBeNull();
    act(() => hydrated!.unmount());
    server.remove();
  });

  it("C-QCARD.states answered: the forward action to the Answer screen goes; Open the conversation stays", () => {
    expect(questionActions(ACTIONS, { state: "answered", answered: 3 })).toEqual([ACTIONS[0]]);
    expect(questionActions(ACTIONS, { state: "seen", answered: 0 })).toEqual(ACTIONS);
  });

  it("L-INBOX.kinds, BLD-A199 (J-TRACK/6): a reminder for a partly answered set keeps Answer the questions in its foot, with the card's ticks", async () => {
    served = questionSet(2);
    await open({
      ...ITEM,
      id: "78",
      kind: "answer_reminder",
      line: "1 day left to answer Meera’s questions",
    });
    expect(host.querySelectorAll(".qcard-inbox [role=img][aria-label=Answered]")).toHaveLength(2);
    expect(footLinks()).toEqual([
      ["Open the conversation", `/ideas/${IDEA}/conversation`],
      ["Answer the questions", `/ideas/${IDEA}/answer`],
    ]);
  });

  it("L-INBOX.kinds, BLD-A199 (J-TRACK/6): an answer reminder leads to Answer in its own words while anything is left, and drops it once all are sent", () => {
    const partly = { state: "partly_answered", answered: 2 } as const;
    expect(questionActions(ACTIONS, partly, "answer_reminder")).toEqual(ACTIONS); // "Answer the questions", /answer
    expect(questionActions(ACTIONS, partly).map((a) => a.label)).toContain("Carry on answering"); // the questions item
    expect(questionActions(ACTIONS, { state: "answered", answered: 3 }, "answer_reminder")).toEqual([
      ACTIONS[0],
    ]);
  });
});

describe("J-TRACK/4 S-R3: after the answers send, the shell hears every Inbox count", () => {
  let heard: unknown[];
  const onCounts = (e: Event) => heard.push((e as CustomEvent).detail);
  beforeEach(() => {
    heard = [];
    window.addEventListener(COUNTS_EVENT, onCounts);
  });
  afterEach(() => window.removeEventListener(COUNTS_EVENT, onCounts));

  it("L-INBOX.rules/1 V-ACC.track/8: the counts are read again and sent on COUNTS_EVENT", async () => {
    await tellInboxCounts();
    expect(calls).toEqual(["GET /api/inbox/counts"]);
    expect(heard).toEqual([COUNTS]);
  });

  it("a count that cannot be read sends nothing and never throws", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("fetch failed");
      }),
    );
    await expect(tellInboxCounts()).resolves.toBeUndefined();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json(503, { error: { code: "unavailable" } })),
    );
    await tellInboxCounts();
    expect(heard).toEqual([]);
  });
});
