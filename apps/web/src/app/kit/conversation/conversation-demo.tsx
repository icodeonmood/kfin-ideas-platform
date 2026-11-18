"use client";

import { Conversation } from "@/components/convo/conversation";
import type { ConversationView } from "@/lib/contracts";

/** Synthetic: the pack's fictional cast and idea ("Ravi's idea, after teaming up"). The e2e spec answers every call
 * for this reference. */
export const DEMO_IDEA = "IDEA-2026-001412";

const RAVI = {
  id: "6c1f6a0e-1b8e-4d0a-9a51-0d6f3e2a1b01",
  name: "Ravi Nair",
  first_name: "Ravi",
  initials: "RN",
};
const ADITI = {
  id: "6c1f6a0e-1b8e-4d0a-9a51-0d6f3e2a1b02",
  name: "Aditi Sharma",
  first_name: "Aditi",
  initials: "AS",
};
const PRAKASH = {
  id: "6c1f6a0e-1b8e-4d0a-9a51-0d6f3e2a1b03",
  name: "Prakash Kumar",
  first_name: "Prakash",
  initials: "PK",
};
const KAVYA = {
  id: "6c1f6a0e-1b8e-4d0a-9a51-0d6f3e2a1b04",
  name: "Kavya Menon",
  first_name: "Kavya",
  initials: "KM",
};

export const DEMO_VIEW: ConversationView = {
  idea: {
    id: DEMO_IDEA,
    title: "Rejection SMS codes confuse investors",
    status: "with_review_desk",
    meta: `${DEMO_IDEA}, with the review desk`,
  },
  audience: "crew_and_desk",
  header: { whose: "The idea", line: "Ravi Nair’s idea, Investor service, Hyderabad" },
  participants: [
    { person: RAVI, label: "Ravi Nair", doing: "Shared the idea", you: false },
    { person: ADITI, label: "Aditi Sharma", doing: "On the crew", you: false },
    { person: PRAKASH, label: "Prakash Kumar", doing: "On the crew", you: false },
    { person: KAVYA, label: "You", doing: "Joined today", you: true },
  ],
  entries: [
    {
      type: "event",
      id: "6c1f6a0e-0000-4000-8000-000000000001",
      code: "idea.shared",
      text: "Ravi Nair shared it. Monday 9 November",
      at: "2026-11-09T10:00:00+05:30",
    },
    {
      type: "event",
      id: "6c1f6a0e-0000-4000-8000-000000000002",
      code: "teamup.approved_team_only",
      text: "Ravi Nair approved your team-up request. Today, 10:05 am",
      at: "2026-11-17T10:05:00+05:30",
    },
    {
      type: "message",
      id: "6c1f6a0e-0000-4000-8000-000000000003",
      from: RAVI,
      from_label: "Ravi Nair",
      you: false,
      text: "Welcome to the crew, Kavya. Your call log is exactly what this idea needed. Could you add last week’s R07 calls before the review desk looks at it on Friday?",
      files: [],
      at: "2026-11-17T10:07:00+05:30",
      at_label: "Today, 10:07 am",
      mentions: [],
      mentions_you: false,
      removed: false,
    },
  ],
  composer: {
    placeholder: "Message the crew",
    visibility: "The crew and the review desk see this conversation.",
    can_attach: false,
  },
};

const MEERA = {
  id: "6c1f6a0e-1b8e-4d0a-9a51-0d6f3e2a1b05",
  name: "Meera Iyer",
  first_name: "Meera",
  initials: "MI",
};

/** The sharer's own idea with the review desk's open questions (Messages.md's default; lane B's card, BLD-B249). The
 * e2e spec answers `GET /api/ideas/:id/question-set` for it. */
export const DEMO_QUESTIONS_VIEW: ConversationView = {
  ...DEMO_VIEW,
  idea: { ...DEMO_VIEW.idea, status: "needs_you", meta: `${DEMO_IDEA}, needs you` },
  audience: "you_and_desk",
  header: { whose: "Your idea", line: "Your idea, shared Monday 9 November" },
  participants: [
    { person: MEERA, label: "Meera from the review desk", doing: "Reviewing it", you: false },
    { person: KAVYA, label: "You", doing: "Shared the idea", you: true },
  ],
  entries: [
    {
      type: "event",
      id: "6c1f6a0e-0000-4000-8000-000000000011",
      code: "desk.opened",
      text: "Meera from the review desk opened it. Monday 16 November, 9:50 am",
      at: "2026-11-16T09:50:00+05:30",
    },
    {
      type: "questions",
      id: "6c1f6a0e-0000-4000-8000-000000000012",
      set_id: "6c1f6a0e-0000-4000-8000-000000000013",
      state: "seen",
      by: MEERA,
      by_label: "Meera from the review desk",
      count: 3,
      answered: 0,
      due_at: "2026-11-19T18:00:00+05:30",
      title: "Meera has 3 questions about your idea",
      deadline:
        "Answer by Thursday 19 November, 6 pm. One at a time, typed or spoken, and each answer is added to its part of your idea.",
      answer_url: `/ideas/${DEMO_IDEA}/answer`,
      at: "2026-11-16T11:20:00+05:30",
      at_label: "Monday 16 November, 11:20 am",
    },
  ],
  composer: {
    placeholder: "Message the review desk",
    visibility: "Only you and the review desk see this conversation.",
    questions_line:
      "Answer Meera’s 3 questions with Answer the questions, so each answer lands on its part of your idea. Write here for anything else.",
    can_attach: true,
  },
};

/** Twelve messages back and forth after the kit's lines: long enough to open past the fold at any width, so e2e can
 * check that it opens at the newest one (BLD-F081). */
export const DEMO_LONG_VIEW: ConversationView = {
  ...DEMO_VIEW,
  entries: [
    ...DEMO_VIEW.entries,
    ...Array.from({ length: 12 }, (_, i) => {
      const p = [RAVI, ADITI, PRAKASH][i % 3]!;
      return {
        type: "message" as const,
        id: `6c1f6a0e-0000-4000-8000-0000000003${String(i).padStart(2, "0")}`,
        from: p,
        from_label: p.name,
        you: false,
        text: `Call log, day ${i + 1}: most callers asked why the redemption did not go through, and what R07 means.`,
        files: [],
        at: "2026-11-17T11:00:00+05:30",
        at_label: "Today, 11:00 am",
        mentions: [],
        mentions_you: false,
        removed: false,
      };
    }),
  ],
};

export type DemoView = "crew" | "questions" | "long";

export function ConversationDemo({ view = "crew" }: { view?: DemoView }) {
  const initial = view === "questions" ? DEMO_QUESTIONS_VIEW : view === "long" ? DEMO_LONG_VIEW : DEMO_VIEW;
  return <Conversation initial={initial} ideaId={DEMO_IDEA} />;
}
