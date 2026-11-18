// @vitest-environment jsdom
/**
 * S-08, an idea's conversation (lane F; L-CONVO, Messages.md): the states the board draws (your idea with the
 * review desk and its questions, the build team's idea with a file, after teaming up, where you were mentioned, no
 * messages yet, a merged idea's closed box), the box (empty, sent, refused, paused, failed), the @mention picker by
 * keyboard, removing one's own message, and the helpers. Every call is answered by a mocked fetch. Synthetic people
 * only: the pack's fictional cast.
 */
import { act, createElement, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) =>
    createElement("a", { href, ...rest }, children),
}));

const { Conversation } = await import("@/components/convo/conversation");
const {
  S08_COPY,
  errorText,
  fileSize,
  mentionAt,
  mentionChoices,
  mentionHint,
  mentionsIn,
  putMention,
  withMentions,
} = await import("@/components/convo/compose");
type View = import("@/lib/contracts").ConversationView;
type Entry = View["entries"][number];

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

// --- Fixtures (synthetic: the pack's fictional cast) -------------------------------------------------------------
const KAVYA = { id: "u-kavya", name: "Kavya Menon", first_name: "Kavya", initials: "KM" };
const MEERA = {
  id: "u-meera",
  name: "Meera Iyer",
  first_name: "Meera",
  initials: "MI",
  role_label: "from the review desk",
};
const RAVI = { id: "u-ravi", name: "Ravi Nair", first_name: "Ravi", initials: "RN" };
const ADITI = { id: "u-aditi", name: "Aditi Sharma", first_name: "Aditi", initials: "AS" };
const PRAKASH = { id: "u-prakash", name: "Prakash Kumar", first_name: "Prakash", initials: "PK" };
const ARJUN = { id: "u-arjun", name: "Arjun Rao", first_name: "Arjun", initials: "AR" };
const SANJAY = { id: "u-sanjay", name: "Sanjay Pillai", first_name: "Sanjay", initials: "SP" };
const NOW = Date.parse("2026-11-17T10:30:00+05:30");

function event(id: string, text: string, extra: Partial<Entry> = {}): Entry {
  return { type: "event", id, code: "desk.opened", text, at: "2026-11-16T09:50:00+05:30", ...extra } as Entry;
}

function message(id: string, from: typeof KAVYA, label: string, text: string, extra: object = {}): Entry {
  return {
    type: "message",
    id,
    from,
    from_label: label,
    you: false,
    text,
    files: [],
    at: "2026-11-17T10:07:00+05:30",
    at_label: "Today, 10:07 am",
    mentions: [],
    mentions_you: false,
    removed: false,
    ...extra,
  } as Entry;
}

/** The board's default: Kavya's idea, with the review desk, Meera's 3 questions open. */
function yourIdea(): View {
  return {
    idea: {
      id: "IDEA-2026-001481",
      title: "Investors call to ask why a redemption was rejected",
      status: "needs_you",
      meta: "IDEA-2026-001481, needs you",
    },
    audience: "you_and_desk",
    header: { whose: "Your idea", line: "Your idea, shared Saturday 14 November" },
    participants: [
      { person: MEERA, label: "Meera from the review desk", doing: "Reviewing it", you: false },
      { person: KAVYA, label: "You", doing: "Shared the idea", you: true },
    ],
    entries: [
      event("shared:IDEA-2026-001481", "You shared it. Saturday 14 November, 10:05 am", {
        code: "idea.shared",
      }),
      event(
        "checked:IDEA-2026-001481",
        "Checked and matched. 1 folio number hidden, 2 similar ideas found. 10:06 am",
      ),
      event("e-open", "Meera from the review desk opened it. Monday 16 November, 9:50 am"),
      {
        type: "questions",
        id: "e-asked",
        set_id: "set-1",
        state: "sent",
        by: MEERA,
        by_label: "Meera from the review desk",
        count: 3,
        answered: 0,
        due_at: "2026-11-19T18:00:00+05:30",
        title: "Meera has 3 questions about your idea",
        deadline:
          "Answer by Thursday 19 November, 6 pm. One at a time, typed or spoken, and each answer is added to its part of your idea.",
        answer_url: "/ideas/IDEA-2026-001481/answer",
        at: "2026-11-16T11:20:00+05:30",
        at_label: "Monday 16 November, 11:20 am",
      } as Entry,
    ],
    composer: {
      placeholder: "Message the review desk",
      visibility: "Only you and the review desk see this conversation.",
      questions_line:
        "Answer Meera’s 3 questions with Answer the questions, so each answer lands on its part of your idea. Write here for anything else.",
      can_attach: true,
    },
  } as View;
}

/** After teaming up: Ravi's idea, read by Kavya on the crew. */
function afterTeamingUp(): View {
  return {
    idea: {
      id: "IDEA-2026-001412",
      title: "Rejection SMS codes confuse investors",
      status: "with_review_desk",
      meta: "IDEA-2026-001412, with the review desk",
    },
    audience: "crew_and_desk",
    header: { whose: "The idea", line: "Ravi Nair’s idea, Investor service, Hyderabad" },
    participants: [
      { person: RAVI, label: "Ravi Nair", doing: "Shared the idea", you: false },
      { person: ADITI, label: "Aditi Sharma", doing: "On the crew", you: false },
      { person: PRAKASH, label: "Prakash Kumar", doing: "On the crew", you: false },
      { person: KAVYA, label: "You", doing: "Joined today", you: true },
    ],
    entries: [
      event("e-shared", "Ravi Nair shared it. Monday 9 November"),
      event("e-approved", "Ravi Nair approved your team-up request. Today, 10:05 am", {
        code: "teamup.approved_team_only",
      }),
      message(
        "m-welcome",
        RAVI,
        "Ravi Nair",
        "Welcome to the crew, Kavya. Your call log is exactly what this idea needed. Could you add last week’s R07 calls before the review desk looks at it on Friday?",
      ),
    ],
    composer: {
      placeholder: "Message the crew",
      visibility: "The crew and the review desk see this conversation.",
      can_attach: false,
    },
  } as View;
}

// --- Harness -----------------------------------------------------------------------------------------------------
let host: HTMLDivElement;
let root: Root;
let calls: { method: string; url: string; body: unknown; key: string | null }[];
let answers: ((method: string, url: string, body: unknown) => { status: number; json?: unknown } | Error)[];
/** Lane B's question-set reads (BLD-B249) are answered apart from the conversation's own calls: none by default (404),
 * so a test that is not about the card sees the plain entry and the calls it expects. */
let setReads: string[];
let setReply: { status: number; json?: unknown };

function respond(status: number, json?: unknown) {
  return { status, json };
}

beforeEach(() => {
  host = document.createElement("div");
  document.body.append(host);
  root = createRoot(host);
  calls = [];
  answers = [];
  setReads = [];
  setReply = { status: 404, json: { error: { code: "not_found", message: "" } } };
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      if (url.includes("/question-set")) {
        setReads.push(url);
        return new Response(JSON.stringify(setReply.json), {
          status: setReply.status,
          headers: { "Content-Type": "application/json" },
        });
      }
      const method = (init.method ?? "GET").toUpperCase();
      const body = typeof init.body === "string" ? (JSON.parse(init.body) as unknown) : undefined;
      const headers = new Headers(init.headers);
      calls.push({ method, url, body, key: headers.get("Idempotency-Key") });
      const next = answers.shift();
      const out = next ? next(method, url, body) : respond(500);
      if (out instanceof Error) throw out;
      return new Response(out.json === undefined ? null : JSON.stringify(out.json), {
        status: out.status,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
});

afterEach(() => {
  act(() => root.unmount());
  host.remove();
  vi.unstubAllGlobals();
});

async function show(view: View, ideaId = view.idea.id) {
  await act(async () => {
    root.render(createElement(Conversation, { initial: view, ideaId, now: () => NOW }));
  });
}

function $(sel: string): HTMLElement | null {
  return host.querySelector<HTMLElement>(sel);
}

function textbox(): HTMLTextAreaElement {
  return host.querySelector("textarea")!;
}

/** The name a screen reader hears: aria-label, else the words less anything aria-hidden. */
function nameOf(el: Element): string {
  const label = el.getAttribute("aria-label");
  if (label) return label;
  const copy = el.cloneNode(true) as Element;
  copy.querySelectorAll('[aria-hidden="true"]').forEach((x) => x.remove());
  return (copy.textContent ?? "").trim();
}

function button(name: string): HTMLButtonElement {
  const b = [...host.querySelectorAll("button")].find((x) => nameOf(x) === name);
  if (!b) throw new Error(`no button ${name}`);
  return b;
}

function links(name: string): HTMLAnchorElement[] {
  return [...host.querySelectorAll("a")].filter((a) => a.textContent?.trim() === name);
}

async function type(value: string, caret = value.length) {
  const box = textbox();
  await act(async () => {
    const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")!.set!;
    setter.call(box, value);
    box.setSelectionRange(caret, caret);
    box.dispatchEvent(new Event("input", { bubbles: true }));
  });
}

async function key(k: string) {
  await act(async () => {
    textbox().dispatchEvent(new KeyboardEvent("keydown", { key: k, bubbles: true, cancelable: true }));
  });
}

async function submit() {
  await act(async () => {
    button(S08_COPY.send).click();
  });
}

function alerts(): string[] {
  return [...host.querySelectorAll('[role="alert"]')].map((a) => a.textContent ?? "");
}

// --- The screen --------------------------------------------------------------------------------------------------
describe("S-08 states", () => {
  it("S-08.layout your idea with the review desk: header, the timeline as a log, the questions with Answer the questions, the labelled box, In this conversation", async () => {
    await show(yourIdea());
    expect($("h1")?.textContent).toBe("Investors call to ask why a redemption was rejected");
    expect($("h1 a")?.getAttribute("href")).toBe("/ideas/IDEA-2026-001481");
    expect(host.textContent).toContain("Your idea, shared Saturday 14 November");
    expect(host.textContent).toContain("Needs you");
    expect(host.textContent).toContain("IDEA-2026-001481");

    const log = $('[role="log"]')!;
    expect(log.getAttribute("aria-labelledby")).toBe($("h2")!.id);
    expect($("h2")?.textContent).toBe("Conversation");
    expect(log.querySelectorAll("li.cv-ev")).toHaveLength(3);
    expect(log.textContent).toContain("You shared it. Saturday 14 November, 10:05 am");
    expect(log.textContent).toContain("Meera has 3 questions about your idea");
    expect(log.textContent).toContain(
      "Answer by Thursday 19 November, 6 pm. One at a time, typed or spoken, and each answer is added to its part of your idea.",
    );
    // S-08.rules/1: questions are answered on S-R3, from the card and from the line above the box.
    const answer = links(S08_COPY.answer);
    expect(answer.map((a) => a.getAttribute("href"))).toEqual([
      "/ideas/IDEA-2026-001481/answer",
      "/ideas/IDEA-2026-001481/answer",
    ]);
    expect(host.textContent).toContain(
      "Answer Meera’s 3 questions with Answer the questions, so each answer lands on its part of your idea. Write here for anything else.",
    );

    const box = textbox();
    expect(box.getAttribute("aria-label")).toBe("Message the review desk");
    expect(box.getAttribute("placeholder")).toBe("Message the review desk");
    const who = document.getElementById(box.getAttribute("aria-describedby")!)!;
    expect(who.textContent).toBe("Only you and the review desk see this conversation.");
    expect(button(S08_COPY.send).getAttribute("type")).toBe("submit");

    const side = $("aside")!;
    expect(side.querySelector("h2")?.textContent).toBe("In this conversation");
    expect(side.textContent).toContain("Meera from the review deskReviewing it");
    expect(side.textContent).toContain("YouShared the idea");
    expect(side.textContent).toContain(S08_COPY.sideNote);
    // The phone's "i" opens the side panel as a sheet (S-08.rules/4).
    const info = button(S08_COPY.people);
    expect(info.getAttribute("aria-controls")).toBe(side.id);
    expect(info.getAttribute("aria-expanded")).toBe("false");
    await act(async () => info.click());
    expect(info.getAttribute("aria-expanded")).toBe("true");
    expect(side.classList.contains("open")).toBe(true);
    expect(document.activeElement).toBe(button(S08_COPY.close));
    await act(async () => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    });
    expect(side.classList.contains("open")).toBe(false);
    expect(document.activeElement).toBe(info);
  });

  it("S-08 idea=Plain words, with its build team: the build team's message with a checked file and View, the build team's box", async () => {
    const v = yourIdea();
    v.idea = {
      ...v.idea,
      id: "IDEA-2026-001471",
      status: "being_built",
      title: "Plain words for transaction rejections",
    };
    v.header = { whose: "Your idea", line: "Your idea, being built by Arjun Rao’s team" };
    v.entries = [
      message(
        "m-arjun",
        ARJUN,
        "Arjun Rao",
        "We rewrote 12 rejection reasons in plain words, from your idea.",
        {
          files: [
            {
              id: "ATT-2026-000412",
              kind: "file",
              name: "plain-rejection-reasons.xlsx",
              type: "XLSX",
              size: 20480,
              state: "checked",
              added_by: ARJUN,
              added_at: "2026-11-15T18:40:00+05:30",
              view_url: "/api/attachments/ATT-2026-000412",
            },
          ],
        },
      ),
    ];
    v.composer = {
      placeholder: "Message the build team",
      visibility: "You, the build team and the review desk see this conversation.",
      can_attach: true,
    };
    await show(v);
    expect(host.textContent).toContain("Being built");
    expect(host.textContent).toContain("Your idea, being built by Arjun Rao’s team");
    const files = $('ul[aria-label="Files in Arjun Rao’s message"]')!;
    expect(files.textContent).toContain("plain-rejection-reasons.xlsx");
    expect(files.textContent).toContain("20 KB");
    expect(files.textContent).toContain("Checked");
    const view = files.querySelector("a")!;
    expect(view.getAttribute("href")).toBe("/api/attachments/ATT-2026-000412");
    expect(view.getAttribute("aria-label")).toBe("View plain-rejection-reasons.xlsx");
    expect(textbox().getAttribute("aria-label")).toBe("Message the build team");
  });

  it("S-08 idea=Ravi's idea, after teaming up (J-TEAMUP/6): the approval line, Ravi's welcome, the crew's box; no attach control (BLD-F063, BLD-F064)", async () => {
    await show(afterTeamingUp());
    expect(host.textContent).toContain("Ravi Nair approved your team-up request. Today, 10:05 am");
    expect(host.textContent).toContain("Ravi Nair’s idea, Investor service, Hyderabad");
    expect($(".cv-msg b")?.textContent).toBe("Ravi Nair");
    expect(textbox().getAttribute("aria-label")).toBe("Message the crew");
    expect(host.textContent).toContain("The crew and the review desk see this conversation.");
    expect(host.querySelector('[aria-label="Attach a file"]')).toBeNull();
    expect(host.querySelector('input[type="file"]')).toBeNull();
  });

  it("S-08 idea=Sanjay's idea, where you were mentioned: the mention is highlighted and the message marked as mentioning you", async () => {
    const v = afterTeamingUp();
    v.entries = [
      message(
        "m-sanjay",
        SANJAY,
        "Sanjay Pillai",
        "@Kavya Menon your R07 call examples would help us write the script.",
        {
          mentions: [KAVYA],
          mentions_you: true,
        },
      ),
    ];
    v.composer = {
      placeholder: "Reply to Sanjay",
      visibility: "The crew, the review desk and anyone they mention see this conversation.",
      can_attach: false,
    };
    await show(v);
    const li = $("#entry-m-sanjay")!;
    expect(li.classList.contains("mentions-you")).toBe(true);
    expect(li.querySelector(".cv-ment")?.textContent).toBe("@Kavya Menon");
    expect(li.querySelector(".cv-bub")?.textContent).toBe(
      "@Kavya Menon your R07 call examples would help us write the script.",
    );
    expect(textbox().getAttribute("aria-label")).toBe("Reply to Sanjay");
  });

  it("S-08 view=No messages yet: the event lines and the empty card", async () => {
    const v = yourIdea();
    v.entries = v.entries.slice(0, 2);
    delete v.composer.questions_line;
    v.empty = {
      title: "No messages yet",
      body: "If the review desk has a question, it shows here and in your Inbox, and we tell you on Teams.",
    };
    await show(v);
    expect($(".cv-empty h3")?.textContent).toBe("No messages yet");
    expect(host.textContent).toContain(
      "If the review desk has a question, it shows here and in your Inbox, and we tell you on Teams.",
    );
  });

  it("S-08 view=Answers sent: the answers as one message, each with Added to, and when the desk decides", async () => {
    const v = yourIdea();
    v.entries = [
      {
        type: "answers",
        id: "e-answers",
        set_id: "set-1",
        from: KAVYA,
        title: "Your answers to Meera’s 3 questions",
        answers: [
          {
            id: "a1",
            question_id: "q1",
            text: "All of them. R07 is about half the calls.",
            added_to: "summary",
            added_to_label: "The problem",
            at: "2026-11-16T16:32:00+05:30",
            files: [],
          },
          {
            id: "a3",
            question_id: "q3",
            text: "Two screenshots attached, folio hidden.",
            added_to: "evidence",
            added_to_label: "Attached",
            at: "2026-11-16T16:32:00+05:30",
            files: [
              {
                id: "ATT-2026-000501",
                kind: "file",
                name: "rejection-sms-1.png",
                type: "PNG",
                state: "checked",
                added_by: KAVYA,
                added_at: "2026-11-16T16:30:00+05:30",
                view_url: "/api/attachments/ATT-2026-000501",
              },
            ],
          },
        ],
        footer: "Each answer was added to its part of your idea. Meera decides by Friday 20 November.",
        at: "2026-11-16T16:32:00+05:30",
        at_label: "Monday 16 November, 4:32 pm",
      } as Entry,
    ];
    delete v.composer.questions_line;
    await show(v);
    const li = $("#entry-e-answers")!;
    expect(li.textContent).toContain("Your answers to Meera’s 3 questions");
    expect(li.textContent).toContain("Added to The problem");
    expect(li.textContent).toContain("Added to Attached");
    expect(li.querySelector("a")?.getAttribute("href")).toBe("/api/attachments/ATT-2026-000501");
    expect(li.textContent).toContain(
      "Each answer was added to its part of your idea. Meera decides by Friday 20 November.",
    );
  });

  it("S-08 a reader who did not ask: the questions' plain title and a link to the idea (BLD-F065)", async () => {
    const v = afterTeamingUp();
    v.entries = [
      {
        type: "questions",
        id: "e-asked",
        set_id: "set-1",
        state: "sent",
        by: MEERA,
        by_label: "Meera from the review desk",
        count: 2,
        answered: 0,
        due_at: "2026-11-19T18:00:00+05:30",
        title: "Meera from the review desk asked 2 questions.",
        at: "2026-11-16T11:20:00+05:30",
        at_label: "Monday 16 November, 11:20 am",
      } as Entry,
    ];
    await show(v);
    expect(host.textContent).toContain("Meera from the review desk asked 2 questions.");
    expect(links(S08_COPY.answer)).toHaveLength(0);
    expect(links(S08_COPY.seeOnIdea)[0]?.getAttribute("href")).toBe("/ideas/IDEA-2026-001412");
    // BLD-B249: the card is the sharer's; anyone else keeps the plain line and never reads the set
    expect(setReads).toEqual([]);
    expect($(".qcard")).toBeNull();
  });

  it("S-08 L-MERGE.effects/6 a merged idea: no box, the closing line with where to write", async () => {
    const v = afterTeamingUp();
    v.composer = {
      ...v.composer,
      closed: "This idea is now part of another one. Write in IDEA-2026-001412’s conversation.",
    };
    v.entries = [
      event(
        "e-merged",
        "It’s now part of IDEA-2026-001412. The conversation carries on there. Today, 10:05 am",
        {
          link: { label: "IDEA-2026-001412", to: "/ideas/IDEA-2026-001412/conversation" },
        },
      ),
    ];
    await show(v);
    expect(host.querySelector("textarea")).toBeNull();
    expect(host.textContent).toContain(
      "This idea is now part of another one. Write in IDEA-2026-001412’s conversation.",
    );
    expect(links("IDEA-2026-001412")[0]?.getAttribute("href")).toBe("/ideas/IDEA-2026-001412/conversation");
  });
});

// --- C-QCARD in the conversation (lane B, BLD-B249) ---------------------------------------------------------------
/** Meera's 3 questions as `GET /ideas/:id/question-set` sends them to Kavya (lane B), `answered` of them sent. */
function sharerSet(answered = 0, id = "set-1") {
  const parts = [
    ["summary", "The problem", "Is it mostly R07, or all rejection codes?"],
    ["often", "How often", "Is the 40 calls a day at one branch, or across Hyderabad?"],
    ["evidence", "Attached", "Can you add a screenshot of the SMS, with the folio hidden?"],
  ] as const;
  return {
    id,
    idea_id: "IDEA-2026-001481",
    idea: { id: "IDEA-2026-001481", title: "Investors call to ask why a redemption was rejected" },
    by: { ...MEERA, city: null, area: null },
    state: answered ? "partly_answered" : "seen",
    time_to_answer: "3d",
    sent_at: "2026-11-16T11:20:00+05:30",
    seen_at: "2026-11-16T12:05:00+05:30",
    due_at: new Date(Date.now() + 3 * 86_400_000).toISOString(),
    answered_at: null,
    extended_times: 0,
    reminded_at: null,
    count: 3,
    answered,
    overdue: false,
    questions: parts.map(([part, part_name, text], i) => ({
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
              sent: true,
            }
          : null,
    })),
    countdown: { label: "3 days left to answer", variant: "normal" },
    deadline: "Answer by Thursday 19 November, 6 pm",
    progress: `${answered} of 3 answered`,
    send_label: "Answer at least one question",
  };
}

async function settle() {
  for (let i = 0; i < 5; i++) await act(async () => await Promise.resolve());
}

describe("S-08 C-QCARD.places: the questions as lane B's card for the sharer (BLD-B249, J-TRACK/3)", () => {
  it("Messages.md: the sharer's open set is the card, in the conversation's words, read by its own set id", async () => {
    setReply = { status: 200, json: sharerSet() };
    await show(yourIdea());
    await settle();
    expect(setReads).toEqual(["/api/ideas/IDEA-2026-001481/question-set?set_id=set-1"]);
    expect(calls).toEqual([]); // the conversation's own calls are untouched
    const entry = $("#entry-e-asked")!;
    // The message line stays: who asked and when; the card is the body, not the plain line
    expect(entry.querySelector(".cv-who")?.textContent).toContain("Meera from the review desk");
    expect(entry.querySelector(".cv-who")?.textContent).toContain("Monday 16 November, 11:20 am");
    expect(entry.querySelector(".cv-ask")).toBeNull();
    const card = entry.querySelector("article.qcard")!;
    expect(card.querySelector("h3")?.textContent).toBe("Meera has 3 questions about your idea");
    expect(card.getAttribute("aria-labelledby")).toBe(card.querySelector("h3")?.id);
    expect(card.querySelector(".qcard-h")?.textContent).toContain("left"); // the countdown beside the title
    expect([...card.querySelectorAll(".qcard-list li")].map((li) => li.textContent)).toEqual([
      "Is it mostly R07, or all rejection codes?Answer goes to The problem",
      "Is the 40 calls a day at one branch, or across Hyderabad?Answer goes to How often",
      "Can you add a screenshot of the SMS, with the folio hidden?Answer goes to Attached",
    ]);
    expect(card.querySelector(".qcard-f .meta")?.textContent).toBe(
      "Answer by Thursday 19 November, 6 pm. One at a time, typed or spoken, and each answer is added to its part of your idea.",
    );
    // S-08.rules/1: one Answer the questions on the card, one in the line above the box, both to S-R3
    expect(links(S08_COPY.answer).map((a) => a.getAttribute("href"))).toEqual([
      "/ideas/IDEA-2026-001481/answer",
      "/ideas/IDEA-2026-001481/answer",
    ]);
  });

  it("C-QCARD.states partly answered: a tick on the answered question and Carry on answering", async () => {
    setReply = { status: 200, json: sharerSet(1) };
    const v = yourIdea();
    v.entries = v.entries.map((e) =>
      e.type === "questions" ? { ...e, state: "partly_answered", answered: 1 } : e,
    );
    await show(v);
    await settle();
    const card = $("#entry-e-asked article.qcard")!;
    expect(
      [...card.querySelectorAll(".qcard-list li")].map((li) => li.querySelector("[role=img]") !== null),
    ).toEqual([true, false, false]);
    expect(links("Carry on answering").map((a) => a.getAttribute("href"))).toEqual([
      "/ideas/IDEA-2026-001481/answer",
    ]);
  });

  it("L-QUESTIONS.clock/1: another set, a refused read or a failed one keeps the plain entry", async () => {
    for (const reply of [
      { status: 200, json: sharerSet(0, "set-2") },
      { status: 404, json: { error: { code: "not_found", message: "" } } },
      { status: 503, json: { error: { code: "unavailable", message: "" } } },
    ]) {
      setReply = reply;
      setReads = [];
      await show(yourIdea());
      await settle();
      expect(setReads).toEqual(["/api/ideas/IDEA-2026-001481/question-set?set_id=set-1"]);
      expect($("#entry-e-asked .qcard")).toBeNull();
      expect($("#entry-e-asked .cv-ask .cv-askt")?.textContent).toBe("Meera has 3 questions about your idea");
      act(() => root.unmount());
      root = createRoot(host);
    }
  });
});

describe("S-08 the box", () => {
  it("S-08.rules/2 nothing typed: the board's words under the box, announced, and nothing sent", async () => {
    await show(afterTeamingUp());
    await type("   ");
    await submit();
    expect(alerts()).toEqual(["Write a message or attach a file first."]);
    expect(calls).toHaveLength(0);
    const box = textbox();
    expect(box.getAttribute("aria-invalid")).toBe("true");
    expect(box.getAttribute("aria-describedby")).toContain(host.querySelector('[role="alert"]')!.id);
    expect(document.activeElement).toBe(box);
  });

  it("S-08 J-TEAMUP/6 sending: POST with an idempotency key, then the conversation is read again and the box clears (BLD-F050)", async () => {
    const after = afterTeamingUp();
    const hello = "Hello, crew. I can share last week’s R07 calls by Thursday.";
    after.entries = [
      ...after.entries,
      message("m-new", KAVYA, "You", hello, { you: true, can_remove_until: "2026-11-17T10:35:00+05:30" }),
    ];
    answers.push(
      () => respond(201, { entry: after.entries.at(-1), hidden: 0 }),
      () => respond(200, after),
    );
    await show(afterTeamingUp());
    await type(hello);
    await submit();
    expect(calls.map((c) => `${c.method} ${c.url}`)).toEqual([
      "POST /api/ideas/IDEA-2026-001412/conversation/messages",
      "GET /api/ideas/IDEA-2026-001412/conversation",
    ]);
    expect(calls[0]!.body).toEqual({ text: hello, mentions: [] });
    expect(calls[0]!.key).toMatch(/^[\w-]{8,200}$/);
    expect(textbox().value).toBe("");
    expect($("#entry-m-new .cv-bub")?.textContent).toBe(hello);
    expect($("#entry-m-new")?.classList.contains("me")).toBe(true);
    expect(alerts()).toEqual([]);
  });

  it("S-08 sent, then the read fails: the message POST returned shows at once, the box clears, nothing is sent twice", async () => {
    const hello = "Hello, crew.";
    const mine = message("m-new", KAVYA, "You", hello, {
      you: true,
      can_remove_until: "2026-11-17T10:35:00+05:30",
    });
    answers.push(
      () => respond(201, { entry: mine, hidden: 0 }),
      () => new Error("offline"),
    );
    await show(afterTeamingUp());
    await type(hello);
    await submit();
    expect($("#entry-m-new .cv-bub")?.textContent).toBe(hello);
    expect(textbox().value).toBe("");
    expect(alerts()).toEqual([]);
    await submit(); // an empty box: refused here, not sent again
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(1);
  });

  it("S-08 a refused message keeps the words and shows the server's reason, announced; a retry of the same words reuses the key", async () => {
    answers.push(
      () => respond(422, { error: { code: "too_long", message: "Keep a message under 4,000 characters.", field: "text" } }),
      () => respond(503, { error: "paused", switch: "submissions", banner: "Sharing and editing ideas is paused for a short while. You can still browse and track your ideas." }),
    ); // prettier-ignore
    await show(afterTeamingUp());
    await type("A long message.");
    await submit();
    expect(alerts()).toEqual(["Keep a message under 4,000 characters."]);
    expect(textbox().value).toBe("A long message.");
    await submit();
    expect(alerts()).toEqual([
      "Sharing and editing ideas is paused for a short while. You can still browse and track your ideas.",
    ]);
    expect(calls[0]!.key).toBe(calls[1]!.key);
    await type("A shorter one.");
    answers.push(() => new Error("offline"));
    await submit();
    expect(alerts()).toEqual([S08_COPY.failed]);
    expect(calls[2]!.key).not.toBe(calls[0]!.key); // new words, new key
  });

  it("S-08 L-MERGE.effects/6 closed while open: 409, its reason, and the conversation read again shows where to write", async () => {
    const closed = afterTeamingUp();
    closed.composer = {
      ...closed.composer,
      closed: "This idea is now part of another one. Write in the idea it joined.",
    };
    answers.push(
      () => respond(409, { error: { code: "conversation_closed", message: closed.composer.closed } }),
      () => respond(200, closed),
    );
    await show(afterTeamingUp());
    await type("Still there?");
    await submit();
    expect(host.querySelector("textarea")).toBeNull();
    expect(host.textContent).toContain("This idea is now part of another one. Write in the idea it joined.");
  });

  it("S-08 L-CONVO/6 the @mention picker by keyboard: @ opens the list, arrows move, Enter picks, the id is sent", async () => {
    answers.push(
      () => respond(201, { entry: null, hidden: 0 }),
      () => respond(200, afterTeamingUp()),
    );
    await show(afterTeamingUp());
    await type("Thanks @");
    const box = textbox();
    const list = host.querySelector('[role="listbox"]')!;
    expect(list.getAttribute("aria-label")).toBe("People to mention");
    expect(box.getAttribute("aria-controls")).toBe(list.id);
    const options = [...list.querySelectorAll('[role="option"]')];
    expect(options.map((o) => o.querySelector(".cv-menu-n")?.textContent)).toEqual([
      "Ravi Nair",
      "Aditi Sharma",
      "Prakash Kumar",
    ]); // never the reader
    expect(host.textContent).toContain("3 people to mention. Use the up and down arrows, then Enter.");
    expect(box.getAttribute("aria-activedescendant")).toBe(options[0]!.id);
    await key("ArrowDown");
    expect(box.getAttribute("aria-activedescendant")).toBe(options[1]!.id);
    expect(options[1]!.getAttribute("aria-selected")).toBe("true");
    await key("ArrowUp");
    await key("ArrowUp"); // wraps to the last
    expect(box.getAttribute("aria-activedescendant")).toBe(options[2]!.id);
    await type("Thanks @Ad");
    const narrowed = [...host.querySelectorAll('[role="option"]')];
    expect(narrowed.map((o) => o.querySelector(".cv-menu-n")?.textContent)).toEqual(["Aditi Sharma"]);
    expect(host.textContent).toContain("1 person to mention.");
    await key("Enter");
    expect(box.value).toBe("Thanks @Aditi Sharma ");
    expect(host.querySelector('[role="listbox"]')).toBeNull();
    expect(box.hasAttribute("aria-activedescendant")).toBe(false);
    await type("Thanks @Aditi Sharma for the list.");
    await submit();
    expect(calls[0]!.body).toEqual({ text: "Thanks @Aditi Sharma for the list.", mentions: [ADITI.id] });
  });

  it("S-08 the @mention picker: Tab leaves the box and closes the list without picking", async () => {
    await show(afterTeamingUp());
    await type("Hi @Ra");
    expect(host.querySelector('[role="listbox"]')).not.toBeNull();
    const tab = new KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true });
    await act(async () => {
      textbox().dispatchEvent(tab);
    });
    expect(tab.defaultPrevented).toBe(false); // the browser moves focus on as usual
    expect(host.querySelector('[role="listbox"]')).toBeNull();
    expect(textbox().value).toBe("Hi @Ra");
  });

  it("S-08 the @mention picker: Escape closes the list and keeps the words; a deleted mention is not sent", async () => {
    answers.push(
      () => respond(201, { entry: null, hidden: 0 }),
      () => respond(200, afterTeamingUp()),
    );
    await show(afterTeamingUp());
    await type("@Ra");
    await key("Enter");
    expect(textbox().value).toBe("@Ravi Nair ");
    await type("Hi @Pr");
    expect(host.querySelector('[role="listbox"]')).not.toBeNull();
    await key("Escape");
    expect(host.querySelector('[role="listbox"]')).toBeNull();
    expect(textbox().value).toBe("Hi @Pr");
    await type("Hi @Pra"); // the same "@": stays closed until a new one
    expect(host.querySelector('[role="listbox"]')).toBeNull();
    await submit();
    expect(calls[0]!.body).toEqual({ text: "Hi @Pra", mentions: [] }); // "@Ravi Nair" was deleted
  });
});

describe("S-08 removing a message (L-CONVO/10)", () => {
  function withMine(until: string): View {
    const v = afterTeamingUp();
    v.entries = [
      ...v.entries,
      message("m-mine", KAVYA, "You", "Wrong idea, sorry.", { you: true, can_remove_until: until }),
    ];
    return v;
  }

  it("S-08 Remove on one's own message within 5 minutes: DELETE, then read again", async () => {
    const removed = withMine("2026-11-17T10:35:00+05:30");
    removed.entries[removed.entries.length - 1] = message("m-mine", KAVYA, "You", "Message removed", {
      you: true,
      removed: true,
    });
    answers.push(
      () => respond(200, { entry: removed.entries.at(-1) }),
      () => respond(200, removed),
    );
    await show(withMine("2026-11-17T10:35:00+05:30"));
    expect(host.querySelectorAll("#entry-m-welcome button")).toHaveLength(0); // not Kavya's
    await act(async () => button("Remove your message from Today, 10:07 am").click());
    expect(calls.map((c) => `${c.method} ${c.url}`)).toEqual([
      "DELETE /api/ideas/IDEA-2026-001412/conversation/messages/m-mine",
      "GET /api/ideas/IDEA-2026-001412/conversation",
    ]);
    expect($("#entry-m-mine .cv-bub")?.textContent).toBe("Message removed");
    expect($("#entry-m-mine .cv-bub")?.classList.contains("removed")).toBe(true);
    expect(host.querySelectorAll("#entry-m-mine button")).toHaveLength(0);
    // WCAG 2.4.3: the button went with the message, so focus is on that line, never dropped to the page.
    expect(document.activeElement).toBe($("#entry-m-mine"));
    expect($("#entry-m-mine")?.getAttribute("tabindex")).toBe("-1");
  });

  it("S-08 removed, then the read fails: the DELETE's answer already shows the line as removed, focus on it", async () => {
    const gone = message("m-mine", KAVYA, "You", "Message removed", { you: true, removed: true });
    answers.push(
      () => respond(200, { entry: gone }),
      () => respond(500),
    );
    await show(withMine("2026-11-17T10:35:00+05:30"));
    await act(async () => button("Remove your message from Today, 10:07 am").click());
    expect($("#entry-m-mine .cv-bub")?.textContent).toBe("Message removed");
    expect(document.activeElement).toBe($("#entry-m-mine"));
    expect(alerts()).toEqual([]);
  });

  it("S-08 too late: no Remove after 5 minutes; a refusal from the server is said under the message", async () => {
    await show(withMine("2026-11-17T10:29:00+05:30"));
    expect(host.querySelectorAll("#entry-m-mine button")).toHaveLength(0);

    answers.push(() =>
      respond(409, {
        error: {
          code: "too_late",
          message: "A message can be removed only in the first 5 minutes after sending.",
        },
      }),
    );
    act(() => root.unmount()); // a new page: the screen reads `initial` once
    root = createRoot(host);
    await show(withMine("2026-11-17T10:35:00+05:30"));
    await act(async () => button("Remove your message from Today, 10:07 am").click());
    expect(alerts()).toEqual(["A message can be removed only in the first 5 minutes after sending."]);
    expect($("#entry-m-mine [role=alert]")).not.toBeNull();
  });
});

describe("S-08 helpers", () => {
  it("S-08 mentionAt: an @ at the start or after a space, up to the caret, on one line", () => {
    expect(mentionAt("@", 1)).toEqual({ start: 0, query: "" });
    expect(mentionAt("Thanks @Rav", 11)).toEqual({ start: 7, query: "Rav" });
    expect(mentionAt("Thanks @Ravi Na", 15)).toEqual({ start: 7, query: "Ravi Na" });
    expect(mentionAt("mail@example", 12)).toBeNull();
    expect(mentionAt("@Ravi\nnext", 10)).toBeNull();
    expect(mentionAt("no at here", 10)).toBeNull();
  });

  it("S-08 mentionChoices, putMention, mentionsIn and withMentions", () => {
    const people = [RAVI, ADITI, PRAKASH].map((p) => ({ ...p, doing: "On the crew" }));
    expect(mentionChoices(people, "").map((p) => p.id)).toEqual([RAVI.id, ADITI.id, PRAKASH.id]);
    expect(mentionChoices(people, "kum").map((p) => p.id)).toEqual([PRAKASH.id]);
    expect(mentionChoices(people, "zz")).toEqual([]);
    expect(putMention("Hi @Ra and more", { start: 3, query: "Ra" }, 6, RAVI)).toEqual({
      text: "Hi @Ravi Nair  and more",
      caret: 14,
    });
    const picked = new Map([
      [RAVI.id, RAVI.name],
      [ADITI.id, ADITI.name],
    ]);
    expect(mentionsIn("@Ravi Nair over to you", picked)).toEqual([RAVI.id]);
    expect(withMentions("@Ravi Nair and @Aditi Sharma, see this", ["Ravi Nair", "Aditi Sharma"])).toEqual([
      { text: "@Ravi Nair", mention: true },
      { text: " and ", mention: false },
      { text: "@Aditi Sharma", mention: true },
      { text: ", see this", mention: false },
    ]);
    expect(withMentions("No names", [])).toEqual([{ text: "No names", mention: false }]);
    expect(mentionHint(0)).toBe("");
  });

  it("S-08 errorText and fileSize", () => {
    expect(errorText({ error: { code: "x", message: "Mention up to 10 people in a message." } })).toBe(
      "Mention up to 10 people in a message.",
    );
    expect(errorText({ error: "paused", banner: "Paused." })).toBe("Paused.");
    expect(errorText({ error: { code: "in_progress", message: "" } })).toBe(S08_COPY.failed);
    expect(errorText(null, "Other.")).toBe("Other.");
    expect(fileSize(2048)).toBe("2 KB");
    expect(fileSize(2.4 * 1024 * 1024)).toBe("2.4 MB");
    expect(fileSize(3 * 1024 * 1024)).toBe("3 MB");
    expect(fileSize(undefined)).toBeUndefined();
  });
});
