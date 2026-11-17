import type { DecisionForViewerResponse } from "@/lib/contracts/api";
import { dayLabel } from "@/lib/desk/when";

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
 * The card's sentence for a decision, composed from lane B's decision (BLD-E012) in S-06.states' words: what was
 * decided and what happens next. The reason itself is shown below the card word for word, under its heading.
 */
export function decisionSentence(
  d: Decided,
  reviewer: string | null,
  stages: StageWords[],
): { lead: string; rest: string } | null {
  const who = reviewer ? `${reviewer} from the review desk` : "The review desk";
  const whose = reviewer ? `${reviewer}’s` : "The review desk’s";
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
