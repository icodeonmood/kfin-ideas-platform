// @vitest-environment jsdom
/**
 * S-R2.left/3, BLD-B280 (the lead's answer (b) of 26 Nov; DEC-107, DEC-132): its sharer may remove a file after the
 * answer is sent, so an answer sent with only a file can be left with nothing. S-R2 then says "The file sent with this
 * answer was removed." where the words would be, as an empty part reads, and the desk never sees an empty answer. An
 * answer that still has its file, or has words, shows no such line. Synthetic data only.
 */
import { createElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: ReactNode }) =>
    createElement("a", { href, ...rest }, children),
}));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: () => undefined, push: () => undefined }),
}));

const { AskedQuestion } = await import("@/app/desk/ideas/[id]/reviewer-idea");
type Question = import("@/lib/contracts").ReviewerQuestion;
type Answer = NonNullable<Question["answer"]>;

const IDEA = "IDEA-2026-000931";
const REMOVED = "The file sent with this answer was removed.";

function question(answer: Partial<Answer>): Question {
  return {
    id: "3f2a9c1e-7b4d-4e8a-9c6f-1d2e3f4a5b6c",
    text: "Can you add the November call log for branch R07?",
    asked_at: "2026-11-16T05:50:00Z",
    asked_by: "Meera",
    asked_line: "You asked, Monday 16 November, 11:20 am",
    state: "Answered",
    answer: {
      id: "8c7b6a5d-4e3f-4a2b-9c1d-0e9f8a7b6c5d",
      text: "",
      at: "2026-11-16T11:02:00Z",
      by: "Kavya",
      line: "Kavya answered, Monday 16 November, 4:32 pm",
      files: [],
      files_removed: null,
      ...answer,
    },
  };
}

function render(q: Question): HTMLElement {
  const host = document.createElement("div");
  host.innerHTML = renderToStaticMarkup(createElement(AskedQuestion, { q, ideaId: IDEA }));
  return host;
}

describe("S-R2.left/3, BLD-B280: an answer whose file was removed after it was sent", () => {
  it("BLD-B280, DEC-107: a file-only answer whose file was removed reads the line in place of the words, muted as an empty part", () => {
    const host = render(question({ files_removed: REMOVED }));
    const answer = host.querySelector(".ri-a")!;
    expect(answer.textContent).toContain("Kavya answered, Monday 16 November, 4:32 pm");
    const line = answer.querySelector("p.body > span.muted");
    expect(line?.textContent).toBe(REMOVED);
    expect(answer.querySelector(".ri-a-files")).toBeNull();
  });

  it("BLD-B280, DEC-132: an answer that still has its file lists it and says nothing was removed", () => {
    const host = render(
      question({
        files: [{ id: "ATT-2026-500101", name: "call-log-R07.xlsx", hidden: null, customer_detail: false }],
      }),
    );
    const answer = host.querySelector(".ri-a")!;
    expect(answer.textContent).not.toContain(REMOVED);
    expect([...answer.querySelectorAll(".ri-a-files li")].map((li) => li.textContent)).toEqual([
      "call-log-R07.xlsx",
    ]);
  });

  it("BLD-B280: an answer not yet sent shows no answer at all, so no line", () => {
    const host = render({ ...question({}), state: "Not answered yet", answer: null });
    expect(host.querySelector(".ri-a")).toBeNull();
    expect(host.textContent).not.toContain(REMOVED);
  });
});
