/**
 * S-H6's words and switches (reference/copy/Profile.md; L-NOTIFY/2; V-FIELDS.one/5). Pure, so the unit tests read
 * them directly. The worker (services/worker/wall/profile.py) owns the values and checks every save again.
 */
import type { PersonSettings } from "@/lib/contracts/entities";
import type { ReferAs } from "@/lib/refer-as";

/** V-FIELDS.one/5 (S-H6.rules/1, NOT DRAWN default): a switch that did not save flips back with this under it. */
export const SAVE_FAILED = "Couldn't save that. Try again.";

// S-H6's parts the board does not draw (BLD-E043). Each line below waits for HR's sign-off (docs/BUILD_LOG.md).
// NOT DRAWN (BLD-E043): HR sign-off
export const LOAD_FAILED = "We can't load your profile just now. Please try again in a minute.";
/** F-COPY.states/3's one way on from the error state. */
// NOT DRAWN (BLD-E043): HR sign-off
export const TRY_AGAIN = "Try again";
/** On the Teams switch while IT has not approved Teams (DEC-105). */
// NOT DRAWN (BLD-E043): HR sign-off
export const COMING_SOON = "Coming soon";
/** A One's link under the line in the head (S-H6.rules/4). */
// NOT DRAWN (BLD-E043): HR sign-off
export const ONE_DASHBOARD_LINK = "Your One dashboard";

/** S-H6.layout/3: the Wall switch's line follows its state (Profile.md, `wall` Shown and Hidden). */
export const WALL_LINE = {
  on: "Your name shows on the Wall next to your shared ideas. It applies to every idea you share, and you can change it here any time.",
  off: "Your ideas show on the Wall without your name. It applies to every idea you share, and you can change it here any time.",
} as const;

export type ReachKey = "teams" | "email" | "reminders";

/** S-H6.layout/4, L-NOTIFY/2: how we reach you, each on by default. */
export const REACH: readonly { key: ReachKey; title: string; line: string }[] = [
  {
    key: "teams",
    title: "Teams messages",
    line: "When the review desk asks you something, or one of your ideas moves a stage.",
  },
  { key: "email", title: "Email", line: "The same updates, for your records." },
  {
    key: "reminders",
    title: "Reminders before a question is due",
    line: "A day before, and again two hours before.",
  },
];

export type SwitchKey = "show_name_on_wall" | ReachKey;

/** The state of one switch from a settings body, or undefined when the body does not carry it as a boolean. */
export function switchState(
  settings: Partial<PersonSettings> | null | undefined,
  key: SwitchKey,
): boolean | undefined {
  const v = settings?.[key];
  return typeof v === "boolean" ? v : undefined;
}

/** DEC-108 (3): the four answers in lane C's values (`lib/refer-as.ts`, BLD-C111); "unset" is "Prefer not to say". */
export const REFER_AS_OPTIONS: readonly { value: ReferAs; label: string }[] = [
  // NOT DRAWN (BLD-E043): HR sign-off
  { value: "she", label: "She" },
  // NOT DRAWN (BLD-E043): HR sign-off
  { value: "he", label: "He" },
  // NOT DRAWN (BLD-E043): HR sign-off
  { value: "they", label: "They" },
  // NOT DRAWN (BLD-E043): HR sign-off
  { value: "unset", label: "Prefer not to say" },
];

/** DEC-108 (3): the question, and the one thing the answer is used for. */
// NOT DRAWN (BLD-E043): HR sign-off
export const REFER_AS_TITLE = "How should we refer to you?";
// NOT DRAWN (BLD-E043): HR sign-off
export const REFER_AS_LINE = "We use this only to word the English copy of your voice notes.";

/** "340"; "1,340" in the Indian grouping once it passes a thousand. */
export const pointsText = (points: number) => Math.max(0, Math.trunc(points)).toLocaleString("en-IN");
