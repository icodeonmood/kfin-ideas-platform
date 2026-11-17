/**
 * How the person wants to be referred to (DEC-108 (3), BLD-E010, BLD-C111). Asked once in Profile (S-H6): "How should
 * we refer to you?", with "Prefer not to say" sent as "unset". Only the person reads or changes it. The worker uses it
 * for one thing: the English copy of their voice notes is worded for she or he; they and unset stay neutral.
 */
export const REFER_AS = ["she", "he", "they", "unset"] as const;
export type ReferAs = (typeof REFER_AS)[number];

/** A request body's value, or undefined when it is not one of the four. `null` is accepted as "unset". */
export function parseReferAs(value: unknown): ReferAs | undefined {
  if (value === null) return "unset";
  return typeof value === "string" && (REFER_AS as readonly string[]).includes(value)
    ? (value as ReferAs)
    : undefined;
}

/** What the table holds: she, he or they; NULL for unset. */
export const storedReferAs = (value: ReferAs): "she" | "he" | "they" | null =>
  value === "unset" ? null : value;

export const wireReferAs = (stored: string | null | undefined): ReferAs =>
  stored === "she" || stored === "he" || stored === "they" ? stored : "unset";
