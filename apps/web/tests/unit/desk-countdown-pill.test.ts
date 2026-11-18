// @vitest-environment jsdom
/**
 * C-PILL.rules/3, S-R1.layout/4, C-QCARD.anatomy/1: every running clock lane B draws is the board's countdown (Desk
 * `.due`), a clock in place of the dot: S-R1's time-left cell and the question card's header. Under a day is "soon",
 * overdue is solid "over"; the card's "Answered" stays a status pill with its dot. Synthetic people only.
 */
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { DeskView } from "@/app/desk/desk-view";
import { QuestionsCard } from "@/components/review/qcard";
import type { DeskResponse, DeskRow, SharerQuestionSetResponse } from "@/lib/contracts";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: () => undefined, push: () => undefined }),
}));
vi.mock("next/link", async () => {
  const { createElement: h } = await import("react");
  return {
    default: (p: { href: string; className?: string; children?: unknown }) =>
      h("a", { href: p.href, className: p.className }, p.children as never),
  };
});

const HOUR = 3_600_000;
const at = (ms: number) => new Date(Date.now() + ms).toISOString();
const IDEA = "IDEA-2026-000912";
const MEERA = {
  id: "u-meera",
  name: "Meera Iyer",
  first_name: "Meera",
  initials: "MI",
  city: null,
  area: null,
};

function doc(html: string): HTMLElement {
  const box = document.createElement("div");
  box.innerHTML = html;
  return box;
}

function questionSet(due: string | null, answered = false): NonNullable<SharerQuestionSetResponse> {
  return {
    id: "8d2f4b6a-1c3e-4a5b-9d7f-2e6c8a0b4d13",
    idea_id: IDEA,
    idea: { id: IDEA, title: "Investors call to ask why a redemption was held" },
    by: MEERA,
    state: answered ? "answered" : "seen",
    time_to_answer: "3d",
    sent_at: at(-HOUR),
    seen_at: at(-HOUR),
    due_at: due,
    answered_at: answered ? at(-HOUR / 2) : null,
    extended_times: 0,
    reminded_at: null,
    count: 1,
    answered: answered ? 1 : 0,
    overdue: false,
    questions: [
      {
        id: "q-1",
        seq: 1,
        part: "often",
        part_name: "How often",
        text: "Is it one branch, or across Hyderabad?",
        suggested: false,
        answer: null,
      },
    ],
    countdown: { label: "3 days left", variant: "normal" },
    deadline: "Answer by Thursday 19 November, 6 pm",
    progress: "0 of 1 answered",
    send_label: "Answer at least one question",
  } as NonNullable<SharerQuestionSetResponse>;
}

const card = (set: NonNullable<SharerQuestionSetResponse>) =>
  doc(renderToStaticMarkup(createElement(QuestionsCard, { ideaId: IDEA, set, variant: "status" })));

describe("C-QCARD.anatomy/1, C-PILL.rules/3: the card's countdown is the board's clock", () => {
  it("days left: the neutral countdown, a clock and no dot", () => {
    const due = card(questionSet(at(80 * HOUR))).querySelector(".qcard-h .due");
    expect(due?.className).toBe("due");
    expect(due?.querySelector("svg")).not.toBeNull();
    expect(due?.querySelector("i")).toBeNull();
    expect(due?.textContent).toMatch(/days? left$/);
  });

  it("under a day: soon, in hours and minutes", () => {
    const due = card(questionSet(at(5 * HOUR))).querySelector(".qcard-h .due");
    expect(due?.className).toBe("due soon");
    expect(due?.textContent).toMatch(/^\d\d:\d\d left$/);
  });

  it("overdue: solid over, with its words", () => {
    const due = card(questionSet(at(-5 * HOUR))).querySelector(".qcard-h .due");
    expect(due?.className).toBe("due over");
    expect(due?.textContent).toBe("Overdue by 5 hours");
  });

  it("answered: the status pill with its dot, no clock", () => {
    const box = card(questionSet(at(80 * HOUR), true));
    expect(box.querySelector(".due")).toBeNull();
    const pill = box.querySelector(".qcard-h .pill.ok");
    expect(pill?.textContent).toBe("Answered");
    expect(pill?.querySelector("i")).not.toBeNull();
  });
});

function row(id: string, due: string, extra: Partial<DeskRow> = {}): DeskRow {
  return {
    idea_id: id,
    title: `Idea ${id}`,
    who: "Kavya Menon, Investor service, Hyderabad",
    questions: "0 of 3 answered",
    time_left: "3 days to answer",
    variant: "normal",
    due_at: due,
    decide_by: "Friday 20 November",
    action: "Remind Kavya",
    action_kind: "remind",
    decision: null,
    committee: null,
    area: "Investor service",
    asked: 3,
    answered: 0,
    set_id: null,
    ...extra,
  };
}

describe("S-R1.layout/4, C-PILL.rules/3: the desk's time left is the board's countdown", () => {
  it("each row's clock is a .due in its look; none is a dotted pill", () => {
    const data: DeskResponse = {
      items: [
        row("IDEA-2026-000101", at(80 * HOUR)),
        row("IDEA-2026-000102", at(5 * HOUR)),
        row("IDEA-2026-000103", at(-5 * HOUR)),
      ],
      total: 3,
      counts: { to_review: 0, waiting: 3, answered: 0, decided: 0 },
      summary: "3 waiting on the sharer",
      tab: "waiting",
      sort: "time_left",
      waiting_on_sharers: [],
      now: new Date().toISOString(),
    };
    const box = doc(renderToStaticMarkup(createElement(DeskView, { initial: data, initialQuery: "" })));
    const clocks = [...box.querySelectorAll(".rd-time .due")];
    expect(clocks.map((c) => c.className)).toEqual(["due", "due soon", "due over"]);
    expect(clocks[0]?.textContent).toMatch(/days? to answer$/);
    expect(clocks[2]?.textContent).toBe("Overdue by 5 hours");
    expect(clocks.every((c) => c.querySelector("svg") && !c.querySelector("i"))).toBe(true);
    expect(box.querySelector(".rd-time .pill")).toBeNull();
  });
});
