// @vitest-environment jsdom
/**
 * DEC-111 (BLD-B257): a sharer never sees the name of the person at the review desk. C-QCARD, in every place it is
 * drawn (S-06 and S-08 `status`, Home's `home`, the Inbox reader's `inbox`), names "the review desk", with no avatar
 * and no initials, and reads a set that comes without the reviewer (`by: null`). S-R3 names the desk in its review
 * bar, above each question, on its send button and once the answers are sent. Synthetic people only.
 */
import { act, createElement, type ReactNode } from "react";
import { createRoot, type Root } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) =>
    createElement("a", { href, ...rest }, children),
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: () => undefined, push: () => undefined }),
}));

const { QuestionsCard } = await import("@/components/review/qcard");
const { readQuestionSet } = await import("@/components/review/qcard-for");
const { AnswerView } = await import("@/app/ideas/[id]/answer/answer-view");
type SharerSet = NonNullable<import("@/lib/contracts").SharerQuestionSetResponse>;
type Sent = import("@/lib/contracts").SendAnswersResponse;

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const IDEA = "IDEA-2026-000931";
const TITLE = "Investors call to ask why a redemption was held";
// The reviewer the server knows and must never send to the sharer: none of these may reach the screen
const REVIEWER = { first: "Meera", full: "Meera Iyer", initials: "MI" };

function set(state: SharerSet["state"] = "seen", answered = 0): SharerSet {
  const parts = [
    ["summary", "The problem", "Is it mostly R07, or all rejection codes?"],
    ["often", "How often", "Is the 40 calls a day at one branch, or across Hyderabad?"],
    ["evidence", "Attached", "Can you add a screenshot of the SMS, with the folio hidden?"],
  ] as const;
  const done = state === "answered";
  return {
    id: "6b1d2c3e-4f5a-4b6c-8d7e-9f0a1b2c3d4e",
    idea_id: IDEA,
    idea: { id: IDEA, title: TITLE },
    by: null,
    state,
    time_to_answer: "3d",
    sent_at: new Date(Date.now() - 3_600_000).toISOString(),
    seen_at: new Date().toISOString(),
    due_at: new Date(Date.now() + 3 * 86_400_000).toISOString(),
    answered_at: done ? new Date().toISOString() : null,
    extended_times: 0,
    reminded_at: null,
    count: 3,
    answered: done ? 3 : answered,
    overdue: false,
    questions: parts.map(([part, part_name, text], i) => ({
      id: `q-${i + 1}`,
      seq: i + 1,
      part,
      part_name,
      text,
      suggested: false,
      answer:
        done || i < answered
          ? {
              id: `a-${i + 1}`,
              question_id: `q-${i + 1}`,
              text: "Our Hyderabad branch alone.",
              files: [],
              by: {
                id: "u-kavya",
                name: "Kavya Menon",
                first_name: "Kavya",
                initials: "KM",
                city: null,
                area: null,
              },
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
    progress: `${done ? 3 : answered} of 3 answered`,
    send_label: "Answer at least one question",
  };
}

function expectNoReviewer(html: string) {
  expect(html).not.toContain(REVIEWER.first);
  expect(html).not.toContain(REVIEWER.full);
  expect(html).not.toMatch(new RegExp(`>${REVIEWER.initials}<`));
  expect(html).not.toContain('class="av ');
  expect(html).not.toContain("from the review desk,"); // the old byline, "Meera from the review desk, …"
}

describe("DEC-111 C-QCARD: the card names the review desk, never the reviewer, with no avatar", () => {
  it("status (S-06, S-08): the byline and the title name the desk", () => {
    const html = renderToStaticMarkup(
      createElement(QuestionsCard, { ideaId: IDEA, set: set(), variant: "status" }),
    );
    expectNoReviewer(html);
    expect(html).toMatch(/<span class="meta">The review desk, .+<\/span>/);
    expect(html).toContain(">The review desk has 3 questions for you</h3>");
  });

  it("status, answered: the title is the desk’s questions", () => {
    const html = renderToStaticMarkup(
      createElement(QuestionsCard, { ideaId: IDEA, set: set("answered"), variant: "status" }),
    );
    expectNoReviewer(html);
    expect(html).toContain(">The review desk’s 3 questions, answered</h3>");
  });

  it("status without a byline (S-08's message line above it): no avatar, no name", () => {
    const html = renderToStaticMarkup(
      createElement(QuestionsCard, { ideaId: IDEA, set: set(), variant: "status", byline: false }),
    );
    expectNoReviewer(html);
    expect(html).toContain(">The review desk has 3 questions for you</h3>");
  });

  it("DEC-111 C-QCARD home (S-03 Needs you): the title names the desk once; the line under it is 'Asked about …'", () => {
    const html = renderToStaticMarkup(
      createElement(QuestionsCard, { ideaId: IDEA, set: set(), variant: "home" }),
    );
    expectNoReviewer(html);
    expect(html).toContain("3 questions from the review desk");
    expect(html).toContain(`Asked about &quot;${TITLE}&quot;`);
    expect(html.match(/review desk/gi)).toHaveLength(1); // named once, in the title (Home.md)
  });

  it("inbox (S-H5 reader's body): no name, no avatar", () => {
    const html = renderToStaticMarkup(
      createElement(QuestionsCard, { ideaId: IDEA, set: set("partly_answered", 1), variant: "inbox" }),
    );
    expectNoReviewer(html);
    expect(html).toContain("Question 1");
  });

  it("C-QCARD.places S-08: a set sent without the reviewer (by: null) is still a card", async () => {
    const reply = set();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify(reply), { status: 200 })),
    );
    try {
      expect(await readQuestionSet(IDEA, reply.id)).toEqual(reply);
    } finally {
      vi.unstubAllGlobals();
    }
  });
});

describe("DEC-111 S-R3: the Answer screen names the review desk", () => {
  let host: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
    root = createRoot(host);
  });
  afterEach(() => {
    act(() => root.unmount());
    host.remove();
    vi.unstubAllGlobals();
  });

  it("the review bar, the question's line, the send button and the sent lines", async () => {
    const draft = set();
    draft.questions[0]!.answer = {
      ...set("answered").questions[0]!.answer!,
      sent: false,
      sent_at: null,
    };
    const sent: Sent = {
      set_id: draft.id,
      state: "partly_answered",
      sent: 1,
      answered: 1,
      count: 3,
      sent_at: new Date().toISOString(),
      progress: "1 of 3 answered",
      sent_line: "Sent to the review desk, 4:32 pm",
      spare: "Answered with 3 days to spare",
      decides_by: "The review desk decides by Friday 20 November",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        String(url).endsWith("/send")
          ? new Response(JSON.stringify(sent), { status: 200 })
          : new Response("{}", { status: 404 }),
      ),
    );
    await act(async () => root.render(createElement(AnswerView, { ideaId: IDEA, initial: draft })));
    expectNoReviewer(host.innerHTML);
    expect(host.textContent).toContain(`The review desk has 3 questions about "${TITLE}".`);
    expect(host.textContent).toMatch(
      /The review desk asked, (?:today |\w+day \d+ \w+, )\d{1,2}(?::\d{2})? (?:am|pm)/,
    );

    const check = [...host.querySelectorAll("button")].find(
      (b) => b.textContent === "Check your answers and send",
    );
    await act(async () => check!.click());
    const send = [...host.querySelectorAll("button")].find((b) => b.textContent?.startsWith("Send "));
    expect(send?.textContent).toMatch(/^Send 1 answer to the review desk(?:Sending…)?$/); // the busy label is kept hidden
    expectNoReviewer(host.innerHTML);

    await act(async () => send!.click());
    expect(host.textContent).toContain(
      `The review desk had 3 questions about "${TITLE}". You answered 1 of 3.`,
    );
    expect(host.textContent).toContain("Sent to the review desk, 4:32 pm");
    expect(host.textContent).toContain(
      "The review desk decides by Friday 20 November, and the decision comes to your Inbox.",
    );
    expectNoReviewer(host.innerHTML);
  });
});
