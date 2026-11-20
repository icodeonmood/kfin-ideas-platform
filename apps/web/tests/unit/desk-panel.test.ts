import { describe, expect, it, vi } from "vitest";

import type { QueueSaveRequest } from "@/lib/contracts";
import {
  bottomBar,
  focusBackTo,
  initialPanel,
  panelReducer,
  queuePut,
  queueSaver,
  queueSnapshot,
  readyLine,
  storedQueue,
  type Panel,
  type PanelEvent,
  type QueuePut,
  type QueuePutResult,
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
    rev: 0,
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

describe("C-SHEET-MERGE focus on close (V-ACC.visual/11, J-REVIEW/M2–M3)", () => {
  const el = (name: string, isConnected = true) => ({ name, isConnected });
  it("goes back to the row's Merge for that idea, also when the sheet was opened from the preview's Merge", () => {
    const rowMerge = el("row merge");
    expect(focusBackTo(rowMerge, el("Similar ideas"), el("preview merge", false))).toBe(rowMerge);
  });
  it("comes to the Similar ideas heading when the row's Merge is gone (merged) or was never there", () => {
    const heading = el("Similar ideas");
    expect(focusBackTo(el("row merge", false), heading, el("preview merge", false))).toBe(heading);
    expect(focusBackTo(undefined, heading)).toBe(heading);
  });
  it("falls back to whatever had focus on open, and to nothing when all of them are gone", () => {
    const opener = el("opener");
    expect(focusBackTo(null, null, opener)).toBe(opener);
    expect(focusBackTo(el("a", false), null, el("b", false))).toBeNull();
  });
});

describe("S-R2 Asking: the queue is saved as it changes (BLD-B272, amends BLD-B244)", () => {
  const STORED_REV = 4; // the read's `queued.rev`: the revision the worker holds for this reviewer
  const q1 = { part: "often" as const, text: "Is it 40 calls a day at one branch?", suggested: true };
  const q2 = { part: "who" as const, text: "Who calls most?", suggested: false };
  const empty = { questions: [], time_to_answer: "3d" as const };
  const kept = (rev: number): QueuePutResult => ({ kept: true, rev });
  const failed: QueuePutResult = { kept: false, stale: false };
  const stale: QueuePutResult = { kept: false, stale: true };

  /** The saver's timers, run by hand. */
  function clock() {
    let due: { fn: () => void }[] = [];
    return {
      timers: {
        set: (fn: () => void) => {
          const t = { fn };
          due.push(t);
          return t;
        },
        clear: (t: unknown) => {
          due = due.filter((x) => x !== t);
        },
      },
      run: () => {
        const now = due;
        due = [];
        now.forEach((t) => t.fn());
      },
      waiting: () => due.length,
    };
  }

  /** A put that answers when the test says so. */
  function worker() {
    const calls: { body: QueueSaveRequest; keepalive: boolean; answer: (r: QueuePutResult) => void }[] = [];
    const put: QueuePut = (body, keepalive) =>
      new Promise((answer) => calls.push({ body, keepalive, answer }));
    return { put, calls };
  }

  const settle = () => new Promise((r) => setTimeout(r, 0));

  function setup(after: string | null = null, base = STORED_REV) {
    const c = clock();
    const w = worker();
    const saver = queueSaver(w.put, { stored: empty, base, after, timers: c.timers });
    return { c, w, saver };
  }

  it("saves nothing while the queue is what the worker holds (the page as it opens)", () => {
    const { c, w, saver } = setup();
    saver.change(empty);
    expect(c.waiting()).toBe(0);
    saver.flush(true);
    expect(w.calls).toHaveLength(0);
  });

  it("saves the whole queue once the changes pause, from the revision the page read and the set it knew", async () => {
    const { c, w, saver } = setup("QS-ANSWERED");
    saver.change({ questions: [q1], time_to_answer: "3d" });
    saver.change({ questions: [q1, q2], time_to_answer: "3d" });
    saver.change({ questions: [q1, q2], time_to_answer: "1w" }); // re-timed
    expect(w.calls).toHaveLength(0); // never while the reviewer is still changing it
    c.run();
    expect(w.calls).toHaveLength(1);
    expect(w.calls[0]!.body).toEqual({
      questions: [q1, q2],
      time_to_answer: "1w",
      base: STORED_REV,
      after: "QS-ANSWERED",
    });
    expect(w.calls[0]!.keepalive).toBe(false);
    w.calls[0]!.answer(kept(STORED_REV + 1));
    await settle();
    saver.change({ questions: [q1, q2], time_to_answer: "1w" }); // the same again: nothing to save
    expect(c.waiting()).toBe(0);
  });

  it("base goes up only from the revisions the worker returns; a failed save leaves it where it was", async () => {
    const { c, w, saver } = setup(null, 0); // nothing stored yet for this reviewer
    saver.change({ questions: [q1], time_to_answer: "3d" });
    c.run();
    expect(w.calls[0]!.body.base).toBe(0);
    w.calls[0]!.answer(kept(1));
    await settle();
    saver.change({ questions: [q1, q2], time_to_answer: "3d" });
    c.run();
    expect(w.calls[1]!.body.base).toBe(1);
    w.calls[1]!.answer(failed); // not kept: the worker still holds revision 1
    await settle();
    saver.change({ questions: [q2], time_to_answer: "3d" });
    c.run();
    expect(w.calls[2]!.body.base).toBe(1);
    w.calls[2]!.answer(kept(2));
    await settle();
    saver.change({ questions: [], time_to_answer: "3d" });
    c.run();
    expect(w.calls.map((x) => x.body.base)).toEqual([0, 1, 1, 2]);
  });

  it("there is no clock in the revision: base is the page's read, whatever the time", async () => {
    const at = vi.spyOn(Date, "now").mockReturnValue(1_763_272_200_000);
    try {
      const { c, w, saver } = setup();
      saver.change({ questions: [q1], time_to_answer: "3d" });
      c.run();
      expect(w.calls[0]!.body.base).toBe(STORED_REV);
      w.calls[0]!.answer(kept(STORED_REV + 1));
      await settle();
      saver.change({ questions: [q1, q2], time_to_answer: "3d" });
      c.run();
      expect(w.calls[1]!.body.base).toBe(STORED_REV + 1);
      expect(Object.keys(w.calls[1]!.body).sort()).toEqual(["after", "base", "questions", "time_to_answer"]);
    } finally {
      at.mockRestore();
    }
  });

  it("one save at a time: a change made meanwhile goes next, from the revision the first one stored", async () => {
    const { c, w, saver } = setup();
    saver.change({ questions: [q1], time_to_answer: "3d" });
    c.run();
    saver.change({ questions: [], time_to_answer: "3d" }); // removed while the first is on its way
    c.run();
    expect(w.calls).toHaveLength(1);
    w.calls[0]!.answer(kept(STORED_REV + 1));
    await settle();
    expect(w.calls).toHaveLength(2);
    expect(w.calls[1]!.body.questions).toEqual([]);
    expect(w.calls[1]!.body.base).toBe(STORED_REV + 1);
  });

  it("a 409 queue_stale (another tab saved since) stops every later save from this page view", async () => {
    const { c, w, saver } = setup();
    saver.change({ questions: [q1], time_to_answer: "3d" });
    c.run();
    saver.change({ questions: [q1, q2], time_to_answer: "3d" }); // waits on the first
    w.calls[0]!.answer(stale);
    await settle();
    expect(w.calls).toHaveLength(1); // what waited is not sent
    saver.change({ questions: [q2], time_to_answer: "1d" });
    expect(c.waiting()).toBe(0);
    saver.pause();
    saver.resume();
    expect(c.waiting()).toBe(0);
    saver.flush(true); // not even as the page goes
    expect(w.calls).toHaveLength(1);
  });

  it("a failed save keeps nothing and is tried again on the next change, never on its own", async () => {
    const { c, w, saver } = setup();
    saver.change({ questions: [q1], time_to_answer: "3d" });
    c.run();
    w.calls[0]!.answer(failed);
    await settle();
    expect(c.waiting()).toBe(0);
    expect(w.calls).toHaveLength(1);
    saver.change({ questions: [q1, q2], time_to_answer: "3d" });
    c.run();
    expect(w.calls).toHaveLength(2);
    expect(w.calls[1]!.body.questions).toEqual([q1, q2]);
    expect(w.calls[1]!.body.base).toBe(STORED_REV);
    // a put that throws is a failed save too: nothing stops, and the next change is saved again
    let thrownCalls = 0;
    const thrown = queueSaver(
      () => {
        thrownCalls += 1;
        return Promise.reject(new Error("offline"));
      },
      { stored: empty, base: 0, after: null, timers: c.timers },
    );
    thrown.change({ questions: [q1], time_to_answer: "3d" });
    c.run();
    await settle();
    expect(thrownCalls).toBe(1);
    thrown.change({ questions: [q1, q2], time_to_answer: "3d" });
    c.run();
    await settle();
    expect(thrownCalls).toBe(2);
  });

  it("Send or a decision pauses it, so no save follows them; a failed send resumes and saves what changed", async () => {
    const { c, w, saver } = setup();
    saver.change({ questions: [q1], time_to_answer: "3d" });
    saver.pause();
    expect(c.waiting()).toBe(0);
    saver.change({ questions: [q1, q2], time_to_answer: "3d" });
    saver.flush(true);
    expect(w.calls).toHaveLength(0);
    saver.resume();
    c.run();
    expect(w.calls.map((x) => x.body.questions)).toEqual([[q1, q2]]);
    w.calls[0]!.answer(kept(STORED_REV + 1));
    await settle();
  });

  it("the close-time save goes at once, kept alive, beside a save on its way, with base + 1", async () => {
    const { c, w, saver } = setup();
    saver.change({ questions: [q1], time_to_answer: "3d" });
    c.run();
    saver.change({ questions: [q1, q2], time_to_answer: "3d" });
    saver.flush(true);
    expect(w.calls).toHaveLength(2);
    expect(w.calls[0]!.body.base).toBe(STORED_REV);
    expect(w.calls[1]!.keepalive).toBe(true);
    expect(w.calls[1]!.body).toMatchObject({ questions: [q1, q2], base: STORED_REV + 1 });
    expect(c.waiting()).toBe(0);
    saver.flush(true); // pagehide, then leaving the page: the same queue does not go twice
    expect(w.calls).toHaveLength(2);
    // answered out of order: the higher revision is what the page keeps
    w.calls[1]!.answer(kept(STORED_REV + 2));
    w.calls[0]!.answer(kept(STORED_REV + 1));
    await settle();
    saver.change({ questions: [q2], time_to_answer: "3d" });
    c.run();
    expect(w.calls[2]!.body.base).toBe(STORED_REV + 2);
  });

  it("the snapshot is the panel's queue and time; queuePut sends it to the desk's route and reads the answer", async () => {
    const p = run([
      { type: "add_suggestion", part: "often", text: q1.text },
      { type: "set_time", time: "1d" },
    ]);
    expect(queueSnapshot(p)).toEqual({ questions: [q1], time_to_answer: "1d" });
    const sent: { url: string; init: RequestInit }[] = [];
    const ok = queuePut("IDEA-2026-000123", (async (url: string, init: RequestInit) => {
      sent.push({ url, init });
      return new Response('{"set_id":"QS-1","rev":6,"count":1}', { status: 200 });
    }) as typeof fetch);
    const body: QueueSaveRequest = { questions: [q1], time_to_answer: "1d", base: 5, after: null };
    expect(await ok(body, true)).toEqual({ kept: true, rev: 6 });
    expect(sent[0]!.url).toBe("/api/desk/ideas/IDEA-2026-000123/question-sets/queued");
    expect(sent[0]!.init).toMatchObject({ method: "PUT", keepalive: true, body: JSON.stringify(body) });
    const answering = (status: number, text: string) =>
      queuePut("IDEA-2026-000123", (async () => new Response(text, { status })) as typeof fetch);
    expect(await answering(409, '{"error":{"code":"queue_stale","message":""}}')(body, false)).toEqual(stale);
    // the idea left the desk, the worker is down, or the answer holds no revision: failed, not stale
    expect(await answering(409, '{"error":{"code":"already_decided","message":""}}')(body, false)).toEqual(
      failed,
    );
    expect(await answering(502, '{"error":{"code":"desk_unavailable","message":""}}')(body, false)).toEqual(
      failed,
    );
    expect(await answering(200, "{}")(body, false)).toEqual(failed);
    const offline = queuePut("IDEA-2026-000123", (async () => {
      throw new TypeError("Failed to fetch");
    }) as typeof fetch);
    expect(await offline(body, false)).toEqual(failed);
  });
});
