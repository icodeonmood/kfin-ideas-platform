// @vitest-environment jsdom
/**
 * S-R2.layout, S-R3.layout (BLD-B261, agreed with lane D): the back links "Review desk" (S-R2) and "Home" (S-R3) draw
 * one chevron, the shared `.back::before`, and take their 44px height from `.back`; lane B's own inline chevron is
 * gone. The links keep their words, which are their accessible names. Synthetic data only.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
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

const { AnswerView } = await import("@/app/ideas/[id]/answer/answer-view");
type SharerSet = NonNullable<import("@/lib/contracts").SharerQuestionSetResponse>;

const IDEA = "IDEA-2026-000931";

function set(): SharerSet {
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
        part: "often",
        part_name: "How often",
        text: "Is the 40 calls a day at one branch, or across Hyderabad?",
        suggested: false,
        answer: null,
      },
    ],
    countdown: { label: "3 days left to answer", variant: "normal" },
    deadline: "Answer by Thursday 19 November, 6 pm",
    progress: "0 of 1 answered",
    send_label: "Answer at least one question",
  };
}

describe("One chevron on the review side's back links", () => {
  it("S-R3.layout: the Home link has no chevron of its own; .back draws it", () => {
    const box = document.createElement("div");
    box.innerHTML = renderToStaticMarkup(createElement(AnswerView, { ideaId: IDEA, initial: set() }));
    const home = box.querySelector<HTMLAnchorElement>("a.back.ans-back");
    expect(home?.getAttribute("href")).toBe("/");
    expect(home?.textContent).toBe("Home");
    expect(home?.querySelector("svg")).toBeNull();
    expect(home?.getAttribute("style")).toBeNull(); // no height of its own
  });

  it("S-R2.layout: the Review desk link has no chevron of its own; .back draws it", () => {
    const src = readFileSync(resolve(__dirname, "../../src/app/desk/ideas/[id]/reviewer-idea.tsx"), "utf8");
    const link = src.match(/<Link\s+href="\/desk"\s+className="back"[\s\S]*?<\/Link>/)?.[0];
    expect(link).toBeDefined();
    expect(link).toContain("Review desk");
    expect(link).not.toContain("<svg");
    expect(link).not.toMatch(/style=|minHeight/);
  });
});
