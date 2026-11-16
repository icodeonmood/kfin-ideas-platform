import { describe, expect, it } from "vitest";

import {
  bottomBar,
  initialPanel,
  panelReducer,
  readyLine,
  type Panel,
  type PanelEvent,
} from "@/lib/desk/panel";

const run = (events: PanelEvent[], start: Panel = initialPanel()) => events.reduce(panelReducer, start);

describe("S-R2 panel (L-REVIEW.panel)", () => {
  it("V-ACC.review/1 opens on Review this idea with one button and Ask collapsed", () => {
    const p = initialPanel();
    expect(p.state).toBe("reviewing");
    expect(p.askOpen).toBe(false);
    expect(p.queued).toEqual([]);
    expect(bottomBar(p, "Kavya")).toEqual({ primary: "Decide on this idea", secondary: null });
  });

  it("V-ACC.review/5 Back from deciding with nothing asked returns to reviewing", () => {
    const p = run([{ type: "decide" }, { type: "back" }]);
    expect(p.state).toBe("reviewing");
  });

  it("V-ACC.review/6 Ask about this opens the section with that part's suggestion queued", () => {
    const p = run([
      { type: "ask_about", part: "often", suggestion: "Is it getting worse, better or about the same?" },
    ]);
    expect(p.askOpen).toBe(true);
    expect(p.queued.map((q) => [q.part, q.suggested])).toEqual([["often", true]]);
    expect(bottomBar(p, "Kavya")).toEqual({
      primary: "Send 1 question to Kavya",
      secondary: "Decide without asking",
    });
    expect(readyLine(p)).toBe("1 question ready");
  });

  it("L-QUESTIONS.ask/2 the part follows the wording until the reviewer pins one", () => {
    let p = run([
      { type: "toggle_ask" },
      { type: "type_question", text: "How often", guessed: "often" },
      { type: "type_question", text: "How often do investors call?", guessed: "often" },
    ]);
    expect(p.draft.part).toBe("often");
    p = run(
      [
        { type: "pin_question", part: "who" },
        { type: "type_question", text: "Which teams?", guessed: "often" },
      ],
      p,
    );
    expect(p.draft.part).toBe("who");
    p = panelReducer(p, { type: "add_question" });
    expect(p.queued.map((q) => [q.part, q.text])).toEqual([["who", "Which teams?"]]);
    expect(p.draft).toEqual({ text: "", part: "summary", partChosen: false });
  });

  it("V-FIELDS.review/1 an empty or repeated question is not added", () => {
    const p = run([
      { type: "add_question" },
      { type: "add_suggestion", part: "fix", text: "Have you seen this solved anywhere?" },
      { type: "add_suggestion", part: "fix", text: "Have you seen this solved anywhere?" },
    ]);
    expect(p.queued).toHaveLength(1);
    expect(run([{ type: "remove_question", key: p.queued[0]!.key }], p).queued).toEqual([]);
  });

  it("Decide without asking keeps the queued questions until the decision is sent", () => {
    const asked = run([
      { type: "ask_about", part: "summary", suggestion: "Can you give one recent example?" },
    ]);
    const deciding = run([{ type: "decide" }], asked);
    expect(deciding.state).toBe("deciding");
    expect(deciding.queued).toHaveLength(1);
    expect(run([{ type: "back" }], deciding).state).toBe("reviewing");
    expect(run([{ type: "choose", choice: "pick" }, { type: "decision_sent" }], deciding).queued).toEqual([]);
  });

  it("sent, answered, follow-up and Back to answered", () => {
    let p = run([{ type: "ask_about", part: "often", suggestion: "x" }, { type: "questions_sent" }]);
    expect(p.state).toBe("sent");
    expect(bottomBar(p, "Kavya").primary).toBeNull();
    p = run([{ type: "answers_in" }, { type: "decide" }, { type: "back" }], p);
    expect(p.state).toBe("answered");
    p = run([{ type: "follow_up" }], p);
    expect([p.state, p.askOpen]).toEqual(["reviewing", true]);
  });

  it("L-DECIDE.options join applies to Pick only; Not now keeps its return period", () => {
    let p = run([
      { type: "decide" },
      { type: "choose", choice: "pick" },
      { type: "join_with", ideaId: "IDEA-2026-001412" },
    ]);
    expect(p.joinWith).toBe("IDEA-2026-001412");
    p = run(
      [
        { type: "choose", choice: "not_now" },
        { type: "set_return", returnIn: "6m" },
      ],
      p,
    );
    expect([p.joinWith, p.returnIn]).toEqual([null, "6m"]);
    expect(bottomBar(p, "Kavya")).toEqual({ primary: "Send decision to Kavya", secondary: "Back" });
  });

  it("a decided panel stays decided", () => {
    const p = run([
      { type: "decide" },
      { type: "choose", choice: "pick" },
      { type: "decision_sent" },
      { type: "decide" },
    ]);
    expect(p.state).toBe("decided");
  });
});
