/**
 * The reviewer's panel on S-R2 as a reducer (L-REVIEW.panel, S-R2.panel, S-R2.rules/1–2). Framework-free so the
 * transitions are tested once and the component only renders what it is given.
 *
 * Working states: reviewing (the default; asking is reviewing with questions queued), sent, answered, deciding,
 * decided. "Decide without asking" keeps queued questions (they are dropped by the server once the decision is
 * sent); "Back" from deciding returns where the reviewer came from.
 */
import type { DecisionChoice, IdeaPart, ReturnIn, TimeToAnswer } from "@/lib/contracts";

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

export function initialPanel(state: PanelState = "reviewing", defaultTime: TimeToAnswer = "3d"): Panel {
  return {
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
