import { describe, expect, it } from "vitest";

import {
  bottomBar,
  initialPanel,
  panelReducer,
  readyLine,
  storedQueue,
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

describe("S-R2 Asking: the reviewer's stored queue (J-REVIEW/A1–A3, BLD-B244)", () => {
  const set = {
    set_id: "QS-1",
    questions: [
      {
        id: "Q-1",
        part: "often",
        part_name: "How often",
        text: "Is it 40 calls a day at one branch?",
        suggested: true,
      },
      { id: "Q-2", part: "evidence", part_name: "Attached", text: "Can you add the SMS?", suggested: false },
      { id: "Q-3", part: "fix", part_name: "Fix", text: null, suggested: false },
      { id: "Q-4", part: "nowhere", part_name: "?", text: "Dropped: no such part", suggested: false },
    ],
    time_to_answer: "1w",
    ready_line: "2 questions ready",
    send_label: "Send 2 questions to Kavya",
  };

  it("keeps the questions the panel can send, with their time to answer", () => {
    expect(storedQueue(set)).toEqual({
      questions: [
        { part: "often", text: "Is it 40 calls a day at one branch?", suggested: true },
        { part: "evidence", text: "Can you add the SMS?", suggested: false },
      ],
      timeToAnswer: "1w",
    });
    expect(storedQueue(null)).toBeNull();
    expect(storedQueue({ ...set, questions: [set.questions[2]!] })).toBeNull();
    expect(storedQueue({ ...set, time_to_answer: null })?.timeToAnswer).toBeNull();
  });

  it("starts with 2 questions ready and Send 2 questions to Kavya, Ask still folded (S-R2.panel/2)", () => {
    const p = initialPanel("reviewing", "3d", storedQueue(set));
    expect(p.state).toBe("reviewing");
    expect(p.askOpen).toBe(false);
    expect(p.timeToAnswer).toBe("1w");
    expect(p.queued.map((q) => q.text)).toEqual([
      "Is it 40 calls a day at one branch?",
      "Can you add the SMS?",
    ]);
    expect(readyLine(p)).toBe("2 questions ready");
    expect(bottomBar(p, "Kavya")).toEqual({
      primary: "Send 2 questions to Kavya",
      secondary: "Decide without asking",
    });
    // a question added here follows the stored ones
    const added = run([{ type: "add_suggestion", part: "who", text: "Who calls most?" }], p);
    expect(added.queued.map((q) => q.key)).toEqual([1, 2, 3]);
  });

  it("a follow-up stored on an answered set opens as asking, as Ask a follow-up does, and Back keeps it", () => {
    const p = initialPanel("answered", "3d", storedQueue(set));
    expect(p.state).toBe("reviewing");
    expect(p.queued).toHaveLength(2);
    const back = run([{ type: "decide" }, { type: "back" }], p);
    expect(back.state).toBe("reviewing");
    expect(back.queued).toHaveLength(2);
  });

  it("a stored queue never reopens a sent or decided panel", () => {
    expect(initialPanel("sent", "3d", storedQueue(set)).queued).toEqual([]);
    expect(initialPanel("decided", "3d", storedQueue(set)).state).toBe("decided");
  });
});
