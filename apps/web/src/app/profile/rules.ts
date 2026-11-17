/**
 * S-H6's words and switches (reference/copy/Profile.md; L-NOTIFY/2; V-FIELDS.one/5). Pure, so the unit tests read
 * them directly. The worker (services/worker/wall/profile.py) owns the values and checks every save again.
 */
import type { PersonSettings } from "@/lib/contracts/entities";

/** V-FIELDS.one/5 (S-H6.rules/1, NOT DRAWN default): a switch that did not save flips back with this under it. */
export const SAVE_FAILED = "Couldn't save that. Try again.";
export const LOAD_FAILED = "We can't load your profile just now. Please try again in a minute.";

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

/** Lane C's `GET/PUT /api/me/refer-as` values (DEC-108, BLD-C111); "unset" is "Prefer not to say". */
export const REFER_AS = ["she", "he", "they", "unset"] as const;
export type ReferAs = (typeof REFER_AS)[number];

export const REFER_AS_OPTIONS: readonly { value: ReferAs; label: string }[] = [
  { value: "she", label: "She" },
  { value: "he", label: "He" },
  { value: "they", label: "They" },
  { value: "unset", label: "Prefer not to say" },
];

/** DEC-108 (3): the question, and the one thing the answer is used for (BLD-E043, NOT DRAWN). */
export const REFER_AS_TITLE = "How should we refer to you?";
export const REFER_AS_LINE = "We use this only to word the English copy of your voice notes.";

export function isReferAs(value: unknown): value is ReferAs {
  return typeof value === "string" && (REFER_AS as readonly string[]).includes(value);
}

/** "340"; "1,340" in the Indian grouping once it passes a thousand. */
export const pointsText = (points: number) => Math.max(0, Math.trunc(points)).toLocaleString("en-IN");
