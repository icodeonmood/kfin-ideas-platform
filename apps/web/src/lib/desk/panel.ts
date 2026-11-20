/**
 * The reviewer's panel on S-R2 as a reducer (L-REVIEW.panel, S-R2.panel, S-R2.rules/1–2). Framework-free so the
 * transitions are tested once and the component only renders what it is given.
 *
 * Working states: reviewing (the default; asking is reviewing with questions queued), sent, answered, deciding,
 * decided. "Decide without asking" keeps queued questions (they are dropped by the server once the decision is
 * sent); "Back" from deciding returns where the reviewer came from.
 */
import type {
  DecisionChoice,
  IdeaPart,
  QueueSaveRequest,
  ReturnIn,
  ReviewerQueuedSet,
  TimeToAnswer,
} from "@/lib/contracts";

export type PanelState = "reviewing" | "sent" | "answered" | "deciding" | "decided";

export interface QueuedQuestion {
  key: number;
  part: IdeaPart;
  text: string;
  suggested: boolean;
}

export interface Panel {
  state: PanelState;
  /** Where "Back" from deciding goes (L-REVIEW.panel transitions). */
  cameFrom: "reviewing" | "answered";
  /** "Ask {sharer} first" is collapsed by default (S-R2.panel/2). */
  askOpen: boolean;
  queued: QueuedQuestion[];
  timeToAnswer: TimeToAnswer;
  draft: { text: string; part: IdeaPart; partChosen: boolean };
  choice: DecisionChoice | null;
  reason: string;
  returnIn: ReturnIn;
  joinWith: string | null;
  nextKey: number;
}

export type PanelEvent =
  | { type: "toggle_ask" }
  | { type: "ask_about"; part: IdeaPart; suggestion: string | null }
  | { type: "type_question"; text: string; guessed: IdeaPart }
  | { type: "pin_question"; part: IdeaPart }
  | { type: "add_question" }
  | { type: "add_suggestion"; part: IdeaPart; text: string }
  | { type: "remove_question"; key: number }
  | { type: "set_time"; time: TimeToAnswer }
  | { type: "questions_sent" }
  | { type: "answers_in" }
  | { type: "follow_up" }
  | { type: "decide" }
  | { type: "back" }
  | { type: "choose"; choice: DecisionChoice }
  | { type: "type_reason"; text: string }
  | { type: "set_return"; returnIn: ReturnIn }
  | { type: "join_with"; ideaId: string | null }
  | { type: "decision_sent" };

/** The questions this reviewer queued and has not sent, as stored (J-REVIEW/A1). */
export type StoredQueue = {
  questions: { part: IdeaPart; text: string; suggested: boolean }[];
  timeToAnswer: TimeToAnswer | null;
};

const IDEA_PARTS: readonly IdeaPart[] = ["summary", "often", "who", "cost", "evidence", "fix"];
const TIMES: readonly TimeToAnswer[] = ["1d", "3d", "1w"];

/** `panel.queued` from the reviewer's page data, kept to the questions the panel can send. */
export function storedQueue(set: ReviewerQueuedSet | null | undefined): StoredQueue | null {
  const questions = (set?.questions ?? []).flatMap((q) => {
    const part = IDEA_PARTS.find((p) => p === q.part);
    const text = q.text?.trim();
    return part && text ? [{ part, text, suggested: q.suggested }] : [];
  });
  if (!questions.length) return null;
  return { questions, timeToAnswer: TIMES.find((t) => t === set?.time_to_answer) ?? null };
}

/**
 * The panel as the page opens. A stored queue (S-R2 "Asking Kavya") is the starting queue: the Ask section's header
 * reads "{n} questions ready" and the bar "Send {n} questions to Kavya", while the section itself stays folded until
 * opened (S-R2.panel/2); on an answered set it is a follow-up the reviewer started. The page saves the queue as it
 * changes (`queueSaver`, BLD-B272, amending BLD-B244), so a reload opens on the queue as the reviewer left it.
 */
export function initialPanel(
  state: PanelState = "reviewing",
  defaultTime: TimeToAnswer = "3d",
  stored: StoredQueue | null = null,
): Panel {
  const base: Panel = {
    state,
    cameFrom: state === "answered" ? "answered" : "reviewing",
    askOpen: false,
    queued: [],
    timeToAnswer: defaultTime,
    draft: { text: "", part: "summary", partChosen: false },
    choice: null,
    reason: "",
    returnIn: "3m",
    joinWith: null,
    nextKey: 1,
  };
  if (!stored || (state !== "reviewing" && state !== "answered")) return base;
  const queued = stored.questions.map((q, i) => ({ key: i + 1, ...q }));
  return {
    ...base,
    state: "reviewing",
    queued,
    timeToAnswer: stored.timeToAnswer ?? defaultTime,
    nextKey: queued.length + 1,
  };
}

function queue(p: Panel, part: IdeaPart, text: string, suggested: boolean): Panel {
  const t = text.trim();
  if (!t || p.queued.some((q) => q.text === t)) return p;
  return {
    ...p,
    queued: [...p.queued, { key: p.nextKey, part, text: t, suggested }],
    nextKey: p.nextKey + 1,
  };
}

export function panelReducer(p: Panel, e: PanelEvent): Panel {
  switch (e.type) {
    case "toggle_ask":
      return { ...p, askOpen: !p.askOpen };
    case "ask_about": {
      // S-R2.rules/2: "Ask about this" opens the section with that part's first suggestion queued.
      const opened = { ...p, askOpen: true, state: p.state === "answered" ? "reviewing" : p.state } as Panel;
      return e.suggestion ? queue(opened, e.part, e.suggestion, true) : opened;
    }
    case "type_question":
      // The part follows the wording until the reviewer picks one (L-QUESTIONS.ask/2).
      return {
        ...p,
        draft: { ...p.draft, text: e.text, part: p.draft.partChosen ? p.draft.part : e.guessed },
      };
    case "pin_question":
      return { ...p, draft: { ...p.draft, part: e.part, partChosen: true } };
    case "add_question": {
      const added = queue(p, p.draft.part, p.draft.text, false);
      return added === p ? p : { ...added, draft: { text: "", part: "summary", partChosen: false } };
    }
    case "add_suggestion":
      return queue(p, e.part, e.text, true);
    case "remove_question":
      return { ...p, queued: p.queued.filter((q) => q.key !== e.key) };
    case "set_time":
      return { ...p, timeToAnswer: e.time };
    case "questions_sent":
      return { ...p, state: "sent", queued: [], askOpen: false, cameFrom: "reviewing" };
    case "answers_in":
      return { ...p, state: "answered", cameFrom: "answered" };
    case "follow_up":
      // A new set after answers (L-QUESTIONS.ask/6): back to reviewing with the Ask section open.
      return { ...p, state: "reviewing", askOpen: true, cameFrom: "answered" };
    case "decide":
      return p.state === "decided"
        ? p
        : { ...p, state: "deciding", cameFrom: p.state === "answered" ? "answered" : "reviewing" };
    case "back":
      return p.state === "deciding" ? { ...p, state: p.cameFrom } : p;
    case "choose":
      return { ...p, choice: e.choice, joinWith: e.choice === "pick" ? p.joinWith : null };
    case "type_reason":
      return { ...p, reason: e.text };
    case "set_return":
      return { ...p, returnIn: e.returnIn };
    case "join_with":
      return { ...p, joinWith: e.ideaId };
    case "decision_sent":
      return { ...p, state: "decided", queued: [], askOpen: false };
  }
}

/** What one save of the queue sends, less its revision and `after` (BLD-B272): the whole queue and its time. */
export type QueueSnapshot = Pick<QueueSaveRequest, "questions" | "time_to_answer">;

export function queueSnapshot(p: Pick<Panel, "queued" | "timeToAnswer">): QueueSnapshot {
  return {
    questions: p.queued.map((q) => ({ part: q.part, text: q.text, suggested: q.suggested })),
    time_to_answer: p.timeToAnswer,
  };
}

/** The wait after the last change before the queue is saved: typing never waits on it (BLD-B272). */
export const QUEUE_SAVE_WAIT_MS = 700;

/** Sends one save; true when the worker kept it. `keepalive` lets a save started as the page goes finish. */
export type QueuePut = (body: QueueSaveRequest, keepalive: boolean) => Promise<boolean>;

export interface QueueSaver {
  /** The panel's queue after a change (add, remove, re-time): saved once the changes pause. */
  change(snapshot: QueueSnapshot): void;
  /** Save what is waiting now, as the page goes (pagehide, leaving the page). */
  flush(keepalive?: boolean): void;
  /** Send or a decision is on its way: nothing more is saved; `resume` if it fails (what changed is then saved). */
  pause(): void;
  resume(): void;
}

/**
 * Saves the reviewer's queue as it changes (BLD-B272; S-R2.panel Asking, L-QUESTIONS.states "queued"). One save at a
 * time, of the whole queue, after `wait` ms without a change; nothing is saved while the queue is what the worker
 * already holds. Each save carries a revision that only grows (the clock in ms, or one more than the last), so a
 * late save never overwrites a newer one, and `after`, the latest set the page knew, so one that arrives after Send
 * keeps nothing. A failed save leaves the panel's queue as it is and is tried again on the next change. The page is
 * never held up: it renders from its own queue whatever the saves do.
 */
export function queueSaver(
  put: QueuePut,
  opts: {
    stored: QueueSnapshot;
    rev: number;
    after: string | null;
    wait?: number;
    now?: () => number;
    timers?: { set: (fn: () => void, ms: number) => unknown; clear: (t: unknown) => void };
  },
): QueueSaver {
  const wait = opts.wait ?? QUEUE_SAVE_WAIT_MS;
  const now = opts.now ?? (() => Date.now());
  const timers = opts.timers ?? {
    set: (fn: () => void, ms: number) => setTimeout(fn, ms),
    clear: (t: unknown) => clearTimeout(t as ReturnType<typeof setTimeout>),
  };
  let rev = opts.rev;
  let held = JSON.stringify(opts.stored); // what the worker holds
  let sending: string | null = null; // what it will hold once the save on its way is kept
  let latest: QueueSnapshot | null = null;
  let timer: unknown = null;
  let again = false;
  let paused = false;

  const stopTimer = () => {
    if (timer !== null) timers.clear(timer);
    timer = null;
  };
  const later = () => {
    timer = timers.set(() => save(false), wait);
  };

  function save(keepalive: boolean) {
    stopTimer();
    if (paused || latest === null) return;
    const json = JSON.stringify(latest);
    if (json === (sending ?? held)) return;
    if (sending !== null && !keepalive) {
      again = true; // one at a time: the latest queue goes as soon as this one is answered
      return;
    }
    rev = Math.max(rev + 1, Math.floor(now()));
    const body: QueueSaveRequest = { ...latest, rev, after: opts.after };
    sending = json;
    void put(body, keepalive)
      .catch(() => false)
      .then((kept) => {
        if (kept) held = json;
        if (sending === json) sending = null;
        if (again) {
          again = false;
          save(false);
        }
      });
  }

  return {
    change(snapshot) {
      latest = snapshot;
      stopTimer();
      if (!paused && JSON.stringify(snapshot) !== (sending ?? held)) later();
    },
    flush(keepalive = false) {
      save(keepalive);
    },
    pause() {
      paused = true;
      stopTimer();
    },
    resume() {
      paused = false;
      if (latest !== null && JSON.stringify(latest) !== (sending ?? held)) later();
    },
  };
}

/** The saver's `put` against the review side's API: PUT /api/desk/ideas/{id}/question-sets/queued. */
export function queuePut(ideaId: string, fetcher: typeof fetch = fetch): QueuePut {
  const url = `/api/desk/ideas/${encodeURIComponent(ideaId)}/question-sets/queued`;
  return async (body, keepalive) => {
    try {
      const res = await fetcher(url, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        keepalive,
      });
      return res.ok;
    } catch {
      return false;
    }
  };
}

/** What the bottom bar shows (S-R2.panel/1–2, /4–5). */
export function bottomBar(
  p: Panel,
  sharerFirstName: string,
): {
  primary: string | null;
  secondary: string | null;
} {
  const n = p.queued.length;
  if (p.state === "deciding") return { primary: `Send decision to ${sharerFirstName}`, secondary: "Back" };
  if (p.state === "decided" || p.state === "sent") return { primary: null, secondary: null };
  if (p.state === "reviewing" && n > 0) {
    return {
      primary: `Send ${n} question${n === 1 ? "" : "s"} to ${sharerFirstName}`,
      secondary: "Decide without asking",
    };
  }
  return { primary: "Decide on this idea", secondary: null };
}

/** The Ask section's header once questions are queued: "2 questions ready" (S-R2.panel/2). */
export function readyLine(p: Panel): string | null {
  const n = p.queued.length;
  return n ? `${n} question${n === 1 ? "" : "s"} ready` : null;
}

/**
 * Where focus goes back to when a sheet on the reviewer's page closes (V-ACC.visual/11): the first of the candidates
 * still on the page. For the merge sheet that is the row's Merge for that idea, then the Similar ideas heading, then
 * whatever had focus when it opened (C-SHEET-MERGE, J-REVIEW/M2–M3).
 */
export function focusBackTo<T extends { isConnected: boolean }>(
  ...candidates: (T | null | undefined)[]
): T | null {
  return candidates.find((c): c is T => c != null && c.isConnected) ?? null;
}
