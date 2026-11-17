/**
 * S-ONE's field rules and words (V-FIELDS.one, L-ONES), mirrored from the worker (services/worker/wall/common.py),
 * which checks every one of them again. Pure, so the unit tests read them directly.
 */
export const MSG_OUT_OF_RANGE = "Pick a number from 1 to 999.";
export const MSG_BRIEF = "Keep it to one sentence, up to 140 characters.";
export const MSG_SAVE_FAILED = "Couldn't save that. Try again.";
/** NOT DRAWN (L-ONES.rules/5): a proposed brief waits for the programme team (BLD-E041). */
export const MSG_BRIEF_PENDING =
  "Your new brief is with the programme team. It goes on the Wall once they approve it.";
export const MSG_NO_BRIEF = "No brief on the Wall yet.";
export const LOAD_FAILED = "We can't load your One dashboard just now. Please try again in a minute.";

/** V-FIELDS.one/1: a whole number from 1 to 999, or null. */
export function wholeNumber(raw: string): number | null {
  const t = raw.trim();
  if (!/^\d{1,3}$/.test(t)) return null;
  const n = Number(t);
  return n >= 1 && n <= 999 ? n : null;
}

/** V-FIELDS.one/4: one sentence, 20 to 140 characters, as the worker reads it (spaces collapsed). */
export function briefProblem(text: string): string | null {
  const clean = text.split(/\s+/).filter(Boolean).join(" ");
  if (clean.length < 20 || clean.length > 140 || /[.!?]\s+\S/.test(clean)) return MSG_BRIEF;
  return null;
}

/** "620 hours a month" → "620" and "hours a month"; "₹18 lakh a year" → "₹18" and "lakh a year" (S-ONE.layout/5). */
export function splitFigure(value: string): { big: string; unit: string } {
  const m = /^(₹?\s?\d[\d,]*(?:\.\d+)?)(?:\s+(.+))?$/.exec(value.trim());
  return m ? { big: m[1]!, unit: m[2] ?? "" } : { big: value, unit: "" };
}
