/**
 * S-06 with lane B's C-QCARD (C-QCARD.anatomy, S-06.states; J-TRACK/3, J-TRACK/5; BLD-E051). Questions from the
 * desk: the card leads, its countdown in the header and the deadline line on its own, "Answer by …. One at a time,
 * typed or spoken.", with one button to Answer. Answers sent with a question left open: "Sent." leads and the card,
 * partly answered, sits under it; the sentence's rest is its own span (S-06.layout/2, J-TRACK/7). Rendered on the server, as the page renders it. Synthetic people only.
 */
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
