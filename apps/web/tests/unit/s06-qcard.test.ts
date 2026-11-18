/**
 * S-06 with lane B's C-QCARD (C-QCARD.anatomy, S-06.states; J-TRACK/3, J-TRACK/5; BLD-E051). Questions from the
 * desk: the card leads, its countdown in the header and the deadline line on its own, "Answer by …. One at a time,
 * typed or spoken.", with one button to Answer. Answers sent with a question left open: "Sent." leads and the card,
 * partly answered, sits under it; the sentence's rest is its own span on its own line in every state but Just shared
 * (S-06.layout/2, Status.md; J-TRACK/7, J-REVIEW/6). Rendered on the server, as the page renders it. Synthetic people only.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { createElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn(), replace: vi.fn(), push: vi.fn() }),
  useParams: () => ({ id: "IDEA-2026-000003" }),
  usePathname: () => "/ideas/IDEA-2026-000003",
}));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) =>
    createElement("a", { href, ...rest }, children),
}));
vi.mock("@/lib/motion/spark", () => ({ sparkBurst: vi.fn() }));
vi.mock("@/components/teamup/teamup-sheet", async (actual) => ({
  ...(await actual<typeof import("@/components/teamup/teamup-sheet")>()),
  useTeamUpSheet: () => ({ open: vi.fn(), close: vi.fn(), isOpen: false, sheet: null }),
}));

const { SharerScreen } = await import("@/app/ideas/[id]/sharer-screen");
type Props = Parameters<typeof SharerScreen>[0];

const REF = "IDEA-2026-000003";
const DAY = 24 * 60 * 60 * 1000;
const HARISH = {
  id: "p-h",
  name: "Harish Kulkarni",
  first_name: "Harish",
  initials: "HK",
  city: null,
  area: null,
};
const QUESTIONS = [
  ["How many folios were held last month?", "often", "How often"],
  ["Which teams see the hold first?", "who", "Who it affects"],
  ["Is there a report that shows the holds?", "attached", "Attached"],
] as const;

function set(state: "seen" | "partly_answered") {
  const sent = new Date(Date.now() - DAY).toISOString();
  return {
    id: "qs-1",
    idea_id: REF,
    by: HARISH,
    state,
    time_to_answer: null,
    sent_at: sent,
    seen_at: sent,
    due_at: new Date(Date.now() + 2 * DAY).toISOString(),
    answered_at: null,
    extended_times: 0,
    reminded_at: null,
    count: 3,
    answered: state === "partly_answered" ? 2 : 0,
    overdue: false,
    questions: QUESTIONS.map(([text, part, name], i) => ({
      id: `q${i + 1}`,
      seq: i + 1,
      part,
      part_name: name,
      text,
      suggested: false,
      answer:
        state === "partly_answered" && i < 2
          ? { id: `a${i + 1}`, text: "An answer.", files: [], sent: true, saved_at: sent }
          : null,
    })),
    idea: { id: REF, title: "PAN mismatch holds new folios for days" },
    countdown: { label: "2 days left", variant: "normal" },
    deadline: "Answer by Friday 20 November, 5:39 am",
    progress: "",
    send_label: "",
  };
}

function props(state: "questions" | "answers_sent"): Props {
  const asking = state === "questions";
  return {
    view: {
      view: "sharer",
      screen: "S-06",
      idea: {
        id: REF,
        ref: REF,
        title: "PAN mismatch holds new folios for days",
        status: "needs_you",
        stages: [],
        own_words: [],
        hidden: [],
        files: [],
        has_open_questions: true,
        kept_separate: false,
      },
      page: {
        state,
        state_label: "",
        pill: { status: "needs_you", label: "Needs you", variant: "warn" },
        breadcrumb: { label: "My ideas", to: "/my-ideas", current: REF },
        shared_label: null,
        first_arrival: false,
        card: asking
          ? null
          : {
              lead: "Sent. Harish has your answers.",
              rest: "Each answer was added to its part of your idea, under What you shared.",
            },
        ...(asking ? { card_from: "question_set" } : {}),
        window: null,
        actions: { conversation: { label: "Open the conversation", to: `/ideas/${REF}/conversation` } },
        lane_b: { question_set: `/api/ideas/${REF}/question-set`, decision: `/api/ideas/${REF}/decision` },
        shared: {
          intro: "",
          rows: [],
          hidden: { chips: [], more: 0, note: "", all: [] },
          attached: { label: "Attached", files: [], answers: [] },
          fix: { label: "Your fix", answers: [] },
        },
        conversation: null,
        similar: { heading: "Colleagues on something similar", intro: "", tiles: [] },
        merged: null,
        own_words_unmasked: false,
      },
    },
    decision: null,
    questions: set(asking ? "seen" : "partly_answered"),
    partFailed: false,
  } as unknown as Props;
}

const text = (html: string) =>
  html
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();

describe("S-06.states with lane B's C-QCARD (J-TRACK/3, /5; BLD-E051)", () => {
  it("Questions from the review desk: the card leads; the deadline line ends at its sentence; one way to Answer", () => {
    const html = renderToStaticMarkup(createElement(SharerScreen, props("questions")));
    expect(html).toContain('class="card qcard"');
    expect(text(html)).toContain("Harish from the review desk,");
    expect(html).toContain(">Harish has 3 questions for you</h3>");
    for (const [q] of QUESTIONS) expect(html).toContain(q);
    // C-QCARD.anatomy/4: the deadline line alone; the countdown is the header's pill
    expect(html).toContain(
      '<p class="meta">Answer by Friday 20 November, 5:39 am. One at a time, typed or spoken.</p>',
    );
    expect(html).toMatch(new RegExp(`href="/ideas/${REF}/answer"[^>]*>Answer the questions</a>`));
    expect(html).not.toContain("Sent. Harish has your answers.");
    expect(html).toMatch(/class="ip-card-body"><article class="card qcard"/);
  });

  it("Answers sent with a question left: Sent. leads, the partly answered card under it says Carry on answering", () => {
    const html = renderToStaticMarkup(createElement(SharerScreen, props("answers_sent")));
    const sent = html.indexOf("Sent. Harish has your answers.");
    expect(sent).toBeGreaterThan(-1);
    expect(html.indexOf('class="card qcard"')).toBeGreaterThan(sent);
    expect(html).toMatch(/>Carry on answering<\/a>/);
    // S-06.layout/2 (J-TRACK/7): the rest of the sentence is its own span after the white first clause
    expect(html).toContain(
      '<span class="ip-lead">Sent. Harish has your answers.</span> <span class="ip-rest">Each answer was added to its part of your idea, under What you shared.</span>',
    );
    expect(html.split('aria-label="Answered"').length - 1).toBe(2);
  });
});

const { decisionSentence } = await import("@/app/ideas/[id]/decision");

/** The page in `state` with this card sentence and no question set. */
function withCard(state: string, card: { lead: string; rest: string; phone_rest?: string }): Props {
  const p = props("answers_sent");
  const view = p.view as unknown as { idea: Record<string, unknown>; page: Record<string, unknown> };
  view.idea.has_open_questions = false;
  view.page.state = state;
  view.page.card = card;
  return { ...p, questions: null };
}

describe("S-06.layout/2, Status.md (J-REVIEW/6, J-TRACK/7): the card sentence's rest is its own line", () => {
  it("each decision's rest from lane B's decision is apart from its lead", () => {
    const at = "2026-11-13T05:30:00Z";
    const stages = [{ stage: "built", state: "now", detail: "Team chosen by Friday 27 November" }];
    const d = (choice: string, extra: Record<string, unknown> = {}) =>
      ({
        decision: { choice, merged_into: null },
        decided_at: at,
        return_at: null,
        lines: null,
        ...extra,
      }) as never;
    expect(decisionSentence(d("pick"), "Lavanya", stages as never)).toEqual({
      lead: "Picked. A team is being chosen to build it.",
      rest: "Lavanya from the review desk picked it on Friday 13 November. The build team is chosen by Friday 27 November.",
    });
    expect(decisionSentence(d("not_now", { return_at: "2027-02-16T04:00:00Z" }), "Harish", [])?.rest).toMatch(
      /^Your idea stays open, .* Harish’s full reason is below\.$/,
    );
    expect(decisionSentence(d("not_picked"), "Harish", [])).toEqual({
      lead: "Not picked.",
      rest: "Harish’s full reason is below.",
    });
  });

  it.each([
    [
      "picked",
      "Picked. A team is being chosen to build it.",
      "Lavanya from the review desk picked it on Friday 13 November.",
    ],
    [
      "not_now",
      "Not now. The review desk looks at it again on Tuesday 16 February.",
      "Harish’s full reason is below.",
    ],
    ["not_picked", "Not picked.", "Harish’s full reason is below."],
    ["answers_sent", "Sent. Harish has your answers.", "Each answer was added to its part of your idea."],
    ["withdrawn", "Withdrawn. It’s back in your drafts.", "Nobody else can see it now. No reason given."],
  ])("%s: the lead, then the rest in its own element on its own line", (state, lead, rest) => {
    const html = renderToStaticMarkup(createElement(SharerScreen, withCard(state, { lead, rest })));
    expect(html).toContain(`<span class="ip-lead">${lead}</span> <span class="ip-rest">${rest}</span>`);
  });

  it("just shared keeps the board's one line, with the phone's own words", () => {
    const html = renderToStaticMarkup(
      createElement(
        SharerScreen,
        withCard("just_shared", {
          lead: "The review desk will look at it by Tuesday 24 November.",
          rest: "We’ll tell you on Teams and by email when anything changes.",
          phone_rest: "We’ll tell you on Teams and by email.",
        }),
      ),
    );
    expect(html).not.toContain('class="ip-rest"');
    expect(html).toContain(
      '<span class="ip-desk">We’ll tell you on Teams and by email when anything changes.</span>',
    );
  });
});

describe("S-06.states, reversed by the Ones Committee: the committee's card keeps its own styled row and heading", () => {
  it("renders the card with ip-r-by and ip-r-h inside ip-rcard, and the reason card gives way", () => {
    const p = withCard("reversed", { lead: "", rest: "" });
    const view = p.view as unknown as { page: Record<string, unknown> };
    view.page.card = null;
    const rohan = { ...HARISH, id: "p-r", name: "Rohan Mehta", first_name: "Rohan", initials: "RM" };
    const decision = {
      decision: {
        choice: "not_now",
        merged_into: null,
        reason: "A reason the sharer reads.",
        reason_heading: "Why",
        by_line: "by Meera from the review desk",
      },
      decided_at: "2026-11-16T05:30:00Z",
      return_at: "2027-02-16T04:00:00Z",
      joined_into: null,
      reversal: { to: "not_now", note: "Hold it till the quarter turns.", by: rohan },
      lines: {
        committee_line: null,
        reversal: {
          from_line: "Rohan Mehta from the Ones Committee, Tuesday 24 November, 5:40 pm",
          title: "The Ones Committee changed the decision to not now",
          note_heading: "The committee’s note to you",
          was_line: "Was: Picked",
          was_by_line: "by Meera from the review desk, Monday 16 November",
          final_line: "This is final. It comes back to the review desk on Tuesday 16 February 2027.",
          track_line: "Picked, then moved to not now by the Ones Committee",
        },
      },
    };
    const html = renderToStaticMarkup(createElement(SharerScreen, { ...p, decision } as unknown as Props));
    expect(html).toMatch(
      /<div class="ip-rcard"><div class="ip-r-by">.*<p>Rohan Mehta from the Ones Committee, Tuesday 24 November, 5:40 pm<\/p><\/div><h2 class="ip-r-h">The Ones Committee changed the decision to not now<\/h2>/,
    );
    expect(html).toContain("“Hold it till the quarter turns.”");
    expect(html).not.toMatch(/class="ip-q-(by|h)"/);
    expect(html).not.toContain("A reason the sharer reads.");
    // The two classes are styled under the card (the old ip-q-* rules left with lane E's questions card)
    const css = readFileSync(resolve(__dirname, "../../src/app/ideas/[id]/idea-page.css"), "utf8");
    expect(css).toMatch(/\.ip-rcard \.ip-r-by \{\s*display: flex;/);
    expect(css).toMatch(/\.ip-rcard \.ip-r-h \{[^}]*font: 500 19px\/1\.3 var\(--fd\);/);
  });
});
