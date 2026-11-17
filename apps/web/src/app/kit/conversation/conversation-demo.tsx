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

export function ConversationDemo() {
  return <Conversation initial={DEMO_VIEW} ideaId={DEMO_IDEA} />;
}
