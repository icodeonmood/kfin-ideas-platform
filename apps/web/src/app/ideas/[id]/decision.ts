import type { DecisionForViewerResponse } from "@/lib/contracts/api";
import { dayLabel } from "@/lib/desk/when";
import { REVIEW_DESK_START } from "@/lib/review-desk";

import type { StageWords } from "./track";

/** Lane B's decision as the sharer gets it in full (not the stage-only shape). */
export type Decided = Exclude<NonNullable<DecisionForViewerResponse>, { stage_only: true }>;

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

function monthOf(iso: string): string {
  const m = Number(
    new Intl.DateTimeFormat("en-GB", { timeZone: "Asia/Kolkata", month: "numeric" }).format(new Date(iso)),
  );
  return MONTHS[m - 1] ?? "";
}

export const capital = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/**
 * Whether a speaker on S-06 gets a face. The review desk itself (DEC-111) and the Ones Committee itself (DEC-113)
 * come with no id and no initials for anyone outside the desk and the committee, so neither an avatar nor initials
 * is drawn: in "You and the review desk" (BLD-E058) and on the reversal card (lane B's `reversal.by`; BLD-E071).
 */
export function hasFace(p: { id: string | null; initials: string }): boolean {
  return Boolean(p.id) && Boolean(p.initials);
}

/**
 * The card's sentence for a decision, composed from lane B's decision (BLD-E012) in S-06.states' words: what was
 * decided and what happens next. The reason itself is shown below the card word for word, under its heading.
 *
 * `reviewer` is the first name the worker sends in `idea.review.reviewer` only to a sharer on the review desk or the
 * Ones Committee (DEC-111, BLD-E053). Everyone else gets none, so the sentence names the review desk: "The review
 * desk picked it on …", "The review desk’s full reason is below." (changed by DEC-111, HR sign-off).
 */
export function decisionSentence(
  d: Decided,
  reviewer: string | null,
  stages: StageWords[],
): { lead: string; rest: string } | null {
  const who = reviewer ? `${reviewer} from the review desk` : REVIEW_DESK_START;
  const whose = reviewer ? `${reviewer}’s` : `${REVIEW_DESK_START}’s`;
  const merged = d.decision.merged_into;
  switch (d.decision.choice) {
    case "pick": {
      const team = stages.find((s) => s.stage === "built")?.detail?.match(/^Team chosen by (.+)$/)?.[1];
      const joined = merged ? ` and joined it with ${merged}, so one team builds one fix` : "";
      return {
        lead: "Picked. A team is being chosen to build it.",
        rest:
          `${who} picked it on ${dayLabel(d.decided_at)}${joined}.` +
          (team ? ` The build team is chosen by ${team}.` : ""),
      };
    }
    case "not_now":
      if (!d.return_at) return null;
      return {
        lead: `Not now. The review desk looks at it again on ${dayLabel(d.return_at)}.`,
        rest:
          "Your idea stays open, with your answers and anyone who teams up, and comes back to the review desk " +
          `first thing in ${monthOf(d.return_at)}. ${whose} full reason is below.`,
      };
    case "not_picked":
      return merged
        ? {
            lead: `Not picked on its own. Your words carry on in ${merged}.`,
            rest:
              "It’s the same problem as an idea the review desk is taking forward. Your words were added to it, with " +
              `credit to you, and you’ll get its updates. ${whose} full reason is below.`,
          }
        : { lead: "Not picked.", rest: `${whose} full reason is below.` };
    default:
      return null;
  }
}
